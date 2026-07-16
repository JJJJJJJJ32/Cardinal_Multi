"""
modules/multi/models/account.py
────────────────────────────────
ORM-модель таблицы accounts.

Хранит данные аккаунтов FunPay.
Секретные поля (golden_key, telegram_bot_token) — Fernet-зашифрованы.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modules.core.database import Base


class Account(Base):
    """
    Таблица accounts — один аккаунт FunPay.

    .. note::
        golden_key и telegram_bot_token хранятся в зашифрованном виде.
        Для шифрования/дешифровки используй modules.core.encryption.Encryption.

    Атрибуты:
        id:                   PK, автоинкремент.
        name:                 Отображаемое имя аккаунта (напр. "@username").
        golden_key_encrypted: Зашифрованный golden_key FunPay.
        telegram_token_encrypted: Зашифрованный токен Telegram-бота (опционально).
        owner_chat_id:        Telegram chat_id владельца аккаунта.
        is_primary:           Является ли аккаунт основным (только один может быть True).
        is_active:            Включён ли аккаунт.
        settings:             JSON с дополнительными настройками аккаунта.
        lots:                 Связанные лоты (relationship).
        created_at:           Время создания (из Base).
        updated_at:           Время последнего обновления (из Base).
    """

    __tablename__ = "accounts"

    # ── Первичный ключ ────────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Первичный ключ аккаунта",
    )

    # ── Идентификация ─────────────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default="Аккаунт",
        comment="Отображаемое имя аккаунта (напр. @username)",
    )

    funpay_username: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="Имя пользователя FunPay (заполняется после проверки golden_key)",
    )

    funpay_user_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="ID пользователя на FunPay",
    )

    # ── Секреты (зашифрованы через Fernet) ───────────────────────────────────
    golden_key_encrypted: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Зашифрованный golden_key FunPay (Fernet)",
    )

    telegram_token_encrypted: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Зашифрованный токен Telegram-бота (Fernet). None = использует главный бот.",
    )

    # ── Telegram ──────────────────────────────────────────────────────────────
    owner_chat_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="Telegram chat_id владельца аккаунта",
    )

    # ── Флаги ─────────────────────────────────────────────────────────────────
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Основной аккаунт (с ним работают плагины Cardinal)",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Аккаунт активен (False = не запускать)",
    )

    # ── JSON-настройки ────────────────────────────────────────────────────────
    settings: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        default=dict,
        comment="JSON с дополнительными настройками аккаунта",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    lots: Mapped[list["AccountLot"]] = relationship(  # type: ignore[name-defined]
        "AccountLot",
        back_populates="account",
        cascade="all, delete-orphan",
        lazy="select",
    )

    events: Mapped[list["EventLog"]] = relationship(  # type: ignore[name-defined]
        "EventLog",
        back_populates="account",
        cascade="all, delete-orphan",
        lazy="select",
    )

    # ──────────────────────────────────────────────────────────────────────────
    # Вспомогательные методы
    # ──────────────────────────────────────────────────────────────────────────

    def get_golden_key(self) -> str:
        """
        Расшифровывает и возвращает golden_key.

        :return: открытый golden_key.
        :raises EncryptionError: если расшифровка не удалась.
        """
        from modules.core.encryption import Encryption
        return Encryption().decrypt(self.golden_key_encrypted)

    def set_golden_key(self, golden_key: str) -> None:
        """
        Шифрует и сохраняет golden_key.

        :param golden_key: открытый golden_key FunPay.
        """
        from modules.core.encryption import Encryption
        self.golden_key_encrypted = Encryption().encrypt(golden_key)

    def get_telegram_token(self) -> str | None:
        """
        Расшифровывает и возвращает токен Telegram-бота.

        :return: открытый токен или None если не задан.
        """
        if not self.telegram_token_encrypted:
            return None
        from modules.core.encryption import Encryption
        return Encryption().decrypt(self.telegram_token_encrypted)

    def set_telegram_token(self, token: str | None) -> None:
        """
        Шифрует и сохраняет токен Telegram-бота.

        :param token: открытый токен или None для удаления.
        """
        if token is None:
            self.telegram_token_encrypted = None
            return
        from modules.core.encryption import Encryption
        self.telegram_token_encrypted = Encryption().encrypt(token)

    def to_display_dict(self) -> dict[str, Any]:
        """
        Возвращает словарь для отображения в UI (без секретов).

        :return: dict с безопасными полями аккаунта.
        """
        return {
            "id":              self.id,
            "name":            self.name,
            "funpay_username": self.funpay_username,
            "funpay_user_id":  self.funpay_user_id,
            "owner_chat_id":   self.owner_chat_id,
            "is_primary":      self.is_primary,
            "is_active":       self.is_active,
            "settings":        self.settings or {},
            "created_at":      str(self.created_at),
            "updated_at":      str(self.updated_at),
        }

    def __repr__(self) -> str:
        return (
            f"<Account id={self.id} name={self.name!r} "
            f"primary={self.is_primary} active={self.is_active}>"
        )