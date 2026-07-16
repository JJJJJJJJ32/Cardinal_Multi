"""
modules/diagnostics/checker.py
Полная диагностика всех подсистем Cardinal_Multi.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import aiohttp
from loguru import logger
from sqlalchemy import text

from modules.core.config import get_settings
from modules.core.database import get_session


@dataclass
class CheckResult:
    """Результат одной проверки."""
    ok: bool
    message: str
    detail: Optional[str] = None
    latency_ms: Optional[float] = None

    @property
    def icon(self) -> str:
        return "✅" if self.ok else "❌"

    def __str__(self) -> str:
        base = f"{self.icon} {self.message}"
        if self.detail:
            base += f" ({self.detail})"
        if self.latency_ms is not None:
            base += f" [{self.latency_ms:.0f}ms]"
        return base


class DiagnosticsChecker:
    """
    Проверяет состояние всех подсистем.
    Вызывается по команде или при ACCOUNT_ERROR.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._log = logger.bind(module="DiagnosticsChecker")

    async def check_all(self) -> Dict[str, CheckResult]:
        """
        Запустить все проверки параллельно.
        Returns:
            Словарь {subsystem_name: CheckResult}
        """
        import asyncio

        results = await asyncio.gather(
            self.check_telegram(),
            self.check_lolzteam(),
            self.check_gemini(),
            self.check_database(),
            return_exceptions=True,
        )

        keys = ["telegram", "lolzteam", "gemini", "database"]
        output: Dict[str, CheckResult] = {}

        for key, result in zip(keys, results):
            if isinstance(result, Exception):
                output[key] = CheckResult(ok=False, message=f"Ошибка проверки", detail=str(result))
            else:
                output[key] = result

        return output

    async def check_funpay(self, golden_key: str, account_name: str = "") -> CheckResult:
        """
        Проверить подключение к FunPay с golden_key.
        TODO: подключить FunPayAPI когда будет доступен в контексте.
        """
        # Заглушка — в реальном коде создать FunPayAPI(golden_key) и вызвать me()
        return CheckResult(
            ok=True,
            message=f"FunPay: подключён {account_name}",
            detail="(проверка через API не реализована в данной версии)",
        )

    async def check_telegram(self) -> CheckResult:
        """Проверить что Telegram-бот отвечает на getMe."""
        token = self._settings.main_telegram_token
        if not token:
            return CheckResult(ok=False, message="Telegram: токен не настроен")

        url = f"https://api.telegram.org/bot{token}/getMe"
        start = time.monotonic()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    latency = (time.monotonic() - start) * 1000
                    if resp.status == 200:
                        data = await resp.json()
                        username = data.get("result", {}).get("username", "?")
                        return CheckResult(
                            ok=True,
                            message=f"Telegram: работает (@{username})",
                            latency_ms=latency,
                        )
                    return CheckResult(
                        ok=False,
                        message="Telegram: ошибка",
                        detail=f"HTTP {resp.status}",
                        latency_ms=latency,
                    )
        except asyncio.TimeoutError:
            return CheckResult(ok=False, message="Telegram: таймаут")
        except Exception as e:
            return CheckResult(ok=False, message="Telegram: ошибка", detail=str(e))

    async def check_lolzteam(self, lolz_token: Optional[str] = None) -> CheckResult:
        """
        Проверить Lolzteam API через GET /me.
        """
        token = lolz_token
        if not token:
            return CheckResult(ok=False, message="Lolzteam: токен не передан")

        url = "https://api.lzt.market/me"
        start = time.monotonic()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    latency = (time.monotonic() - start) * 1000
                    if resp.status == 200:
                        data = await resp.json()
                        balance = data.get("user", {}).get("balance", "?")
                        username = data.get("user", {}).get("username", "?")
                        return CheckResult(
                            ok=True,
                            message=f"Lolzteam API: ✅ (@{username})",
                            detail=f"баланс: {balance} руб",
                            latency_ms=latency,
                        )
                    elif resp.status == 401:
                        return CheckResult(
                            ok=False,
                            message="Lolzteam: неверный токен",
                            latency_ms=latency,
                        )
                    return CheckResult(
                        ok=False,
                        message="Lolzteam: ошибка API",
                        detail=f"HTTP {resp.status}",
                        latency_ms=latency,
                    )
        except Exception as e:
            return CheckResult(ok=False, message="Lolzteam: ошибка", detail=str(e))

    async def check_gemini(self) -> CheckResult:
        """Проверить Gemini API ключ если настроен."""
        settings_dict = self._settings.model_dump() if hasattr(self._settings, "model_dump") else {}
        api_key = settings_dict.get("gemini_api_key") or os.getenv("GEMINI_API_KEY")

        if not api_key:
            return CheckResult(
                ok=True,
                message="AI: работает без LLM",
                detail="GEMINI_API_KEY не настроен",
            )

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models"
            f"?key={api_key}"
        )
        start = time.monotonic()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    latency = (time.monotonic() - start) * 1000
                    if resp.status == 200:
                        return CheckResult(
                            ok=True,
                            message="Gemini API: работает ✅",
                            latency_ms=latency,
                        )
                    elif resp.status == 400:
                        return CheckResult(
                            ok=False,
                            message="Gemini: ошибка ключа ❌",
                            detail="Неверный API ключ",
                            latency_ms=latency,
                        )
                    return CheckResult(
                        ok=False,
                        message="Gemini: ошибка",
                        detail=f"HTTP {resp.status}",
                        latency_ms=latency,
                    )
        except Exception as e:
            return CheckResult(ok=False, message="Gemini: ошибка", detail=str(e))

    async def check_database(self) -> CheckResult:
        """Проверить подключение к БД и её размер."""
        start = time.monotonic()
        try:
            async with get_session() as session:
                await session.execute(text("SELECT 1"))
            latency = (time.monotonic() - start) * 1000

            # Размер файла БД
            db_path = "./data/cardinal_multi.db"
            size_mb: Optional[float] = None
            if os.path.exists(db_path):
                size_mb = os.path.getsize(db_path) / (1024 * 1024)

            detail = f"размер: {size_mb:.2f} МБ" if size_mb is not None else None
            return CheckResult(
                ok=True,
                message="База данных: OK ✅",
                detail=detail,
                latency_ms=latency,
            )
        except Exception as e:
            return CheckResult(ok=False, message="База данных: ошибка ❌", detail=str(e))

    def format_report(self, results: Dict[str, CheckResult]) -> str:
        """Форматировать результаты диагностики для Telegram."""
        lines = ["🔍 <b>Диагностика Cardinal_Multi</b>", ""]
        for key, result in results.items():
            lines.append(str(result))
        return "\n".join(lines)