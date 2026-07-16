import asyncio
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from cachetools import TTLCache
from loguru import logger


class ThrottlingMiddleware(BaseMiddleware):
    """
    Ограничение: 1 запрос в секунду на пользователя.
    Использует TTLCache (ключ = user_id, TTL = rate_limit сек).
    """

    def __init__(self, rate_limit: float = 1.0) -> None:
        self.rate_limit = rate_limit
        # Кэш хранит user_id → True пока действует throttle
        self.cache: TTLCache = TTLCache(maxsize=1024, ttl=rate_limit)
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)

        if user.id in self.cache:
            logger.debug(f"ThrottlingMiddleware: throttle для user_id={user.id}")
            # Молча игнорируем
            return

        self.cache[user.id] = True
        return await handler(event, data)