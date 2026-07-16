from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from loguru import logger


class AuthMiddleware(BaseMiddleware):
    """
    Проверяет, что входящий update приходит от разрешённого chat_id.
    allowed_ids передаётся при инициализации.
    """

    def __init__(self, allowed_ids: list[int]) -> None:
        self.allowed_ids = set(allowed_ids)
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Достаём user из event
        user = data.get("event_from_user")

        if user is None:
            # Если нет пользователя — пробуем достать из update
            update: Update = data.get("event_update")
            if update:
                if update.message:
                    user = update.message.from_user
                elif update.callback_query:
                    user = update.callback_query.from_user

        if user is None:
            logger.warning("AuthMiddleware: не удалось определить пользователя")
            return

        if user.id not in self.allowed_ids:
            logger.warning(
                f"AuthMiddleware: доступ запрещён для user_id={user.id} "
                f"(@{user.username})"
            )
            # Пытаемся ответить отказом
            if hasattr(event, "answer"):
                try:
                    await event.answer("⛔ Доступ запрещён.")
                except Exception:
                    pass
            elif hasattr(event, "message") and event.message:
                try:
                    await event.message.answer("⛔ Доступ запрещён.")
                except Exception:
                    pass
            return

        return await handler(event, data)