"""
Настройки Lolzteam для конкретного лота FunPay.
Связан с account_lots.id из Модуля 1.
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
    JSON,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modules.core.database import Base


class DeliveryMode(str, PyEnum):
    """Режим выдачи товара."""

    AUTO = "auto"
    CONFIRM = "confirm"


class LotLolzteamSettings(Base):
    """
    Настройки автозакупки Lolzteam для лота.

    lot_id связан с account_lots.id (Модуль 1).
    common_filters  — общие фильтры (цена, рейтинг, etc.).
    specific_filters — специфичные фильтры категории.
    """

    __tablename__ = "lot_lolzteam_settings"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    lot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("account_lots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    lolzteam_category: Mapped[str] = mapped_column(
        String(128), nullable=False
    )
    common_filters: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    specific_filters: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    delivery_mode: Mapped[str] = mapped_column(
        Enum(DeliveryMode),
        nullable=False,
        default=DeliveryMode.AUTO,
    )
    max_search_hours: Mapped[int] = mapped_column(
        Integer, nullable=False, default=2
    )
    delay_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "lot_id": self.lot_id,
            "is_enabled": self.is_enabled,
            "lolzteam_category": self.lolzteam_category,
            "common_filters": self.common_filters,
            "specific_filters": self.specific_filters,
            "delivery_mode": self.delivery_mode,
            "max_search_hours": self.max_search_hours,
            "delay_minutes": self.delay_minutes,
        }