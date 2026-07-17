"""
EventBus — внутренняя шина событий Cardinal_Multi.

Фиксы:
  B-20  / TC-083 — один handler не должен ломать остальных
  TC-084 — emit несуществующего типа
  TC-085 — emit с None payload
  TC-086 — burst-устойчивость (без блокировки)
"""

from __future__ import annotations

import asyncio
import enum
from collections import defaultdict
from typing import Any, Callable, Coroutine, Dict, List, Optional, Union

from loguru import logger


# ═══════════════════════════════════════════════════════════════════════════════
# EventType enum
# ═══════════════════════════════════════════════════════════════════════════════
class EventType(str, enum.Enum):
    """Все типы событий, поддерживаемые системой."""

    # Заказы
    NEW_ORDER = "new_order"
    ORDER_COMPLETED = "order_completed"

    # Сообщения
    NEW_MESSAGE = "new_message"

    # Товары
    ITEM_PURCHASED = "item_purchased"
    ITEM_DELIVERED = "item_delivered"

    # Аккаунты
    ACCOUNT_STARTED = "account_started"
    ACCOUNT_STOPPED = "account_stopped"
    ACCOUNT_ERROR = "account_error"

    # Система
    SYSTEM_ERROR = "system_error"
    SYSTEM_WARNING = "system_warning"


# Тип для handler'а — синхронная или асинхронная функция
HandlerType = Callable[..., Union[None, Coroutine[Any, Any, None]]]


# ═══════════════════════════════════════════════════════════════════════════════
# EventBus (Singleton)
# ═══════════════════════════════════════════════════════════════════════════════
class EventBus:
    """
    Простая шина событий с pub/sub.

    Гарантии:
      - Один упавший handler НЕ блокирует остальных (FIX B-20)
      - emit() с неизвестным EventType — тихий пропуск (TC-084)
      - emit() с payload=None допустим (TC-085)
    """

    _instance: Optional["EventBus"] = None

    def __new__(cls) -> "EventBus":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._handlers: Dict[str, List[HandlerType]] = defaultdict(list)
            cls._instance._initialized = True
        return cls._instance

    # ─── Подписка ────────────────────────────────────────────────────────────
    def subscribe(self, event_type: Union[EventType, str], handler: HandlerType) -> None:
        """Подписать handler на событие."""
        key = event_type.value if isinstance(event_type, EventType) else str(event_type)
        self._handlers[key].append(handler)
        logger.debug(f"EventBus: подписан {handler.__name__} на {key}")

    def unsubscribe(self, event_type: Union[EventType, str], handler: HandlerType) -> None:
        """Отписать handler от события."""
        key = event_type.value if isinstance(event_type, EventType) else str(event_type)
        try:
            self._handlers[key].remove(handler)
            logger.debug(f"EventBus: отписан {handler.__name__} от {key}")
        except ValueError:
            logger.warning(
                f"EventBus: handler {handler.__name__} не найден для {key}"
            )

    # ─── Публикация ──────────────────────────────────────────────────────────
    async def emit(
        self,
        event_type: Union[EventType, str],
        payload: Any = None,
    ) -> None:
        """
        Отправить событие всем подписчикам.

        TC-084: если нет подписчиков — тихий пропуск.
        TC-085: payload может быть None.
        B-20 / TC-083: каждый handler обёрнут в try/except.
        """
        key = event_type.value if isinstance(event_type, EventType) else str(event_type)
        handlers = self._handlers.get(key)

        if not handlers:
            logger.debug(f"EventBus: нет подписчиков на '{key}', пропуск")
            return

        logger.debug(f"EventBus: emit '{key}' → {len(handlers)} handler(s)")

        for handler in handlers:
            try:
                result = handler(payload)
                # Если handler — корутина, дожидаемся
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                # ── FIX B-20 / TC-083 ────────────────────────────────────────
                # Один handler упал — логируем и продолжаем
                logger.error(
                    f"EventBus: handler '{handler.__name__}' на событие '{key}' "
                    f"упал с ошибкой: {exc!r}",
                    exc_info=True,
                )

    # ─── Утилиты ─────────────────────────────────────────────────────────────
    def clear(self) -> None:
        """Удалить все подписки (для тестов)."""
        self._handlers.clear()
        logger.debug("EventBus: все подписки удалены")

    def handler_count(self, event_type: Union[EventType, str]) -> int:
        """Количество подписчиков на событие."""
        key = event_type.value if isinstance(event_type, EventType) else str(event_type)
        return len(self._handlers.get(key, []))