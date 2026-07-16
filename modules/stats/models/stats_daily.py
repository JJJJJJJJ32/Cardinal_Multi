"""
modules/stats/models/stats_daily.py
Агрегированная дневная статистика по аккаунту.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import Date, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modules.core.database import Base


class StatsDaily(Base):
    """
    Агрегированная статистика за один день для одного аккаунта FunPay.
    Уникальность: (account_id, date) — один ряд на аккаунт в день.
    """

    __tablename__ = "stats_daily"
    __table_args__ = (
        UniqueConstraint("account_id", "date", name="uq_stats_account_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    account_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Количество завершённых заказов FunPay за день
    orders_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Выручка с FunPay (сумма заказов в рублях)
    revenue: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Расходы на Lolzteam (покупки аккаунтов) за день
    lolz_expenses: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Прибыль = revenue - lolz_expenses (денормализовано для быстрых запросов)
    profit: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Среднее время от ITEM_PURCHASED до ITEM_DELIVERED (в секундах)
    avg_delivery_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # relationship (lazy load — не нужен для агрегации)
    # account = relationship("Account", back_populates="stats_daily")