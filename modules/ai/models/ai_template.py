"""
ORM-модель шаблона ответа AI.
"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import Integer, String, Text, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from modules.core.database import Base


class AITemplate(Base):
    """
    Шаблон ответа: набор триггерных слов → текст ответа.

    Attributes:
        id: первичный ключ
        account_id: FK на аккаунт
        name: название шаблона
        trigger_keywords: JSON-список слов-триггеров
        response_text: текст ответа
        is_enabled: включён ли шаблон
        priority: приоритет (меньше — выше)
        created_at / updated_at: временны́е метки
    """

    __tablename__ = "ai_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    trigger_keywords: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def get_keywords(self) -> list[str]:
        """Возвращает список ключевых слов."""
        return json.loads(self.trigger_keywords)

    def set_keywords(self, keywords: list[str]) -> None:
        """Сохраняет ключевые слова в JSON."""
        self.trigger_keywords = json.dumps(keywords, ensure_ascii=False)