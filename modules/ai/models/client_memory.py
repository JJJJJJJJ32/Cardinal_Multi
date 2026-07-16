"""
ORM-модель памяти клиента (покупателя).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from modules.core.database import Base

MEMORY_DAYS: int = 30
MAX_MESSAGES: int = 50


class ClientMemory(Base):
    """
    Память о покупателе: история сообщений, покупок и ответов AI.

    Атрибуты хранятся сериализованными в JSON.
    Изолировано по account_id.
    """

    __tablename__ = "client_memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    buyer_username: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    messages_history: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    purchases_history: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    ai_responses_history: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # ─── messages ──────────────────────────────────────────────────

    def get_messages(self) -> list[dict[str, Any]]:
        return json.loads(self.messages_history)

    def add_message(self, role: str, text: str) -> None:
        """Добавляет сообщение (role: 'buyer'|'ai'), хранит последние MAX_MESSAGES."""
        msgs = self.get_messages()
        msgs.append({"role": role, "text": text, "ts": datetime.utcnow().isoformat()})
        self.messages_history = json.dumps(msgs[-MAX_MESSAGES:], ensure_ascii=False)
        self.last_seen = datetime.utcnow()

    # ─── purchases ─────────────────────────────────────────────────

    def get_purchases(self) -> list[dict[str, Any]]:
        return json.loads(self.purchases_history)

    def add_purchase(self, lot_id: str, lot_title: str, amount: float) -> None:
        purchases = self.get_purchases()
        purchases.append({
            "lot_id": lot_id,
            "lot_title": lot_title,
            "amount": amount,
            "ts": datetime.utcnow().isoformat(),
        })
        self.purchases_history = json.dumps(purchases, ensure_ascii=False)

    # ─── ai responses ──────────────────────────────────────────────

    def get_ai_responses(self) -> list[dict[str, Any]]:
        return json.loads(self.ai_responses_history)

    def add_ai_response(self, question: str, answer: str, source: str) -> None:
        responses = self.get_ai_responses()
        responses.append({
            "question": question,
            "answer": answer,
            "source": source,
            "ts": datetime.utcnow().isoformat(),
        })
        self.ai_responses_history = json.dumps(responses, ensure_ascii=False)

    # ─── helpers ───────────────────────────────────────────────────

    def is_expired(self) -> bool:
        """Возвращает True если запись старше MEMORY_DAYS дней."""
        return datetime.utcnow() - self.last_seen > timedelta(days=MEMORY_DAYS)

    def has_bought_before(self) -> bool:
        return len(self.get_purchases()) > 0

    def already_answered(self, question: str) -> str | None:
        """
        Проверяет, был ли уже дан ответ на похожий вопрос.
        Простое сравнение по вхождению слов.
        Возвращает текст прошлого ответа или None.
        """
        q_lower = question.lower()
        for resp in self.get_ai_responses():
            if resp.get("question", "").lower() == q_lower:
                return resp.get("answer")
        return None