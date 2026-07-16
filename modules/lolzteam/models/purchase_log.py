"""
Лог каждой попытки покупки на Lolzteam Market.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from modules.core.database import Base


class PurchaseLog(Base):
    """
    Запись о попытке покупки товара на Lolzteam.

    provider_mode — "api" или "playwright".
    """

    __tablename__ = "purchase_log"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    order_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lolzteam_item_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    filters_used: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    found_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    rejected_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    purchase_price: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    status: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    provider_mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default="api"
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )