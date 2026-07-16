"""
modules/multi/account_manager.py
─────────────────────────────────
AccountManager — центральный менеджер всех аккаунтов FunPay.

Отвечает за:
- Загрузку аккаунтов из БД
- Запуск/остановку/перезапуск каждого аккаунта
- Управление основным аккаунтом
- Клонирование настроек между аккаунтами
- Периодическую проверку состояния всех аккаунтов
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger
from sqlalchemy import select, update

from modules.core.base_module import BaseModule, ModuleStatus
from modules.core.database import get_session
from modules.core.events import EventBus, EventType
from modules.multi.account import AccountWrapper, AccountState
from modules.multi.models.account import Account as AccountModel
from modules.multi.models.account_lot import AccountLot, EventLog


class AccountManager(BaseModule):
    """
    Менеджер аккаунтов FunPay для Cardinal_Multi.

    Максимум 5 аккаунтов.
    Первый аккаунт (is_primary=True) — основной.

    Пример::

        manager = AccountManager()
        await manager.setup()
        await manager.start()

        # Добавление аккаунта
        await manager.add_account("my_golden_key", name="Аккаунт 1")

        # Остановка
        await manager.stop()
    """

    name = "AccountManager"
    version = "1.0.0"
    description = "Управление несколькими аккаунтами FunPay"

    MAX_ACCOUNTS = 5
    HEALTH_CHECK_INTERVAL = 30  # секунд

    def __init__(self) -> None:
        super().__init__()
        # account_id → AccountWrapper
        self._accounts: dict[int, AccountWrapper] = {}
        self._health_check_task: asyncio.Task | None = None

    # ──────────────────────────────────────────────────────────────────────────
    # Жизненный цикл (BaseModule)
    # ──────────────────────────────────────────────────────────────────────────

    async def setup(self) -> None:
        """
        Загружает аккаунты из БД и создаёт AccountWrapper'ы.
        """
        await super().setup()

        async with get_session() as session:
            result = await session.execute(
                select(AccountModel)
                .where(AccountModel.is_active == True)
                .order_by(AccountModel.is_primary.desc(), AccountModel.id)
            )
            models: list[AccountModel] = list(result.scalars().all())

        if not models:
            self._log.warning(
                "Нет активных аккаунтов в БД. "
                "Запусти setup.py для добавления аккаунта."
            )
            self._set_running()
            return

        for model in models:
            wrapper = AccountWrapper(model)
            self._accounts[model.id] = wrapper
            self._log.info(
                "Аккаунт загружен: id={}, name={}, primary={}",
                model.id, model.name, model.is_primary,
            )

        self._log.info(
            "AccountManager: загружено {} аккаунтов из БД.", len(self._accounts)
        )

    async def start(self) -> None:
        """
        Запускает все активные аккаунты и health-check мониторинг.
        """
        await super().start()

        if not self._accounts:
            self._log.warning("Нет аккаунтов для запуска.")
            self._set_running()
            return

        # Запускаем аккаунты (основной первым)
        start_tasks = []
        for account_id in sorted(
            self._accounts.keys(),
            key=lambda aid: (not self._accounts[aid].model.is_primary, aid),
        ):
            wrapper = self._accounts[account_id]
            start_tasks.append(self._start_account_safe(wrapper))

        results = await asyncio.gather(*start_tasks, return_exceptions=True)

        started = sum(1 for r in results if r is True)
        failed  = len(results) - started
        self._log.info(
            "AccountManager: запущено {}/{} аккаунтов ({}  ошибок).",
            started, len(results), failed,
        )

        # Запускаем health-check
        self._health_check_task = asyncio.create_task(
            self._health_check_loop(),
            name="account_manager_health_check",
        )

        self._set_running()

    async def stop(self) -> None:
        """
        Останавливает все аккаунты и health-check.
        """
        await super().stop()

        # Останавливаем health-check
        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        # Останавливаем все аккаунты параллельно
        if self._accounts:
            stop_tasks = [
                wrapper.stop()
                for wrapper in self._accounts.values()
                if wrapper.is_running
            ]
            if stop_tasks:
                await asyncio.gather(*stop_tasks, return_exceptions=True)

        self._set_stopped()
        self._log.info("AccountManager: все аккаунты остановлены.")

    def status(self) -> dict[str, Any]:
        """Возвращает статус всех аккаунтов для UI."""
        accounts_status = {
            aid: wrapper.status()
            for aid, wrapper in self._accounts.items()
        }
        running_count = sum(
            1 for w in self._accounts.values() if w.is_running
        )
        return {
            **super().status(),
            "accounts":       accounts_status,
            "total_accounts": len(self._accounts),
            "running":        running_count,
            "stopped":        len(self._accounts) - running_count,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Управление аккаунтами
    # ──────────────────────────────────────────────────────────────────────────

    async def add_account(
        self,
        golden_key: str,
        name: str = "Аккаунт",
        telegram_token: str | None = None,
        owner_chat_id: str | None = None,
    ) -> AccountModel:
        """
        Добавляет новый аккаунт в БД и запускает его.

        :param golden_key: golden_key FunPay аккаунта.
        :param name: отображаемое имя.
        :param telegram_token: токен Telegram-бота (опционально).
        :param owner_chat_id: Telegram chat_id владельца.
        :return: созданная ORM-модель аккаунта.
        :raises ValueError: если превышен лимит аккаунтов.
        :raises ValueError: если golden_key уже используется.
        """
        if len(self._accounts) >= self.MAX_ACCOUNTS:
            raise ValueError(
                f"Превышен лимит аккаунтов ({self.MAX_ACCOUNTS}). "
                "Удали существующий аккаунт перед добавлением нового."
            )

        from modules.core.encryption import Encryption

        # Создаём модель
        model = AccountModel()
        model.name = name
        model.set_golden_key(golden_key)
        model.is_primary = len(self._accounts) == 0  # первый = primary
        model.is_active = True

        if telegram_token:
            model.set_telegram_token(telegram_token)
        if owner_chat_id:
            model.owner_chat_id = owner_chat_id

        async with get_session() as session:
            session.add(model)
            await session.flush()  # получаем id
            await session.refresh(model)
            account_id = model.id

        self._log.info(
            "Аккаунт добавлен: id={}, name={}, primary={}",
            account_id, name, model.is_primary,
        )

        # Создаём wrapper и запускаем
        wrapper = AccountWrapper(model)
        self._accounts[account_id] = wrapper

        if self._status == ModuleStatus.RUNNING:
            await self._start_account_safe(wrapper)

        return model

    async def remove_account(self, account_id: int) -> None:
        """
        Останавливает и удаляет аккаунт из системы.

        :param account_id: ID аккаунта.
        :raises ValueError: если аккаунт не найден.
        :raises ValueError: если пытаются удалить основной аккаунт при наличии других.
        """
        if account_id not in self._accounts:
            raise ValueError(f"Аккаунт {account_id} не найден.")

        wrapper = self._accounts[account_id]

        if wrapper.model.is_primary and len(self._accounts) > 1:
            raise ValueError(
                f"Нельзя удалить основной аккаунт (id={account_id}) "
                "пока есть другие аккаунты. "
                "Сначала сделай другой аккаунт основным."
            )

        # Останавливаем процесс
        if wrapper.is_running:
            await wrapper.stop()

        # Удаляем из БД
        async with get_session() as session:
            model = await session.get(AccountModel, account_id)
            if model:
                await session.delete(model)

        del self._accounts[account_id]
        self._log.info("Аккаунт {} удалён.", account_id)

    async def restart_account(self, account_id: int) -> bool:
        """
        Перезапускает аккаунт.

        :param account_id: ID аккаунта.
        :return: True если перезапуск успешен.
        :raises ValueError: если аккаунт не найден.
        """
        wrapper = self._get_wrapper(account_id)
        self._log.info("Перезапуск аккаунта {}...", account_id)
        return await wrapper.restart()

    async def set_primary(self, account_id: int) -> None:
        """
        Делает аккаунт основным.

        Снимает флаг is_primary со всех остальных аккаунтов.
        Плагины Cardinal начнут работать с этим аккаунтом после перезапуска.

        :param account_id: ID нового основного аккаунта.
        :raises ValueError: если аккаунт не найден.
        """
        if account_id not in self._accounts:
            raise ValueError(f"Аккаунт {account_id} не найден.")

        async with get_session() as session:
            # Снимаем primary со всех
            await session.execute(
                update(AccountModel).values(is_primary=False)
            )
            # Устанавливаем primary для нужного
            await session.execute(
                update(AccountModel)
                .where(AccountModel.id == account_id)
                .values(is_primary=True)
            )

        # Обновляем in-memory модели
        for aid, wrapper in self._accounts.items():
            wrapper.model.is_primary = (aid == account_id)

        self._log.info("Аккаунт {} назначен основным.", account_id)

    async def clone_settings(self, from_account_id: int, to_account_id: int) -> None:
        """
        Клонирует настройки Cardinal конфигов от одного аккаунта к другому.

        Копирует:
        - configs/_main.cfg (кроме golden_key и Telegram секций)
        - configs/auto_response.cfg
        - configs/auto_delivery.cfg

        :param from_account_id: ID исходного аккаунта.
        :param to_account_id: ID целевого аккаунта.
        :raises ValueError: если аккаунт не найден.
        """
        src_wrapper = self._get_wrapper(from_account_id)
        dst_wrapper = self._get_wrapper(to_account_id)

        src_configs = src_wrapper.account_dir / "configs"
        dst_configs = dst_wrapper.account_dir / "configs"

        import shutil
        import configparser

        for cfg_file in ["auto_response.cfg", "auto_delivery.cfg"]:
            src = src_configs / cfg_file
            dst = dst_configs / cfg_file
            if src.exists():
                shutil.copy2(str(src), str(dst))
                self._log.info(
                    "Конфиг {} клонирован: {} → {}",
                    cfg_file, from_account_id, to_account_id,
                )

        # _main.cfg — копируем без golden_key и Telegram-секций
        src_main = src_configs / "_main.cfg"
        dst_main = dst_configs / "_main.cfg"
        if src_main.exists() and dst_main.exists():
            src_cfg = configparser.ConfigParser()
            src_cfg.read(str(src_main), encoding="utf-8")

            dst_cfg = configparser.ConfigParser()
            dst_cfg.read(str(dst_main), encoding="utf-8")

            # Секции, которые НЕ клонируем (содержат секреты)
            skip_sections = {"Credentials", "Telegram"}

            for section in src_cfg.sections():
                if section in skip_sections:
                    continue
                if not dst_cfg.has_section(section):
                    dst_cfg.add_section(section)
                for key, value in src_cfg.items(section):
                    dst_cfg.set(section, key, value)

            with open(dst_main, "w", encoding="utf-8") as f:
                dst_cfg.write(f)

            self._log.info(
                "_main.cfg настройки клонированы: {} → {} (без секретов)",
                from_account_id, to_account_id,
            )

    # ──────────────────────────────────────────────────────────────────────────
    # Вспомогательные методы
    # ──────────────────────────────────────────────────────────────────────────

    async def _start_account_safe(self, wrapper: AccountWrapper) -> bool:
        """
        Запускает аккаунт с обработкой исключений.

        :param wrapper: AccountWrapper для запуска.
        :return: True если запуск успешен.
        """
        try:
            return await wrapper.start()
        except Exception as exc:
            self._log.error(
                "Исключение при запуске аккаунта {}: {}",
                wrapper.account_id, exc,
            )
            return False

    async def _health_check_loop(self) -> None:
        """
        Фоновая задача: периодическая проверка состояния всех аккаунтов.

        Запускается каждые HEALTH_CHECK_INTERVAL секунд.
        """
        self._log.debug("Health-check запущен (интервал: {}с).", self.HEALTH_CHECK_INTERVAL)

        while True:
            await asyncio.sleep(self.HEALTH_CHECK_INTERVAL)
            for account_id, wrapper in list(self._accounts.items()):
                if (
                    wrapper._state == AccountState.RUNNING
                    and not wrapper.is_running
                ):
                    self._log.warning(
                        "Health-check: аккаунт {} не отвечает. "
                        "Процесс завершился неожиданно.",
                        account_id,
                    )
                    EventBus().emit(EventType.ACCOUNT_ERROR, {
                        "account_id": account_id,
                        "message": "Процесс Cardinal завершился неожиданно",
                    })

    def _get_wrapper(self, account_id: int) -> AccountWrapper:
        """
        Возвращает AccountWrapper по ID.

        :param account_id: ID аккаунта.
        :return: AccountWrapper.
        :raises ValueError: если аккаунт не найден.
        """
        if account_id not in self._accounts:
            raise ValueError(f"Аккаунт {account_id} не найден.")
        return self._accounts[account_id]

    def get_primary_account(self) -> AccountWrapper | None:
        """
        Возвращает wrapper основного аккаунта.

        :return: AccountWrapper или None если нет активных аккаунтов.
        """
        for wrapper in self._accounts.values():
            if wrapper.model.is_primary:
                return wrapper
        return None

    def get_all_wrappers(self) -> list[AccountWrapper]:
        """Возвращает список всех AccountWrapper'ов."""
        return list(self._accounts.values())

    async def log_event(
        self,
        account_id: int | None,
        event_type: str,
        data: dict | None = None,
    ) -> None:
        """
        Записывает событие в таблицу events_log.

        :param account_id: ID аккаунта (None = системное событие).
        :param event_type: тип события.
        :param data: данные события (JSON-сериализуемый dict).
        """
        try:
            log_entry = EventLog(
                account_id=account_id,
                event_type=event_type,
                data=data,
            )
            async with get_session() as session:
                session.add(log_entry)
        except Exception as exc:
            self._log.error("Ошибка записи события в БД: {}", exc)