"""
Запись об одной итерации поиска в search_loop.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from modules.core.database import Base


class SearchAttempt(Base):
    """
    Одна итерация поиска товара на Lolzteam.

    attempt_number — порядковый номер попытки (1, 2, 3 ...).
    best_price     — лучшая найденная цена (если найдено).
    best_item_id   — item_id лучшего товара (если найдено).
    status         — "found" / "not_found" / "error".
    """

    __tablename__ = "search_attempts"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    order_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
    )
    found_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    best_price: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    best_item_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(64), nullable=False, default="not_found"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )