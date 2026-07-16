"""
modules/balance/monitor.py
Мониторинг балансов FunPay и Lolzteam каждые 30 минут.
Отложенная выдача: APScheduler job каждую минуту.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import aiohttp
from loguru import logger
from sqlalchemy import select

from modules.core.database import get_session
from modules.core.notifier import get_notifier
from modules.balance.models.balance_alert import BalanceAlert, AlertSource
from modules.balance.models.delayed_delivery import DelayedDelivery, DeliveryStatus
from modules.core.events import EventBus, EventType
from modules.stats.models.balance_history import BalanceHistory, BalanceSource
from modules.stats.formatter import format_balance_alert


# Антиспам: минимальный интервал уведомлений (секунды)
ALERT_COOLDOWN_SECONDS = 3600  # 1 час


class BalanceMonitor:
    """
    Мониторинг баланса FunPay и Lolzteam.
    Работает через APScheduler (внешний) — сам не создаёт scheduler.
    """

    def __init__(self, accounts_getter) -> None:
        """
        Args:
            accounts_getter: async callable() → List[Account]
                             Обычно AccountManager.get_active_accounts()
        """
        self._accounts_getter = accounts_getter
        self._log = logger.bind(module="BalanceMonitor")
        self._notifier = get_notifier()

    def setup_events(self) -> None:
        """Подписаться на ITEM_PURCHASED для отложенной выдачи."""
        EventBus().subscribe(EventType.ITEM_PURCHASED, self._on_item_purchased)

    def teardown_events(self) -> None:
        EventBus().unsubscribe(EventType.ITEM_PURCHASED, self._on_item_purchased)

    # ──────────────────────────────────────────────
    # Проверка баланса (APScheduler каждые 30 минут)
    # ──────────────────────────────────────────────

    async def check_balances(self) -> None:
        """Основная точка входа для APScheduler."""
        self._log.debug("Начало проверки балансов...")
        accounts = await self._accounts_getter()

        for account in accounts:
            try:
                await self._check_account_balance(account)
            except Exception as e:
                self._log.error(f"Ошибка проверки баланса аккаунта {account.id}: {e}")

    async def _check_account_balance(self, account) -> None:
        funpay_balance = await self._get_funpay_balance(account)
        lolz_balance = await self._get_lolz_balance(account)

        # Записываем историю баланса
        async with get_session() as session:
            now = datetime.utcnow()
            if funpay_balance is not None:
                session.add(BalanceHistory(
                    account_id=account.id,
                    source=BalanceSource.FUNPAY,
                    amount=funpay_balance,
                    recorded_at=now,
                ))
            if lolz_balance is not None:
                session.add(BalanceHistory(
                    account_id=account.id,
                    source=BalanceSource.LOLZTEAM,
                    amount=lolz_balance,
                    recorded_at=now,
                ))
            await session.commit()

        # Проверяем пороги
        await self._check_threshold(
            account=account,
            source=AlertSource.FUNPAY,
            current=funpay_balance,
            label="FunPay",
        )
        await self._check_threshold(
            account=account,
            source=AlertSource.LOLZTEAM,
            current=lolz_balance,
            label="Lolzteam",
        )

    async def _check_threshold(
        self,
        account,
        source: AlertSource,
        current: Optional[float],
        label: str,
    ) -> None:
        if current is None:
            return

        async with get_session() as session:
            result = await session.execute(
                select(BalanceAlert).where(
                    BalanceAlert.account_id == account.id,
                    BalanceAlert.source == source,
                    BalanceAlert.is_enabled == True,
                )
            )
            alert = result.scalar_one_or_none()

        if alert is None:
            return

        if current >= alert.threshold_amount:
            return  # Всё нормально

        # Антиспам: проверить когда последний раз уведомляли
        now = datetime.utcnow()
        if alert.last_notified_at is not None:
            elapsed = (now - alert.last_notified_at).total_seconds()
            if elapsed < ALERT_COOLDOWN_SECONDS:
                self._log.debug(
                    f"[{account.name}] {label} баланс низкий, "
                    f"но уведомление было {int(elapsed)} сек назад — пропуск."
                )
                return

        # Отправить уведомление
        funpay_b = current if source == AlertSource.FUNPAY else None
        lolz_b = current if source == AlertSource.LOLZTEAM else None
        funpay_t = alert.threshold_amount if source == AlertSource.FUNPAY else None
        lolz_t = alert.threshold_amount if source == AlertSource.LOLZTEAM else None

        text = format_balance_alert(
            account_name=account.name or f"#{account.id}",
            funpay_balance=funpay_b,
            funpay_threshold=funpay_t,
            lolz_balance=lolz_b,
            lolz_threshold=lolz_t,
        )

        telegram_token = account.get_telegram_token() if hasattr(account, "get_telegram_token") else None
        await self._notifier.send(
            text=text,
            chat_id=str(account.owner_chat_id) if account.owner_chat_id else None,
            token=telegram_token,
        )

        # Обновить last_notified_at
        async with get_session() as session:
            result = await session.execute(
                select(BalanceAlert).where(BalanceAlert.id == alert.id)
            )
            alert_row = result.scalar_one_or_none()
            if alert_row:
                alert_row.last_notified_at = now
                await session.commit()

        self._log.warning(
            f"[{account.name}] НИЗКИЙ БАЛАНС {label}: "
            f"{current:.2f} < порог {alert.threshold_amount:.2f}"
        )

    async def _get_funpay_balance(self, account) -> Optional[float]:
        """
        Заглушка: реальный парсинг FunPay баланса.
        В проекте golden_key хранится зашифрованным в Account.
        Здесь нужна интеграция с FunPayAPI (модуль 1-4).
        """
        # TODO: интегрировать с FunPayAPI через cardinal_bridge
        # Пример: return await funpay_api.get_balance(account.get_golden_key())
        return None

    async def _get_lolz_balance(self, account) -> Optional[float]:
        """
        Запрос баланса Lolzteam: GET /balance.
        Токен берётся из Account.settings["lolz_token"].
        """
        settings = account.settings or {}
        lolz_token = settings.get("lolz_token")
        if not lolz_token:
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.lzt.market/balance",
                    headers={"Authorization": f"Bearer {lolz_token}"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return float(data.get("balance", {}).get("balance", 0))
        except Exception as e:
            self._log.error(f"Ошибка запроса баланса Lolzteam: {e}")
        return None

    # ──────────────────────────────────────────────
    # Отложенная выдача
    # ──────────────────────────────────────────────

    async def _on_item_purchased(self, data: Dict[str, Any]) -> None:
        """
        При ITEM_PURCHASED: если лот имеет delivery_delay_minutes > 0 — создать запись.
        """
        account_id = data.get("account_id")
        order_id = data.get("order_id")
        lot_settings = data.get("lot_settings", {})

        delay_minutes: int = int(lot_settings.get("delivery_delay_minutes", 0))

        if delay_minutes <= 0:
            # Выдать немедленно — просто эмитим событие обратно
            EventBus().emit(EventType.ITEM_DELIVERED, data)
            return

        deliver_at = datetime.utcnow() + timedelta(minutes=delay_minutes)

        async with get_session() as session:
            record = DelayedDelivery(
                order_id=str(order_id),
                account_id=account_id,
                deliver_at=deliver_at,
                status=DeliveryStatus.PENDING,
                payload=json.dumps(data, default=str),
            )
            session.add(record)
            await session.commit()

        self._log.info(
            f"Отложенная выдача: order={order_id}, через {delay_minutes} мин "
            f"в {deliver_at.strftime('%H:%M:%S')}"
        )

    async def process_delayed_deliveries(self) -> None:
        """
        APScheduler: вызывается каждую минуту.
        Берёт все PENDING записи с deliver_at <= now() и выдаёт товар.
        """
        now = datetime.utcnow()

        async with get_session() as session:
            result = await session.execute(
                select(DelayedDelivery).where(
                    DelayedDelivery.status == DeliveryStatus.PENDING,
                    DelayedDelivery.deliver_at <= now,
                )
            )
            pending: List[DelayedDelivery] = result.scalars().all()

        for record in pending:
            try:
                # Восстановить payload и эмитить ITEM_DELIVERED
                payload = json.loads(record.payload or "{}")
                EventBus().emit(EventType.ITEM_DELIVERED, payload)

                async with get_session() as session:
                    result = await session.execute(
                        select(DelayedDelivery).where(DelayedDelivery.id == record.id)
                    )
                    row = result.scalar_one_or_none()
                    if row:
                        row.status = DeliveryStatus.DELIVERED
                        await session.commit()

                self._log.info(
                    f"Отложенная выдача выполнена: order={record.order_id}"
                )
            except Exception as e:
                self._log.error(
                    f"Ошибка отложенной выдачи order={record.order_id}: {e}"
                )