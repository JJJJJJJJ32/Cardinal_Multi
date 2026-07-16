"""
modules/balance/models/balance_alert.py
Настройки порогов уведомлений о низком балансе.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from modules.core.database import Base


class AlertSource(str, enum.Enum):
    FUNPAY = "funpay"
    LOLZTEAM = "lolzteam"


class BalanceAlert(Base):
    """
    Конфигурация порога баланса для одного аккаунта и одного источника.
    Уведомлять не чаще 1 раза в час (anti-spam через last_notified_at).
    """

    __tablename__ = "balance_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    account_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    source: Mapped[AlertSource] = mapped_column(Enum(AlertSource), nullable=False)

    # Порог ниже которого слать уведомление
    threshold_amount: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)

    # Когда последний раз уведомляли (для anti-spam)
    last_notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)