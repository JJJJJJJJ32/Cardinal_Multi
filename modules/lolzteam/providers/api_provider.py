"""
Реализация LolzteamProvider через aiohttp (основной режим).

Особенности:
- SSL отключён (verify_ssl=False).
- Timeout 300 сек на каждый запрос.
- Rate-limit 429 обрабатывается через X-RateLimit-Reset.
- fast-buy с retry_request повторяется до 100 раз.
- Задержка 3 сек между поисковыми запросами.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import aiohttp
from loguru import logger

from .base import LolzteamProvider

_BASE_URL = "https://prod-api.lzt.market"
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=300)
_SEARCH_DELAY = 3.0          # сек между поисковыми запросами
_FAST_BUY_MAX_RETRIES = 100  # максимум повторов при retry_request
_FAST_BUY_RETRY_DELAY = 0.5  # сек между retry_request попытками
_GENERIC_RETRY = 3           # попыток при обычных сетевых ошибках


def _contains_retry_request(data: Any) -> bool:
    """Рекурсивно проверяет наличие 'retry_request' в любом поле ответа."""
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "retry_request" or value == "retry_request":
                return True
            if _contains_retry_request(value):
                return True
    elif isinstance(data, list):
        for item in data:
            if _contains_retry_request(item):
                return True
    elif isinstance(data, str) and data == "retry_request":
        return True
    return False


class LolzteamApiProvider(LolzteamProvider):
    """
    Провайдер Lolzteam через REST API.

    Args:
        api_token: Bearer-токен Lolzteam Market.
    """

    def __init__(self, api_token: str) -> None:
        self._token = api_token
        self._session: aiohttp.ClientSession | None = None

    # ── Сессия ───────────────────────────────────────────────────

    async def _get_session(self) -> aiohttp.ClientSession:
        """Возвращает (или создаёт) aiohttp-сессию."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(ssl=False)
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                connector=connector,
                timeout=_REQUEST_TIMEOUT,
            )
        return self._session

    async def close(self) -> None:
        """Закрыть aiohttp-сессию."""
        if self._session and not self._session.closed:
            await self._session.close()

    # ── Базовый запрос ───────────────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json: dict | None = None,
        retry_count: int = _GENERIC_RETRY,
    ) -> dict:
        """
        Выполняет HTTP-запрос к Lolzteam API.

        Обрабатывает:
        - 429 через X-RateLimit-Reset.
        - Сетевые ошибки с retry_count попытками.

        Args:
            method:      HTTP метод (GET, POST).
            path:        Путь без base URL (например "/steam").
            params:      Query parameters (для GET).
            json:        JSON body (для POST).
            retry_count: Количество повторов при сетевых ошибках.

        Returns:
            Распарсенный JSON-ответ.

        Raises:
            RuntimeError: Если все попытки исчерпаны.
        """
        url = f"{_BASE_URL}{path}"
        session = await self._get_session()

        for attempt in range(1, retry_count + 1):
            try:
                async with session.request(
                    method,
                    url,
                    params=params,
                    json=json,
                ) as resp:

                    if resp.status == 429:
                        reset_ts = resp.headers.get("X-RateLimit-Reset")
                        if reset_ts:
                            wait = float(reset_ts) - time.time() + 1.0
                            wait = max(wait, 1.0)
                        else:
                            wait = 60.0
                        logger.warning(
                            f"[Lolzteam API] 429 Rate-limit. "
                            f"Ждём {wait:.1f} сек. "
                            f"URL={url}"
                        )
                        await asyncio.sleep(wait)
                        continue  # повтор без уменьшения счётчика

                    resp.raise_for_status()
                    return await resp.json()

            except aiohttp.ClientResponseError as exc:
                logger.warning(
                    f"[Lolzteam API] HTTP {exc.status} "
                    f"попытка {attempt}/{retry_count}: {url}"
                )
                if attempt < retry_count:
                    await asyncio.sleep(1.0 * attempt)
                else:
                    raise RuntimeError(
                        f"Lolzteam API ошибка {exc.status} после "
                        f"{retry_count} попыток: {url}"
                    ) from exc

            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                logger.warning(
                    f"[Lolzteam API] Сетевая ошибка "
                    f"попытка {attempt}/{retry_count}: {exc}"
                )
                if attempt < retry_count:
                    await asyncio.sleep(1.0 * attempt)
                else:
                    raise RuntimeError(
                        f"Lolzteam API недоступен после "
                        f"{retry_count} попыток"
                    ) from exc

        raise RuntimeError(f"_request: неожиданный выход из цикла ({url})")

    # ── Поиск ────────────────────────────────────────────────────

    async def search(
        self,
        category: str,
        filters: dict,
    ) -> list[dict]:
        """
        Поиск товаров в категории.
        Всегда добавляет order_by=price_to_up.
        Задержка 3 сек перед запросом.
        """
        await asyncio.sleep(_SEARCH_DELAY)

        params = dict(filters)
        params.setdefault("order_by", "price_to_up")

        logger.debug(
            f"[Lolzteam API] Поиск: /{category} params={params}"
        )
        data = await self._request("GET", f"/{category}", params=params)
        items: list[dict] = data.get("items", [])
        logger.debug(
            f"[Lolzteam API] Найдено {len(items)} товаров в /{category}"
        )
        return items

    # ── Товар ────────────────────────────────────────────────────

    async def get_item(self, item_id: int) -> dict:
        """Получить полные данные товара."""
        logger.debug(f"[Lolzteam API] get_item: {item_id}")
        data = await self._request("GET", f"/{item_id}")
        return data.get("item", data)

    # ── Покупка ──────────────────────────────────────────────────

    async def fast_buy(
        self,
        item_id: int,
        price: float,
        balance_id: int,
    ) -> dict:
        """
        Быстрая покупка.
        При 'retry_request' в ответе — повторять до 100 раз.
        """
        body = {"price": price, "balance_id": balance_id}
        path = f"/{item_id}/fast-buy"

        for attempt in range(1, _FAST_BUY_MAX_RETRIES + 1):
            logger.debug(
                f"[Lolzteam API] fast_buy item={item_id} "
                f"попытка {attempt}/{_FAST_BUY_MAX_RETRIES}"
            )
            try:
                result = await self._request("POST", path, json=body)
            except RuntimeError as exc:
                logger.error(
                    f"[Lolzteam API] fast_buy ошибка попытка "
                    f"{attempt}: {exc}"
                )
                if attempt < _FAST_BUY_MAX_RETRIES:
                    await asyncio.sleep(_FAST_BUY_RETRY_DELAY)
                    continue
                raise

            if _contains_retry_request(result):
                logger.info(
                    f"[Lolzteam API] fast_buy retry_request "
                    f"item={item_id} попытка {attempt}"
                )
                await asyncio.sleep(_FAST_BUY_RETRY_DELAY)
                continue

            logger.info(
                f"[Lolzteam API] fast_buy успех item={item_id} "
                f"цена={price}"
            )
            return result

        raise RuntimeError(
            f"fast_buy: retry_request не прошёл за "
            f"{_FAST_BUY_MAX_RETRIES} попыток (item={item_id})"
        )

    async def confirm_buy(
        self,
        item_id: int,
        price: int,
        balance_id: int,
    ) -> dict:
        """Подтверждение покупки (fallback)."""
        body = {"price": price, "balance_id": balance_id}
        logger.debug(
            f"[Lolzteam API] confirm_buy item={item_id} price={price}"
        )
        return await self._request(
            "POST", f"/{item_id}/confirm-buy", json=body
        )

    # ── Балансы / профиль ────────────────────────────────────────

    async def get_balances(self) -> list[dict]:
        """Получить список балансов аккаунта."""
        logger.debug("[Lolzteam API] get_balances")
        data = await self._request("GET", "/balance")
        return data.get("balances", [data])

    async def get_profile(self) -> dict:
        """Получить профиль (проверка соединения)."""
        logger.debug("[Lolzteam API] get_profile")
        return await self._request("GET", "/me")