"""
ORM-модель лога AI-обработки сообщения.
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import Integer, String, Text, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from modules.core.database import Base


class AnswerSource(str, Enum):
    """Источник финального ответа."""
    GREETING = "greeting"
    BOT_QUESTION = "bot_question"
    TEMPLATE = "template"
    LOT_INFO = "lot_info"
    USER_INSTRUCTIONS = "user_instructions"
    BUYER_HISTORY = "buyer_history"
    BUYER_PURCHASES = "buyer_purchases"
    GEMINI = "gemini"
    ESCALATED = "escalated"
    NO_ANSWER = "no_answer"


class AILog(Base):
    """
    Лог каждого обработанного AI-модулем сообщения.
    """

    __tablename__ = "ai_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    buyer_username: Mapped[str] = mapped_column(String(200), nullable=False)
    incoming_message: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(50), nullable=False)
    lot_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_source: Mapped[str] = mapped_column(
        String(50), nullable=False, default=AnswerSource.NO_ANSWER.value
    )
    llm_called: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    final_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalated_to_owner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    escalation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def set_lot_context(self, ctx: dict[str, Any]) -> None:
        self.lot_context = json.dumps(ctx, ensure_ascii=False)

    def get_lot_context(self) -> dict[str, Any]:
        if not self.lot_context:
            return {}
        return json.loads(self.lot_context)