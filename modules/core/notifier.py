"""
TelegramNotifier — безопасная отправка уведомлений в Telegram.

Фиксы:
  B-13   — anti-spam (cooldown per alert type)
  TC-052 — retry при 429 Too Many Requests
  TC-088 — повторная проверка < ALERT_COOLDOWN
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional

import aiohttp
from loguru import logger

# ═══════════════════════════════════════════════════════════════════════════════
# Константы
# ═══════════════════════════════════════════════════════════════════════════════
TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

MAX_RETRIES = 3
BASE_RETRY_DELAY = 1.0      # секунды (начальная задержка)
MAX_RETRY_AFTER = 60         # не ждать дольше 60 сек
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10, connect=5)

# Anti-spam
DEFAULT_COOLDOWN_SECONDS = 3600  # 1 час


class TelegramNotifier:
    """
    Отправка сообщений в Telegram с:
      - retry/backoff при 429
      - anti-spam cooldown per (chat_id, alert_key)
      - отсутствие логирования body (секреты)
    """

    def __init__(
        self,
        token: str,
        chat_id: str | int,
        *,
        cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
    ) -> None:
        self._token = token
        self._chat_id = str(chat_id)
        self._cooldown_seconds = cooldown_seconds

        # ── FIX B-13: anti-spam кэш ─────────────────────────────────────────
        # Ключ: (chat_id, alert_key) → время последней отправки (timestamp)
        self._sent_cache: Dict[str, float] = {}

    # ─────────────────────────────────────────────────────────────────────────
    # Публичный метод
    # ─────────────────────────────────────────────────────────────────────────
    async def send(
        self,
        text: str,
        *,
        chat_id: Optional[str | int] = None,
        alert_key: Optional[str] = None,
        parse_mode: str = "HTML",
        disable_preview: bool = True,
    ) -> bool:
        """
        Отправить сообщение.

        alert_key — если задан, применяется cooldown.
                    Повторная отправка с тем же ключом блокируется
                    на cooldown_seconds (FIX B-13).

        Возвращает True при успехе, False при отказе.
        """
        target_chat = str(chat_id) if chat_id else self._chat_id

        # ── Anti-spam check (FIX B-13 / TC-088) ─────────────────────────────
        if alert_key is not None:
            cache_key = f"{target_chat}:{alert_key}"
            last_sent = self._sent_cache.get(cache_key, 0)
            elapsed = time.monotonic() - last_sent

            if elapsed < self._cooldown_seconds:
                remaining = self._cooldown_seconds - elapsed
                logger.debug(
                    f"Notifier: пропуск alert_key='{alert_key}' — "
                    f"cooldown ещё {remaining:.0f} сек"
                )
                return False

        # ── Отправка с retry (TC-052) ────────────────────────────────────────
        url = TELEGRAM_API.format(token=self._token)
        payload = {
            "chat_id": target_chat,
            "text": text[:4096],  # Telegram лимит
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_preview,
        }

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
                    async with session.post(url, json=payload) as resp:
                        if resp.status == 200:
                            # Успех — обновляем кэш
                            if alert_key is not None:
                                cache_key = f"{target_chat}:{alert_key}"
                                self._sent_cache[cache_key] = time.monotonic()

                            logger.debug(
                                f"Notifier: сообщение отправлено в chat_id={target_chat}"
                            )
                            return True

                        if resp.status == 429:
                            # TC-052: Too Many Requests
                            data = await resp.json()
                            retry_after = data.get("parameters", {}).get(
                                "retry_after", BASE_RETRY_DELAY * attempt
                            )
                            retry_after = min(retry_after, MAX_RETRY_AFTER)

                            logger.warning(
                                f"Notifier: 429 Too Many Requests, "
                                f"retry через {retry_after} сек "
                                f"(попытка {attempt}/{MAX_RETRIES})"
                            )
                            await asyncio.sleep(retry_after)
                            continue

                        # Другие ошибки
                        logger.warning(
                            f"Notifier: Telegram вернул {resp.status} "
                            f"(попытка {attempt}/{MAX_RETRIES})"
                        )

            except asyncio.TimeoutError:
                logger.warning(
                    f"Notifier: таймаут при отправке "
                    f"(попытка {attempt}/{MAX_RETRIES})"
                )
            except aiohttp.ClientError as exc:
                logger.warning(
                    f"Notifier: ошибка сети — {exc!r} "
                    f"(попытка {attempt}/{MAX_RETRIES})"
                )

            # Экспоненциальный backoff
            if attempt < MAX_RETRIES:
                delay = BASE_RETRY_DELAY * (2 ** (attempt - 1))
                await asyncio.sleep(delay)

        logger.error(
            f"Notifier: не удалось отправить сообщение после {MAX_RETRIES} попыток"
        )
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # Утилиты
    # ─────────────────────────────────────────────────────────────────────────
    def reset_cooldown(self, alert_key: str, chat_id: Optional[str | int] = None) -> None:
        """
        Сбросить cooldown для alert_key (TC-089: баланс выше порога → сброс).
        """
        target_chat = str(chat_id) if chat_id else self._chat_id
        cache_key = f"{target_chat}:{alert_key}"
        if cache_key in self._sent_cache:
            del self._sent_cache[cache_key]
            logger.debug(f"Notifier: cooldown сброшен для '{alert_key}'")

    def clear_cache(self) -> None:
        """Очистить весь anti-spam кэш."""
        self._sent_cache.clear()