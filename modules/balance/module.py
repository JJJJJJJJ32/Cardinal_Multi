"""
modules/balance/module.py
BaseModule для мониторинга баланса и отложенной выдачи.
"""

from __future__ import annotations

from typing import Any, Callable, Dict

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from modules.core.base_module import BaseModule, ModuleStatus
from modules.balance.monitor import BalanceMonitor


class BalanceModule(BaseModule):
    """
    Модуль баланса:
    - Проверка баланса FunPay/Lolzteam каждые 30 минут.
    - Уведомление владельца при низком балансе.
    - Отложенная выдача: APScheduler каждую минуту.
    """

    name = "BalanceModule"

    def __init__(
        self,
        scheduler: AsyncIOScheduler,
        accounts_getter: Callable,
    ) -> None:
        super().__init__()
        self._scheduler = scheduler
        self._monitor = BalanceMonitor(accounts_getter)
        self._log = logger.bind(module=self.name)

    async def setup(self) -> None:
        self._status = ModuleStatus.SETTING_UP
        self._monitor.setup_events()
        self._log.info("BalanceModule: настройка завершена.")
        self._status = ModuleStatus.IDLE

    async def start(self) -> None:
        self._status = ModuleStatus.STARTING

        # Проверка баланса каждые 30 минут
        self._scheduler.add_job(
            self._monitor.check_balances,
            trigger="interval",
            minutes=30,
            id="balance_check",
            replace_existing=True,
        )

        # Отложенная выдача каждую минуту
        self._scheduler.add_job(
            self._monitor.process_delayed_deliveries,
            trigger="interval",
            minutes=1,
            id="delayed_delivery",
            replace_existing=True,
        )

        # Запустить проверку сразу при старте
        self._scheduler.add_job(
            self._monitor.check_balances,
            trigger="date",
            id="balance_check_startup",
            replace_existing=True,
        )

        self._status = ModuleStatus.RUNNING
        self._log.info("BalanceModule запущен.")

    async def stop(self) -> None:
        self._status = ModuleStatus.STOPPING
        self._monitor.teardown_events()

        for job_id in ("balance_check", "delayed_delivery", "balance_check_startup"):
            try:
                self._scheduler.remove_job(job_id)
            except Exception:
                pass

        self._status = ModuleStatus.STOPPED
        self._log.info("BalanceModule остановлен.")

    def status(self) -> Dict[str, Any]:
        return {
            "module": self.name,
            "status": self._status.value,
            "error": self._error,
        }