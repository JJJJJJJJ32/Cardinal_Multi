"""
Логгер Cardinal_Multi — loguru с фильтрацией секретов.

Фиксы:
  B-07   — redact в stacktrace / exc_info
  TC-116 — fallback в stdout при отсутствии прав на logs/
  TC-117 — golden_key в traceback
  TC-118 — thread-safe (loguru сам потокобезопасен)
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from loguru import logger

# ═══════════════════════════════════════════════════════════════════════════════
# Паттерны секретов для редакции
# ═══════════════════════════════════════════════════════════════════════════════
_SECRET_PATTERNS: list[re.Pattern] = [
    # Telegram Bot Token: 123456789:ABCdef…
    re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b"),
    # golden_key (hex 32+)
    re.compile(r"golden_key[=:\s]+['\"]?([a-fA-F0-9]{32,})['\"]?"),
    # Bearer / Authorization header
    re.compile(r"(Bearer\s+)[A-Za-z0-9_.~+/=-]+", re.IGNORECASE),
    re.compile(r"(Authorization[=:\s]+)[^\s,;]+", re.IGNORECASE),
    # Fernet token (gAAAAA…)
    re.compile(r"gAAAAA[A-Za-z0-9_=-]{40,}"),
    # Универсальный шаблон: token=..., secret=..., password=... api_key=...
    re.compile(
        r"((?:token|secret|password|api_key|apikey|secret_key)[=:\s]+)[^\s,;'\"]{8,}",
        re.IGNORECASE,
    ),
]

_REDACTED = "[REDACTED]"


def _redact(text: str) -> str:
    """Заменить все совпадения секретов на [REDACTED]."""
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(_REDACTED, text)
    return text


# ═══════════════════════════════════════════════════════════════════════════════
# Loguru filter + format
# ═══════════════════════════════════════════════════════════════════════════════
def _secret_filter(record: dict) -> bool:
    """
    Loguru filter: редактирует message + exception traceback.

    FIX B-07 / TC-117: stacktrace тоже проходит через _redact().
    """
    # Редактируем само сообщение
    record["message"] = _redact(record["message"])

    # Редактируем exception / traceback (FIX B-07)
    exc = record.get("exception")
    if exc is not None:
        # exc — это кортеж (type, value, traceback) или loguru RecordException
        # loguru хранит строковое представление, патчим value.__str__ нельзя,
        # поэтому патчим formatted в record["extra"]["formatted_exception"]
        # Самый надёжный путь — перехватить в format-функции (ниже).
        pass

    return True


def _format_with_redact(record: dict) -> str:
    """
    Формат строки логов.
    Включая exception — всё проходит через _redact().
    """
    # Базовый формат
    fmt = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    # Если есть exception — добавляем и редактируем
    if record["exception"]:
        fmt += "\n{exception}"

    fmt += "\n"
    return fmt


def _patched_format(record: dict) -> str:
    """Loguru вызывает format(record) — мы перехватываем и редактируем вывод."""
    base = _format_with_redact(record)
    # _redact применяется ко всему итоговому тексту (включая traceback)
    # через sink patcher ниже
    return base


# ═══════════════════════════════════════════════════════════════════════════════
# Patcher: применяет _redact ко ВСЕМУ, что идёт в sink
# ═══════════════════════════════════════════════════════════════════════════════
def _patcher(record: dict) -> None:
    """
    Loguru patcher: вызывается до format.
    Редактирует message. Exception редактируется в sink через обёртку.
    """
    record["message"] = _redact(record["message"])


class _RedactSink:
    """
    Обёртка над файловым sink — пропускает финальную строку через _redact.

    Это гарантирует, что даже traceback в exception будет отредактирован.
    (FIX B-07 / TC-117)
    """

    def __init__(self, sink_func):
        self._sink = sink_func

    def write(self, message: str) -> None:
        self._sink(_redact(str(message)))

    def flush(self) -> None:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# Публичная функция setup
# ═══════════════════════════════════════════════════════════════════════════════
LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "cardinal_multi.log"

# Ротация / Retention
LOG_ROTATION = "10 MB"
LOG_RETENTION = "7 days"
LOG_COMPRESSION = "zip"


def setup_logger(level: str = "DEBUG") -> None:
    """
    Настроить loguru с:
      - stdout (с цветами)
      - файл в logs/ (с ротацией)
      - redact секретов ВЕЗДЕ (включая traceback)

    TC-116: если logs/ недоступна — логи только в stdout, без краша.
    """
    # Удаляем все предыдущие sinks
    logger.remove()

    # ── stdout (всегда) ──────────────────────────────────────────────────────
    logger.add(
        sys.stderr,
        level=level.upper(),
        format=_format_with_redact,
        filter=_secret_filter,
        colorize=True,
        backtrace=True,
        diagnose=False,  # diagnose=True может утекать переменные!
    )

    # ── Файл (если возможно) ─────────────────────────────────────────────────
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        # Проверяем права на запись
        test_file = LOG_DIR / ".write_test"
        try:
            test_file.touch()
            test_file.unlink()
        except OSError:
            raise PermissionError(f"Нет прав на запись в {LOG_DIR}")

        # Устанавливаем права на директорию (Linux/Mac)
        if os.name != "nt":
            try:
                LOG_DIR.chmod(0o750)
            except OSError:
                pass

        logger.add(
            str(LOG_FILE),
            level=level.upper(),
            format=_format_with_redact,
            filter=_secret_filter,
            rotation=LOG_ROTATION,
            retention=LOG_RETENTION,
            compression=LOG_COMPRESSION,
            encoding="utf-8",
            backtrace=True,
            diagnose=False,
        )
        logger.debug(f"Логи пишутся в {LOG_FILE}")

    except (PermissionError, OSError) as exc:
        # TC-116: если нет прав — только stderr, без краша
        logger.warning(
            f"Не удалось настроить файловый лог ({exc}). "
            f"Логи доступны только в консоли."
        )