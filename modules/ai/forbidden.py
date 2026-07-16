"""
Проверка запрещённых тем в сообщениях покупателей.
"""

from __future__ import annotations

from loguru import logger


DEFAULT_FORBIDDEN: list[str] = [
    "поставщики",
    "lolzteam",
    "закупка",
    "автоматизация",
    "внутренние процессы",
    "где покупаешь",
]


class ForbiddenTopicChecker:
    """
    Проверяет, содержит ли сообщение запрещённые темы.

    Темы настраиваются через Telegram и загружаются из БД.
    По умолчанию используется DEFAULT_FORBIDDEN.
    """

    def __init__(self, forbidden_topics: list[str] | None = None) -> None:
        self._topics: list[str] = forbidden_topics or DEFAULT_FORBIDDEN

    def update_topics(self, topics: list[str]) -> None:
        """Обновляет список запрещённых тем (вызывается из Telegram-панели)."""
        self._topics = topics
        logger.debug(f"[AI:Forbidden] Обновлены запрещённые темы: {topics}")

    def is_forbidden(self, text: str) -> bool:
        """
        Проверяет наличие запрещённых тем в тексте.

        Args:
            text: текст входящего сообщения

        Returns:
            True если тема запрещена
        """
        lower = text.lower()
        for topic in self._topics:
            if topic.lower() in lower:
                logger.debug(f"[AI:Forbidden] Найдена запрещённая тема: '{topic}'")
                return True
        return False

    def get_topics(self) -> list[str]:
        return list(self._topics)