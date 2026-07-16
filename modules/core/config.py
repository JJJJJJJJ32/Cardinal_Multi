"""
modules/core/config.py
──────────────────────
Единая точка конфигурации Cardinal_Multi.

Загружает:
1. .env через pydantic-settings (наши настройки)
2. Cardinal .cfg конфиги (configs/_main.cfg и др.) для read-only доступа

Все настройки валидируются Pydantic v2 при старте.
"""

from __future__ import annotations

import configparser
from pathlib import Path
from typing import Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from loguru import logger


# ─── Cardinal CFG пути ────────────────────────────────────────────────────────
CARDINAL_CONFIGS = {
    "main":          Path("configs/_main.cfg"),
    "auto_response": Path("configs/auto_response.cfg"),
    "auto_delivery": Path("configs/auto_delivery.cfg"),
}


# ─── Pydantic модели настроек ─────────────────────────────────────────────────

class AccountEnvConfig(BaseSettings):
    """
    Настройки одного аккаунта FunPay из .env.
    Используется внутри MultiSettings.
    """

    model_config = SettingsConfigDict(extra="ignore")

    golden_key: str
    """Ключ авторизации FunPay."""

    telegram_token: Optional[str] = None
    """Токен Telegram-бота для этого аккаунта (опционально)."""

    owner_chat_id: Optional[str] = None
    """Telegram chat_id владельца аккаунта."""

    is_primary: bool = False
    """Является ли аккаунт основным."""


