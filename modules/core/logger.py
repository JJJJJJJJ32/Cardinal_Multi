"""
modules/core/logger.py
─────────────────────
Настройка loguru-логгера для Cardinal_Multi.
Пишет ТОЛЬКО в файл. В консоль — только rich (через ui/console.py).
Стандартный logging Cardinal не затрагивается.
"""

from __future__ import annotations

import sys
import logging
from pathlib import Path
from loguru import logger

# ─── Константы ────────────────────────────────────────────────────────────────
LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "cardinal_multi.log"
ROTATION = "00:00"          # ротация в полночь
RETENTION = "30 days"       # хранить 30 дней
COMPRESSION = "zip"         # сжимать старые логи
LOG_FORMAT = (
    "<green>{time:DD.MM.YYYY HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{line}</cyan> | "
    "{message}"
)


class InterceptHandler(logging.Handler):
    """
    Перехватчик стандартного logging → loguru.
    Позволяет видеть логи Cardinal в нашем файле,
    не изменяя ни одной строки кода Cardinal.
    """

    def emit(self, record: logging.LogRecord) -> None:
        # Определяем соответствующий уровень loguru
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Находим реального вызывающего (не logging internals)
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore[assignment]
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logger(log_level: str = "DEBUG") -> None:
    """
    Инициализирует loguru logger.

    - Удаляет дефолтный sink (stderr).
    - Добавляет file sink с ротацией.
    - Перехватывает стандартный logging Cardinal.

    :param log_level: минимальный уровень логирования (DEBUG/INFO/WARNING/ERROR).
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Удаляем стандартный вывод loguru (stderr)
    logger.remove()

    # Файловый sink — только файл, никакой консоли
    logger.add(
        str(LOG_FILE),
        level=log_level,
        format=LOG_FORMAT,
        rotation=ROTATION,
        retention=RETENTION,
        compression=COMPRESSION,
        encoding="utf-8",
        enqueue=True,       # thread-safe очередь
        backtrace=True,
        diagnose=True,
    )

    # Перехватываем стандартный logging Cardinal (FPC, TGBot, FunPayAPI, main)
    logging.basicConfig(handlers=[InterceptHandler()], level=logging.DEBUG, force=True)

    # Подавляем слишком шумные библиотеки в нашем файле
    for noisy_logger in ("httpx", "httpcore", "asyncio", "urllib3", "telebot"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    logger.debug("Logger Cardinal_Multi инициализирован. Файл: {}", LOG_FILE)


def get_logger(name: str):
    """
    Возвращает loguru logger с привязанным именем модуля.

    :param name: имя модуля/компонента.
    :return: loguru logger instance.

    Пример::

        log = get_logger("multi.account_manager")
        log.info("Запуск аккаунта {}", account_id)
    """
    return logger.bind(name=name)