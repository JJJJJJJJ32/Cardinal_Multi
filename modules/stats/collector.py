"""
modules/stats/collector.py
Сбор и агрегация статистики заказов.
Подписывается на ORDER_COMPLETED и ITEM_PURCHASED.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import func, select

from modules.core.database import get_session
from modules.core.events import EventBus, EventType
from modules.stats.models.stats_daily import StatsDaily
from modules.stats.models.balance_history import BalanceHistory, BalanceSource


class StatsCollector:
    """
    Обрабатывает входящие события и записывает/обновляет агрегаты в stats_daily.
    """

    def __init__(self) -> None:
        self._log = logger.bind(module="StatsCollector")

    def setup(self) -> None:
        """Подписаться на события EventBus."""
        bus = EventBus()
        bus.subscribe(EventType.ORDER_COMPLETED, self._on_order_completed)
        bus.subscribe(EventType.ITEM_PURCHASED, self._on_item_purchased)
        bus.subscribe(EventType.ITEM_DELIVERED, self._on_item_delivered)
        self._log.info("StatsCollector подписан на события.")

    def teardown(self) -> None:
        bus = EventBus()
        bus.unsubscribe(EventType.ORDER_COMPLETED, self._on_order_completed)
        bus.unsubscribe(EventType.ITEM_PURCHASED, self._on_item_purchased)
        bus.unsubscribe(EventType.ITEM_DELIVERED, self._on_item_delivered)

    # ──────────────────────────────────────────────
    # Обработчики событий
    # ──────────────────────────────────────────────

    async def _on_order_completed(self, data: Dict[str, Any]) -> None:
        """
        ORDER_COMPLETED → обновить orders_count и revenue.
        data: {account_id, order_id, order_short, runner_tag}
        """
        account_id: int = data.get("account_id")
        if not account_id:
            return

        # Сумма заказа — достаём из order_short (объект FunPayAPI)
        order_short = data.get("order_short")
        amount: float = 0.0
        if order_short:
            try:
                # В объектах FunPay обычно есть .price или .sum
                amount = float(getattr(order_short, "price", 0) or
                               getattr(order_short, "sum", 0) or 0)
            except Exception:
                amount = 0.0

        today = date.today()
        async with get_session() as session:
            row = await self._get_or_create(session, account_id, today)
            row.orders_count += 1
            row.revenue += amount
            row.profit = row.revenue - row.lolz_expenses
            await session.commit()

        self._log.debug(
            f"ORDER_COMPLETED: account={account_id}, amount={amount:.2f}"
        )

    async def _on_item_purchased(self, data: Dict[str, Any]) -> None:
        """
        ITEM_PURCHASED → записать расход Lolzteam.
        data ожидается: {account_id, price, ...}
        """
        account_id: int = data.get("account_id")
        price: float = float(data.get("price", 0) or 0)
        if not account_id:
            return

        today = date.today()
        async with get_session() as session:
            row = await self._get_or_create(session, account_id, today)
            row.lolz_expenses += price
            row.profit = row.revenue - row.lolz_expenses
            await session.commit()

        # Также записать в balance_history как расход
        async with get_session() as session:
            record = BalanceHistory(
                account_id=account_id,
                source=BalanceSource.LOLZTEAM,
                amount=-price,  # отрицательный — расход
                recorded_at=datetime.utcnow(),
            )
            session.add(record)
            await session.commit()

        self._log.debug(
            f"ITEM_PURCHASED: account={account_id}, expense={price:.2f}"
        )

    async def _on_item_delivered(self, data: Dict[str, Any]) -> None:
        """
        ITEM_DELIVERED → пересчитать среднее время выдачи.
        data ожидается: {account_id, order_id, purchased_at}
        """
        account_id: int = data.get("account_id")
        purchased_at_raw = data.get("purchased_at")
        if not account_id or not purchased_at_raw:
            return

        try:
            if isinstance(purchased_at_raw, str):
                purchased_at = datetime.fromisoformat(purchased_at_raw)
            elif isinstance(purchased_at_raw, datetime):
                purchased_at = purchased_at_raw
            else:
                return
        except ValueError:
            return

        delivery_seconds = (datetime.utcnow() - purchased_at).total_seconds()
        today = date.today()

        async with get_session() as session:
            row = await self._get_or_create(session, account_id, today)
            # Скользящее среднее
            if row.avg_delivery_time is None:
                row.avg_delivery_time = delivery_seconds
            else:
                row.avg_delivery_time = (row.avg_delivery_time + delivery_seconds) / 2
            await session.commit()

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────

    @staticmethod
    async def _get_or_create(
        session, account_id: int, day: date
    ) -> StatsDaily:
        """Получить или создать запись StatsDaily для (account_id, date)."""
        result = await session.execute(
            select(StatsDaily).where(
                StatsDaily.account_id == account_id,
                StatsDaily.date == day,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = StatsDaily(account_id=account_id, date=day)
            session.add(row)
            await session.flush()
        return row

    # ──────────────────────────────────────────────
    # Запросы для построения отчётов
    # ──────────────────────────────────────────────

    async def get_stats(
        self,
        account_id: Optional[int],
        period_days: Optional[int],
    ) -> Dict[str, Any]:
        """
        Вернуть агрегированную статистику.

        Args:
            account_id: конкретный аккаунт или None (все аккаунты).
            period_days: кол-во дней (1/7/30) или None (всё время).
        """
        async with get_session() as session:
            query = select(StatsDaily)

            if account_id is not None:
                query = query.where(StatsDaily.account_id == account_id)

            if period_days is not None:
                since = date.today() - timedelta(days=period_days - 1)
                query = query.where(StatsDaily.date >= since)

            result = await session.execute(query)
            rows: List[StatsDaily] = result.scalars().all()

        if not rows:
            return {
                "orders_count": 0,
                "revenue": 0.0,
                "lolz_expenses": 0.0,
                "profit": 0.0,
                "avg_delivery_time": None,
            }

        return {
            "orders_count": sum(r.orders_count for r in rows),
            "revenue": sum(r.revenue for r in rows),
            "lolz_expenses": sum(r.lolz_expenses for r in rows),
            "profit": sum(r.profit for r in rows),
            "avg_delivery_time": (
                sum(r.avg_delivery_time for r in rows if r.avg_delivery_time)
                / max(1, sum(1 for r in rows if r.avg_delivery_time))
            )
            if any(r.avg_delivery_time for r in rows)
            else None,
        }

    async def cleanup_old_data(self, days: int = 90) -> int:
        """Удалить данные старше N дней. Возвращает кол-во удалённых рядов."""
        cutoff = date.today() - timedelta(days=days)
        async with get_session() as session:
            result = await session.execute(
                select(StatsDaily).where(StatsDaily.date < cutoff)
            )
            rows = result.scalars().all()
            count = len(rows)
            for row in rows:
                await session.delete(row)
            await session.commit()
        return count