"""
bot/middlewares/auth.py
ACL middleware для Telegram-бота.

ИЗМЕНЕНИЯ (security fix):
  - явное разделение allowed_user_ids и allowed_chat_ids
  - fail-closed: если оба списка пустые — запрещаем всё
  - корректная работа в private чате И в группах
  - нет утечки внутренних данных в ответе пользователю
  - логирование без PII (только numeric id)
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Optional

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from loguru import logger

_log = logger.bind(name="auth")


def _extract_ids(data: dict[str, Any], event: TelegramObject) -> tuple[Optional[int], Optional[int]]:
    """
    Извлекает (user_id, chat_id) из контекста апдейта.
    Поддерживает: Message, CallbackQuery, InlineQuery и Update-обёртку.
    """
    user_id: Optional[int] = None
    chat_id: Optional[int] = None

    # 1. Стандартный aiogram context key
    user = data.get("event_from_user")
    if user is not None:
        user_id = getattr(user, "id", None)

    # 2. Прямые атрибуты события
    if hasattr(event, "chat") and event.chat:  # type: ignore[union-attr]
        chat_id = getattr(event.chat, "id", None)  # type: ignore[union-attr]

    # 3. CallbackQuery → message.chat
    if chat_id is None:
        msg = getattr(event, "message", None)
        if msg is not None:
            chat = getattr(msg, "chat", None)
            if chat is not None:
                chat_id = getattr(chat, "id", None)

    # 4. Фоллбек через Update
    update: Optional[Update] = data.get("event_update")
    if update and (user_id is None or chat_id is None):
        for upd_field in (update.message, update.edited_message, update.channel_post):
            if upd_field:
                if user_id is None and getattr(upd_field, "from_user", None):
                    user_id = upd_field.from_user.id
                if chat_id is None and getattr(upd_field, "chat", None):
                    chat_id = upd_field.chat.id
                break

        if update.callback_query:
            cq = update.callback_query
            if user_id is None and cq.from_user:
                user_id = cq.from_user.id
            if chat_id is None and cq.message and cq.message.chat:
                chat_id = cq.message.chat.id

        if update.inline_query:
            if user_id is None and update.inline_query.from_user:
                user_id = update.inline_query.from_user.id

    return user_id, chat_id


class AuthMiddleware(BaseMiddleware):
    """
    ACL Middleware.

    Разрешает апдейт если:
      user_id ∈ allowed_user_ids  ИЛИ  chat_id ∈ allowed_chat_ids

    Fail-closed: если оба списка пустые — ВСЁ запрещено.

    Пример использования:
        # Private-чат с владельцем (user_id == chat_id в личке)
        AuthMiddleware(allowed_user_ids=[123456789])

        # Группа
        AuthMiddleware(allowed_chat_ids=[-1001234567890])

        # Оба варианта
        AuthMiddleware(
            allowed_user_ids=[123456789],
            allowed_chat_ids=[-1001234567890],
        )
    """

    def __init__(
        self,
        allowed_user_ids: Optional[list[int]] = None,
        allowed_chat_ids: Optional[list[int]] = None,
    ) -> None:
        super().__init__()
        self.allowed_user_ids: frozenset[int] = frozenset(allowed_user_ids or [])
        self.allowed_chat_ids: frozenset[int] = frozenset(allowed_chat_ids or [])

        if not self.allowed_user_ids and not self.allowed_chat_ids:
            _log.critical(
                "AuthMiddleware: оба allowlist пустые! "
                "Все запросы будут ОТКЛОНЕНЫ (fail-closed)."
            )

    def _is_allowed(self, user_id: Optional[int], chat_id: Optional[int]) -> bool:
        # Fail-closed: пустые списки = запрет всего
        if not self.allowed_user_ids and not self.allowed_chat_ids:
            return False
        if user_id is not None and user_id in self.allowed_user_ids:
            return True
        if chat_id is not None and chat_id in self.allowed_chat_ids:
            return True
        return False

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id, chat_id = _extract_ids(data, event)

        if not self._is_allowed(user_id, chat_id):
            _log.warning(
                "AuthMiddleware: ACCESS DENIED | user_id={} chat_id={}",
                user_id,
                chat_id,
            )
            # Отвечаем кратко, без внутренней информации
            await self._deny(event)
            return  # Не передаём дальше по цепочке

        return await handler(event, data)

    @staticmethod
    async def _deny(event: TelegramObject) -> None:
        """Тихо отклоняем запрос. Не раскрываем детали системы."""
        try:
            if hasattr(event, "answer"):
                await event.answer("⛔ Access denied.")  # type: ignore[union-attr]
            elif hasattr(event, "message") and getattr(event, "message", None):
                await event.message.answer("⛔ Access denied.")  # type: ignore[union-attr]
        except Exception:
            pass  # Игнорируем ошибки отправки deny-ответа