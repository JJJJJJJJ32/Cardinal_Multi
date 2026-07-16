"""
modules/core/notifier.py
Централизованный модуль отправки уведомлений в Telegram.
Используется всеми модулями (stats, balance, emergency, diagnostics, updates).
"""

from __future__ import annotations

import asyncio
from typing import Optional

import aiohttp
from loguru import logger

from modules.core.config import get_settings


class TelegramNotifier:
    """
    Отправляет сообщения в Telegram через Bot API.
    Поддерживает как главного бота, так и per-account ботов.
    """

    BASE_URL = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(self) -> None:
        self._settings = get_settings()
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def send(
        self,
        text: str,
        chat_id: Optional[str] = None,
        token: Optional[str] = None,
        parse_mode: str = "HTML",
    ) -> bool:
        """
        Отправить сообщение.

        Args:
            text:       Текст сообщения (HTML разметка по умолчанию).
            chat_id:    ID чата. Если None — берётся main_telegram_chat_id из .env.
            token:      Токен бота. Если None — берётся main_telegram_token из .env.
            parse_mode: Режим парсинга (HTML / Markdown).

        Returns:
            True если успешно, False при ошибке.
        """
        _token = token or self._settings.main_telegram_token
        _chat_id = chat_id or self._settings.main_telegram_chat_id

        if not _token or not _chat_id:
            logger.warning(
                "TelegramNotifier: токен или chat_id не настроены, "
                "уведомление пропущено."
            )
            return False

        url = self.BASE_URL.format(token=_token)
        payload = {
            "chat_id": _chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }

        try:
            session = await self._get_session()
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return True
                body = await resp.text()
                logger.error(f"TelegramNotifier: ошибка {resp.status}: {body}")
                return False
        except asyncio.TimeoutError:
            logger.error("TelegramNotifier: таймаут при отправке сообщения.")
            return False
        except Exception as e:
            logger.error(f"TelegramNotifier: неожиданная ошибка: {e}")
            return False

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


# Синглтон для использования во всех модулях
_notifier: Optional[TelegramNotifier] = None


def get_notifier() -> TelegramNotifier:
    global _notifier
    if _notifier is None:
        _notifier = TelegramNotifier()
    return _notifier