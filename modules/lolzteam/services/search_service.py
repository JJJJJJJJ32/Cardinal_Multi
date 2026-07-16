
"""
Сервис поиска товаров на Lolzteam Market.

search_loop запускается через asyncio.create_task().
Не блокирует основной поток.
Проверяет order.is_cancelled на каждой итерации.
Интервал 10 минут между попытками.
Максимум = max_search_hours * 6 попыток.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING, Any

from loguru import logger
from sqlalchemy import select, update

from modules.core.database import get_session
from modules.core.events import EventBus, EventType

from ..models.order import Order, OrderStatus
from ..models.search_attempt import SearchAttempt
from ..models.lot_settings import LotLolzteamSettings
from ..categories.registry import CategoryRegistry
from ..categories.search_builder import SearchQueryBuilder

if TYPE_CHECKING:
    from ..providers.base import LolzteamProvider

_SEARCH_INTERVAL_MINUTES = 10
_DEFAULT_MAX_HOURS = 2


class SearchService:
    """
    Управляет поиском товаров для заказа.

    Методы вызываются из LolzteamModule.
    search_loop — запускается как asyncio.Task.
    """

    def __init__(self, provider: "LolzteamProvider") -> None:
        self._provider = provider
        self._bus = EventBus()
        self._registry = CategoryRegistry()

    # ── Публичный API ────────────────────────────────────────────

    def start_search(self, order: Order, settings: LotLolzteamSettings) -> asyncio.Task:
        """
        Запустить поиск в фоне (create_task).

        Args:
            order:    Объект заказа из БД.
            settings: Настройки лота Lolzteam.

        Returns:
            asyncio.Task — задача поиска.
        """
        task = asyncio.create_task(
            self._search_loop(order, settings),
            name=f"lolzteam_search_{order.funpay_order_id}",
        )
        logger.info(
            f"[SearchService] Запущен поиск для заказа "
            f"#{order.funpay_order_id}"
        )
        return task

    # ── Search Loop ──────────────────────────────────────────────

    async def _search_loop(
        self,
        order: Order,
        settings: LotLolzteamSettings,
    ) -> None:
        """
        Основной цикл поиска.
        Запускается через create_task — не блокирует основной поток.
        """
        max_hours = settings.max_search_hours or _DEFAULT_MAX_HOURS
        max_attempts = max_hours * 6  # каждые 10 мин = 6 раз/час

        # Задержка перед первым поиском (если задана в настройках)
        if settings.delay_minutes > 0:
            logger.debug(
                f"[SearchService] Задержка {settings.delay_minutes} мин "
                f"перед поиском заказа #{order.funpay_order_id}"
            )
            await asyncio.sleep(settings.delay_minutes * 60)

        category = self._registry.get(settings.lolzteam_category)
        if category is None:
            logger.error(
                f"[SearchService] Неизвестная категория "
                f"'{settings.lolzteam_category}' "
                f"для заказа #{order.funpay_order_id}"
            )
            return

        builder = SearchQueryBuilder(category)

        for attempt_num in range(1, max_attempts + 1):
            # ── Проверить отмену ──────────────────────────────────
            async with get_session() as session:
                fresh_order = await session.get(Order, order.id)
                if fresh_order is None or fresh_order.is_cancelled:
                    logger.info(
                        f"[SearchService] Заказ #{order.funpay_order_id} "
                        f"отменён. Поиск остановлен."
                    )
                    return

            logger.info(
                f"[SearchService] Попытка {attempt_num}/{max_attempts} "
                f"для заказа #{order.funpay_order_id}"
            )

            # ── Обновить счётчик попыток ──────────────────────────
            await self._increment_attempts(order.id)

            # ── Поиск ────────────────────────────────────────────
            try:
                params = builder.build(
                    settings.common_filters,
                    settings.specific_filters,
                )
                results = await self._provider.search(
                    category.url_path, params
                )
            except Exception as exc:
                logger.error(
                    f"[SearchService] Ошибка поиска "
                    f"попытка {attempt_num}: {exc}"
                )
                await self._save_attempt(
                    order.id, attempt_num, 0, None, None, "error"
                )
                await asyncio.sleep(_SEARCH_INTERVAL_MINUTES * 60)
                continue

            # ── Фильтрация ────────────────────────────────────────
            suitable = self._filter_results(
                results, settings.common_filters
            )

            await self._save_attempt(
                order.id,
                attempt_num,
                len(suitable),
                suitable[0]["price"] if suitable else None,
                suitable[0].get("item_id") if suitable else None,
                "found" if suitable else "not_found",
            )

            if suitable:
                best = min(suitable, key=lambda x: x.get("price", 0))
                logger.info(
                    f"[SearchService] Найден товар "
                    f"item_id={best.get('item_id')} "
                    f"цена={best.get('price')} "
                    f"для заказа #{order.funpay_order_id}"
                )
                await self._update_order_status(
                    order.id, OrderStatus.FOUND
                )
                self._bus.emit(
                    EventType.SEARCH_COMPLETED,
                    {
                        "order_id": order.id,
                        "funpay_order_id": order.funpay_order_id,
                        "item": best,
                        "settings": settings,
                    },
                )
                return
            else:
                # Сценарий В — сообщение покупателю при первой попытке
                if attempt_num == 1:
                    self._bus.emit(
                        EventType.SEARCH_STARTED,
                        {
                            "order_id": order.id,
                            "funpay_order_id": order.funpay_order_id,
                            "buyer_chat_id": order.buyer_chat_id,
                        },
                    )

            # Ждём до следующей попытки
            if attempt_num < max_attempts:
                await asyncio.sleep(_SEARCH_INTERVAL_MINUTES * 60)

        # ── Сценарий Г — не найден за N часов ───────────────────
        logger.warning(
            f"[SearchService] Товар не найден за {max_hours} ч. "
            f"Заказ #{order.funpay_order_id}"
        )
        await self._update_order_status(order.id, OrderStatus.PROBLEM)
        self._bus.emit(
            EventType.SEARCH_COMPLETED,
            {
                "order_id": order.id,
                "funpay_order_id": order.funpay_order_id,
                "item": None,
                "not_found": True,
                "max_hours": max_hours,
                "buyer_username": order.buyer_username,
                "settings": settings,
            },
        )

    # ── Фильтрация результатов ────────────────────────────────────

    def _filter_results(
        self,
        results: list[dict],
        common_filters: dict[str, Any],
    ) -> list[dict]:
        """
        Применяет фильтры к результатам поиска.

        Проверяет:
        - цена в диапазоне pmin/pmax
        - рейтинг продавца >= min_rating
        - отзывов >= min_reviews
        - позитивных отзывов >= 75%
        - обязательные слова есть в названии
        - запрещённые слова НЕТ в названии
        """
        pmin = common_filters.get("pmin")
        pmax = common_filters.get("pmax")
        min_rating = common_filters.get("min_rating", 0)
        min_reviews = common_filters.get("min_reviews", 0)
        required_words: list[str] = common_filters.get("required_words", [])
        forbidden_words: list[str] = common_filters.get("forbidden_words", [])

        suitable = []

        for item in results:
            price = item.get("price", 0)
            title = (item.get("title") or "").lower()

            seller = item.get("seller", {}) or {}
            rating = seller.get("rating", 0) or 0
            reviews_count = seller.get("reviews_count", 0) or 0
            pos_reviews = seller.get("positive_reviews", 0) or 0

            # Цена
            if pmin is not None and price < float(pmin):
                continue
            if pmax is not None and price > float(pmax):
                continue

            # Рейтинг
            if rating < float(min_rating):
                continue

            # Отзывы
            if reviews_count < int(min_reviews):
                continue

            # Положительные отзывы >= 75%
            if reviews_count > 0:
                pos_pct = (pos_reviews / reviews_count) * 100
                if pos_pct < 75:
                    continue

            # Обязательные слова
            ok = True
            for word in required_words:
                if word.lower() not in title:
                    ok = False
                    break
            if not ok:
                continue

            # Запрещённые слова
            skip = False
            for word in forbidden_words:
                if word.lower() in title:
                    skip = True
                    break
            if skip:
                continue

            suitable.append(item)

        return suitable

    # ── Вспомогательные методы ────────────────────────────────────

    async def _update_order_status(
        self,
        order_id: int,
        status: OrderStatus,
    ) -> None:
        """Обновить статус заказа в БД."""
        async with get_session() as session:
            await session.execute(
                update(Order)
                .where(Order.id == order_id)
                .values(status=status)
            )

    async def _increment_attempts(self, order_id: int) -> None:
        """Увеличить счётчик попыток поиска."""
        async with get_session() as session:
            result = await session.execute(
                select(Order).where(Order.id == order_id)
            )
            order = result.scalar_one_or_none()
            if order:
                order.search_attempts_count += 1

    async def _save_attempt(
        self,
        order_id: int,
        attempt_number: int,
        found_count: int,
        best_price: float | None,
        best_item_id: int | None,
        status: str,
    ) -> None:
        """Сохранить запись о попытке поиска в БД."""
        async with get_session() as session:
            attempt = SearchAttempt(
                order_id=order_id,
                attempt_number=attempt_number,
                found_count=found_count,
                best_price=best_price,
                best_item_id=best_item_id,
                status=status,
            )
            session.add(attempt)