"""
modules/cardinal_bridge/hooks.py
─────────────────────────────────
Мост между Cardinal и системой событий Cardinal_Multi.

ПРИНЦИП РАБОТЫ:
    1. Создаём файл-плагин plugins/cardinal_multi_bridge.py
       (Cardinal сам его загрузит через BIND_TO_PRE_INIT)
    2. Плагин получает экземпляр Cardinal и добавляет наши хэндлеры
       в cardinal.new_order_handlers, cardinal.new_message_handlers и др.
    3. При срабатывании Cardinal-хэндлера → emit() в наш EventBus

НЕ ИЗМЕНЯЕТ:
    - cardinal.py (ни одной строки)
    - FunPayAPI/ (ни одной строки)
    - tg_bot/ (ни одной строки)
    - plugins/ (только добавляем новый файл)

СОВМЕСТИМОСТЬ:
    Все существующие плагины Cardinal работают без изменений.
    Наши хэндлеры добавляются ПОСЛЕ стандартных (append, не insert).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

# ─── Импорты Cardinal (доступны только когда Cardinal уже запущен) ─────────────
try:
    from FunPayAPI.updater.events import (
        NewOrderEvent,
        NewMessageEvent,
        OrderStatusChangedEvent,
        LastChatMessageChangedEvent,
        InitialOrderEvent,
        OrdersListChangedEvent,
    )
    from FunPayAPI.common.enums import EventTypes as FunPayEventTypes
    FUNPAY_API_AVAILABLE = True
except ImportError:
    FUNPAY_API_AVAILABLE = False
    logger.warning(
        "FunPayAPI недоступен при импорте hooks.py. "
        "Убедитесь, что Cardinal запущен из правильной директории."
    )

from modules.core.events import EventBus, EventType

if TYPE_CHECKING:
    # Тип только для аннотаций — не импортируем реально
    from cardinal import Cardinal  # type: ignore[import]

# ─── Константы ────────────────────────────────────────────────────────────────
MULTI_PLUGIN_UUID = "CARDINAL_MULTI_BRIDGE"
PLUGIN_FILE = Path("plugins/cardinal_multi_bridge.py")


# ─── Хэндлеры Cardinal-событий ────────────────────────────────────────────────

def _make_new_order_handler(account_id: int):
    """
    Фабрика хэндлера нового заказа.

    :param account_id: ID аккаунта в нашей БД.
    :return: хэндлер-функция совместимая с Cardinal.
    """
    def handler(event: "NewOrderEvent") -> None:
        """Хэндлер нового заказа Cardinal → EventBus."""
        try:
            bus = EventBus()
            data = {
                "account_id":  account_id,
                "order_id":    event.order.id,
                "order_short": event.order,     # полный объект FunPayAPI
                "runner_tag":  event.runner_tag,
            }
            bus.emit(EventType.NEW_ORDER, data)
            logger.debug(
                "[Bridge] NEW_ORDER: account_id={}, order_id={}",
                account_id,
                event.order.id,
            )
        except Exception as exc:
            logger.error("[Bridge] Ошибка в NEW_ORDER хэндлере: {}", exc)

    return handler


def _make_new_message_handler(account_id: int):
    """
    Фабрика хэндлера нового сообщения.

    :param account_id: ID аккаунта в нашей БД.
    :return: хэндлер-функция совместимая с Cardinal.
    """
    def handler(event: "NewMessageEvent") -> None:
        """Хэндлер нового сообщения Cardinal → EventBus."""
        try:
            bus = EventBus()
            data = {
                "account_id":  account_id,
                "message_id":  event.message.id,
                "chat_id":     event.message.chat_id,
                "text":        event.message.text,
                "author":      event.message.author,
                "author_id":   event.message.author_id,
                "message_obj": event.message,   # полный объект FunPayAPI
                "stack":       event.stack,
                "runner_tag":  event.runner_tag,
            }
            bus.emit(EventType.NEW_MESSAGE, data)
            logger.debug(
                "[Bridge] NEW_MESSAGE: account_id={}, chat_id={}, author={}",
                account_id,
                event.message.chat_id,
                event.message.author,
            )
        except Exception as exc:
            logger.error("[Bridge] Ошибка в NEW_MESSAGE хэндлере: {}", exc)

    return handler


def _make_order_status_handler(account_id: int):
    """
    Фабрика хэндлера изменения статуса заказа.

    :param account_id: ID аккаунта в нашей БД.
    :return: хэндлер-функция совместимая с Cardinal.
    """
    def handler(event: "OrderStatusChangedEvent") -> None:
        """Хэндлер изменения статуса заказа Cardinal → EventBus."""
        try:
            bus = EventBus()
            data = {
                "account_id":  account_id,
                "order_id":    event.order.id,
                "order_short": event.order,
                "runner_tag":  event.runner_tag,
            }

            # Определяем тип эмита по статусу
            from FunPayAPI.common.enums import OrderStatuses
            if event.order.status == OrderStatuses.CLOSED:
                bus.emit(EventType.ORDER_COMPLETED, data)
                logger.debug(
                    "[Bridge] ORDER_COMPLETED: account_id={}, order_id={}",
                    account_id, event.order.id,
                )
            else:
                bus.emit(EventType.ORDER_STATUS_CHANGED, data)
                logger.debug(
                    "[Bridge] ORDER_STATUS_CHANGED: account_id={}, order_id={}, status={}",
                    account_id, event.order.id, event.order.status,
                )

        except Exception as exc:
            logger.error("[Bridge] Ошибка в ORDER_STATUS хэндлере: {}", exc)

    return handler


def _make_last_chat_message_handler(account_id: int):
    """
    Фабрика хэндлера изменения последнего сообщения в чате.

    :param account_id: ID аккаунта в нашей БД.
    :return: хэндлер-функция совместимая с Cardinal.
    """
    def handler(event: "LastChatMessageChangedEvent") -> None:
        """Хэндлер LAST_CHAT_MESSAGE_CHANGED Cardinal → EventBus."""
        try:
            bus = EventBus()
            data = {
                "account_id": account_id,
                "chat_id":    event.chat.id,
                "chat_obj":   event.chat,
                "runner_tag": event.runner_tag,
            }
            bus.emit(EventType.LOT_CHANGED, data)
        except Exception as exc:
            logger.error("[Bridge] Ошибка в LAST_CHAT_MESSAGE хэндлере: {}", exc)

    return handler


# ─── Установка хуков ──────────────────────────────────────────────────────────

def install_hooks(cardinal: "Cardinal", account_id: int) -> None:
    """
    Устанавливает хуки на события Cardinal для указанного аккаунта.

    Добавляет наши хэндлеры в списки Cardinal.
    Не изменяет существующие хэндлеры.
    Безопасно для всех плагинов.

    :param cardinal: экземпляр Cardinal.
    :param account_id: ID аккаунта в нашей БД (из таблицы accounts).
    """
    if not FUNPAY_API_AVAILABLE:
        logger.error(
            "[Bridge] FunPayAPI недоступен. Хуки не установлены для account_id={}.",
            account_id,
        )
        return

    hooks_installed: list[str] = []

    # ── NEW_ORDER ─────────────────────────────────────────────────────────────
    if hasattr(cardinal, "new_order_handlers"):
        cardinal.new_order_handlers.append(
            (_make_new_order_handler(account_id), MULTI_PLUGIN_UUID)
        )
        hooks_installed.append("NEW_ORDER")
    else:
        logger.warning(
            "[Bridge] cardinal.new_order_handlers не найден. "
            "Проверь версию Cardinal."
        )

    # ── NEW_MESSAGE ───────────────────────────────────────────────────────────
    if hasattr(cardinal, "new_message_handlers"):
        cardinal.new_message_handlers.append(
            (_make_new_message_handler(account_id), MULTI_PLUGIN_UUID)
        )
        hooks_installed.append("NEW_MESSAGE")
    else:
        logger.warning("[Bridge] cardinal.new_message_handlers не найден.")

    # ── ORDER_STATUS_CHANGED ──────────────────────────────────────────────────
    if hasattr(cardinal, "order_status_changed_handlers"):
        cardinal.order_status_changed_handlers.append(
            (_make_order_status_handler(account_id), MULTI_PLUGIN_UUID)
        )
        hooks_installed.append("ORDER_STATUS_CHANGED")
    else:
        logger.debug(
            "[Bridge] cardinal.order_status_changed_handlers не найден — пропуск."
        )

    # ── LAST_CHAT_MESSAGE_CHANGED ─────────────────────────────────────────────
    if hasattr(cardinal, "last_chat_message_changed_handlers"):
        cardinal.last_chat_message_changed_handlers.append(
            (_make_last_chat_message_handler(account_id), MULTI_PLUGIN_UUID)
        )
        hooks_installed.append("LAST_CHAT_MESSAGE_CHANGED")
    else:
        logger.debug(
            "[Bridge] cardinal.last_chat_message_changed_handlers не найден — пропуск."
        )

    logger.info(
        "[Bridge] Хуки установлены для account_id={}: {}",
        account_id,
        ", ".join(hooks_installed),
    )


def remove_hooks(cardinal: "Cardinal") -> None:
    """
    Удаляет все наши хуки из Cardinal (при остановке аккаунта).

    :param cardinal: экземпляр Cardinal.
    """
    handler_lists = [
        "new_order_handlers",
        "new_message_handlers",
        "order_status_changed_handlers",
        "last_chat_message_changed_handlers",
    ]

    removed_count = 0
    for attr in handler_lists:
        if hasattr(cardinal, attr):
            handlers: list = getattr(cardinal, attr)
            original_len = len(handlers)
            # Удаляем все хэндлеры с нашим UUID
            setattr(
                cardinal,
                attr,
                [(h, uid) for h, uid in handlers if uid != MULTI_PLUGIN_UUID],
            )
            removed_count += original_len - len(getattr(cardinal, attr))

    logger.info("[Bridge] Удалено {} хуков из Cardinal.", removed_count)


# ─── Генератор файла плагина для основного Cardinal ───────────────────────────

def generate_plugin_file(account_id: int = 1) -> None:
    """
    Создаёт файл plugins/cardinal_multi_bridge.py.

    Этот файл — стандартный плагин Cardinal с BIND_TO_PRE_INIT.
    Cardinal сам его загружает при старте.
    Это самый чистый способ интеграции.

    :param account_id: ID основного аккаунта (обычно 1).
    """
    PLUGIN_FILE.parent.mkdir(parents=True, exist_ok=True)

    content = f'''"""
