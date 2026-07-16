"""
modules/updates/models/update_check.py
Кэш результата проверки обновлений GitHub.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from modules.core.database import Base


class UpdateCheck(Base):
    """
    Хранит результат последней проверки GitHub Releases.
    Содержит только одну запись (id=1) — обновляется на месте.
    """

    __tablename__ = "update_check"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    latest_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    current_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # changelog из GitHub release body
    changelog: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    release_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)