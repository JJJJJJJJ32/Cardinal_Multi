"""
modules/multi/account.py
─────────────────────────
Класс AccountWrapper — управление одним аккаунтом FunPay.

Каждый аккаунт запускается как отдельный subprocess.
Это обеспечивает:
- Истинную изоляцию (память, файлы, threading)
- Падение одного аккаунта не роняет другие
- Cardinal синглтон не конфликтует

Структура данных аккаунта:
    data/accounts/{account_id}/
        configs/
            _main.cfg        ← копия/симлинк основного Cardinal конфига
            auto_response.cfg
            auto_delivery.cfg
        logs/
            log.log
        storage/
        plugins/             ← симлинк на основную папку plugins/
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import sys
import time
from enum import Enum, auto
from pathlib import Path
from typing import Any

from loguru import logger

from modules.core.events import EventBus, EventType
from modules.multi.models.account import Account as AccountModel


class AccountState(str, Enum):
    """Состояния аккаунта FunPay."""
    IDLE      = "idle"
    STARTING  = "starting"
    RUNNING   = "running"
    STOPPING  = "stopping"
    STOPPED   = "stopped"
    ERROR     = "error"
    RESTARTING = "restarting"


# ─── Пути ──────────────────────────────────────────────────────────────────────
ACCOUNTS_DATA_DIR = Path("data/accounts")
MAIN_CONFIGS_DIR  = Path("configs")
MAIN_PLUGINS_DIR  = Path("plugins")
MAIN_STORAGE_DIR  = Path("storage")


class AccountWrapper:
    """
    Обёртка над одним аккаунтом FunPay.

    Запускает Cardinal как subprocess с изолированной рабочей директорией.
    Следит за процессом, перезапускает при ошибках.

    Пример::

        model = await AccountRepository.get_by_id(1)
        account = AccountWrapper(model)
        await account.start()
        # ...
        await account.stop()
    """

    MAX_RESTART_ATTEMPTS = 3
    RESTART_DELAY_SECONDS = 30

    def __init__(self, model: AccountModel) -> None:
        """
        :param model: ORM-модель аккаунта из таблицы accounts.
        """
        self.model = model
        self.account_id = model.id
        self.account_dir = ACCOUNTS_DATA_DIR / str(self.account_id)

        self._state: AccountState = AccountState.IDLE
        self._process: subprocess.Popen | None = None
        self._restart_count: int = 0
        self._start_time: float | None = None
        self._stop_requested: bool = False
        self._monitor_task: asyncio.Task | None = None

        self._log = logger.bind(account_id=self.account_id, name=model.name)

    # ──────────────────────────────────────────────────────────────────────────
    # Подготовка директорий
    # ──────────────────────────────────────────────────────────────────────────

    def prepare_directory(self) -> None:
        """
        Создаёт изолированную директорию аккаунта.

        Структура:
            data/accounts/{id}/
                configs/   ← изолированные конфиги
                logs/      ← изолированные логи
                storage/   ← изолированное хранилище
                plugins    ← симлинк на основную папку plugins/

        :raises OSError: если не удалось создать директории.
        """
        self._log.debug("Подготовка директории аккаунта: {}", self.account_dir)

        # Создаём основные директории
        for subdir in ["configs", "logs", "storage"]:
            (self.account_dir / subdir).mkdir(parents=True, exist_ok=True)

        # Копируем конфиги если ещё нет
        self._setup_configs()

        # Симлинк на общую папку плагинов
        plugins_link = self.account_dir / "plugins"
        if not plugins_link.exists():
            if MAIN_PLUGINS_DIR.exists():
                try:
                    plugins_link.symlink_to(
                        MAIN_PLUGINS_DIR.resolve(),
                        target_is_directory=True,
                    )
                    self._log.debug("Симлинк plugins → {}", MAIN_PLUGINS_DIR.resolve())
                except OSError:
                    # На Windows симлинки требуют прав администратора
                    # Копируем как fallback
                    shutil.copytree(
                        str(MAIN_PLUGINS_DIR),
                        str(plugins_link),
                        dirs_exist_ok=True,
                    )
                    self._log.warning(
                        "Симлинк недоступен (Windows?). Папка plugins скопирована."
                    )

        self._log.info("Директория аккаунта подготовлена: {}", self.account_dir)

    def _setup_configs(self) -> None:
        """
        Копирует Cardinal конфиги в директорию аккаунта.

        Первичный аккаунт: использует оригинальные конфиги.
        Дополнительные аккаунты: копирует шаблоны и создаёт
        минимальный _main.cfg с golden_key аккаунта.
        """
        configs_dir = self.account_dir / "configs"

        # Конфиги для копирования
        config_files = [
            "_main.cfg",
            "auto_response.cfg",
            "auto_delivery.cfg",
        ]

        for cfg_file in config_files:
            dst = configs_dir / cfg_file
            if dst.exists():
                continue  # уже скопирован — не перезаписываем

            src = MAIN_CONFIGS_DIR / cfg_file
            if src.exists():
                shutil.copy2(str(src), str(dst))
                self._log.debug("Конфиг скопирован: {} → {}", src, dst)
            else:
                self._log.debug(
                    "Исходный конфиг не найден, пропуск: {}", src
                )

    def update_golden_key_in_config(self) -> None:
        """
        Записывает golden_key аккаунта в его _main.cfg.

        Вызывается при первом запуске аккаунта или смене ключа.
        """
        import configparser

        cfg_path = self.account_dir / "configs" / "_main.cfg"
        if not cfg_path.exists():
            self._log.warning(
                "Файл _main.cfg не найден для аккаунта {}. "
                "Cardinal создаст его при первом запуске.",
                self.account_id,
            )
            return

        try:
            golden_key = self.model.get_golden_key()
        except Exception as exc:
            self._log.error("Не удалось получить golden_key: {}", exc)
            return

        config = configparser.ConfigParser()
        config.read(str(cfg_path), encoding="utf-8")

        if "Credentials" not in config:
            config["Credentials"] = {}

        config["Credentials"]["golden_key"] = golden_key

        with open(cfg_path, "w", encoding="utf-8") as f:
            config.write(f)

        self._log.debug("golden_key записан в конфиг аккаунта {}", self.account_id)

    # ──────────────────────────────────────────────────────────────────────────
    # Запуск / Остановка
    # ──────────────────────────────────────────────────────────────────────────

    async def start(self) -> bool:
        """
        Запускает аккаунт как subprocess Cardinal.

        :return: True если запуск успешен, False иначе.
        """
        if self._state in (AccountState.RUNNING, AccountState.STARTING):
            self._log.warning(
                "Аккаунт {} уже запущен (состояние: {}). Пропуск.",
                self.account_id, self._state,
            )
            return False

        self._state = AccountState.STARTING
        self._stop_requested = False

        try:
            self.prepare_directory()
            self.update_golden_key_in_config()
        except Exception as exc:
            self._log.error("Ошибка подготовки аккаунта {}: {}", self.account_id, exc)
            self._state = AccountState.ERROR
            return False

        success = await self._launch_process()
        if success:
            self._state = AccountState.RUNNING
            self._start_time = time.time()
            self._restart_count = 0
            # Запускаем монитор процесса
            self._monitor_task = asyncio.create_task(
                self._monitor_process(),
                name=f"monitor_account_{self.account_id}",
            )
            EventBus().emit(EventType.ACCOUNT_STARTED, {"account_id": self.account_id})
            self._log.info("Аккаунт {} запущен (PID: {})", self.account_id, self._process.pid)
        else:
            self._state = AccountState.ERROR

        return success

    async def stop(self) -> None:
        """
        Корректно останавливает аккаунт.

        Посылает SIGTERM процессу, ждёт 10 секунд, затем SIGKILL.
        """
        self._stop_requested = True
        self._state = AccountState.STOPPING

        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        if self._process and self._process.poll() is None:
            self._log.info(
                "Остановка аккаунта {} (PID: {})", self.account_id, self._process.pid
            )
            try:
                self._process.terminate()
                # Ждём корректного завершения
                await asyncio.sleep(10)
                if self._process.poll() is None:
                    self._log.warning(
                        "Принудительное завершение аккаунта {} (SIGKILL)",
                        self.account_id,
                    )
                    self._process.kill()
            except Exception as exc:
                self._log.error("Ошибка при остановке аккаунта {}: {}", self.account_id, exc)

        self._state = AccountState.STOPPED
        EventBus().emit(EventType.ACCOUNT_STOPPED, {"account_id": self.account_id})
        self._log.info("Аккаунт {} остановлен.", self.account_id)

    async def restart(self) -> bool:
        """
        Перезапускает аккаунт.

        :return: True если перезапуск успешен.
        """
        self._state = AccountState.RESTARTING
        self._log.info("Перезапуск аккаунта {}...", self.account_id)
        await self.stop()
        await asyncio.sleep(5)
        return await self.start()

    # ──────────────────────────────────────────────────────────────────────────
    # Запуск процесса
    # ──────────────────────────────────────────────────────────────────────────

    async def _launch_process(self) -> bool:
        """
        Запускает subprocess Cardinal в директории аккаунта.

        :return: True если процесс запустился.
        """
        cardinal_main = Path("cardinal") / "main.py"

        # Ищем main.py Cardinal
        if not cardinal_main.exists():
            # Попробуем в корне (если Cardinal не в подпапке)
            cardinal_main = Path("main.py")

        if not cardinal_main.exists():
            self._log.error(
                "Файл Cardinal main.py не найден. "
                "Ожидался: cardinal/main.py или main.py"
            )
            return False

        cmd = [
            sys.executable,
            str(cardinal_main.resolve()),
        ]

        try:
            self._process = subprocess.Popen(
                cmd,
                cwd=str(self.account_dir.resolve()),  # рабочая директория аккаунта
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self._log.debug(
                "Subprocess запущен: cmd={}, cwd={}",
                cmd,
                self.account_dir,
            )
            return True

        except FileNotFoundError as exc:
            self._log.error(
                "Python/Cardinal не найден для запуска аккаунта {}: {}",
                self.account_id, exc,
            )
            return False
        except Exception as exc:
            self._log.error(
                "Ошибка запуска subprocess аккаунта {}: {}",
                self.account_id, exc,
            )
            return False

    # ──────────────────────────────────────────────────────────────────────────
    # Мониторинг процесса
    # ──────────────────────────────────────────────────────────────────────────

    async def _monitor_process(self) -> None:
        """
        Фоновая задача мониторинга subprocess.

        При падении процесса — пытается перезапустить (до MAX_RESTART_ATTEMPTS).
        При превышении лимита — emit(ACCOUNT_ERROR) и остановка.
        """
        self._log.debug("Монитор аккаунта {} запущен.", self.account_id)

        while not self._stop_requested:
            await asyncio.sleep(5)  # проверяем каждые 5 секунд

            if self._process is None:
                break

            return_code = self._process.poll()
            if return_code is None:
                continue  # процесс работает

            # Процесс завершился
            if self._stop_requested:
                self._log.debug("Аккаунт {} завершён штатно.", self.account_id)
                break

            self._log.warning(
                "Аккаунт {} упал (код: {}). Попытка перезапуска {}/{}",
                self.account_id,
                return_code,
                self._restart_count + 1,
                self.MAX_RESTART_ATTEMPTS,
            )

            EventBus().emit(EventType.ACCOUNT_ERROR, {
                "account_id":   self.account_id,
                "return_code":  return_code,
                "restart_attempt": self._restart_count + 1,
            })

            if self._restart_count >= self.MAX_RESTART_ATTEMPTS:
                self._log.error(
                    "Аккаунт {} превысил лимит перезапусков ({})."
                    " Аккаунт остановлен.",
                    self.account_id,
                    self.MAX_RESTART_ATTEMPTS,
                )
                self._state = AccountState.ERROR
                EventBus().emit(EventType.ACCOUNT_ERROR, {
                    "account_id": self.account_id,
                    "fatal":      True,
                    "message":    f"Превышен лимит перезапусков ({self.MAX_RESTART_ATTEMPTS})",
                })
                break

            # Ждём перед перезапуском
            await asyncio.sleep(self.RESTART_DELAY_SECONDS)
            self._restart_count += 1

            success = await self._launch_process()
            if not success:
                self._log.error(
                    "Не удалось перезапустить аккаунт {}.", self.account_id
                )
                self._state = AccountState.ERROR
                break

        self._log.debug("Монитор аккаунта {} завершён.", self.account_id)

    # ──────────────────────────────────────────────────────────────────────────
    # Статус
    # ──────────────────────────────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        """
        Возвращает текущее состояние аккаунта для UI.

        :return: словарь с состоянием аккаунта.
        """
        uptime_seconds = None
        if self._start_time and self._state == AccountState.RUNNING:
            uptime_seconds = int(time.time() - self._start_time)

        return {
            "account_id":      self.account_id,
            "name":            self.model.name,
            "funpay_username": self.model.funpay_username,
            "is_primary":      self.model.is_primary,
            "state":           self._state.value,
            "pid":             self._process.pid if self._process else None,
            "restart_count":   self._restart_count,
            "uptime_seconds":  uptime_seconds,
        }

    @property
    def is_running(self) -> bool:
        """True если процесс Cardinal запущен и работает."""
        if self._process is None:
            return False
        if self._state != AccountState.RUNNING:
            return False
        return self._process.poll() is None

    def __repr__(self) -> str:
        return (
            f"<AccountWrapper id={self.account_id} "
            f"name={self.model.name!r} "
            f"state={self._state.value}>"
        )