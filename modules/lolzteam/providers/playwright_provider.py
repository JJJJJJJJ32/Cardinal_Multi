"""
Реализация LolzteamProvider через Playwright (fallback).

Используется когда API токен НЕ задан.
Headless Chromium, вход по логину/паролю.
Cookies сохраняются в ./data/lolz_session.json.
"""

from __future__ import annotations

import asyncio
import json
import random
from pathlib import Path
from typing import Any

from loguru import logger

from .base import LolzteamProvider

_BASE_URL = "https://lzt.market"
_API_URL = "https://prod-api.lzt.market"
_COOKIES_PATH = Path("data/lolz_session.json")
_MIN_DELAY = 2.0
_MAX_DELAY = 3.0
_SEARCH_DELAY = 3.0
_FAST_BUY_MAX_RETRIES = 100
_FAST_BUY_RETRY_DELAY = 0.5


def _contains_retry_request(data: Any) -> bool:
    """Рекурсивно проверяет наличие 'retry_request' в ответе."""
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


class LolzteamPlaywrightProvider(LolzteamProvider):
    """
    Провайдер Lolzteam через Playwright браузер.

    Args:
        login:    Логин на lzt.market.
        password: Пароль на lzt.market.
    """

    def __init__(self, login: str, password: str) -> None:
        self._login = login
        self._password = password
        self._browser = None
        self._context = None
        self._page = None

    # ── Жизненный цикл ───────────────────────────────────────────

    async def _ensure_browser(self) -> None:
        """Инициализирует браузер и выполняет вход если нужно."""
        if self._browser is not None:
            return

        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError(
                "playwright не установлен. "
                "Выполни: playwright install chromium"
            ) from exc

        logger.warning(
            "⚠️ Работа через браузер (Playwright). "
            "Для стабильной работы получи API токен: "
            "lolz.live/account/api/get-token"
        )

        pw = await async_playwright().__aenter__()
        self._browser = await pw.chromium.launch(headless=True)
        self._context = await self._browser.new_context(
            ignore_https_errors=True,
        )

        if _COOKIES_PATH.exists():
            logger.info("[Lolzteam PW] Загружаем сохранённые cookies")
            cookies_raw = _COOKIES_PATH.read_text(encoding="utf-8")
            cookies = json.loads(cookies_raw)
            await self._context.add_cookies(cookies)
        else:
            await self._login_flow()

        self._page = await self._context.new_page()

    async def _login_flow(self) -> None:
        """Выполнить вход на lzt.market."""
        logger.info("[Lolzteam PW] Выполняем вход...")
        page = await self._context.new_page()
        await page.goto(f"{_BASE_URL}/login", timeout=30_000)
        await asyncio.sleep(random.uniform(_MIN_DELAY, _MAX_DELAY))

        await page.fill('input[name="login"]', self._login)
        await asyncio.sleep(random.uniform(0.5, 1.0))
        await page.fill('input[name="password"]', self._password)
        await asyncio.sleep(random.uniform(0.5, 1.0))

        await page.click('button[type="submit"]')
        await asyncio.sleep(random.uniform(_MIN_DELAY, _MAX_DELAY))

        cookies = await self._context.cookies()
        _COOKIES_PATH.parent.mkdir(parents=True, exist_ok=True)
        _COOKIES_PATH.write_text(
            json.dumps(cookies, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("[Lolzteam PW] Вход выполнен, cookies сохранены")
        await page.close()

    async def _save_cookies(self) -> None:
        """Сохранить текущие cookies в файл."""
        if self._context is None:
            return
        cookies = await self._context.cookies()
        _COOKIES_PATH.parent.mkdir(parents=True, exist_ok=True)
        _COOKIES_PATH.write_text(
            json.dumps(cookies, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    async def _api_call(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        body: dict | None = None,
    ) -> dict:
        """
        Выполнить API-запрос через браузерный fetch (с cookies).

        Args:
            method: HTTP метод.
            path:   Путь (без base URL).
            params: Query params.
            body:   JSON body для POST.

        Returns:
            Распарсенный JSON.
        """
        await self._ensure_browser()

        query = ""
        if params:
            query = "?" + "&".join(f"{k}={v}" for k, v in params.items())

        url = f"{_API_URL}{path}{query}"

        fetch_script = f"""
        async () => {{
            const resp = await fetch('{url}', {{
                method: '{method}',
                headers: {{
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                }},
                {f"body: JSON.stringify({json.dumps(body)})," if body else ""}
            }});
            return await resp.json();
        }}
        """

        result = await self._page.evaluate(fetch_script)
        return result if isinstance(result, dict) else {"data": result}

    async def close(self) -> None:
        """Закрыть браузер и сохранить cookies."""
        await self._save_cookies()
        if self._browser:
            await self._browser.close()
            self._browser = None

    # ── LolzteamProvider interface ───────────────────────────────

    async def search(
        self,
        category: str,
        filters: dict,
    ) -> list[dict]:
        """Поиск через браузерный fetch с задержкой 3 сек."""
        await asyncio.sleep(_SEARCH_DELAY)

        params = dict(filters)
        params.setdefault("order_by", "price_to_up")

        logger.debug(
            f"[Lolzteam PW] Поиск: /{category} params={params}"
        )
        data = await self._api_call("GET", f"/{category}", params=params)
        items: list[dict] = data.get("items", [])
        logger.debug(
            f"[Lolzteam PW] Найдено {len(items)} товаров в /{category}"
        )
        return items

    async def get_item(self, item_id: int) -> dict:
        """Получить данные товара."""
        logger.debug(f"[Lolzteam PW] get_item: {item_id}")
        data = await self._api_call("GET", f"/{item_id}")
        return data.get("item", data)

    async def fast_buy(
        self,
        item_id: int,
        price: float,
        balance_id: int,
    ) -> dict:
        """
        Быстрая покупка через браузерный fetch.
        При retry_request — повторять до 100 раз.
        """
        body = {"price": price, "balance_id": balance_id}

        for attempt in range(1, _FAST_BUY_MAX_RETRIES + 1):
            logger.debug(
                f"[Lolzteam PW] fast_buy item={item_id} "
                f"попытка {attempt}/{_FAST_BUY_MAX_RETRIES}"
            )
            try:
                result = await self._api_call(
                    "POST", f"/{item_id}/fast-buy", body=body
                )
            except Exception as exc:
                logger.error(
                    f"[Lolzteam PW] fast_buy ошибка: {exc}"
                )
                if attempt < _FAST_BUY_MAX_RETRIES:
                    await asyncio.sleep(_FAST_BUY_RETRY_DELAY)
                    continue
                raise

            if _contains_retry_request(result):
                logger.info(
                    f"[Lolzteam PW] fast_buy retry_request "
                    f"item={item_id} попытка {attempt}"
                )
                await asyncio.sleep(_FAST_BUY_RETRY_DELAY)
                continue

            logger.info(
                f"[Lolzteam PW] fast_buy успех item={item_id}"
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
            f"[Lolzteam PW] confirm_buy item={item_id}"
        )
        return await self._api_call(
            "POST", f"/{item_id}/confirm-buy", body=body
        )

    async def get_balances(self) -> list[dict]:
        """Получить балансы."""
        logger.debug("[Lolzteam PW] get_balances")
        data = await self._api_call("GET", "/balance")
        return data.get("balances", [data])

    async def get_profile(self) -> dict:
        """Получить профиль."""
        logger.debug("[Lolzteam PW] get_profile")
        return await self._api_call("GET", "/me")