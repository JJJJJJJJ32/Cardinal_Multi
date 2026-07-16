"""
modules/core/events.py
──────────────────────
Внутренняя шина событий Cardinal_Multi (не FunPayAPI EventTypes!).
Позволяет модулям общаться между собой без прямых зависимостей.

Паттерн: publish/subscribe (EventBus).
Thread-safe: да (Lock + asyncio-совместимость).

Типы событий:
    FunPay-события (от Cardinal через bridge):
        NEW_ORDER, NEW_MESSAGE, LOT_CHANGED,
        ORDER_COMPLETED, ORDER_STATUS_CHANGED

    Мультиаккаунт-события:
        ACCOUNT_ERROR, ACCOUNT_STARTED, ACCOUNT_STOPPED

    Lolzteam-события (для другого AI):
        SEARCH_STARTED, SEARCH_COMPLETED,
        ITEM_PURCHASED, ITEM_DELIVERED

    Системные:
        BALANCE_LOW, SYSTEM_ERROR
"""

from __future__ import annotations

import asyncio
from enum import Enum, auto
from threading import Lock
from typing import Any, Callable, Coroutine

from loguru import logger


# ─── Типы событий ─────────────────────────────────────────────────────────────

class EventType(str, Enum):
    """
    Все типы событий Cardinal_Multi.
    Строковый Enum для удобства логирования и сериализации.
    """

    # ── FunPay-события ────────────────────────────────────────────────────────
    NEW_ORDER            = "new_order"
    """Новый заказ на FunPay."""

    NEW_MESSAGE          = "new_message"
    """Новое сообщение от покупателя."""

    LOT_CHANGED          = "lot_changed"
    """Изменился статус лота."""

    ORDER_COMPLETED      = "order_completed"
    """Заказ выполнен и подтверждён покупателем."""

    ORDER_STATUS_CHANGED = "order_status_changed"
    """Статус заказа изменился (оплачен/возврат и т.д.)."""

    # ── Мультиаккаунт ─────────────────────────────────────────────────────────
    ACCOUNT_ERROR        = "account_error"
    """Аккаунт FunPay упал или недоступен."""

    ACCOUNT_STARTED      = "account_started"
    """Аккаунт успешно запущен."""

    ACCOUNT_STOPPED      = "account_stopped"
    """Аккаунт остановлен (штатно или по ошибке)."""

    # ── Lolzteam (для другого AI-модуля) ─────────────────────────────────────
    SEARCH_STARTED       = "search_started"
    """Запущен поиск товаров на Lolzteam."""

    SEARCH_COMPLETED     = "search_completed"
    """Поиск товаров на Lolzteam завершён."""

    ITEM_PURCHASED       = "item_purchased"
    """Товар куплен на Lolzteam."""

    ITEM_DELIVERED       = "item_delivered"
    """Купленный товар выдан покупателю на FunPay."""

    # ── Системные ────────────────────────────────────────────────────────────
    BALANCE_LOW          = "balance_low"
    """Баланс аккаунта ниже порогового значения."""

    SYSTEM_ERROR         = "system_error"
    """Критическая системная ошибка."""


# ─── Типы хэндлеров ───────────────────────────────────────────────────────────

# Sync handler: принимает EventType + данные
SyncHandler = Callable[[EventType, Any], None]
# Async handler: возвращает корутину
AsyncHandler = Callable[[EventType, Any], Coroutine[Any, Any, None]]
Handler = SyncHandler | AsyncHandler


# ─── EventBus ─────────────────────────────────────────────────────────────────