class MultiSettings(BaseSettings):
    """
    Главные настройки Cardinal_Multi из .env.

    Все поля читаются из переменных окружения или файла .env.
    Аккаунты хранятся в БД, здесь — только глобальные настройки.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Общие настройки ───────────────────────────────────────────────────────
    log_level: str = "DEBUG"
    """Уровень логирования (DEBUG/INFO/WARNING/ERROR)."""

    max_accounts: int = 5
    """Максимальное количество аккаунтов FunPay."""

    request_delay: float = 6.0
    """Задержка между запросами к FunPay API (секунды)."""

    # ── Главный Telegram-бот (опционально) ───────────────────────────────────
    main_telegram_token: Optional[str] = None
    """Токен главного Telegram-бота для управления всеми аккаунтами."""

    main_telegram_chat_id: Optional[str] = None
    """Chat ID владельца для главного бота."""

    # ── Database ──────────────────────────────────────────────────────────────
    db_path: str = "data/cardinal_multi.db"
    """Путь к файлу SQLite БД."""

    # ── Lolzteam (для другого AI-модуля) ─────────────────────────────────────
    lolzteam_token: Optional[str] = None
    """API-токен Lolzteam (заполняется другим модулем)."""

    # ── AI консультант (для другого AI-модуля) ───────────────────────────────
    openai_api_key: Optional[str] = None
    """OpenAI API ключ (заполняется другим модулем)."""

    # ── Уведомления ──────────────────────────────────────────────────────────
    balance_alert_threshold: float = 100.0
    """Порог баланса (ниже которого — уведомление BALANCE_LOW)."""

    # ─────────────────────────────────────────────────────────────────────────
    # Валидаторы
    # ─────────────────────────────────────────────────────────────────────────

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"LOG_LEVEL должен быть одним из: {allowed}")
        return upper

    @field_validator("max_accounts")
    @classmethod
    def validate_max_accounts(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError("MAX_ACCOUNTS должен быть от 1 до 5.")
        return v

    @field_validator("request_delay")
    @classmethod
    def validate_request_delay(cls, v: float) -> float:
        if v < 1.0:
            raise ValueError("REQUEST_DELAY не может быть меньше 1 секунды.")
        return v

    @model_validator(mode="after")
    def validate_telegram_consistency(self) -> "MultiSettings":
        """Если указан main_telegram_token — должен быть и chat_id."""
        if self.main_telegram_token and not self.main_telegram_chat_id:
            raise ValueError(
                "MAIN_TELEGRAM_CHAT_ID обязателен при наличии MAIN_TELEGRAM_TOKEN."
            )
        return self


# ─── Загрузчик Cardinal .cfg конфигов ─────────────────────────────────────────

class CardinalConfigReader:
    """
    Read-only доступ к .cfg конфигам Cardinal.

    Не модифицирует файлы Cardinal.
    Используется для чтения настроек (например, requestsDelay).

    Пример::

        reader = CardinalConfigReader()
        delay = reader.get("main", "Other", "requestsDelay", fallback="6")
    """

    def __init__(self) -> None:
        self._configs: dict[str, configparser.ConfigParser] = {}
        self._load_all()

    def _load_all(self) -> None:
        """Загружает все доступные Cardinal .cfg файлы."""
        for name, path in CARDINAL_CONFIGS.items():
            if path.exists():
                parser = configparser.ConfigParser()
                parser.read(str(path), encoding="utf-8")
                self._configs[name] = parser
                logger.debug("Cardinal cfg загружен: {} ({})", name, path)
            else:
                logger.debug("Cardinal cfg не найден (пропуск): {}", path)

    def get(
        self,
        config_name: str,
        section: str,
        key: str,
        fallback: str | None = None,
    ) -> str | None:
        """
        Возвращает значение из Cardinal .cfg конфига.

        :param config_name: имя конфига ("main", "auto_response", "auto_delivery").
        :param section: секция конфига.
        :param key: ключ в секции.
        :param fallback: значение по умолчанию если не найдено.
        :return: строковое значение или fallback.
        """
        cfg = self._configs.get(config_name)
        if cfg is None:
            return fallback
        return cfg.get(section, key, fallback=fallback)

    def getboolean(
        self,
        config_name: str,
        section: str,
        key: str,
        fallback: bool = False,
    ) -> bool:
        """
        Возвращает булево значение из Cardinal .cfg конфига.

        :param config_name: имя конфига.
        :param section: секция конфига.
        :param key: ключ в секции.
        :param fallback: значение по умолчанию.
        :return: bool значение.
        """
        cfg = self._configs.get(config_name)
        if cfg is None:
            return fallback
        return cfg.getboolean(section, key, fallback=fallback)

    def has_config(self, config_name: str) -> bool:
        """Проверяет, загружен ли конфиг с таким именем."""
        return config_name in self._configs

    def reload(self) -> None:
        """Перезагружает все конфиги с диска."""
        self._configs.clear()
        self._load_all()
        logger.debug("Cardinal cfg конфиги перезагружены.")


# ─── Глобальный доступ ────────────────────────────────────────────────────────

_settings: MultiSettings | None = None
_cardinal_cfg: CardinalConfigReader | None = None


def get_settings() -> MultiSettings:
    """
    Возвращает глобальный экземпляр настроек.
    Загружает из .env при первом вызове.

    :return: MultiSettings instance.
    :raises SystemExit: если .env не найден или настройки невалидны.
    """
    global _settings
    if _settings is None:
        try:
            _settings = MultiSettings()
            logger.debug("Настройки Cardinal_Multi загружены из .env")
        except Exception as exc:
            logger.error("Ошибка загрузки настроек: {}", exc)
            raise SystemExit(
                f"❌ Ошибка конфигурации: {exc}\n"
                f"   Проверь файл .env (шаблон: .env.example)"
            ) from exc
    return _settings


def get_cardinal_cfg() -> CardinalConfigReader:
    """
    Возвращает глобальный reader Cardinal .cfg конфигов.

    :return: CardinalConfigReader instance.
    """
    global _cardinal_cfg
    if _cardinal_cfg is None:
        _cardinal_cfg = CardinalConfigReader()
    return _cardinal_cfg


def reload_settings() -> MultiSettings:
    """
    Принудительно перезагружает настройки из .env.
    Использовать после изменения .env файла.

    :return: новый MultiSettings instance.
    """
    global _settings
    _settings = None
    return get_settings()