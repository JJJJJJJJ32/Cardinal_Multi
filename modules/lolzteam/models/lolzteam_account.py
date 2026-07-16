"""
Модель аккаунта Lolzteam.
Хранит API-токен, Playwright-credentials и cookies.
Все чувствительные поля шифруются через Encryption.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from modules.core.database import Base
from modules.core.encryption import Encryption


class LolzteamAccount(Base):
    """
    Аккаунт Lolzteam Market.

    mode="api"        — работа через API токен (основной режим).
    mode="playwright" — работа через браузер (fallback).
    """

    __tablename__ = "lolzteam_accounts"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default="api"
    )

    # ── API поля (шифруются) ──────────────────────────────────────
    _api_token_encrypted: Mapped[str | None] = mapped_column(
        "api_token_encrypted", Text, nullable=True
    )
    _client_id_encrypted: Mapped[str | None] = mapped_column(
        "client_id_encrypted", Text, nullable=True
    )
    _client_secret_encrypted: Mapped[str | None] = mapped_column(
        "client_secret_encrypted", Text, nullable=True
    )
    _secret_phrase_encrypted: Mapped[str | None] = mapped_column(
        "secret_phrase_encrypted", Text, nullable=True
    )

    # ── Playwright поля ───────────────────────────────────────────
    login: Mapped[str | None] = mapped_column(
        String(256), nullable=True
    )
    _password_encrypted: Mapped[str | None] = mapped_column(
        "password_encrypted", Text, nullable=True
    )
    session_cookies: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON-строка с куками

    # ── Общие поля ────────────────────────────────────────────────
    balance: Mapped[float | None] = mapped_column(
        nullable=True, default=None
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # ── Шифрованные свойства ──────────────────────────────────────

    def get_api_token(self) -> str | None:
        """Вернуть расшифрованный API токен."""
        if self._api_token_encrypted is None:
            return None
        return Encryption().decrypt(self._api_token_encrypted)

    def set_api_token(self, token: str | None) -> None:
        """Зашифровать и сохранить API токен."""
        if token is None:
            self._api_token_encrypted = None
        else:
            self._api_token_encrypted = Encryption().encrypt(token)

    def get_client_id(self) -> str | None:
        """Вернуть расшифрованный client_id."""
        if self._client_id_encrypted is None:
            return None
        return Encryption().decrypt(self._client_id_encrypted)

    def set_client_id(self, value: str | None) -> None:
        if value is None:
            self._client_id_encrypted = None
        else:
            self._client_id_encrypted = Encryption().encrypt(value)

    def get_client_secret(self) -> str | None:
        """Вернуть расшифрованный client_secret."""
        if self._client_secret_encrypted is None:
            return None
        return Encryption().decrypt(self._client_secret_encrypted)

    def set_client_secret(self, value: str | None) -> None:
        if value is None:
            self._client_secret_encrypted = None
        else:
            self._client_secret_encrypted = Encryption().encrypt(value)

    def get_secret_phrase(self) -> str | None:
        """Вернуть расшифрованный secret_phrase."""
        if self._secret_phrase_encrypted is None:
            return None
        return Encryption().decrypt(self._secret_phrase_encrypted)

    def set_secret_phrase(self, value: str | None) -> None:
        if value is None:
            self._secret_phrase_encrypted = None
        else:
            self._secret_phrase_encrypted = Encryption().encrypt(value)

    def get_password(self) -> str | None:
        """Вернуть расшифрованный пароль (Playwright режим)."""
        if self._password_encrypted is None:
            return None
        return Encryption().decrypt(self._password_encrypted)

    def set_password(self, value: str | None) -> None:
        if value is None:
            self._password_encrypted = None
        else:
            self._password_encrypted = Encryption().encrypt(value)

    def to_dict(self) -> dict[str, Any]:
        """Безопасный дикт (без секретов)."""
        return {
            "id": self.id,
            "mode": self.mode,
            "login": self.login,
            "balance": self.balance,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }