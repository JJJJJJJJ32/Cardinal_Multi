"""
modules/core/base_module.py
────────────────────────────
Базовый класс для всех модулей Cardinal_Multi.

Все новые модули (multi, lolzteam, ai, stats, balance)
наследуют от BaseModule и реализуют:
- setup()  — одноразовая инициализация (DB, соединения и т.д.)
- start()  — запуск фоновых задач
- stop()   — корректная остановка
- status() — текущее состояние для ui/console.py
"""

from __future__ import annotations

import abc
from enum import Enum
from typing import Any

from loguru import logger


class ModuleStatus(str, Enum):
    """Возможные состояния модуля."""

    IDLE       = "idle"
    """Модуль создан, но не инициализирован."""

    SETTING_UP = "setting_up"
    """Выполняется setup()."""

    STARTING   = "starting"
    """Выполняется start()."""

    RUNNING    = "running"
    """Модуль работает штатно."""

    STOPPING   = "stopping"
    """Выполняется stop()."""

    STOPPED    = "stopped"
    """Модуль остановлен."""

    ERROR      = "error"
    """Модуль завершился с ошибкой."""


class BaseModule(abc.ABC):
    """
    Абстрактный базовый класс для всех модулей Cardinal_Multi.

    Обеспечивает:
    - Единый жизненный цикл (setup → start → stop)
    - Отслеживание статуса
    - Логирование с именем модуля
    - Защиту от двойного запуска

    Пример реализации::

        class MyModule(BaseModule):
            name = "MyModule"
            version = "1.0.0"
            description = "Описание модуля"

            async def setup(self) -> None:
                await super().setup()
                # инициализация...

            async def start(self) -> None:
                await super().start()
                # запуск фоновых задач...

            async def stop(self) -> None:
                await super().stop()
                # остановка...

            def status(self) -> dict[str, Any]:
                return {**super().status(), "my_key": "my_value"}
    """

    # Атрибуты, которые должны быть переопределены в подклассах
    name: str = "UnnamedModule"
    version: str = "0.0.0"
    description: str = ""

    def __init__(self) -> None:
        self._status: ModuleStatus = ModuleStatus.IDLE
        self._error: str | None = None
        self._log = logger.bind(module=self.name)

    # ──────────────────────────────────────────────────────────────────────────
    # Жизненный цикл
    # ──────────────────────────────────────────────────────────────────────────

    async def setup(self) -> None:
        """
        Одноразовая инициализация модуля.

        Вызывается один раз при старте системы.
        Здесь: подключение к БД, создание таблиц, загрузка конфигов.

        :raises Exception: если инициализация не удалась.
        """
        self._status = ModuleStatus.SETTING_UP
        self._log.info("Инициализация модуля {} v{}", self.name, self.version)

    async def start(self) -> None:
        """
        Запуск модуля (фоновые задачи, подписки на события).

        Вызывается после setup(). Может запускать asyncio.Task или потоки.

        :raises RuntimeError: если модуль не был setup()'нут.
        """
        if self._status not in (ModuleStatus.SETTING_UP, ModuleStatus.STOPPED):
            raise RuntimeError(
                f"Модуль {self.name}: нельзя запустить из состояния {self._status}."
            )
        self._status = ModuleStatus.STARTING
        self._log.info("Запуск модуля {}", self.name)

    async def stop(self) -> None:
        """
        Корректная остановка модуля.

        Отменяет задачи, закрывает соединения, сохраняет состояние.
        После остановки модуль переходит в STOPPED.
        """
        self._status = ModuleStatus.STOPPING
        self._log.info("Остановка модуля {}", self.name)

    # ──────────────────────────────────────────────────────────────────────────
    # Статус
    # ──────────────────────────────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        """
        Возвращает текущее состояние модуля для dashboard.

        Подклассы могут расширить этот словарь своими данными::

            def status(self) -> dict[str, Any]:
                return {**super().status(), "accounts_active": 3}

        :return: словарь с состоянием модуля.
        """
        return {
            "name":        self.name,
            "version":     self.version,
            "description": self.description,
            "status":      self._status.value,
            "error":       self._error,
        }

    @property
    def is_running(self) -> bool:
        """True если модуль в состоянии RUNNING."""
        return self._status == ModuleStatus.RUNNING

    @property
    def current_status(self) -> ModuleStatus:
        """Текущий статус модуля."""
        return self._status

    # ──────────────────────────────────────────────────────────────────────────
    # Вспомогательные методы для подклассов
    # ──────────────────────────────────────────────────────────────────────────

    def _set_running(self) -> None:
        """Переводит модуль в статус RUNNING. Вызывать в конце start()."""
        self._status = ModuleStatus.RUNNING
        self._log.info("Модуль {} запущен.", self.name)

    def _set_stopped(self) -> None:
        """Переводит модуль в статус STOPPED. Вызывать в конце stop()."""
        self._status = ModuleStatus.STOPPED
        self._log.info("Модуль {} остановлен.", self.name)

    def _set_error(self, error: str) -> None:
        """
        Переводит модуль в статус ERROR.

        :param error: описание ошибки для логов и dashboard.
        """
        self._status = ModuleStatus.ERROR
        self._error = error
        self._log.error("Модуль {} — ошибка: {}", self.name, error)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} status={self._status.value}>"