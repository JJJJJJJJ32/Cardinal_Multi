"""
modules/core/notifier.py
Безопасный Telegram-нотификатор.

ИЗМЕНЕНИЯ (security fix):
  - НЕ логируем полное тело ответа API
  - логируем только: status + description из JSON
  - retry + exponential backoff на 429
  - таймаут total=10s + connect=5s
  - graceful close сессии
"""

from __future__ import annotations

import asyncio
import json
import math
from typing import Optional

import aiohttp
from loguru import logger

_log = logger.bind(name="notifier")

# Максимальное время ожидания при 429 (секунды)
_MAX_RETRY_AFTER = 60.0
# Базовый backoff при отсутствии retry_after в ответе
_BASE_BACKOFF    = 2.0


class TelegramNotifier:
    """
    Асинхронный нотификатор для Telegram Bot API.

    Особенности безопасности:
      - тело ответа НЕ логируется целиком
      - только status + краткое description из JSON
      - retry с backoff на 429
    """

    def __init__(
        self,
        bot_token: str,
        default_chat_id: str | int,
    ) -> None:
        # Валидация: токен не должен быть пустым
        if not bot_token or not str(bot_token).strip():
            raise ValueError("bot_token не может быть пустым")
        if not default_chat_id:
            raise ValueError("default_chat_id не может быть пустым")

        self._bot_token      = bot_token
        self._default_chat_id = str(default_chat_id)
        self._session: Optional[aiohttp.ClientSession] = None

    # ─── Управление сессией ─────────────────────────────────────────────────

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=10.0, connect=5.0)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        """Закрыть aiohttp-сессию при завершении работы бота."""
        if self._session and not self._session.closed:
            await self._session.close()
            _log.debug("aiohttp session closed.")

    # ─── Вспомогательный метод: безопасный парсинг ошибки ──────────────────

    @staticmethod
    def _parse_error_response(raw: str) -> tuple[Optional[str], Optional[float]]:
        """
        Возвращает (description, retry_after) из тела ответа.
        Если не удалось — (None, None).
        Намеренно не перебрасывает исключения.
        """
        try:
            data = json.loads(raw)
        except Exception:
            return None, None

        description = data.get("description")
        retry_after: Optional[float] = None
        params = data.get("parameters")
        if isinstance(params, dict):
            ra = params.get("retry_after")
            if ra is not None:
                try:
                    retry_after = float(ra)
                except (TypeError, ValueError):
                    pass
        return description, retry_after

    # ─── Публичный API ──────────────────────────────────────────────────────

    async def send_message(
        self,
        text: str,
        chat_id: str | int | None = None,
        parse_mode: Optional[str] = "HTML",
        disable_web_page_preview: bool = True,
        max_retries: int = 3,
    ) -> bool:
        """
        Отправить сообщение в Telegram.

        :param text: текст сообщения
        :param chat_id: переопределить chat_id (иначе default_chat_id)
        :param parse_mode: "HTML", "Markdown" или None
        :param disable_web_page_preview: отключить превью ссылок
        :param max_retries: кол-во повторов при 429
        :return: True если успешно
        """
        cid = str(chat_id) if chat_id is not None else self._default_chat_id
        url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"

        payload: dict = {
            "chat_id": cid,
            "text": text,
            "disable_web_page_preview": disable_web_page_preview,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode

        session = await self._get_session()

        for attempt in range(max_retries + 1):
            try:
                async with session.post(url, json=payload) as resp:

                    if resp.status == 200:
                        _log.debug("Message sent to chat_id={}.", cid)
                        return True

                    # ── Читаем body ТОЛЬКО для парсинга ошибки, не для лога ──
                    raw = await resp.text()
                    description, retry_after = self._parse_error_response(raw)

                    # ── Логируем ТОЛЬКО status + description (не body!) ──────
                    _log.error(
                        "sendMessage failed: status={} description={}",
                        resp.status,
                        description or "N/A",
                    )

                    # ── 429 Too Many Requests: ждём retry_after ──────────────
                    if resp.status == 429 and attempt < max_retries:
                        wait = min(
                            retry_after if retry_after else _BASE_BACKOFF * (2 ** attempt),
                            _MAX_RETRY_AFTER,
                        )
                        _log.warning(
                            "Rate limited (429). Retry {}/{} after {:.1f}s.",
                            attempt + 1,
                            max_retries,
                            wait,
                        )
                        await asyncio.sleep(wait)
                        continue

                    # ── 4xx (кроме 429): не ретраим ─────────────────────────
                    if 400 <= resp.status < 500:
                        return False

                    # ── 5xx: ретраим с backoff ───────────────────────────────
                    if resp.status >= 500 and attempt < max_retries:
                        wait = _BASE_BACKOFF * (2 ** attempt)
                        _log.warning("Server error {}. Retry in {:.1f}s.", resp.status, wait)
                        await asyncio.sleep(wait)
                        continue

                    return False

            except asyncio.TimeoutError:
                _log.error("sendMessage timeout (attempt {}/{}).", attempt + 1, max_retries + 1)
                if attempt < max_retries:
                    await asyncio.sleep(_BASE_BACKOFF * (2 ** attempt))
                    continue
                return False

            except aiohttp.ClientError as exc:
                _log.error("sendMessage network error: {}.", type(exc).__name__)
                if attempt < max_retries:
                    await asyncio.sleep(_BASE_BACKOFF * (2 ** attempt))
                    continue
                return False

            except Exception as exc:
                _log.error("sendMessage unexpected error: {}.", type(exc).__name__)
                return False

        return False

    async def send_safe(
        self,
        text: str,
        chat_id: str | int | None = None,
    ) -> bool:
        """
        Алиас: отправка без HTML (plain text).
        Используй когда text содержит пользовательский ввод.
        """
        return await self.send_message(
            text=text,
            chat_id=chat_id,
            parse_mode=None,
        )