class EventBus:
    """
    Шина событий Cardinal_Multi.

    Синглтон. Поддерживает синхронные и асинхронные подписчики.
    Thread-safe для subscribe/unsubscribe.
    emit() можно вызывать из любого потока.

    Пример использования::

        bus = EventBus()

        # Подписка (sync)
        def on_new_order(event: EventType, data: dict) -> None:
            print(f"Новый заказ: {data['order_id']}")

        bus.subscribe(EventType.NEW_ORDER, on_new_order)

        # Публикация
        bus.emit(EventType.NEW_ORDER, {"order_id": "ABC123", "account_id": 1})

        # Отписка
        bus.unsubscribe(EventType.NEW_ORDER, on_new_order)
    """

    _instance: "EventBus | None" = None

    def __new__(cls) -> "EventBus":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._handlers: dict[EventType, list[Handler]] = {}
            cls._instance._lock = Lock()
        return cls._instance

    # ──────────────────────────────────────────────────────────────────────────
    # Subscribe / Unsubscribe
    # ──────────────────────────────────────────────────────────────────────────

    def subscribe(self, event: EventType, handler: Handler) -> None:
        """
        Подписывает хэндлер на событие.

        :param event: тип события из EventType.
        :param handler: функция-обработчик (sync или async).

        Async-хэндлеры запускаются через asyncio.run_coroutine_threadsafe()
        если event loop запущен, иначе через asyncio.run().
        """
        with self._lock:
            if event not in self._handlers:
                self._handlers[event] = []
            if handler not in self._handlers[event]:
                self._handlers[event].append(handler)
                logger.debug(
                    "EventBus: подписка на '{}' → {}.{}",
                    event.value,
                    handler.__module__,
                    handler.__qualname__,
                )

    def unsubscribe(self, event: EventType, handler: Handler) -> None:
        """
        Отписывает хэндлер от события.

        :param event: тип события.
        :param handler: ранее подписанный хэндлер.
        """
        with self._lock:
            if event in self._handlers:
                try:
                    self._handlers[event].remove(handler)
                    logger.debug(
                        "EventBus: отписка от '{}' → {}.{}",
                        event.value,
                        handler.__module__,
                        handler.__qualname__,
                    )
                except ValueError:
                    pass

    def subscribe_many(
        self, subscriptions: dict[EventType, Handler | list[Handler]]
    ) -> None:
        """
        Подписывает несколько хэндлеров за один вызов.

        :param subscriptions: словарь {EventType: handler или [handler1, handler2]}.

        Пример::

            bus.subscribe_many({
                EventType.NEW_ORDER:   handle_order,
                EventType.NEW_MESSAGE: [handle_msg_1, handle_msg_2],
            })
        """
        for event, handlers in subscriptions.items():
            if isinstance(handlers, list):
                for h in handlers:
                    self.subscribe(event, h)
            else:
                self.subscribe(event, handlers)

    # ──────────────────────────────────────────────────────────────────────────
    # Emit
    # ──────────────────────────────────────────────────────────────────────────

    def emit(self, event: EventType, data: Any = None) -> None:
        """
        Публикует событие всем подписчикам.

        Sync-хэндлеры вызываются немедленно в текущем потоке.
        Async-хэндлеры запускаются в event loop (если он есть)
        или создают новый через asyncio.run().

        Ошибка в одном хэндлере не прерывает вызов остальных.

        :param event: тип события.
        :param data: произвольные данные события (dict, объект, None).
        """
        with self._lock:
            handlers = list(self._handlers.get(event, []))

        if not handlers:
            return

        logger.debug("EventBus: emit '{}' → {} подписчиков", event.value, len(handlers))

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    self._call_async(handler, event, data)
                else:
                    handler(event, data)
            except Exception as exc:
                logger.error(
                    "EventBus: ошибка в хэндлере {}.{} для события '{}': {}",
                    handler.__module__,
                    handler.__qualname__,
                    event.value,
                    exc,
                )

    def _call_async(self, handler: AsyncHandler, event: EventType, data: Any) -> None:
        """
        Вызывает async-хэндлер.

        Если есть работающий event loop — schedules coroutine в нём.
        Иначе — создаёт новый event loop.

        :param handler: async функция-обработчик.
        :param event: тип события.
        :param data: данные события.
        """
        try:
            loop = asyncio.get_running_loop()
            # Есть работающий loop — планируем корутину в нём
            asyncio.run_coroutine_threadsafe(handler(event, data), loop)
        except RuntimeError:
            # Нет работающего loop — запускаем синхронно
            asyncio.run(handler(event, data))

    # ──────────────────────────────────────────────────────────────────────────
    # Utility
    # ──────────────────────────────────────────────────────────────────────────

    def clear(self, event: EventType | None = None) -> None:
        """
        Удаляет всех подписчиков.

        :param event: если указан — очищает только этот тип события.
                      Если None — очищает все события.
        """
        with self._lock:
            if event is not None:
                self._handlers.pop(event, None)
            else:
                self._handlers.clear()
        logger.debug("EventBus: очищены подписчики (event={})", event)

    def subscriber_count(self, event: EventType) -> int:
        """
        Возвращает количество подписчиков на событие.

        :param event: тип события.
        :return: количество подписчиков.
        """
        with self._lock:
            return len(self._handlers.get(event, []))

    def __repr__(self) -> str:
        with self._lock:
            total = sum(len(v) for v in self._handlers.values())
        return f"<EventBus: {len(self._handlers)} событий, {total} подписчиков>"