"""
modules/emergency/models/emergency_pause.py
Журнал экстренных пауз.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from modules.core.database import Base


class EmergencyPause(Base):
    """
    Запись факта паузы в журнал.
    account_id = NULL означает глобальную паузу всех аккаунтов.
    """

    __tablename__ = "emergency_pause"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    account_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    is_global: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    paused_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    resumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)