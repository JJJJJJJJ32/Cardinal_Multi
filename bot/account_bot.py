"""
Точка запуска бота аккаунта.
Один экземпляр = один FunPay аккаунт.
"""

import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from loguru import logger

from modules.core.config import get_settings
from modules.core.database import get_session
from modules.multi.models.account import Account

from bot.middlewares.auth import AuthMiddleware
from bot.middlewares.throttling import ThrottlingMiddleware
from bot.handlers import get_account_bot_router
from bot.handlers.notifications import NotificationService


async def run_account_bot(account_id: int, token: str, owner_chat_id: int) -> None:
    """
    Запуск бота для конкретного аккаунта.

    Args:
        account_id: ID аккаунта в БД.
        token: Telegram Bot Token (расшифрованный).
        owner_chat_id: chat_id владельца.
    """
    logger.info(f"Запуск бота аккаунта #{account_id}")

    bot = Bot(token=token)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Middleware
    dp.update.middleware(AuthMiddleware(allowed_ids=[owner_chat_id]))
    dp.message.middleware(ThrottlingMiddleware(rate_limit=1.0))
    dp.callback_query.middleware(ThrottlingMiddleware(rate_limit=1.0))

    # Регистрация хендлеров
    dp.include_router(get_account_bot_router())

    # Уведомления
    notif_service = NotificationService(bot, owner_chat_id, account_id)
    notif_service.start()

    # Graceful shutdown
    async def on_shutdown() -> None:
        logger.info(f"Остановка бота аккаунта #{account_id}")
        await bot.session.close()

    dp.shutdown.register(on_shutdown)

    logger.info(f"Бот аккаунта #{account_id} готов. Polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


async def create_account_bot_from_db(account_id: int) -> None:
    """
    Загружает аккаунт из БД и запускает бота.
    """
    async with get_session() as session:
        account = await session.get(Account, account_id)
        if not account:
            raise ValueError(f"Аккаунт #{account_id} не найден в БД")
        if not account.telegram_token_encrypted:
            raise ValueError(f"Аккаунт #{account_id} не имеет telegram_token")
        if not account.owner_chat_id:
            raise ValueError(f"Аккаунт #{account_id} не имеет owner_chat_id")

        token = account.get_telegram_token()
        chat_id = int(account.owner_chat_id)

    await run_account_bot(account_id, token, chat_id)


if __name__ == "__main__":
    import sys
    acc_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    asyncio.run(create_account_bot_from_db(acc_id))