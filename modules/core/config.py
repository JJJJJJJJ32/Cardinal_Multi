"""
Config — настройки Cardinal_Multi из .env.

Фиксы:
  TC-003 — LOG_LEVEL валидация
  TC-004 — MAX_ACCOUNTS boundary (1..5)
  TC-005 — REQUEST_DELAY >= 1.0
  TC-051 — MAIN_TELEGRAM_TOKEN без CHAT_ID
  TC-061 — reload_settings() возвращает новый инстанс
"""

from __future__ import annotations

import configparser
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings
from loguru import logger


# ═══════════════════════════════════════════════════════════════════════════════
# Допустимые значения
# ═══════════════════════════════════════════════════════════════════════════════
ALLOWED_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

MIN_ACCOUNTS = 1
MAX_ACCOUNTS_LIMIT = 5

MIN_REQUEST_DELAY = 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# Модель настроек
# ═══════════════════════════════════════════════════════════════════════════════
class MultiSettings(BaseSettings):
    """Настройки Cardinal_Multi, загружаемые из .env."""

    # ── Общие ────────────────────────────────────────────────────────────────
    log_level: str = "INFO"
    max_accounts: int = 3
    request_delay: float = 2.0

    # ── Telegram (главный бот) ───────────────────────────────────────────────
    main_telegram_token: Optional[str] = None
    main_telegram_chat_id: Optional[str] = None

    # ── Lolzteam ─────────────────────────────────────────────────────────────
    lolz_api_token: Optional[str] = None
    lolzteam_token: Optional[str] = None
    lolz_login: Optional[str] = None
    lolz_password: Optional[str] = None

    # ── Balance ──────────────────────────────────────────────────────────────
    balance_threshold: float = 0.0
    balance_check_interval: int = 60  # секунды

    # ── Health Check ─────────────────────────────────────────────────────────
    health_check_interval: int = 30  # секунды

    # ── Gemini (если используется) ───────────────────────────────────────────
    gemini_api_key: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # не падать при неизвестных переменных

    # ── TC-003: LOG_LEVEL валидация ──────────────────────────────────────────
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        upper = v.upper().strip()
        if upper not in ALLOWED_LOG_LEVELS:
            raise ValueError(
                f"LOG_LEVEL='{v}' недопустим. "
                f"Допустимые значения: {', '.join(sorted(ALLOWED_LOG_LEVELS))}"
            )
        return upper

    # ── TC-004: MAX_ACCOUNTS boundary ────────────────────────────────────────
    @field_validator("max_accounts")
    @classmethod
    def validate_max_accounts(cls, v: int) -> int:
        if not (MIN_ACCOUNTS <= v <= MAX_ACCOUNTS_LIMIT):
            raise ValueError(
                f"MAX_ACCOUNTS={v} вне допустимого диапазона "
                f"({MIN_ACCOUNTS}..{MAX_ACCOUNTS_LIMIT})"
            )
        return v

    # ── TC-005: REQUEST_DELAY >= 1.0 ─────────────────────────────────────────
    @field_validator("request_delay")
    @classmethod
    def validate_request_delay(cls, v: float) -> float:
        if v < MIN_REQUEST_DELAY:
            raise ValueError(
                f"REQUEST_DELAY={v} слишком мал. "
                f"Минимальное значение: {MIN_REQUEST_DELAY} сек"
            )
        return v

    # ── TC-051: MAIN_TELEGRAM_TOKEN задан, но CHAT_ID пуст ──────────────────
    @model_validator(mode="after")
    def validate_telegram_pair(self) -> "MultiSettings":
        if self.main_telegram_token and not self.main_telegram_chat_id:
            raise ValueError(
                "MAIN_TELEGRAM_TOKEN задан, но MAIN_TELEGRAM_CHAT_ID пуст. "
                "Укажите CHAT_ID для работы Telegram-бота."
            )
        return self


# ═══════════════════════════════════════════════════════════════════════════════
# Публичные функции
# ═══════════════════════════════════════════════════════════════════════════════
@lru_cache(maxsize=1)
def get_settings() -> MultiSettings:
    """
    Загрузить и закэшировать настройки.
    При невалидном .env — SystemExit с понятным сообщением.
    """
    try:
        return MultiSettings()
    except Exception as exc:
        # Красивый вывод ошибки вместо stacktrace
        print(f"\n❌ Ошибка конфигурации (.env):\n   {exc}\n")
        raise SystemExit(1)


def reload_settings() -> MultiSettings:
    """
    Перечитать .env и вернуть НОВЫЙ инстанс настроек.

    TC-061: не меняет закэшированный через get_settings().
    Caller сам решает, применять ли новые настройки.
    """
    try:
        return MultiSettings()
    except Exception as exc:
        logger.error(f"reload_settings: ошибка перезагрузки конфигурации — {exc}")
        raise


# ═══════════════════════════════════════════════════════════════════════════════
# Чтение Cardinal .cfg файлов (read-only утилита)
# ═══════════════════════════════════════════════════════════════════════════════
def read_cardinal_config(
    config_path: str | Path,
) -> Optional[configparser.ConfigParser]:
    """Прочитать .cfg файл Cardinal (INI формат)."""
    path = Path(config_path)
    if not path.exists():
        logger.warning(f"Config: файл не найден — {path}")
        return None

    parser = configparser.ConfigParser()
    try:
        parser.read(str(path), encoding="utf-8")
    except configparser.Error as exc:
        logger.error(f"Config: ошибка парсинга {path} — {exc}")
        return None

    return parser