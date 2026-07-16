"""
modules/updates/checker.py
Проверка обновлений Cardinal_Multi через GitHub Releases API.
Запускается 1 раз при старте + раз в сутки через APScheduler.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import aiohttp
from loguru import logger
from packaging.version import Version, InvalidVersion
from sqlalchemy import select

from modules.core.database import get_session
from modules.core.notifier import get_notifier
from modules.updates.models.update_check import UpdateCheck


# ──────────────────────────────────────────────
# НАСТРОЙКИ (менять под реальный репо)
# ──────────────────────────────────────────────
GITHUB_OWNER = "JJJJJJJJ32"
GITHUB_REPO = "Cardinal_Multi"
CURRENT_VERSION = "1.0.0"          # TODO: брать из конфига/VERSION файла
CHECK_INTERVAL_HOURS = 24
# ──────────────────────────────────────────────


class UpdateChecker:
    """
    Проверяет наличие новых версий Cardinal_Multi на GitHub.
    Уведомляет владельца в Telegram.
    НЕ скачивает и НЕ устанавливает автоматически.
    """

    API_URL = (
        f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
    )

    def __init__(self) -> None:
        self._log = logger.bind(module="UpdateChecker")
        self._notifier = get_notifier()

    async def check(self, force: bool = False) -> Optional[str]:
        """
        Проверить наличие обновления.

        Args:
            force: Игнорировать кэш и проверить принудительно.

        Returns:
            Версия новой версии если есть, иначе None.
        """
        # Проверить кэш в БД
        if not force:
            cached = await self._get_cached()
            if cached and cached.last_checked_at:
                hours_since = (datetime.utcnow() - cached.last_checked_at).total_seconds() / 3600
                if hours_since < CHECK_INTERVAL_HOURS:
                    self._log.debug(
                        f"Проверка обновлений: кэш актуален "
                        f"({hours_since:.1f}ч < {CHECK_INTERVAL_HOURS}ч)."
                    )
                    return None

        self._log.info("Проверка обновлений на GitHub...")

        try:
            release_data = await self._fetch_latest_release()
        except Exception as e:
            self._log.error(f"Ошибка запроса GitHub API: {e}")
            return None

        if not release_data:
            return None

        latest_version_raw: str = release_data.get("tag_name", "").lstrip("v")
        changelog: str = release_data.get("body", "")[:1000]
        release_url: str = release_data.get("html_url", "")

        # Сохранить в кэш
        await self._save_cache(
            latest_version=latest_version_raw,
            changelog=changelog,
            release_url=release_url,
        )

        # Сравнить версии
        try:
            is_newer = Version(latest_version_raw) > Version(CURRENT_VERSION)
        except InvalidVersion:
            self._log.warning(f"Не удалось разобрать версию: {latest_version_raw!r}")
            return None

        if is_newer:
            self._log.info(
                f"Доступна новая версия: {CURRENT_VERSION} → {latest_version_raw}"
            )
            await self._notify_update(
                current=CURRENT_VERSION,
                latest=latest_version_raw,
                changelog=changelog,
                release_url=release_url,
            )
            return latest_version_raw
        else:
            self._log.info(
                f"Версия актуальна: {CURRENT_VERSION} (последняя: {latest_version_raw})"
            )
            return None

    async def _fetch_latest_release(self) -> Optional[dict]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(
                self.API_URL,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 404:
                    self._log.warning("GitHub API: релизов не найдено.")
                    return None
                else:
                    self._log.error(f"GitHub API: HTTP {resp.status}")
                    return None

    async def _notify_update(
        self,
        current: str,
        latest: str,
        changelog: str,
        release_url: str,
    ) -> None:
        # Обрезаем changelog для Telegram
        short_changelog = changelog[:500] + ("..." if len(changelog) > 500 else "")

        text = (
            f"📦 <b>Доступна новая версия Cardinal_Multi!</b>\n"
            f"\n"
            f"Текущая: <code>v{current}</code>\n"
            f"Новая: <code>v{latest}</code>\n"
            f"\n"
            f"Что нового:\n"
            f"<pre>{short_changelog}</pre>\n"
            f"\n"
            f"🔗 <a href=\"{release_url}\">Скачать</a>"
        )

        await self._notifier.send(text=text)

    async def _get_cached(self) -> Optional[UpdateCheck]:
        async with get_session() as session:
            result = await session.execute(
                select(UpdateCheck).order_by(UpdateCheck.id.desc()).limit(1)
            )
            return result.scalar_one_or_none()

    async def _save_cache(
        self,
        latest_version: str,
        changelog: str,
        release_url: str,
    ) -> None:
        async with get_session() as session:
            # Один ряд — обновляем или создаём
            result = await session.execute(
                select(UpdateCheck).limit(1)
            )
            record = result.scalar_one_or_none()

            if record is None:
                record = UpdateCheck()
                session.add(record)

            record.last_checked_at = datetime.utcnow()
            record.latest_version = latest_version
            record.current_version = CURRENT_VERSION
            record.changelog = changelog
            record.release_url = release_url

            await session.commit()