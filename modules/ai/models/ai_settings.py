"""
ORM-модель настроек AI для аккаунта FunPay.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from modules.core.database import Base
from modules.core.encryption import Encryption


class AISettings(Base):
    """
    Настройки AI-модуля для конкретного аккаунта.

    Attributes:
        id: первичный ключ
        account_id: FK на аккаунт FunPay
        mode: режим работы ('careful' | 'standard')
        gemini_api_key_encrypted: зашифрованный API ключ Gemini
        forbidden_topics: JSON-список запрещённых тем
        created_at: дата создания
        updated_at: дата обновления
    """

    __tablename__ = "ai_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="standard")
    gemini_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    forbidden_topics: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=json.dumps(
            ["поставщики", "lolzteam", "закупка", "автоматизация",
             "внутренние процессы", "где покупаешь"],
            ensure_ascii=False
        )
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # ─── helpers ───────────────────────────────────────────────────

    def get_gemini_api_key(self) -> str | None:
        """Расшифровывает и возвращает Gemini API ключ."""
        if not self.gemini_api_key_encrypted:
            return None
        return Encryption().decrypt(self.gemini_api_key_encrypted)

    def set_gemini_api_key(self, key: str) -> None:
        """Шифрует и сохраняет Gemini API ключ."""
        self.gemini_api_key_encrypted = Encryption().encrypt(key)

    def get_forbidden_topics(self) -> list[str]:
        """Возвращает список запрещённых тем."""
        return json.loads(self.forbidden_topics)

    def set_forbidden_topics(self, topics: list[str]) -> None:
        """Сохраняет список запрещённых тем в JSON."""
        self.forbidden_topics = json.dumps(topics, ensure_ascii=False)

    def get_confidence_threshold(self) -> float:
        """Возвращает порог уверенности по режиму."""
        return 0.8 if self.mode == "careful" else 0.5