Cardinal_Multi Bridge Plugin
Автоматически сгенерировано Cardinal_Multi.
НЕ РЕДАКТИРОВАТЬ ВРУЧНУЮ.

Этот файл — точка входа Cardinal_Multi в систему плагинов Cardinal.
Он загружается Cardinal автоматически из папки plugins/.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cardinal import Cardinal

import sys
import os
# Добавляем корень проекта в sys.path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

MULTI_ACCOUNT_ID = {account_id}  # ID основного аккаунта

NAME = "Cardinal Multi Bridge"
VERSION = "1.0.0"
DESCRIPTION = "Мост между Cardinal и Cardinal_Multi"
CREDITS = "Cardinal_Multi"
UUID = "CARDINAL_MULTI_BRIDGE_PLUGIN"
SETTINGS_PAGE = False


def init_cardinal_multi(cardinal: "Cardinal", *args) -> None:
    """
    Инициализация моста Cardinal_Multi.
    Вызывается Cardinal при загрузке плагина.
    """
    try:
        from modules.cardinal_bridge.hooks import install_hooks
        install_hooks(cardinal, MULTI_ACCOUNT_ID)
    except Exception as exc:
        # Ошибка моста НЕ должна останавливать Cardinal
        import logging
        logging.getLogger("FPC").error(
            f"[Cardinal_Multi] Не удалось установить хуки: {{exc}}"
        )


BIND_TO_PRE_INIT = [init_cardinal_multi]
'''

    PLUGIN_FILE.write_text(content, encoding="utf-8")
    logger.info("[Bridge] Файл плагина создан: {}", PLUGIN_FILE)