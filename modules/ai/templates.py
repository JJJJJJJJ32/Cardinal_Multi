"""
Система шаблонных ответов.
Сначала точное совпадение, потом частичное.
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger
from sqlalchemy import select

from modules.core.database import get_session
from modules.ai.models.ai_template import AITemplate


# ─── Встроенные дефолтные шаблоны ──────────────────────────────────────

DEFAULT_TEMPLATES: list[dict] = [
    {
        "name": "наличие",
        "triggers": ["есть", "в наличии", "есть ли", "наличие"],
        "response": "Да, товар в наличии.",
        "priority": 10,
    },
    {
        "name": "скидка",
        "triggers": ["скидка", "дешевле", "скинь цену"],
        "response": "К сожалению, скидку предоставить не могу.",
        "priority": 10,
    },
    {
        "name": "ожидание",
        "triggers": ["когда", "как долго", "сколько ждать"],
        "response": "Выдача происходит автоматически после подтверждения заказа.",
        "priority": 10,
    },
    {
        "name": "возврат",
        "triggers": ["возврат", "вернуть", "не работает"],
        "response": "Пожалуйста, опишите проблему подробнее, передам продавцу.",
        "priority": 10,
    },
]


@dataclass
class TemplateMatch:
    """Результат поиска шаблона."""
    found: bool
    response: str | None
    template_name: str | None


class TemplateEngine:
    """
    Поиск подходящего шаблона для сообщения.

    Приоритет:
    1. Точное совпадение текста и ключевого слова
    2. Частичное совпадение (вхождение)

    Шаблоны загружаются из БД. Если БД пуста — используются DEFAULT_TEMPLATES.
    """

    async def find(self, account_id: int, text: str) -> TemplateMatch:
        """
        Ищет шаблон по тексту сообщения.

        Args:
            account_id: ID аккаунта
            text: текст сообщения

        Returns:
            TemplateMatch
        """
        lower = text.lower().strip()
        templates = await self._load_templates(account_id)

        # Сначала точное совпадение
        for tpl in templates:
            for kw in tpl["triggers"]:
                if kw.lower() == lower:
                    logger.debug(f"[AI:Templates] Точное совпадение: '{tpl['name']}'")
                    return TemplateMatch(True, tpl["response"], tpl["name"])

        # Потом частичное
        for tpl in templates:
            for kw in tpl["triggers"]:
                if kw.lower() in lower:
                    logger.debug(f"[AI:Templates] Частичное совпадение: '{tpl['name']}'")
                    return TemplateMatch(True, tpl["response"], tpl["name"])

        return TemplateMatch(False, None, None)

    async def _load_templates(self, account_id: int) -> list[dict]:
        """
        Загружает шаблоны из БД. Если нет — возвращает DEFAULT_TEMPLATES.
        """
        try:
            async with get_session() as session:
                result = await session.execute(
                    select(AITemplate)
                    .where(AITemplate.account_id == account_id)
                    .where(AITemplate.is_enabled == True)
                    .order_by(AITemplate.priority)
                )
                db_templates = result.scalars().all()

                if db_templates:
                    return [
                        {
                            "name": t.name,
                            "triggers": t.get_keywords(),
                            "response": t.response_text,
                            "priority": t.priority,
                        }
                        for t in db_templates
                    ]
        except Exception as e:
            logger.error(f"[AI:Templates] Ошибка загрузки из БД: {e}")

        logger.debug("[AI:Templates] Используются DEFAULT_TEMPLATES")
        return DEFAULT_TEMPLATES

    async def seed_defaults(self, account_id: int) -> None:
        """
        Записывает дефолтные шаблоны в БД, если их ещё нет.
        Вызывается при первом запуске модуля.
        """
        async with get_session() as session:
            result = await session.execute(
                select(AITemplate).where(AITemplate.account_id == account_id).limit(1)
            )
            if result.scalar_one_or_none() is not None:
                return

            for t in DEFAULT_TEMPLATES:
                tpl = AITemplate(
                    account_id=account_id,
                    name=t["name"],
                    response_text=t["response"],
                    is_enabled=True,
                    priority=t["priority"],
                )
                tpl.set_keywords(t["triggers"])
                session.add(tpl)

            logger.info(f"[AI:Templates] Дефолтные шаблоны записаны для account_id={account_id}")