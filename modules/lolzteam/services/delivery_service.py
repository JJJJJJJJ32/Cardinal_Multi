"""
Сервис выдачи товара покупателю через FunPay.

Режим AUTO   — сразу отправить товар в чат FunPay.
Режим CONFIRM — показать владельцу в Telegram, ждать подтверждения.

Напоминание покупателю через 120 мин.
Закрытие заказа через 12 часов.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Any

from loguru import logger
from sqlalchemy import update

from modules.core.database import get_session
from modules.core.events import EventBus, EventType

from ..models.order import Order, OrderStatus
from ..models.lot_settings import DeliveryMode


class DeliveryService:
    """
    Выдача товара покупателю.
    """

    _REMINDER_DELAY = 120 * 60   # 120 минут в секундах
    _CLOSE_DELAY = 12 * 60 * 60  # 12 часов в секундах

    def __init__(self) -> None:
        self._bus = EventBus()

    # ── Определение формата товара ───────────────────────────────

    @staticmethod
    def parse_item_format(item_data: str) -> dict[str, str]:
        """
        Автоматически определить формат товара.

        Форматы:
        - login:password
        - login:password:extra_data
        - login:password:email:email_password
        - произвольный текст

        Args:
            item_data: Строка с данными товара.

        Returns:
            dict с ключами: type, login, password, extra, raw.
        """
        if not item_data:
            return {"type": "empty", "raw": ""}

        parts = item_data.split(":")

        if len(parts) == 2:
            return {
                "type": "login_password",
                "login": parts[0].strip(),
                "password": parts[1].strip(),
                "raw": item_data,
            }
        elif len(parts) == 3:
            return {
                "type": "login_password_extra",
                "login": parts[0].strip(),
                "password": parts[1].strip(),
                "extra": parts[2].strip(),
                "raw": item_data,
            }
        elif len(parts) >= 4:
            return {
                "type": "login_password_email",
                "login": parts[0].strip(),
                "password": parts[1].strip(),
                "email": parts[2].strip(),
                "email_password": parts[3].strip(),
                "extra": ":".join(parts[4:]).strip() if len(parts) > 4 else "",
                "raw": item_data,
            }
        else:
            return {"type": "text", "raw": item_data}

    # ── Доставка ─────────────────────────────────────────────────

    async def deliver(
        self,
        order: Order,
        item_data: str,
        delivery_mode: str,
    ) -> None:
        """
        Выдать товар покупателю.

        Args:
            order:         Объект заказа.
            item_data:     Расшифрованные данные товара.
            delivery_mode: "auto" или "confirm".
        """
        parsed = self.parse_item_format(item_data)

        if delivery_mode == DeliveryMode.AUTO:
            await self._deliver_auto(order, item_data)
        else:
            await self._deliver_confirm(order, parsed)

    async def _deliver_auto(
        self,
        order: Order,
        item_data: str,
    ) -> None:
        """
        Режим AUTO — сразу отправить товар в чат FunPay.
        """
        logger.info(
            f"[DeliveryService] AUTO выдача для "
            f"заказа #{order.funpay_order_id}"
        )

        # Emit события — LolzteamModule отправит сообщение в FunPay
        self._bus.emit(
            EventType.ITEM_DELIVERED,
            {
                "order_id": order.id,
                "funpay_order_id": order.funpay_order_id,
                "buyer_chat_id": order.buyer_chat_id,
                "buyer_username": order.buyer_username,
                "item_data": item_data,
                "delivery_mode": "auto",
            },
        )

        await self._update_order_status(order.id, OrderStatus.DELIVERED)

        # Запустить напоминание и закрытие в фоне
        asyncio.create_task(
            self._schedule_reminder_and_close(order),
            name=f"lolzteam_reminder_{order.funpay_order_id}",
        )

    async def _deliver_confirm(
        self,
        order: Order,
        parsed: dict[str, Any],
    ) -> None:
        """
        Режим CONFIRM — показать владельцу, ждать кнопки.
        """
        logger.info(
            f"[DeliveryService] CONFIRM выдача для "
            f"заказа #{order.funpay_order_id}"
        )

        await self._update_order_status(order.id, OrderStatus.WAITING)

        # Emit — LolzteamModule отправит Telegram сообщение с кнопками
        self._bus.emit(
            EventType.ITEM_PURCHASED,
            {
                "order_id": order.id,
                "funpay_order_id": order.funpay_order_id,
                "buyer_username": order.buyer_username,
                "parsed_item": parsed,
                "delivery_mode": "confirm",
                "action": "await_confirm",
            },
        )

    # ── Напоминание и автозакрытие ────────────────────────────────

    async def _schedule_reminder_and_close(self, order: Order) -> None:
        """
        Через 120 мин — напомнить покупателю.
        Через 12 часов — закрыть заказ как завершённый.
        """
        logger.debug(
            f"[DeliveryService] Запуск таймеров для "
            f"заказа #{order.funpay_order_id}"
        )

        # Ждём 120 минут → напоминание
        await asyncio.sleep(self._REMINDER_DELAY)

        async with get_session() as session:
            fresh = await session.get(Order, order.id)
            if fresh is None:
                return
            if fresh.status in (
                OrderStatus.COMPLETED,
                OrderStatus.CANCELLED,
                OrderStatus.REFUND,
            ):
                return

        logger.info(
            f"[DeliveryService] Напоминание покупателю "
            f"#{order.funpay_order_id}"
        )
        self._bus.emit(
            EventType.SYSTEM_ERROR,  # используем как generic notification
            {
                "action": "reminder",
                "order_id": order.id,
                "funpay_order_id": order.funpay_order_id,
                "buyer_chat_id": order.buyer_chat_id,
            },
        )

        # Ждём ещё 10 часов (120 мин + 600 мин = 720 мин = 12 ч)
        await asyncio.sleep(self._CLOSE_DELAY - self._REMINDER_DELAY)

        async with get_session() as session:
            fresh = await session.get(Order, order.id)
            if fresh is None:
                return
            if fresh.status in (
                OrderStatus.COMPLETED,
                OrderStatus.CANCELLED,
                OrderStatus.REFUND,
            ):
                return

        # Автозакрытие
        logger.info(
            f"[DeliveryService] Автозакрытие заказа "
            f"#{order.funpay_order_id} (12 ч прошло)"
        )
        await self._update_order_status(order.id, OrderStatus.COMPLETED)
        self._bus.emit(
            EventType.ITEM_DELIVERED,
            {
                "action": "auto_close",
                "order_id": order.id,
                "funpay_order_id": order.funpay_order_id,
            },
        )

    # ── Вспомогательные методы ────────────────────────────────────

    async def _update_order_status(
        self,
        order_id: int,
        status: OrderStatus,
    ) -> None:
        async with get_session() as session:
            now = datetime.utcnow()
            values: dict[str, Any] = {"status": status}
            if status == OrderStatus.COMPLETED:
                values["completed_at"] = now
            await session.execute(
                update(Order)
                .where(Order.id == order_id)
                .values(**values)
            )