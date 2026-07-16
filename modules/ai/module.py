"""
Главный класс AI-модуля. Точка входа.
Наследует BaseModule, подписывается на EventBus.NEW_MESSAGE.
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger
from sqlalchemy import select

from modules.core.base_module import BaseModule
from modules.core.database import get_session
from modules.core.events import EventBus, EventType

from modules.ai.classifier import MessageClassifier, MessageType
from modules.ai.forbidden import ForbiddenTopicChecker
from modules.ai.llm_client import GeminiClient
from modules.ai.memory import MemoryManager
from modules.ai.models.ai_log import AILog, AnswerSource
from modules.ai.models.ai_settings import AISettings
from modules.ai.responder import Responder
from modules.ai.templates import TemplateEngine


class AIModule(BaseModule):
    """
    AI-консультант для покупателей FunPay.

    Жизненный цикл:
    - setup(): загрузка настроек, инициализация компонентов
    - start(): подписка на EventBus.NEW_MESSAGE
    - stop(): отписка

    Изоляция: каждый аккаунт имеет свои настройки,
    шаблоны и память клиентов.
    """

    def __init__(self, account_id: int) -> None:
        super().__init__(name=f"AI-{account_id}")
        self._account_id = account_id

        # Компоненты (инициализируются в setup)
        self._classifier = MessageClassifier()
        self._template_engine = TemplateEngine()
        self._memory_manager = MemoryManager()
        self._gemini_client = GeminiClient()
        self._forbidden_checker = ForbiddenTopicChecker()
        self._responder: Responder | None = None
        self._settings: AISettings | None = None

    # ─── Lifecycle ─────────────────────────────────────────────────

    async def setup(self) -> None:
        """Загружает настройки и инициализирует компоненты."""
        await super().setup()
        logger.info(f"[{self.name}] Setup начат")

        self._settings = await self._load_or_create_settings()

        # Настроить Gemini если есть ключ
        api_key = self._settings.get_gemini_api_key()
        if api_key:
            self._gemini_client.set_api_key(api_key)
        else:
            logger.warning(f"[{self.name}] Gemini API ключ не задан, работаем без LLM")

        # Настроить запрещённые темы
        self._forbidden_checker.update_topics(self._settings.get_forbidden_topics())

        # Создать Responder с текущими настройками
        self._responder = Responder(
            template_engine=self._template_engine,
            memory_manager=self._memory_manager,
            gemini_client=self._gemini_client,
            forbidden_checker=self._forbidden_checker,
            confidence_threshold=self._settings.get_confidence_threshold(),
        )

        # Записать дефолтные шаблоны если нет
        await self._template_engine.seed_defaults(self._account_id)

        logger.info(
            f"[{self.name}] Setup завершён. "
            f"Режим: {self._settings.mode}, "
            f"Gemini: {'вкл' if self._gemini_client.available else 'выкл'}"
        )

    async def start(self) -> None:
        """Подписывается на NEW_MESSAGE и запускает задачу очистки памяти."""
        await super().start()
        EventBus().subscribe(EventType.NEW_MESSAGE, self.on_message)
        logger.info(f"[{self.name}] Подписан на NEW_MESSAGE")

        # Запуск периодической очистки памяти (раз в сутки)
        asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        """Остановка модуля."""
        await super().stop()
        logger.info(f"[{self.name}] Остановлен")

    # ─── Обработчик события ────────────────────────────────────────

    async def on_message(self, data: dict[str, Any]) -> None:
        """
        Точка входа: обрабатывает новое сообщение от покупателя.

        Args:
            data: payload из EventBus.NEW_MESSAGE
        """
        account_id: int = data.get("account_id", self._account_id)

        # Фильтруем только свой аккаунт
        if account_id != self._account_id:
            return

        text: str = data.get("text", "").strip()
        buyer: str = data.get("author", "unknown")
        chat_id = data.get("chat_id")
        lot_info: dict[str, Any] | None = data.get("lot_info")

        if not text:
            return

        logger.info(f"[{self.name}] Сообщение от {buyer}: {text[:80]}")

        # Добавить в историю
        await self._memory_manager.add_incoming_message(account_id, buyer, text)

        # Классифицировать
        msg_type = self._classifier.classify(text)
        logger.debug(f"[{self.name}] Тип сообщения: {msg_type}")

        # Получить ответ
        result = await self._responder.build_response(
            account_id=account_id,
            buyer_username=buyer,
            message_type=msg_type,
            text=text,
            lot_info=lot_info,
        )

        # Отправить ответ покупателю (если есть)
        if result.response and result.source != AnswerSource.NO_ANSWER:
            await self._send_reply(data, result.response)

            # Сохранить в память
            await self._memory_manager.add_ai_reply(
                account_id=account_id,
                buyer_username=buyer,
                question=text,
                answer=result.response,
                source=result.source.value,
            )

        # Уведомить владельца если эскалация
        if result.escalated:
            await self._notify_owner(account_id, buyer, text, result.escalation_reason)

        # Логировать
        await self._write_log(
            account_id=account_id,
            buyer=buyer,
            text=text,
            msg_type=msg_type,
            lot_info=lot_info,
            result=result,
        )

    # ─── Отправка сообщений ────────────────────────────────────────

    async def _send_reply(self, event_data: dict[str, Any], message: str) -> None:
        """
        Отправляет ответ покупателю через FunPay API.

        Использует объект message_obj из payload.
        """
        try:
            message_obj = event_data.get("message_obj")
            stack = event_data.get("stack")

            if stack and message_obj:
                # Используем механизм Cardinal для отправки
                # (runner отправляет через cardinal.account)
                runner_tag: str = event_data.get("runner_tag", "")
                logger.info(
                    f"[{self.name}] Отправка ответа в чат {event_data.get('chat_id')}"
                )
                # NOTE: Конкретный вызов зависит от FunPayAPI/Cardinal
                # Пример: await cardinal.account.send_message(chat_id, message)
                # Здесь — заглушка для переопределения в плагине
                await self._do_send(event_data, message)
            else:
                logger.warning(f"[{self.name}] Нет message_obj/stack для отправки")

        except Exception as e:
            logger.error(f"[{self.name}] Ошибка отправки ответа: {e}")

    async def _do_send(self, event_data: dict[str, Any], message: str) -> None:
        """
        Переопределяется при установке через плагин Cardinal,
        когда есть доступ к cardinal.account.send_message().
        """
        logger.debug(f"[{self.name}] [_do_send] message='{message[:60]}'")

    async def send_manual_reply(
        self,
        account_id: int,
        buyer_chat_id: str,
        message: str,
    ) -> bool:
        """
        Ручная отправка ответа (из Telegram-панели).

        Args:
            account_id: ID аккаунта
            buyer_chat_id: ID чата FunPay
            message: текст сообщения

        Returns:
            True если успешно
        """
        try:
            logger.info(
                f"[{self.name}] Ручной ответ в чат {buyer_chat_id}: {message[:60]}"
            )
            # Логируем как ручной ответ
            async with get_session() as session:
                log = AILog(
                    account_id=account_id,
                    buyer_username=buyer_chat_id,
                    incoming_message="[MANUAL REPLY]",
                    message_type="MANUAL",
                    answer_source=AnswerSource.ESCALATED.value,
                    final_response=message,
                    escalated_to_owner=False,
                )
                session.add(log)
            return True
        except Exception as e:
            logger.error(f"[{self.name}] Ошибка ручного ответа: {e}")
            return False

    # ─── Уведомление владельца ─────────────────────────────────────

    async def _notify_owner(
        self,
        account_id: int,
        buyer: str,
        question: str,
        reason: str | None,
    ) -> None:
        """
        Уведомляет владельца аккаунта об эскалации.
        Сейчас — через EventBus (Telegram-модуль подхватит).
        """
        logger.info(
            f"[{self.name}] Эскалация владельцу. "
            f"Покупатель: {buyer}, вопрос: {question[:60]}, причина: {reason}"
        )
        EventBus().emit(
            "AI_ESCALATION",
            {
                "account_id": account_id,
                "buyer": buyer,
                "question": question,
                "reason": reason,
            },
        )

    # ─── Логирование в БД ─────────────────────────────────────────

    async def _write_log(
        self,
        account_id: int,
        buyer: str,
        text: str,
        msg_type: MessageType,
        lot_info: dict[str, Any] | None,
        result: "ResponderResult",
    ) -> None:
        """Пишет запись лога в таблицу ai_logs."""
        try:
            async with get_session() as session:
                log = AILog(
                    account_id=account_id,
                    buyer_username=buyer,
                    incoming_message=text,
                    message_type=msg_type.value,
                    answer_source=result.source.value,
                    llm_called=result.llm_called,
                    final_response=result.response,
                    escalated_to_owner=result.escalated,
                    escalation_reason=result.escalation_reason,
                )
                if lot_info:
                    log.set_lot_context(lot_info)
                session.add(log)
        except Exception as e:
            logger.error(f"[{self.name}] Ошибка записи лога: {e}")

    # ─── Вспомогательные ───────────────────────────────────────────

    async def _load_or_create_settings(self) -> AISettings:
        """Загружает настройки из БД или создаёт дефолтные."""
        async with get_session() as session:
            result = await session.execute(
                select(AISettings).where(AISettings.account_id == self._account_id)
            )
            settings = result.scalar_one_or_none()

            if settings is None:
                settings = AISettings(account_id=self._account_id)
                session.add(settings)
                logger.info(f"[{self.name}] Созданы дефолтные настройки")

            return settings

    async def _cleanup_loop(self) -> None:
        """Периодически чистит устаревшую память (раз в 24 часа)."""
        while True:
            await asyncio.sleep(86400)  # 24 часа
            try:
                deleted = await self._memory_manager.cleanup_expired()
                logger.info(f"[{self.name}] Плановая очистка: удалено {deleted} записей")
            except Exception as e:
                logger.error(f"[{self.name}] Ошибка очистки памяти: {e}")