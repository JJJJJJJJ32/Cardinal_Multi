"""
modules/multi/models/account_lot.py
────────────────────────────────────
ORM-модели:
    - AccountLot: лот аккаунта FunPay
    - EventLog:   журнал событий (NEW_ORDER, NEW_MESSAGE и т.д.)
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modules.core.database import Base


class AccountLot(Base):
    """
    Таблица account_lots — лот конкретного аккаунта FunPay.

    Кэширует данные лотов для быстрого доступа и аналитики.
    Синхронизируется с FunPay при старте аккаунта.
    """

    __tablename__ = "account_lots"

    # ── Первичный ключ ────────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # ── Связь с аккаунтом ─────────────────────────────────────────────────────
    account_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID аккаунта-владельца лота",
    )

    # ── Данные лота ───────────────────────────────────────────────────────────
    funpay_lot_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="ID лота на FunPay",
    )

    title: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        default="",
        comment="Название лота",
    )

    price: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Цена лота (в валюте FunPay)",
    )

    category: Mapped[str | None] = mapped_column(
        String(256),
        nullable=True,
        comment="Категория лота",
    )

    # ── Флаги ─────────────────────────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Лот активен на FunPay",
    )

    # ── Дополнительные данные ─────────────────────────────────────────────────
    settings: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        default=dict,
        comment="JSON с дополнительными настройками лота",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    account: Mapped["Account"] = relationship(  # type: ignore[name-defined]
        "Account",
        back_populates="lots",
    )

    def __repr__(self) -> str:
        return (
            f"<AccountLot id={self.id} "
            f"account_id={self.account_id} "
            f"funpay_lot_id={self.funpay_lot_id!r} "
            f"active={self.is_active}>"
        )


class EventLog(Base):
    """
    Таблица events_log — журнал событий Cardinal_Multi.

    Хранит историю событий (заказы, сообщения, ошибки и т.д.)
    для аналитики и аудита.
    """

    __tablename__ = "events_log"

    # ── Первичный ключ ────────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # ── Связь с аккаунтом ─────────────────────────────────────────────────────
    account_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="ID аккаунта (NULL = системное событие)",
    )

    # ── Тип события ───────────────────────────────────────────────────────────
    event_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="Тип события из EventType enum",
    )

    # ── Данные события ────────────────────────────────────────────────────────
    data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="JSON с данными события",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    account: Mapped["Account | None"] = relationship(  # type: ignore[name-defined]
        "Account",
        back_populates="events",
    )

    def __repr__(self) -> str:
        return (
            f"<EventLog id={self.id} "
            f"account_id={self.account_id} "
            f"event_type={self.event_type!r}>"
        )