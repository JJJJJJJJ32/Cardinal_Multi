"""
BotManager — управляет запуском главного бота И ботов аккаунтов одновременно.

Логика:
  1. Если у аккаунта есть собственный telegram_token → запускаем отдельный account_bot.
  2. Если нет токена → аккаунт управляется через главный бот.
  3. Все боты запускаются в одном event loop через asyncio.gather.
"""

import asyncio
from loguru import logger

from modules.core.config import get_settings
from modules.core.database import init_db, get_session
from modules.multi.account_manager import AccountManager
from modules.multi.models.account import Account

from bot.main_bot import run_main_bot
from bot.account_bot import run_account_bot


class BotManager:
    """
    Центральный управляющий класс.
    Запускает главный бот + боты аккаунтов.
    """

    def __init__(self) -> None:
        self.account_manager: AccountManager | None = None
        self._tasks: list[asyncio.Task] = []

    async def setup(self) -> None:
        """Инициализация: БД + AccountManager."""
        logger.info("BotManager: инициализация...")
        await init_db()

        self.account_manager = AccountManager()
        await self.account_manager.setup()

    async def start(self) -> None:
        """Запуск всех ботов."""
        if not self.account_manager:
            await self.setup()

        tasks = []

        # 1. Главный бот
        settings = get_settings()
        if settings.main_telegram_token:
            tasks.append(
                asyncio.create_task(
                    run_main_bot(self.account_manager),
                    name="main_bot",
                )
            )
        else:
            logger.warning(
                "BotManager: MAIN_TELEGRAM_TOKEN не задан — главный бот не запущен"
            )

        # 2. Боты аккаунтов (у которых есть собственный токен)
        async with get_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(Account).where(
                    Account.is_active == True,
                    Account.telegram_token_encrypted.isnot(None),
                )
            )
            accounts = result.scalars().all()

        for account in accounts:
            try:
                token = account.get_telegram_token()
                if not token:
                    continue
                if not account.owner_chat_id:
                    logger.warning(
                        f"Аккаунт #{account.id} не имеет owner_chat_id — пропускаем бота"
                    )
                    continue

                tasks.append(
                    asyncio.create_task(
                        run_account_bot(
                            account_id=account.id,
                            token=token,
                            owner_chat_id=int(account.owner_chat_id),
                        ),
                        name=f"account_bot_{account.id}",
                    )
                )
                logger.info(f"BotManager: запуск бота для аккаунта #{account.id}")
            except Exception as e:
                logger.error(f"BotManager: ошибка запуска бота аккаунта #{account.id}: {e}")

        self._tasks = tasks

        if not tasks:
            logger.error("BotManager: нет ботов для запуска!")
            return

        logger.info(f"BotManager: запуск {len(tasks)} бот(ов)...")

        # Запускаем все боты параллельно
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for task, result in zip(tasks, results):
            if isinstance(result, Exception):
                logger.error(f"Задача {task.get_name()} завершилась с ошибкой: {result}")

    async def stop(self) -> None:
        """Graceful shutdown."""
        logger.info("BotManager: остановка...")
        for task in self._tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        logger.info("BotManager: все задачи остановлены.")


async def main() -> None:
    manager = BotManager()
    await manager.setup()
    try:
        await manager.start()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Получен сигнал остановки (Ctrl+C)")
    finally:
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())