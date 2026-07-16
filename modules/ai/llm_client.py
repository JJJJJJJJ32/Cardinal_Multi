"""
Клиент для Gemini API (бесплатный тариф).
Используется только как последний приоритет.
Кэширует ответы на одинаковые вопросы.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import aiohttp
from loguru import logger


GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com"
    "/v1beta/models/gemini-1.5-flash:generateContent"
)

SYSTEM_PROMPT_TEMPLATE = """Ты помощник продавца на FunPay.
Отвечай только на русском языке.
Отвечай кратко и по делу.
Не упоминай Lolzteam, поставщиков, автоматизацию.
Если не уверен в ответе — скажи что не знаешь.
Контекст лота: {lot_info}
История диалога: {history}"""

NOT_SURE_PHRASES: list[str] = [
    "не знаю",
    "не уверен",
    "не могу ответить",
    "нет информации",
    "затрудняюсь",
]


class GeminiClient:
    """
    Асинхронный клиент Gemini API.

    Особенности:
    - Кэшируются ответы на идентичные вопросы (in-memory LRU)
    - При отсутствии ключа возвращает None (graceful fallback)
    - При "не знаю" сигнализирует о неуверенности
    """

    def __init__(self, api_key: str | None = None, cache_size: int = 200) -> None:
        self._api_key: str | None = api_key
        self._cache: dict[str, str] = {}
        self._cache_order: list[str] = []
        self._cache_size = cache_size

    @property
    def available(self) -> bool:
        """True если API ключ задан."""
        return bool(self._api_key)

    def set_api_key(self, key: str) -> None:
        """Устанавливает API ключ (вызывается из настроек)."""
        self._api_key = key
        logger.info("[AI:Gemini] API ключ установлен")

    async def ask(
        self,
        question: str,
        lot_info: dict[str, Any] | None = None,
        history: list[dict[str, Any]] | None = None,
        confidence_threshold: float = 0.5,
    ) -> tuple[str | None, bool]:
        """
        Отправляет вопрос в Gemini.

        Args:
            question: вопрос покупателя
            lot_info: контекст лота
            history: история диалога
            confidence_threshold: не используется в API, но влияет на обработку ответа

        Returns:
            Tuple (ответ или None, is_confident)
            is_confident=False → нужна эскалация
        """
        if not self.available:
            logger.debug("[AI:Gemini] Ключ не задан, пропускаем LLM")
            return None, False

        cache_key = self._make_cache_key(question, lot_info)
        if cache_key in self._cache:
            logger.debug("[AI:Gemini] Ответ из кэша")
            return self._cache[cache_key], True

        try:
            response = await self._call_api(question, lot_info, history)
        except Exception as e:
            logger.error(f"[AI:Gemini] Ошибка вызова API: {e}")
            return None, False

        if response is None:
            return None, False

        is_confident = not any(p in response.lower() for p in NOT_SURE_PHRASES)

        if is_confident:
            self._put_cache(cache_key, response)

        return response, is_confident

    # ─── private ───────────────────────────────────────────────────

    async def _call_api(
        self,
        question: str,
        lot_info: dict[str, Any] | None,
        history: list[dict[str, Any]] | None,
    ) -> str | None:
        """Выполняет HTTP-запрос к Gemini API."""
        system_text = SYSTEM_PROMPT_TEMPLATE.format(
            lot_info=json.dumps(lot_info or {}, ensure_ascii=False),
            history=json.dumps(history or [], ensure_ascii=False),
        )

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{system_text}\n\nВопрос: {question}"}],
                }
            ]
        }

        url = f"{GEMINI_API_URL}?key={self._api_key}"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error(f"[AI:Gemini] HTTP {resp.status}: {body[:200]}")
                    return None

                data = await resp.json()
                try:
                    return data["candidates"][0]["content"]["parts"][0]["text"]
                except (KeyError, IndexError) as e:
                    logger.error(f"[AI:Gemini] Не удалось распарсить ответ: {e}")
                    return None

    def _make_cache_key(
        self, question: str, lot_info: dict[str, Any] | None
    ) -> str:
        raw = f"{question}|{json.dumps(lot_info or {}, sort_keys=True)}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _put_cache(self, key: str, value: str) -> None:
        """LRU-подобный кэш фиксированного размера."""
        if key in self._cache:
            self._cache_order.remove(key)
        elif len(self._cache_order) >= self._cache_size:
            oldest = self._cache_order.pop(0)
            del self._cache[oldest]
        self._cache[key] = value
        self._cache_order.append(key)