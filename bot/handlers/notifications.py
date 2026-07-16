"""
Модуль уведомлений.

Логика: подписывается на EventBus и отправляет сообщения в Telegram.

ВАЖНО (из digest репозитория):
  EventBus — in-memory singleton. Если Cardinal запущен как subprocess,
  события от него НЕ приходят автоматически в этот процесс.
  
  Текущий подход:
    - Регистрируем хендлеры на EventBus (работает если бот и Cardinal в одном процессе).
    - Для subprocess-архитектуры — необходимо добавить IPC (DB polling / Redis pub-sub).
  
  Заглушка для IPC polling реализована ниже (events_log в БД).
"""

import asyncio
from aiogram import Bot, Router, F
from aiogram.types import CallbackQuery
from loguru import logger

from modules.core.events import EventBus, EventType

router = Router(name="notifications")


class NotificationService:
    """
    Сервис уведомлений для одного bot+chat_id.
    Регистрирует хендлеры на EventBus и отправляет сообщения.
    """

    def __init__(self, bot: Bot, chat_id: int, account_id: int) -> None:
        self.bot = bot
        self.chat_id = chat_id
        self.account_id = account_id
        self._enabled: dict[str, bool] = {
            EventType.NEW_ORDER: True,
            EventType.SEARCH_STARTED: True,
            EventType.ITEM_PURCHASED: True,
            EventType.ITEM_DELIVERED: True,
            EventType.ACCOUNT_ERROR: True,
            EventType.BALANCE_LOW: True,
            EventType.NEW_MESSAGE: True,
        }
        self._bus = EventBus()

    def start(self) -> None:
        """Подписываемся на все события."""
        for event_type in self._enabled:
            self._bus.subscribe(event_type, self._make_handler(event_type))
        logger.info(
            f"NotificationService запущен: account_id={self.account_id}, "
            f"chat_id={self.chat_id}"
        )

    def _make_handler(self, event_type: str):
        async def handler(data: dict) -> None:
            if not self._enabled.get(event_type, True):
                return
            if data.get("account_id") != self.account_id:
                return  # не наш аккаунт
            text = self._format_event(event_type, data)
            try:
                await self.bot.send_message(self.chat_id, text, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления {event_type}: {e}")
        return handler

    def _format_event(self, event_type: str, data: dict) -> str:
        templates = {
            EventType.NEW_ORDER: (
                "📦 <b>Новый заказ!</b>\n"
                "Заказ: #{order_id}\n"
                "Лот: {lot_title}\n"
                "Покупатель: {buyer}"
            ),
            EventType.SEARCH_STARTED: (
                "🔍 <b>Поиск начат</b>\n"
                "Лот: {lot_title}"
            ),
            EventType.ITEM_PURCHASED: (
                "🛒 <b>Покупка выполнена!</b>\n"
                "Лот: {lot_title}\n"
                "Цена: {price} руб"
            ),
            EventType.ITEM_DELIVERED: (
                "✅ <b>Товар выдан</b>\n"
                "Заказ: #{order_id}"
            ),
            EventType.ACCOUNT_ERROR: (
                "❌ <b>Ошибка аккаунта!</b>\n"
                "{error}"
            ),
            EventType.BALANCE_LOW: (
                "💸 <b>Баланс ниже порога!</b>\n"
                "Текущий баланс: {balance} руб\n"
                "Порог: {threshold} руб"
            ),
            EventType.NEW_MESSAGE: (
                "💬 <b>Новое сообщение</b>\n"
                "От: {buyer}\n"
                "Текст: {text}"
            ),
        }
        template = templates.get(event_type, "⚡ Событие: {event_type}")
        try:
            return template.format(event_type=event_type, **data)
        except KeyError:
            return f"⚡ <b>{event_type}</b>\n{data}"

    def set_enabled(self, event_type: str, enabled: bool) -> None:
        self._enabled[event_type] = enabled

    # ─── Polling IPC (для subprocess-архитектуры) ──────────────────────────
    async def start_db_polling(self, poll_interval: float = 2.0) -> None:
        """
        Альтернатива EventBus для subprocess-режима.
        Читает новые записи из events_log в БД и отправляет уведомления.
        
        TODO: реализовать чтение из events_log:
          SELECT * FROM events_log 
          WHERE account_id = ? AND id > last_seen_id
          ORDER BY id ASC
        """
        logger.info("DB-polling для уведомлений запущен (заглушка)")
        last_id = 0
        while True:
            try:
                # Здесь будет реальный запрос к events_log
                new_events = []  # заглушка
                for event in new_events:
                    if event["id"] > last_id:
                        last_id = event["id"]
                        text = self._format_event(
                            event["event_type"], event.get("data", {})
                        )
                        await self.bot.send_message(
                            self.chat_id, text, parse_mode="HTML"
                        )
            except Exception as e:
                logger.error(f"Ошибка DB-polling: {e}")
            await asyncio.sleep(poll_interval)