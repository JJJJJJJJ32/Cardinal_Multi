"""
LolzteamModule — главный класс Lolzteam автозакупки.

Наследует BaseModule.
Регистрируется в main.py через setup() → start().

Обрабатывает все 6 сценариев:
А — товар найден, цена ОК → fast_buy → выдача.
Б — товар дороже max_price → уведомление с кнопками.
В — товар не найден сразу → сообщение покупателю.
Г — не найден за N часов → уведомление с кнопками.
Д — проблема с товаром → уведомление, НЕ спор.
Е — лот не настроен → ORDER_MANUAL + уведомление.
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger
from sqlalchemy import select

from modules.core.base_module import BaseModule
from modules.core.config import get_settings
from modules.core.database import get_session
from modules.core.events import EventBus, EventType

from .categories.definitions import register_all as register_categories
from .models.order import Order, OrderStatus
from .models.lot_settings import LotLolzteamSettings, DeliveryMode
from .providers.factory import LolzteamFactory
from .providers.base import LolzteamProvider
from .services.search_service import SearchService
from .services.purchase_service import PurchaseService
from .services.delivery_service import DeliveryService


class LolzteamModule(BaseModule):
    """
    Модуль автозакупки на Lolzteam Market.

    Подписывается на EventType.NEW_ORDER из EventBus.
    Запускает search_loop через asyncio.create_task.
    Обрабатывает SEARCH_COMPLETED → purchase → deliver.
    """

    name = "lolzteam"
    version = "1.0.0"

    def __init__(self) -> None:
        super().__init__()
        self._provider: LolzteamProvider | None = None
        self._search_service: SearchService | None = None
        self._purchase_service: PurchaseService | None = None
        self._delivery_service: DeliveryService | None = None
        self._bus = EventBus()
        self._balance_id: int = 0
        # active tasks — чтобы не потерять ссылки
        self._active_tasks: set[asyncio.Task] = set()

    # ── Жизненный цикл ───────────────────────────────────────────

    async def setup(self) -> None:
        """
        Инициализация модуля:
        1) Регистрация категорий.
        2) Создание провайдера.
        3) Подписка на события.
        """
        await super().setup()

        # Регистрируем все категории
        register_categories()
        logger.info("[LolzteamModule] Категории зарегистрированы")

        # Создаём провайдер
        settings = get_settings()
        self._provider = LolzteamFactory.create(
            api_token=getattr(settings, "lolz_api_token", None)
            or getattr(settings, "lolzteam_token", None),
            login=getattr(settings, "lolz_login", None),
            password=getattr(settings, "lolz_password", None),
        )

        # Инициализируем сервисы
        self._search_service = SearchService(self._provider)
        self._purchase_service = PurchaseService(self._provider)
        self._delivery_service = DeliveryService()

        # Подписка на события
        self._bus.subscribe(EventType.NEW_ORDER, self._on_new_order)
        self._bus.subscribe(
            EventType.SEARCH_COMPLETED, self._on_search_completed
        )
        self._bus.subscribe(
            EventType.ITEM_PURCHASED, self._on_item_purchased
        )

        logger.info("[LolzteamModule] setup завершён")

    async def start(self) -> None:
        """
        Запуск модуля:
        1) Проверка соединения с Lolzteam.
        2) Получение balance_id.
        """
        await super().start()

        try:
            profile = await self._provider.get_profile()
            username = (
                profile.get("user", {}).get("username")
                or profile.get("username")
                or "—"
            )
            logger.info(
                f"[LolzteamModule] Подключён как '{username}'"
            )
        except Exception as exc:
            logger.error(
                f"[LolzteamModule] Не удалось подключиться к Lolzteam: "
                f"{exc}"
            )

        try:
            self._balance_id = (
                await self._purchase_service.get_primary_balance_id()
            )
            logger.info(
                f"[LolzteamModule] balance_id={self._balance_id}"
            )
        except Exception as exc:
            logger.warning(
                f"[LolzteamModule] Не удалось получить balance_id: "
                f"{exc}"
            )

        self._set_running()
        logger.info("[LolzteamModule] Запущен")

    async def stop(self) -> None:
        """Остановка модуля — отменить все активные задачи."""
        for task in list(self._active_tasks):
            if not task.done():
                task.cancel()
        self._active_tasks.clear()

        if hasattr(self._provider, "close"):
            try:
                await self._provider.close()
            except Exception as exc:
                logger.warning(
                    f"[LolzteamModule] Ошибка закрытия провайдера: {exc}"
                )

        self._set_stopped()
        await super().stop()
        logger.info("[LolzteamModule] Остановлен")

    def status(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "running": self._is_running,
            "active_tasks": len(self._active_tasks),
            "balance_id": self._balance_id,
        }

    # ── Обработчики событий ───────────────────────────────────────

    def _on_new_order(self, event: EventType, data: dict) -> None:
        """
        Обработчик нового заказа FunPay.
        Запускает asyncio.Task через create_task.
        НЕ блокирует основной поток.
        """
        task = asyncio.create_task(
            self._handle_new_order(data),
            name=f"lolzteam_order_{data.get('order_id', 'unknown')}",
        )
        self._active_tasks.add(task)
        task.add_done_callback(self._active_tasks.discard)

    def _on_search_completed(
        self, event: EventType, data: dict
    ) -> None:
        """Поиск завершён — запустить покупку или уведомление."""
        task = asyncio.create_task(
            self._handle_search_completed(data),
            name=f"lolzteam_buy_{data.get('funpay_order_id', 'unknown')}",
        )
        self._active_tasks.add(task)
        task.add_done_callback(self._active_tasks.discard)

    def _on_item_purchased(
        self, event: EventType, data: dict
    ) -> None:
        """Товар куплен — запустить выдачу."""
        if data.get("action") not in ("await_confirm", "auto_close"):
            task = asyncio.create_task(
                self._handle_item_purchased(data),
                name=f"lolzteam_deliver_{data.get('funpay_order_id', 'unknown')}",
            )
            self._active_tasks.add(task)
            task.add_done_callback(self._active_tasks.discard)

    # ── Async обработчики (не блокируют основной поток) ──────────

    async def _handle_new_order(self, data: dict) -> None:
        """
        Обработка нового заказа:
        1) Найти/создать Order в БД.
        2) Проверить настройки Lolzteam для лота.
        3) Если нет настроек → Сценарий Е.
        4) Если есть → создать Order и запустить search_loop.
        """
        try:
            funpay_order_id = data.get("order_id", "")
            account_id = data.get("account_id")
            order_short = data.get("order_short")

            # Пытаемся получить lot_id и данные покупателя
            lot_id = None
            buyer_username = None
            buyer_chat_id = None
            funpay_amount = None

            if order_short is not None:
                try:
                    lot_id_raw = getattr(order_short, "lot_id", None)
                    lot_id = int(lot_id_raw) if lot_id_raw else None
                    buyer_username = getattr(
                        order_short, "buyer_username", None
                    )
                    buyer_chat_id = str(
                        getattr(order_short, "chat_id", "")
                    ) or None
                    funpay_amount = float(
                        getattr(order_short, "price", 0) or 0
                    )
                except Exception as parse_exc:
                    logger.warning(
                        f"[LolzteamModule] Ошибка парсинга order_short: "
                        f"{parse_exc}"
                    )

            # Ищем настройки Lolzteam для лота
            settings: LotLolzteamSettings | None = None
            if lot_id is not None:
                async with get_session() as session:
                    result = await session.execute(
                        select(LotLolzteamSettings)
                        .where(LotLolzteamSettings.lot_id == lot_id)
                        .where(LotLolzteamSettings.is_enabled == True)
                    )
                    settings = result.scalar_one_or_none()

            if settings is None:
                # Сценарий Е — лот не настроен
                logger.info(
                    f"[LolzteamModule] Лот {lot_id} не настроен на Lolzteam. "
                    f"Заказ #{funpay_order_id} → ORDER_MANUAL"
                )
                self._bus.emit(
                    EventType.SYSTEM_ERROR,
                    {
                        "action": "order_manual",
                        "order_id": funpay_order_id,
                        "lot_id": lot_id,
                        "buyer_username": buyer_username,
                        "scenario": "Е",
                    },
                )
                return

            # Создаём Order в БД
            async with get_session() as session:
                # Проверяем дублирование
                existing = await session.execute(
                    select(Order).where(
                        Order.funpay_order_id == funpay_order_id
                    )
                )
                order = existing.scalar_one_or_none()

                if order is None:
                    order = Order(
                        funpay_order_id=funpay_order_id,
                        account_id=account_id,
                        lot_id=lot_id,
                        buyer_username=buyer_username,
                        buyer_chat_id=buyer_chat_id,
                        status=OrderStatus.SEARCHING,
                        funpay_amount=funpay_amount,
                    )
                    session.add(order)
                    await session.flush()

                order_id = order.id

            # Перечитать объект вне сессии
            async with get_session() as session:
                order = await session.get(Order, order_id)

            if order is None:
                logger.error(
                    f"[LolzteamModule] Order не найден после создания: "
                    f"#{funpay_order_id}"
                )
                return

            # Запустить search_loop
            task = self._search_service.start_search(order, settings)
            self._active_tasks.add(task)
            task.add_done_callback(self._active_tasks.discard)

        except Exception as exc:
            logger.error(
                f"[LolzteamModule] _handle_new_order ошибка: {exc}",
                exc_info=True,
            )

    async def _handle_search_completed(self, data: dict) -> None:
        """
        Поиск завершён.

        Если item найден:
          - Проверить цену vs max_price.
          - Если ОК → Сценарий А (купить).
          - Если дороже → Сценарий Б (уведомление владельцу с кнопками).

        Если not_found:
          - Сценарий Г.
        """
        try:
            order_id = data.get("order_id")
            funpay_order_id = data.get("funpay_order_id")
            item = data.get("item")
            settings: LotLolzteamSettings = data.get("settings")
            not_found = data.get("not_found", False)
            max_hours = data.get("max_hours", 2)
            buyer_username = data.get("buyer_username")

            if not_found or item is None:
                # Сценарий Г
                logger.warning(
                    f"[LolzteamModule] Сценарий Г: "
                    f"заказ #{funpay_order_id} — не найден за {max_hours} ч."
                )
                self._bus.emit(
                    EventType.SYSTEM_ERROR,
                    {
                        "action": "not_found_timeout",
                        "order_id": order_id,
                        "funpay_order_id": funpay_order_id,
                        "buyer_username": buyer_username,
                        "max_hours": max_hours,
                        "scenario": "Г",
                    },
                )
                return

            price = item.get("price", 0)
            max_price = (settings.common_filters or {}).get("pmax")

            if max_price is not None and float(price) > float(max_price):
                # Сценарий Б — дороже max_price
                logger.info(
                    f"[LolzteamModule] Сценарий Б: "
                    f"заказ #{funpay_order_id} — "
                    f"цена {price} > max_price {max_price}"
                )
                seller = item.get("seller", {}) or {}
                rating = seller.get("rating", 0)
                reviews = seller.get("reviews_count", 0)

                self._bus.emit(
                    EventType.SYSTEM_ERROR,
                    {
                        "action": "price_exceeded",
                        "order_id": order_id,
                        "funpay_order_id": funpay_order_id,
                        "item": item,
                        "price": price,
                        "max_price": max_price,
                        "rating": rating,
                        "reviews": reviews,
                        "buyer_username": buyer_username,
                        "scenario": "Б",
                        "balance_id": self._balance_id,
                    },
                )
                return

            # Сценарий А — покупать
            async with get_session() as session:
                order = await session.get(Order, order_id)
            if order is None:
                logger.error(
                    f"[LolzteamModule] Order {order_id} не найден"
                )
                return

            full_item = await self._purchase_service.purchase(
                order=order,
                item=item,
                balance_id=self._balance_id,
            )

            if full_item is None:
                # Сценарий Д обрабатывается внутри purchase_service
                return

            # Получить расшифрованные данные товара
            item_data = self._extract_item_data(full_item)

            if not item_data:
                logger.error(
                    f"[LolzteamModule] Не удалось извлечь item_data "
                    f"для заказа #{funpay_order_id}"
                )
                return

            # Сохранить item_data в Order
            async with get_session() as session:
                order_db = await session.get(Order, order_id)
                if order_db:
                    order_db.set_item_data(item_data)

            # Выдать товар
            async with get_session() as session:
                order = await session.get(Order, order_id)

            delivery_mode = (
                settings.delivery_mode
                if settings
                else DeliveryMode.AUTO
            )
            await self._delivery_service.deliver(
                order=order,
                item_data=item_data,
                delivery_mode=delivery_mode,
            )

        except Exception as exc:
            logger.error(
                f"[LolzteamModule] _handle_search_completed ошибка: "
                f"{exc}",
                exc_info=True,
            )

    async def _handle_item_purchased(self, data: dict) -> None:
        """
        Товар куплен — выдать покупателю (ITEM_PURCHASED event).
        Дублирующий путь для случаев когда delivery уже известен.
        """
        # Основная логика выдачи уже в _handle_search_completed.
        # Этот обработчик обрабатывает confirm-кнопку от владельца.
        action = data.get("action")
        if action == "do_deliver":
            order_id = data.get("order_id")
            item_data = data.get("item_data")
            if order_id and item_data:
                async with get_session() as session:
                    order = await session.get(Order, order_id)
                if order:
                    await self._delivery_service.deliver(
                        order=order,
                        item_data=item_data,
                        delivery_mode=DeliveryMode.AUTO,
                    )

    # ── Вспомогательные ──────────────────────────────────────────

    @staticmethod
    def _extract_item_data(item: dict) -> str | None:
        """
        Извлечь данные товара (login:password) из ответа Lolzteam API.

        API возвращает данные в разных полях в зависимости от типа товара.
        """
        # Стандартные поля Lolzteam API
        for key in ("item_data", "account_data", "data", "login_data"):
            value = item.get(key)
            if value and isinstance(value, str):
                return value

        # Попытка собрать из login + password
        login = item.get("login") or item.get("account_login")
        password = item.get("password") or item.get("account_password")
        if login and password:
            return f"{login}:{password}"

        # Вложенный item
        nested = item.get("item", {})
        if isinstance(nested, dict):
            for key in ("item_data", "account_data", "data", "login_data"):
                value = nested.get(key)
                if value and isinstance(value, str):
                    return value

        return None