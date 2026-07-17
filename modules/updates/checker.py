"""
UpdateChecker — проверка новых версий Cardinal_Multi через GitHub Releases API.

Фиксы:
  B-01  — graceful fallback если packaging не установлен
  B-18  — кэш последней нотифицированной версии (не спамить)
  TC-079 — InvalidVersion при кривом tag
  TC-080 — пустой список releases
  TC-082 — GitHub 403/rate-limit
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

import aiohttp
from loguru import logger

# ─── FIX B-01: graceful import packaging ────────────────────────────────────
try:
    from packaging.version import Version, InvalidVersion
except ImportError:
    logger.warning(
        "Пакет 'packaging' не установлен — UpdateChecker будет сравнивать "
        "версии как строки. Установите: pip install packaging>=24.0"
    )
    Version = None         # type: ignore[assignment, misc]
    InvalidVersion = None  # type: ignore[assignment, misc]


# ─── Константы ──────────────────────────────────────────────────────────────
GITHUB_API_URL = (
    "https://api.github.com/repos/{owner}/{repo}/releases/latest"
)
DEFAULT_OWNER = "JJJJJJJJ32"
DEFAULT_REPO = "Cardinal_Multi"

CURRENT_VERSION = "1.0.0"   # ← обновлять при релизе (или читать из __version__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)


class UpdateChecker:
    """Проверяет GitHub Releases и уведомляет о новой версии."""

    def __init__(
        self,
        *,
        owner: str = DEFAULT_OWNER,
        repo: str = DEFAULT_REPO,
        current_version: str = CURRENT_VERSION,
        notifier=None,          # TelegramNotifier (опционально)
    ) -> None:
        self._owner = owner
        self._repo = repo
        self._current_version = current_version
        self._notifier = notifier

        # ── FIX B-18: кэш последней отправленной версии ─────────────────────
        self._last_notified_tag: Optional[str] = None

    # ─────────────────────────────────────────────────────────────────────────
    # Публичный метод (вызывается из scheduler)
    # ─────────────────────────────────────────────────────────────────────────
    async def check(self) -> None:
        """Проверить последний релиз на GitHub и уведомить, если есть обновление."""
        try:
            tag, html_url = await self._fetch_latest_release()
        except Exception as exc:
            # TC-066 / TC-082: любая ошибка сети / API — не валим процесс
            logger.warning(f"UpdateChecker: не удалось проверить обновления — {exc}")
            return

        if tag is None:
            # TC-080: пустой ответ / нет релизов
            logger.info("UpdateChecker: релизов на GitHub не найдено")
            return

        # ── Сравнение версий ─────────────────────────────────────────────────
        is_newer = self._is_newer(tag)
        if is_newer is None:
            # TC-079: не удалось распарсить — просто логируем
            return

        if not is_newer:
            logger.info(
                f"UpdateChecker: текущая версия {self._current_version} актуальна "
                f"(latest: {tag})"
            )
            return

        # ── FIX B-18: не спамить одной и той же версией ──────────────────────
        if tag == self._last_notified_tag:
            logger.debug(
                f"UpdateChecker: версия {tag} уже была нотифицирована, пропуск"
            )
            return

        self._last_notified_tag = tag

        msg = (
            f"🆕 Доступна новая версия Cardinal_Multi: {tag}\n"
            f"Текущая: {self._current_version}\n"
            f"Скачать: {html_url or 'https://github.com/' + self._owner + '/' + self._repo + '/releases'}"
        )
        logger.info(msg)

        if self._notifier is not None:
            try:
                await self._notifier.send(msg)
            except Exception as exc:
                logger.warning(f"UpdateChecker: не удалось отправить уведомление — {exc}")

    # ─────────────────────────────────────────────────────────────────────────
    # Приватные методы
    # ─────────────────────────────────────────────────────────────────────────
    async def _fetch_latest_release(self) -> tuple[Optional[str], Optional[str]]:
        """
        Возвращает (tag_name, html_url) или (None, None).

        Raises при фатальных сетевых ошибках.
        """
        url = GITHUB_API_URL.format(owner=self._owner, repo=self._repo)
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": f"CardinalMulti/{self._current_version}",
        }

        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.get(url, headers=headers) as resp:
                # TC-082: GitHub rate limit
                if resp.status == 403:
                    logger.warning(
                        "UpdateChecker: GitHub вернул 403 (rate-limit или forbidden). "
                        "Следующая попытка при следующем цикле."
                    )
                    return None, None

                if resp.status == 404:
                    # Нет релизов вообще
                    return None, None

                resp.raise_for_status()
                data = await resp.json()

        tag = data.get("tag_name")
        html_url = data.get("html_url")

        if not tag:
            return None, None

        return tag, html_url

    def _is_newer(self, tag: str) -> Optional[bool]:
        """
        True  — tag новее текущей версии.
        False — tag такой же или старее.
        None  — не удалось распарсить (TC-079).
        """
        # Убираем ведущую "v" ("v1.2.3" → "1.2.3")
        clean_tag = tag.lstrip("vV")
        clean_current = self._current_version.lstrip("vV")

        # Если packaging доступен — точное семантическое сравнение
        if Version is not None:
            try:
                remote = Version(clean_tag)
            except InvalidVersion:
                logger.warning(
                    f"UpdateChecker: не удалось распарсить версию из тега: '{tag}'"
                )
                return None
            try:
                local = Version(clean_current)
            except InvalidVersion:
                logger.error(
                    f"UpdateChecker: не удалось распарсить ТЕКУЩУЮ версию: "
                    f"'{self._current_version}'"
                )
                return None
            return remote > local

        # Fallback: простое строковое сравнение (лучше чем ничего)
        logger.debug("UpdateChecker: packaging недоступен, строковое сравнение")
        return clean_tag != clean_current