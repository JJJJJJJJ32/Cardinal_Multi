"""
Классификатор типа входящего сообщения.
Работает без LLM — только на основе правил и ключевых слов.
"""

from __future__ import annotations

from enum import Enum


class MessageType(str, Enum):
    """Тип входящего сообщения."""
    GREETING = "GREETING"
    BOT_QUESTION = "BOT_QUESTION"
    LOT_QUESTION = "LOT_QUESTION"
    GENERAL_QUESTION = "GENERAL_QUESTION"
    NO_ANSWER_NEEDED = "NO_ANSWER_NEEDED"


# ─── Словари для классификации ─────────────────────────────────────────

GREETINGS: frozenset[str] = frozenset({
    "привет", "здравствуй", "здравствуйте",
    "добрый день", "добрый вечер", "доброе утро",
    "хай", "хей", "hello", "hi", "ку", "прив",
})

BOT_PHRASES: frozenset[str] = frozenset({
    "ты бот", "это бот", "бот?", "живой?",
    "человек?", "автоответ", "ты живой", "это автоответ",
})

QUESTION_WORDS: frozenset[str] = frozenset({
    "что", "как", "где", "когда", "почему", "зачем",
    "можно", "есть ли", "работает ли", "подойдёт",
    "сколько", "какой", "какие", "который",
})


class MessageClassifier:
    """
    Классифицирует входящие сообщения без использования LLM.

    Порядок проверки:
    1. Приветствие
    2. Вопрос о боте
    3. Вопросительные слова / знак '?'
    4. Иначе — NO_ANSWER_NEEDED
    """

    def classify(self, text: str) -> MessageType:
        """
        Определяет тип сообщения по тексту.

        Args:
            text: входящий текст сообщения

        Returns:
            MessageType
        """
        normalized = text.lower().strip()

        if self._is_greeting(normalized):
            return MessageType.GREETING

        if self._is_bot_question(normalized):
            return MessageType.BOT_QUESTION

        if self._is_question(normalized):
            return self._resolve_question_type(normalized)

        return MessageType.NO_ANSWER_NEEDED

    # ─── private ───────────────────────────────────────────────────

    def _is_greeting(self, text: str) -> bool:
        """Точное совпадение или начало сообщения."""
        if text in GREETINGS:
            return True
        for g in GREETINGS:
            if text.startswith(g):
                return True
        return False

    def _is_bot_question(self, text: str) -> bool:
        return any(phrase in text for phrase in BOT_PHRASES)

    def _is_question(self, text: str) -> bool:
        if "?" in text:
            return True
        words = set(text.split())
        return bool(words & QUESTION_WORDS)

    def _resolve_question_type(self, text: str) -> MessageType:
        """
        Уточняет — вопрос по лоту или общий.
        В базовой реализации всё возвращается как LOT_QUESTION,
        расширяется через контекст лота в Responder.
        """
        return MessageType.LOT_QUESTION