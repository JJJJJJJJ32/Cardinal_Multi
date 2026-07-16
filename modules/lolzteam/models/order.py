"""
Модель заказа для Lolzteam автозакупки.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum as PyEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Float,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from modules.core.database import Base
from modules.core.encryption import Encryption


class OrderStatus(str, PyEnum):
    """Статус заказа в Lolzteam модуле."""

    NEW = "новый"
    SEARCHING = "в_поиске"
    FOUND = "найден"
    PURCHASED = "куплен"
    DELIVERED = "выдан"
    WAITING = "ожидает"
    PROBLEM = "проблема"
    REFUND = "возврат"
    COMPLETED = "завершён"
    CANCELLED = "отменён"


class Order(Base):
    """
    Заказ FunPay, для которого ведётся закупка на Lolzteam.

    funpay_order_id — уникальный ID заказа из FunPay.
    account_id      — FK на accounts.id (Модуль 1).
    lot_id          — FK на account_lots.id (Модуль 1).
    item_data       — зашифрованный login:password (или другой формат).
    """

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    funpay_order_id: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, index=True
    )
    account_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    lot_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("account_lots.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    buyer_username: Mapped[str | None] = mapped_column(
        String(256), nullable=True
    )
    buyer_chat_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    status: Mapped[str] = mapped_column(
        Enum(OrderStatus),
        nullable=False,
        default=OrderStatus.NEW,
        index=True,
    )
    funpay_amount: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    lolzteam_amount: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    lolzteam_item_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    _item_data_encrypted: Mapped[str | None] = mapped_column(
        "item_data_encrypted", Text, nullable=True
    )

    search_attempts_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    is_cancelled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    # ── Шифрованные поля ─────────────────────────────────────────

    def get_item_data(self) -> str | None:
        """Вернуть расшифрованные данные товара."""
        if self._item_data_encrypted is None:
            return None
        return Encryption().decrypt(self._item_data_encrypted)

    def set_item_data(self, value: str | None) -> None:
        """Зашифровать и сохранить данные товара."""
        if value is None:
            self._item_data_encrypted = None
        else:
            self._item_data_encrypted = Encryption().encrypt(value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "funpay_order_id": self.funpay_order_id,
            "account_id": self.account_id,
            "lot_id": self.lot_id,
            "buyer_username": self.buyer_username,
            "buyer_chat_id": self.buyer_chat_id,
            "status": self.status,
            "funpay_amount": self.funpay_amount,
            "lolzteam_amount": self.lolzteam_amount,
            "lolzteam_item_id": self.lolzteam_item_id,
            "search_attempts_count": self.search_attempts_count,
            "is_cancelled": self.is_cancelled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }