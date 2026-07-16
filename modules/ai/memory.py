"""
Менеджер памяти клиентов (покупателей).
Изолировано по account_id. Хранит 30 дней.
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from sqlalchemy import select, delete

from modules.core.database import get_session
from modules.ai.models.client_memory import ClientMemory


class MemoryManager:
    """
    CRUD для ClientMemory.

    Изоляция: все запросы включают фильтр account_id.
    Автоочистка: удаляет записи старше 30 дней.
    """

    async def get_or_create(
        self, account_id: int, buyer_username: str
    ) -> ClientMemory:
        """
        Возвращает память покупателя или создаёт новую запись.

        Args:
            account_id: ID аккаунта FunPay
            buyer_username: имя покупателя

        Returns:
            ClientMemory
        """
        async with get_session() as session:
            result = await session.execute(
                select(ClientMemory)
                .where(ClientMemory.account_id == account_id)
                .where(ClientMemory.buyer_username == buyer_username)
            )
            mem = result.scalar_one_or_none()

            if mem is None:
                mem = ClientMemory(
                    account_id=account_id,
                    buyer_username=buyer_username,
                )
                session.add(mem)
                logger.debug(
                    f"[AI:Memory] Создана новая запись для {buyer_username} "
                    f"(account={account_id})"
                )

            return mem

    async def save(self, memory: ClientMemory) -> None:
        """Сохраняет изменения в ClientMemory."""
        async with get_session() as session:
            session.add(memory)

    async def add_incoming_message(
        self, account_id: int, buyer_username: str, text: str
    ) -> None:
        """Добавляет входящее сообщение покупателя в историю."""
        mem = await self.get_or_create(account_id, buyer_username)
        mem.add_message("buyer", text)
        await self.save(mem)

    async def add_ai_reply(
        self,
        account_id: int,
        buyer_username: str,
        question: str,
        answer: str,
        source: str,
    ) -> None:
        """Добавляет AI-ответ в историю."""
        mem = await self.get_or_create(account_id, buyer_username)
        mem.add_message("ai", answer)
        mem.add_ai_response(question, answer, source)
        await self.save(mem)

    async def get_context_for_llm(
        self, account_id: int, buyer_username: str
    ) -> dict[str, Any]:
        """
        Возвращает контекст покупателя для передачи в Gemini.
        """
        mem = await self.get_or_create(account_id, buyer_username)
        return {
            "has_purchases": mem.has_bought_before(),
            "purchases": mem.get_purchases()[-5:],
            "last_messages": mem.get_messages()[-10:],
        }

    async def already_answered(
        self, account_id: int, buyer_username: str, question: str
    ) -> str | None:
        """Проверяет, был ли ранее дан ответ на такой же вопрос."""
        mem = await self.get_or_create(account_id, buyer_username)
        return mem.already_answered(question)

    async def cleanup_expired(self) -> int:
        """
        Удаляет записи памяти старше 30 дней.
        Возвращает количество удалённых записей.
        """
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(days=30)

        async with get_session() as session:
            result = await session.execute(
                delete(ClientMemory).where(ClientMemory.last_seen < cutoff)
            )
            deleted = result.rowcount
            if deleted:
                logger.info(f"[AI:Memory] Удалено {deleted} устаревших записей памяти")
            return deleted