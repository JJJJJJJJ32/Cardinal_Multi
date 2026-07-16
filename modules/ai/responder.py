"""
Главная логика построения ответа по приоритетам:
1. Шаблоны
2. Информация лота
3. Инструкции
4. История покупателя
5. История покупок
6. Gemini
7. Эскалация
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from modules.ai.classifier import MessageType
from modules.ai.forbidden import ForbiddenTopicChecker
from modules.ai.llm_client import GeminiClient
from modules.ai.memory import MemoryManager
from modules.ai.models.ai_log import AnswerSource
from modules.ai.templates import TemplateEngine


# ─── Фиксированные ответы ──────────────────────────────────────────────

GREETING_RESPONSE = (
    "Здравствуйте! Если у вас есть вопросы по товару, я постараюсь помочь."
)
BOT_RESPONSE = (
    "Я помощник продавца и помогаю отвечать на вопросы по товарам."
)
UNCERTAIN_RESPONSE = (
    "Я помощник продавца и не уверен в ответе. Передал вопрос владельцу."
)


@dataclass
class ResponderResult:
    """Результат работы Responder."""
    response: str | None = None
    source: AnswerSource = AnswerSource.NO_ANSWER
    llm_called: bool = False
    escalated: bool = False
    escalation_reason: str | None = None


class Responder:
    """
    Выбирает и строит ответ покупателю по цепочке приоритетов.

    Инициализируется с компонентами:
    - template_engine: поиск по шаблонам
    - memory_manager: история покупателя
    - gemini_client: LLM последнего шанса
    - forbidden_checker: фильтр запрещённых тем
    """

    def __init__(
        self,
        template_engine: TemplateEngine,
        memory_manager: MemoryManager,
        gemini_client: GeminiClient,
        forbidden_checker: ForbiddenTopicChecker,
        confidence_threshold: float = 0.5,
    ) -> None:
        self._templates = template_engine
        self._memory = memory_manager
        self._gemini = gemini_client
        self._forbidden = forbidden_checker
        self._confidence_threshold = confidence_threshold

    async def build_response(
        self,
        account_id: int,
        buyer_username: str,
        message_type: MessageType,
        text: str,
        lot_info: dict[str, Any] | None = None,
    ) -> ResponderResult:
        """
        Строит ответ по приоритетам.

        Args:
            account_id: ID аккаунта
            buyer_username: имя покупателя
            message_type: тип сообщения (из классификатора)
            text: текст сообщения
            lot_info: контекст лота (из FunPay)

        Returns:
            ResponderResult
        """

        # ── 0. Специальные типы ──────────────────────────────────
        if message_type == MessageType.GREETING:
            return ResponderResult(
                response=GREETING_RESPONSE,
                source=AnswerSource.GREETING,
            )

        if message_type == MessageType.BOT_QUESTION:
            return ResponderResult(
                response=BOT_RESPONSE,
                source=AnswerSource.BOT_QUESTION,
            )

        if message_type == MessageType.NO_ANSWER_NEEDED:
            return ResponderResult(source=AnswerSource.NO_ANSWER)

        # ── 1. Запрещённые темы → молчать ───────────────────────
        if self._forbidden.is_forbidden(text):
            logger.info(f"[AI:Responder] Запрещённая тема — молчим. user={buyer_username}")
            return ResponderResult(source=AnswerSource.NO_ANSWER)

        # ── 2. Шаблоны ───────────────────────────────────────────
        match = await self._templates.find(account_id, text)
        if match.found:
            logger.info(f"[AI:Responder] Шаблон '{match.template_name}'")
            return ResponderResult(
                response=match.response,
                source=AnswerSource.TEMPLATE,
            )

        # ── 3. Информация лота ───────────────────────────────────
        if lot_info:
            lot_answer = self._try_lot_info(text, lot_info)
            if lot_answer:
                return ResponderResult(
                    response=lot_answer,
                    source=AnswerSource.LOT_INFO,
                )

        # ── 4. История покупателя (уже отвечали?) ────────────────
        cached_answer = await self._memory.already_answered(account_id, buyer_username, text)
        if cached_answer:
            logger.debug(f"[AI:Responder] Ответ из истории покупателя")
            return ResponderResult(
                response=cached_answer,
                source=AnswerSource.BUYER_HISTORY,
            )

        # ── 5. Покупки покупателя (учитываем контекст) ───────────
        mem_ctx = await self._memory.get_context_for_llm(account_id, buyer_username)

        # ── 6. Gemini ─────────────────────────────────────────────
        if self._gemini.available:
            logger.info(f"[AI:Responder] Вызываем Gemini для user={buyer_username}")
            answer, is_confident = await self._gemini.ask(
                question=text,
                lot_info=lot_info,
                history=mem_ctx.get("last_messages", []),
                confidence_threshold=self._confidence_threshold,
            )

            if answer and is_confident:
                return ResponderResult(
                    response=answer,
                    source=AnswerSource.GEMINI,
                    llm_called=True,
                )

            # Gemini неуверен → эскалация
            return ResponderResult(
                response=UNCERTAIN_RESPONSE,
                source=AnswerSource.ESCALATED,
                llm_called=True,
                escalated=True,
                escalation_reason="Gemini не уверен в ответе",
            )

        # ── 7. Нет Gemini → эскалация ────────────────────────────
        return ResponderResult(
            response=UNCERTAIN_RESPONSE,
            source=AnswerSource.ESCALATED,
            escalated=True,
            escalation_reason="Нет ключа Gemini, ответ не найден",
        )

    # ─── private helpers ───────────────────────────────────────────

    def _try_lot_info(
        self, text: str, lot_info: dict[str, Any]
    ) -> str | None:
        """
        Пробует найти ответ в полях лота.
        Базовая реализация: ищет description.
        Расширяемо под конкретную структуру FunPayAPI.
        """
        description: str = lot_info.get("description", "")
        if not description:
            return None

        lower_text = text.lower()
        # Если вопрос про цену и в лоте есть цена
        if any(w in lower_text for w in ["сколько стоит", "цена", "стоимость"]):
            price = lot_info.get("price")
            if price:
                return f"Цена товара: {price} руб."

        # Если в описании лота упоминается ключевое слово вопроса
        question_words = [w for w in lower_text.split() if len(w) > 3]
        for word in question_words:
            if word in description.lower():
                return None  # Отдадим в Gemini с контекстом лота

        return None