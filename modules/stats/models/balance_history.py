"""
modules/stats/models/balance_history.py
История снятий баланса (FunPay и Lolzteam).
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from modules.core.database import Base


class BalanceSource(str, enum.Enum):
    FUNPAY = "funpay"
    LOLZTEAM = "lolzteam"


class BalanceHistory(Base):
    """
    Снапшот баланса в момент проверки.
    Позволяет строить графики и считать расходы по периодам.
    """

    __tablename__ = "balance_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    account_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    source: Mapped[BalanceSource] = mapped_column(
        Enum(BalanceSource), nullable=False
    )

    amount: Mapped[float] = mapped_column(Float, nullable=False)

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )