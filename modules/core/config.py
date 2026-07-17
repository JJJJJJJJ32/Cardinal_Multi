"""
modules/core/config.py

Единая точка конфигурации Cardinal_Multi.

Загружает настройки из .env через pydantic-settings.
Дополнительно предоставляет read-only доступ к .cfg-файлам Cardinal.

Правила:
- Используй get_settings() везде в коде — не создавай MultiSettings() напрямую.
- Не импортируй этот модуль в __init__.py пакетов — избегай циклических импортов.
"""

from __future__ import annotations

import configparser
from pathlib import Path
from typing import Optional

from loguru import logger
from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ─── Пути к Cardinal .cfg ────────────────────────────────────────────────────
CARDINAL_CONFIGS: dict[str, Path] = {
    "main":          Path("configs/_main.cfg"),
    "auto_response": Path("configs/auto_response.cfg"),
    "auto_delivery": Path("configs/auto_delivery.cfg"),
}


# ─── Главный класс настроек ──────────────────────────────────────────────────
class MultiSettings(BaseSettings):
    """
    Настройки Cardinal_Multi, загружаемые из .env.

    Поддерживает backward-compatibility по именам ключей:
    - LOLZ_API_TOKEN и LOLZTEAM_TOKEN — оба рабочих.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Логирование ───────────────────────────────────────────────────────────
    log_level: str = Field(
        default="INFO",
        description=(
            "Уровень логирования. "
            "Допустимые значения: DEBUG, INFO, WARNING, ERROR, CRITICAL. "
            "DEBUG содержит чувствительные данные — НЕ используй в продакшене."
        ),
    )

    # ── Мультиаккаунты ────────────────────────────────────────────────────────
    max_accounts: int = Field(
        default=5,
        validation_alias=AliasChoices("MAX_ACCOUNTS"),
        description="Макс. количество аккаунтов FunPay (1..5, лимит AccountManager).",
    )
    request_delay: float = Field(
        default=1.0,
        validation_alias=AliasChoices("REQUEST_DELAY"),
        description="Задержка между запросами к FunPay API (секунды).",
    )

    # ── Telegram ──────────────────────────────────────────────────────────────
    main_telegram_token: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("MAIN_TELEGRAM_TOKEN"),
        description="Токен главного Telegram-бота управления.",
    )
    # ВАЖНО: chat_id — int, не str.
    # В .env пишется как число: MAIN_TELEGRAM_CHAT_ID=123456789
    main_telegram_chat_id: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("MAIN_TELEGRAM_CHAT_ID"),
        description="Chat ID владельца для уведомлений от всех модулей.",
    )

    # ── Мониторинг баланса ────────────────────────────────────────────────────
    balance_alert_threshold: float = Field(
        default=100.0,
        validation_alias=AliasChoices("BALANCE_ALERT_THRESHOLD"),
        description="Порог баланса FunPay для уведомления (рубли, >= 0).",
    )

    # ── AI (опционально) ──────────────────────────────────────────────────────
    openai_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY"),
    )

    # ── Lolzteam ──────────────────────────────────────────────────────────────
    # Основной ключ: LOLZ_API_TOKEN (соответствует .env.example)
    # Back-compat:   LOLZTEAM_TOKEN (старые установки)
    lolz_api_token: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("LOLZ_API_TOKEN", "LOLZTEAM_TOKEN"),
        description="Bearer-токен Lolzteam Market API.",
    )
    lolz_login: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("LOLZ_LOGIN"),
        description="Логин lzt.market (Playwright режим).",
    )
    lolz_password: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("LOLZ_PASSWORD"),
        description="Пароль lzt.market (Playwright режим).",
    )
    lolz_client_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("LOLZ_CLIENT_ID"),
    )
    lolz_client_secret: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("LOLZ_CLIENT_SECRET"),
    )
    lolz_secret_phrase: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("LOLZ_SECRET_PHRASE"),
    )

    # ── Свойства обратной совместимости ───────────────────────────────────────
    @property
    def lolzteam_token(self) -> Optional[str]:
        """Алиас: старый код может обращаться к settings.lolzteam_token."""
        return self.lolz_api_token

    @property
    def has_lolz(self) -> bool:
        """True если задан хотя бы один способ авторизации в Lolzteam."""
        return bool(self.lolz_api_token or (self.lolz_login and self.lolz_password))

    @property
    def lolz_mode(self) -> str:
        """Определяет режим Lolzteam: 'api' | 'playwright' | 'none'."""
        if self.lolz_api_token:
            return "api"
        if self.lolz_login and self.lolz_password:
            return "playwright"
        return "none"

    # ── Валидаторы ────────────────────────────────────────────────────────────
    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.strip().upper()
        if upper not in allowed:
            raise ValueError(
                f"LOG_LEVEL='{v}' недопустим. "
                f"Допустимые значения: {', '.join(sorted(allowed))}"
            )
        return upper

    @field_validator("max_accounts")
    @classmethod
    def _validate_max_accounts(cls, v: int) -> int:
        # Синхронизировано с AccountManager.MAX_ACCOUNTS = 5
        if not 1 <= v <= 5:
            raise ValueError(
                f"MAX_ACCOUNTS={v} выходит за пределы 1..5. "
                f"AccountManager поддерживает максимум 5 аккаунтов."
            )
        return v

    @field_validator("request_delay")
    @classmethod
    def _validate_request_delay(cls, v: float) -> float:
        if v < 0.0:
            raise ValueError(
                f"REQUEST_DELAY={v} не может быть отрицательным."
            )
        return v

    @field_validator("balance_alert_threshold")
    @classmethod
    def _validate_balance_threshold(cls, v: float) -> float:
        if v < 0.0:
            raise ValueError(
                f"BALANCE_ALERT_THRESHOLD={v} не может быть отрицательным."
            )
        return v

    @model_validator(mode="after")
    def _validate_telegram_pair(self) -> "MultiSettings":
        """
        Предупреждаем (не падаем!) если задан только токен без chat_id.
        Падать здесь слишком строго — пользователь мог не дочитать .env.
        """
        if self.main_telegram_token and not self.main_telegram_chat_id:
            logger.warning(
                "MAIN_TELEGRAM_TOKEN задан, но MAIN_TELEGRAM_CHAT_ID пустой. "
                "Уведомления Telegram работать не будут."
            )
        return self


# ─── CardinalConfigReader ────────────────────────────────────────────────────
class CardinalConfigReader:
    """
    Read-only доступ к .cfg файлам Cardinal (INI-формат).

    Пример:
        reader = CardinalConfigReader()
        delay = reader.get("main", "Other", "requestsDelay", fallback="6")
        auto_response_on = reader.getboolean("auto_response", "Settings", "Enabled", fallback=False)
    """

    def __init__(self) -> None:
        self._configs: dict[str, configparser.ConfigParser] = {}
        self._load_all()

    def _load_all(self) -> None:
        for name, path in CARDINAL_CONFIGS.items():
            if not path.exists():
                logger.debug("Cardinal cfg не найден (пропуск): {}", path)
                continue
            parser = configparser.ConfigParser()
            try:
                parser.read(str(path), encoding="utf-8")
                self._configs[name] = parser
                logger.debug("Cardinal cfg загружен: {} → {}", name, path)
            except configparser.Error as exc:
                logger.error("Ошибка чтения Cardinal cfg '{}': {}", path, exc)

    def get(
        self,
        config_name: str,
        section: str,
        key: str,
        fallback: str | None = None,
    ) -> str | None:
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
        cfg = self._configs.get(config_name)
        if cfg is None:
            return fallback
        return cfg.getboolean(section, key, fallback=fallback)

    def getint(
        self,
        config_name: str,
        section: str,
        key: str,
        fallback: int = 0,
    ) -> int:
        cfg = self._configs.get(config_name)
        if cfg is None:
            return fallback
        return cfg.getint(section, key, fallback=fallback)

    def has_config(self, config_name: str) -> bool:
        return config_name in self._configs

    def reload(self) -> None:
        self._configs.clear()
        self._load_all()
        logger.info("Cardinal cfg конфиги перезагружены.")


# ─── Синглтоны ───────────────────────────────────────────────────────────────
_settings: MultiSettings | None = None
_cardinal_cfg: CardinalConfigReader | None = None


def get_settings() -> MultiSettings:
    """
    Возвращает глобальный экземпляр настроек Cardinal_Multi.

    При первом вызове читает .env.
    При ошибке конфигурации — завершает процесс с понятным сообщением.
    """
    global _settings
    if _settings is None:
        try:
            _settings = MultiSettings()
            logger.debug(
                "Настройки загружены: log_level={}, max_accounts={}, lolz_mode={}",
                _settings.log_level,
                _settings.max_accounts,
                _settings.lolz_mode,
            )
        except Exception as exc:
            logger.critical("Критическая ошибка конфигурации: {}", exc)
            raise SystemExit(
                f"\n❌ Ошибка конфигурации:\n{exc}\n\n"
                f"Проверь файл .env (шаблон: .env.example)\n"
            ) from exc
    return _settings


def get_cardinal_cfg() -> CardinalConfigReader:
    """Возвращает глобальный читатель Cardinal .cfg файлов."""
    global _cardinal_cfg
    if _cardinal_cfg is None:
        _cardinal_cfg = CardinalConfigReader()
    return _cardinal_cfg


def reload_settings() -> MultiSettings:
    """Сбрасывает кэш и перечитывает .env. Полезно в тестах."""
    global _settings
    _settings = None
    return get_settings()