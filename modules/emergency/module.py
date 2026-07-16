"""
modules/emergency/module.py
BaseModule для экстренной паузы.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from loguru import logger

from modules.core.base_module import BaseModule, ModuleStatus
from modules.emergency.pause import PauseManager


class EmergencyModule(BaseModule):
    """
    Модуль экстренной паузы Cardinal_Multi.
    Предоставляет глобальный PauseManager другим модулям.
    """

    name = "EmergencyModule"

    def __init__(self) -> None:
        super().__init__()
        self._pause_manager = PauseManager()
        self._log = logger.bind(module=self.name)

    async def setup(self) -> None:
        self._status = ModuleStatus.SETTING_UP
        self._log.info("EmergencyModule: готов.")
        self._status = ModuleStatus.IDLE

    async def start(self) -> None:
        self._status = ModuleStatus.RUNNING
        self._log.info("EmergencyModule запущен.")

    async def stop(self) -> None:
        self._status = ModuleStatus.STOPPING
        # Снять все паузы при остановке
        if self._pause_manager.is_global_paused():
            await self._pause_manager.resume(account_id=None)
        self._status = ModuleStatus.STOPPED
        self._log.info("EmergencyModule остановлен.")

    async def pause(
        self,
        account_id: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> None:
        await self._pause_manager.pause(account_id=account_id, reason=reason)

    async def resume(self, account_id: Optional[int] = None) -> None:
        await self._pause_manager.resume(account_id=account_id)

    def is_paused(self, account_id: int) -> bool:
        return self._pause_manager.is_paused(account_id)

    @property
    def manager(self) -> PauseManager:
        return self._pause_manager

    def status(self) -> Dict[str, Any]:
        return {
            "module": self.name,
            "status": self._status.value,
            "pause_state": self._pause_manager.get_status(),
            "error": self._error,
        }