"""
modules/balance/models/delayed_delivery.py
Очередь отложенных выдач товаров.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from modules.core.database import Base


class DeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class DelayedDelivery(Base):
    """
    Запись об отложенной выдаче товара.
    Создаётся при ITEM_PURCHASED, если delivery_delay_minutes > 0.
    APScheduler каждую минуту проверяет deliver_at <= now().
    """

    __tablename__ = "delayed_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ID заказа FunPay (строкой, т.к. может иметь любой формат)
    order_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # ID аккаунта для которого выдавать
    account_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Когда выдать товар
    deliver_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    status: Mapped[DeliveryStatus] = mapped_column(
        Enum(DeliveryStatus),
        nullable=False,
        default=DeliveryStatus.PENDING,
    )

    # Сырые данные события ITEM_PURCHASED для передачи при выдаче
    payload: Mapped[str] = mapped_column(String(4096), nullable=True)