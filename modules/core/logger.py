"""
modules/core/logger.py
Безопасная инициализация loguru.

ИЗМЕНЕНИЯ (security fix):
  - diagnose/backtrace управляются через env (default=False)
  - уровень перехвата std logging = log_level (не forced DEBUG)
  - patcher редактирует токены/ключи до записи в файл
  - права на logs/ = 0700, лог-файл = 0600
  - шумные библиотеки прижаты до WARNING
"""

from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Pattern

from loguru import logger

# ─── Пути ───────────────────────────────────────────────────────────────────
LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "cardinal_multi.log"

# ─── Формат ─────────────────────────────────────────────────────────────────
LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "{extra[name]} | "
    "<cyan>{module}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)

ROTATION    = "10 MB"
RETENTION   = "30 days"
COMPRESSION = "zip"

# ─── Паттерны для редактирования секретов ────────────────────────────────────
_SENSITIVE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # golden_key=..., token=..., Authorization: Bearer ...
    (
        re.compile(
            r"(?i)\b(golden_key|token|authorization|cookie|api_key|secret)\b"
            r"(\s*[:=]\s*)([^\s'\";,&]{4,})",
            re.IGNORECASE,
        ),
        r"\1\2[REDACTED]",
    ),
    # Telegram Bot Token: 123456789:ABCdef...
    (
        re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{20,}\b"),
        "[REDACTED_TG_TOKEN]",
    ),
    # FunPay golden_key (hex-подобная строка длиной 32-128)
    (
        re.compile(r"(?<=['\"\s=:])([a-f0-9]{32,128})(?=['\"\s,;])"),
        "[REDACTED_KEY]",
    ),
]


def _redact(text: str) -> str:
    """Удаляет секреты из строки перед логированием."""
    if not text:
        return text
    result = text
    for pattern, repl in _SENSITIVE_PATTERNS:
        result = pattern.sub(repl, result)
    return result


def _patch_record(record: dict[str, Any]) -> None:
    """loguru patcher — вызывается для каждой записи до записи в sink."""
    record["message"] = _redact(str(record.get("message", "")))
    extra = record.get("extra") or {}
    for key, val in list(extra.items()):
        if isinstance(val, str):
            extra[key] = _redact(val)


class InterceptHandler(logging.Handler):
    """
    Перехватывает стандартный logging → loguru.
    НЕ форсирует DEBUG: уровень берётся из basicConfig.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: Any = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore[assignment]
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logger(log_level: str = "INFO") -> None:
    """
    Инициализация логгера.

    Управление через env-переменные:
      CARDINAL_MULTI_LOG_DIAGNOSE=1  — включить diagnose (только для локальной отладки)
      CARDINAL_MULTI_LOG_BACKTRACE=1 — включить backtrace (только для локальной отладки)

    По умолчанию оба ВЫКЛЮЧЕНЫ (безопасный дефолт для продакшена).
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Hardening прав на директорию логов
    try:
        LOG_DIR.chmod(0o700)
    except OSError:
        pass

    # Читаем env-флаги (явно opt-in, дефолт = выключено)
    enable_diagnose  = os.getenv("CARDINAL_MULTI_LOG_DIAGNOSE",  "0").strip() == "1"
    enable_backtrace = os.getenv("CARDINAL_MULTI_LOG_BACKTRACE", "0").strip() == "1"

    normalized_level = log_level.upper()

    # Удаляем дефолтный stderr-sink
    logger.remove()

    # Применяем patcher (редактирование секретов)
    logger.configure(patcher=_patch_record)

    # ── Sink: файл ─────────────────────────────────────────────────────────
    logger.add(
        str(LOG_FILE),
        level=normalized_level,
        format=LOG_FORMAT,
        rotation=ROTATION,
        retention=RETENTION,
        compression=COMPRESSION,
        encoding="utf-8",
        enqueue=True,           # thread-safe
        backtrace=enable_backtrace,
        diagnose=enable_diagnose,
    )

    # ── Sink: консоль ──────────────────────────────────────────────────────
    logger.add(
        sys.stdout,
        level=normalized_level,
        format=LOG_FORMAT,
        backtrace=enable_backtrace,
        diagnose=enable_diagnose,
        colorize=True,
    )

    # Hardening прав на файл логов
    try:
        LOG_FILE.touch(mode=0o600, exist_ok=True)
    except OSError:
        pass

    # ── Перехват стандартного logging ──────────────────────────────────────
    # Уровень = выбранный log_level, НЕ forced DEBUG
    numeric_level = getattr(logging, normalized_level, logging.INFO)
    logging.basicConfig(
        handlers=[InterceptHandler()],
        level=numeric_level,
        force=True,
    )

    # Прижимаем шумные библиотеки до WARNING
    _NOISY_LIBS = (
        "httpx", "httpcore", "asyncio", "urllib3",
        "telebot", "aiohttp.access", "aiohttp.server",
        "aiogram", "apscheduler",
    )
    for lib in _NOISY_LIBS:
        logging.getLogger(lib).setLevel(logging.WARNING)

    logger.bind(name="logger").info(
        "Logger initialized | level={} | diagnose={} | backtrace={} | file={}",
        normalized_level,
        enable_diagnose,
        enable_backtrace,
        LOG_FILE,
    )


def get_logger(name: str):
    """Возвращает loguru-логгер с именем модуля."""
    return logger.bind(name=name)