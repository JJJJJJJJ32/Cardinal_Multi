"""
bot/bot_manager.py

BotManager — запускает главный Telegram-бот и боты аккаунтов в одном event loop.

Порядок запуска:
1) Если MAIN_TELEGRAM_TOKEN задан → run_main_bot(account_manager)
2) Для каждого активного аккаунта с зашифрованным telegram_token → run_account_bot(...)
3) Все корутины запускаются через asyncio.gather()
"""

from __future__ import annotations

import asyncio
from typing import Sequence

from loguru import logger
from sqlalchemy import select

from modules.core.config import get_settings
from modules.core.database import get_session, init_db
from modules.multi.account_manager import AccountManager
from modules.multi.models.account import Account


# ─── Импорты bot/* с graceful fallback ───────────────────────────────────────
# (Позволяет запустить проект даже если bot/* частично не реализован)
try:
    from bot.main_bot import run_main_bot
    _HAS_MAIN_BOT = True
except ImportError as _e:
    logger.warning("bot.main_bot недоступен: {}", _e)
    _HAS_MAIN_BOT = False

try:
    from bot.account_bot import run_account_bot
    _HAS_ACCOUNT_BOT = True
except ImportError as _e:
    logger.warning("bot.account_bot недоступен: {}", _e)
    _HAS_ACCOUNT_BOT = False


# ─── BotManager ──────────────────────────────────────────────────────────────
class BotManager:
    """
    Управляет жизненным циклом всех Telegram-ботов.

    Запуск: await BotManager().start()
    """

    def __init__(self) -> None:
        self.account_manager: AccountManager | None = None
        self._tasks: list[asyncio.Task] = []

    # ── Инициализация ─────────────────────────────────────────────────────────
    async def setup(self) -> None:
        """Инициализирует БД и AccountManager."""
        logger.info("BotManager.setup(): init_db + AccountManager.setup()")
        await init_db()

        self.account_manager = AccountManager()
        await self.account_manager.setup()

    # ── Получение аккаунтов из БД ─────────────────────────────────────────────
    async def _get_accounts_with_tokens(self) -> Sequence[Account]:
        """
        Возвращает список активных аккаунтов с Telegram-токеном.

        Важно: загружаем все поля ВНУТРИ сессии и возвращаем
        уже "отсоединённые" объекты с явно загруженными данными.
        Это исключает DetachedInstanceError после закрытия сессии.
        """
        async with get_session() as session:
            result = await session.execute(
                select(Account).where(
                    Account.is_active.is_(True),
                    Account.telegram_token_encrypted.is_not(None),
                )
            )
            accounts = result.scalars().all()

            # Принудительно "пробуждаем" все нужные атрибуты пока сессия открыта
            for acc in accounts:
                _ = acc.id
                _ = acc.name
                _ = acc.owner_chat_id
                _ = acc.telegram_token_encrypted

            return accounts

    # ── Запуск ────────────────────────────────────────────────────────────────
    async def start(self) -> None:
        """
        Запускает все боты и ждёт их завершения.
        Блокирует до остановки или KeyboardInterrupt.
        """
        if self.account_manager is None:
            await self.setup()

        assert self.account_manager is not None

        settings = get_settings()
        tasks: list[asyncio.Task] = []

        # 1) Главный бот
        if settings.main_telegram_token:
            if _HAS_MAIN_BOT:
                tasks.append(
                    asyncio.create_task(
                        run_main_bot(self.account_manager),
                        name="main_bot",
                    )
                )
                logger.info("BotManager: главный бот запущен.")
            else:
                logger.error(
                    "BotManager: MAIN_TELEGRAM_TOKEN задан, но bot.main_bot недоступен."
                )
        else:
            logger.warning(
                "BotManager: MAIN_TELEGRAM_TOKEN не задан — главный бот не запущен."
            )

        # 2) Боты аккаунтов
        if _HAS_ACCOUNT_BOT:
            accounts = await self._get_accounts_with_tokens()

            for account in accounts:
                try:
                    token = account.get_telegram_token()
                    if not token:
                        logger.warning(
                            "Аккаунт #%s: get_telegram_token() вернул None — пропуск.",
                            account.id,
                        )
                        continue

                    if not account.owner_chat_id:
                        logger.warning(
                            "Аккаунт #%s: owner_chat_id не задан — пропуск.",
                            account.id,
                        )
                        continue

                    owner_chat_id = int(account.owner_chat_id)

                    tasks.append(
                        asyncio.create_task(
                            run_account_bot(
                                account_id=account.id,
                                token=token,
                                owner_chat_id=owner_chat_id,
                            ),
                            name=f"account_bot_{account.id}",
                        )
                    )
                    logger.info(
                        "BotManager: account_bot запущен для account_id=%s (%s).",
                        account.id,
                        account.name,
                    )
                except Exception as exc:
                    logger.error(
                        "BotManager: не удалось запустить account_bot для #%s: %s",
                        account.id,
                        exc,
                    )
        else:
            logger.warning("BotManager: bot.account_bot недоступен — боты аккаунтов не запущены.")

        # Проверяем что есть что запускать
        if not tasks:
            logger.error("BotManager: нет задач для запуска. Проверь конфиг.")
            return

        self._tasks = tasks
        logger.info("BotManager: запущено задач: %d", len(tasks))

        # Ждём завершения всех задач
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for task, result in zip(tasks, results):
            if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
                logger.error(
                    "BotManager: задача '%s' завершилась с ошибкой: %s",
                    task.get_name(),
                    result,
                )

    # ── Остановка ─────────────────────────────────────────────────────────────
    async def stop(self) -> None:
        """
        Корректно отменяет все запущенные задачи.
        Ждёт завершения каждой перед выходом.
        """
        logger.info("BotManager: остановка (%d задач)...", len(self._tasks))

        for task in self._tasks:
            if not task.done():
                task.cancel()

        for task in self._tasks:
            try:
                await task
            except asyncio.CancelledError:
                logger.debug("BotManager: задача '%s' отменена.", task.get_name())
            except Exception as exc:
                logger.error(
                    "BotManager: ошибка при остановке '%s': %s",
                    task.get_name(),
                    exc,
                )

        self._tasks.clear()
        logger.info("BotManager: все задачи остановлены.")


# ─── Точка входа (если запускать отдельно) ────────────────────────────────────
async def _main() -> None:
    manager = BotManager()
    await manager.setup()
    try:
        await manager.start()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("BotManager: прерывание по сигналу.")
    finally:
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(_main())