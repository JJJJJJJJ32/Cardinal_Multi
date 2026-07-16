"""
Сервис покупки товаров на Lolzteam Market.

Реализует все сценарии:
А — товар в пределах цены → fast_buy.
Б — товар дороже max_price → уведомление владельцу.
Д — проблема с товаром → уведомление, не спор.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from loguru import logger
from sqlalchemy import update

from modules.core.database import get_session
from modules.core.events import EventBus, EventType

from ..models.order import Order, OrderStatus
from ..models.purchase_log import PurchaseLog

if TYPE_CHECKING:
    from ..providers.base import LolzteamProvider


class PurchaseService:
    """
    Сервис покупки: fast_buy / confirm_buy, логирование.
    """

    def __init__(self, provider: "LolzteamProvider") -> None:
        self._provider = provider
        self._bus = EventBus()

    # ── Получить balance_id ───────────────────────────────────────

    async def get_primary_balance_id(self) -> int:
        """
        Получить ID основного баланса Lolzteam.

        Returns:
            balance_id (int).

        Raises:
            RuntimeError: Если балансы недоступны.
        """
        balances = await self._provider.get_balances()
        if not balances:
            raise RuntimeError("Lolzteam: балансы не получены")
        # Первый баланс считается основным
        return balances[0].get("id", 0)

    # ── Покупка ──────────────────────────────────────────────────

    async def purchase(
        self,
        order: Order,
        item: dict[str, Any],
        balance_id: int,
    ) -> dict[str, Any] | None:
        """
        Выполнить покупку товара.

        Сценарий А: fast_buy → get_item → emit ITEM_PURCHASED.
        При неудаче fast_buy → пробует confirm_buy.

        Args:
            order:      Объект заказа из БД.
            item:       Данные товара (из search результата).
            balance_id: ID баланса Lolzteam.

        Returns:
            Данные купленного товара или None при ошибке.
        """
        item_id = item.get("item_id") or item.get("id")
        price = item.get("price", 0)

        if item_id is None:
            logger.error(
                f"[PurchaseService] item_id не найден в данных товара: "
                f"{item}"
            )
            return None

        log = PurchaseLog(
            order_id=order.id,
            lolzteam_item_id=item_id,
            filters_used=None,
            found_count=1,
            rejected_count=0,
            purchase_price=price,
            provider_mode="api",
        )

        try:
            # Сценарий А — fast_buy
            logger.info(
                f"[PurchaseService] fast_buy item={item_id} "
                f"price={price} order=#{order.funpay_order_id}"
            )
            result = await self._provider.fast_buy(
                item_id=int(item_id),
                price=float(price),
                balance_id=balance_id,
            )

        except RuntimeError as fast_buy_exc:
            logger.warning(
                f"[PurchaseService] fast_buy неудача, "
                f"пробуем confirm_buy: {fast_buy_exc}"
            )
            try:
                result = await self._provider.confirm_buy(
                    item_id=int(item_id),
                    price=int(price),
                    balance_id=balance_id,
                )
            except Exception as confirm_exc:
                logger.error(
                    f"[PurchaseService] confirm_buy тоже неудача: "
                    f"{confirm_exc}"
                )
                log.status = "error"
                log.error_message = str(confirm_exc)
                await self._save_log(log)
                await self._update_order_status(
                    order.id, OrderStatus.PROBLEM
                )
                # Сценарий Д
                self._bus.emit(
                    EventType.SYSTEM_ERROR,
                    {
                        "order_id": order.id,
                        "funpay_order_id": order.funpay_order_id,
                        "item_id": item_id,
                        "error": str(confirm_exc),
                        "scenario": "Д",
                    },
                )
                return None

        # ── Получить полные данные товара ─────────────────────────
        try:
            full_item = await self._provider.get_item(int(item_id))
        except Exception as exc:
            logger.warning(
                f"[PurchaseService] get_item ошибка: {exc}. "
                f"Используем данные из fast_buy."
            )
            full_item = result

        # ── Обновить заказ в БД ───────────────────────────────────
        await self._update_order_purchased(
            order_id=order.id,
            item_id=int(item_id),
            lolzteam_amount=float(price),
        )

        log.status = "success"
        await self._save_log(log)

        logger.info(
            f"[PurchaseService] Куплен item={item_id} "
            f"для заказа #{order.funpay_order_id}"
        )

        # ── Emit ITEM_PURCHASED ───────────────────────────────────
        self._bus.emit(
            EventType.ITEM_PURCHASED,
            {
                "order_id": order.id,
                "funpay_order_id": order.funpay_order_id,
                "item": full_item,
                "purchase_result": result,
            },
        )

        return full_item

    # ── Вспомогательные методы ────────────────────────────────────

    async def _update_order_status(
        self,
        order_id: int,
        status: OrderStatus,
    ) -> None:
        async with get_session() as session:
            await session.execute(
                update(Order)
                .where(Order.id == order_id)
                .values(status=status)
            )

    async def _update_order_purchased(
        self,
        order_id: int,
        item_id: int,
        lolzteam_amount: float,
    ) -> None:
        async with get_session() as session:
            await session.execute(
                update(Order)
                .where(Order.id == order_id)
                .values(
                    status=OrderStatus.PURCHASED,
                    lolzteam_item_id=item_id,
                    lolzteam_amount=lolzteam_amount,
                )
            )

    async def _save_log(self, log: PurchaseLog) -> None:
        async with get_session() as session:
            session.add(log)