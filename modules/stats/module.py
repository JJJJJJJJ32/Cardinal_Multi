"""
modules/stats/module.py
BaseModule для системы статистики.
"""

from __future__ import annotations

from typing import Any, Dict

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from modules.core.base_module import BaseModule, ModuleStatus
from modules.stats.collector import StatsCollector


class StatsModule(BaseModule):
    """
    Модуль статистики Cardinal_Multi.
    - Подписывается на события через StatsCollector.
    - Раз в сутки очищает данные старше 90 дней.
    """

    name = "StatsModule"

    def __init__(self, scheduler: AsyncIOScheduler) -> None:
        super().__init__()
        self._scheduler = scheduler
        self._collector = StatsCollector()
        self._log = logger.bind(module=self.name)

    async def setup(self) -> None:
        self._status = ModuleStatus.SETTING_UP
        self._collector.setup()
        self._log.info("StatsModule: настройка завершена.")
        self._status = ModuleStatus.IDLE

    async def start(self) -> None:
        self._status = ModuleStatus.STARTING

        # Автоочистка раз в сутки в 3:00
        self._scheduler.add_job(
            self._cleanup_job,
            trigger="cron",
            hour=3,
            minute=0,
            id="stats_cleanup",
            replace_existing=True,
        )

        self._status = ModuleStatus.RUNNING
        self._log.info("StatsModule запущен.")

    async def stop(self) -> None:
        self._status = ModuleStatus.STOPPING
        self._collector.teardown()

        try:
            self._scheduler.remove_job("stats_cleanup")
        except Exception:
            pass

        self._status = ModuleStatus.STOPPED
        self._log.info("StatsModule остановлен.")

    async def _cleanup_job(self) -> None:
        deleted = await self._collector.cleanup_old_data(days=90)
        self._log.info(f"Автоочистка статистики: удалено {deleted} старых записей.")

    @property
    def collector(self) -> StatsCollector:
        return self._collector

    def status(self) -> Dict[str, Any]:
        return {
            "module": self.name,
            "status": self._status.value,
            "error": self._error,
        }