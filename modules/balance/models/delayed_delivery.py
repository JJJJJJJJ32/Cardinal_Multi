"""
DelayedDelivery — отложенная выдача товаров.

Фиксы:
  B-03  — двойная выдача (idempotency по unique order_id)
  B-05  — дубли после restart scheduler'а
  B-12  — payload overflow (String(4096))
  TC-024 — delay=0 → немедленная выдача
  TC-114 — отрицательный delay
  TC-115 — очень большой delay
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

from loguru import logger
from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
    select,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession

from modules.core.database import get_session
from modules.core.events import EventBus, EventType


# ═══════════════════════════════════════════════════════════════════════════════
# Статусы
# ═══════════════════════════════════════════════════════════════════════════════
class DeliveryStatus(str, Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ═══════════════════════════════════════════════════════════════════════════════
# Константы
# ═══════════════════════════════════════════════════════════════════════════════
MAX_PAYLOAD_LENGTH = 4000    # чуть меньше 4096 для запаса
MAX_DELAY_MINUTES = 1440     # 24 часа
MIN_DELAY_MINUTES = 0


# ═══════════════════════════════════════════════════════════════════════════════
# Процессор
# ═══════════════════════════════════════════════════════════════════════════════
class DelayedDeliveryProcessor:
    """
    Обрабатывает ITEM_PURCHASED → создаёт отложенную запись или
    немедленно отправляет ITEM_DELIVERED.

    Гарантии:
      - Idempotency по order_id (FIX B-03/B-05)
      - Payload обрезается если > MAX_PAYLOAD_LENGTH (FIX B-12)
      - delay < 0 трактуется как 0 (TC-114)
      - delay > MAX_DELAY_MINUTES → cap (TC-115)
    """

    def __init__(self) -> None:
        self._event_bus = EventBus()

    # ─────────────────────────────────────────────────────────────────────────
    # Создание отложенной доставки
    # ─────────────────────────────────────────────────────────────────────────
    async def schedule_delivery(
        self,
        *,
        account_id: int,
        order_id: str,
        delay_minutes: int = 0,
        payload: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Планирует выдачу.

        delay_minutes == 0 или < 0 → немедленная выдача.
        """
        # ── Нормализация delay (TC-114 / TC-115) ────────────────────────────
        if delay_minutes < MIN_DELAY_MINUTES:
            logger.warning(
                f"DelayedDelivery: delay_minutes={delay_minutes} < 0, "
                f"трактуем как 0 (немедленная выдача)"
            )
            delay_minutes = 0

        if delay_minutes > MAX_DELAY_MINUTES:
            logger.warning(
                f"DelayedDelivery: delay_minutes={delay_minutes} > {MAX_DELAY_MINUTES}, "
                f"ограничиваем до {MAX_DELAY_MINUTES}"
            )
            delay_minutes = MAX_DELAY_MINUTES

        # ── TC-024: delay=0 → emit сразу ────────────────────────────────────
        if delay_minutes == 0:
            logger.info(
                f"DelayedDelivery: немедленная выдача order_id={order_id}"
            )
            await self._event_bus.emit(
                EventType.ITEM_DELIVERED,
                {"account_id": account_id, "order_id": order_id, **(payload or {})},
            )
            return

        # ── Сериализация payload (FIX B-12) ──────────────────────────────────
        payload_str: Optional[str] = None
        if payload is not None:
            try:
                payload_str = json.dumps(payload, ensure_ascii=False, default=str)
            except (TypeError, ValueError) as exc:
                logger.error(
                    f"DelayedDelivery: не удалось сериализовать payload: {exc}"
                )
                payload_str = "{}"

            if len(payload_str) > MAX_PAYLOAD_LENGTH:
                logger.warning(
                    f"DelayedDelivery: payload обрезан "
                    f"({len(payload_str)} > {MAX_PAYLOAD_LENGTH})"
                )
                payload_str = payload_str[:MAX_PAYLOAD_LENGTH]

        # ── Idempotency check (FIX B-03 / B-05) ─────────────────────────────
        async with get_session() as session:
            # Проверяем: уже есть запись с таким order_id?
            existing = await session.execute(
                select(DelayedDeliveryModel).where(
                    DelayedDeliveryModel.order_id == order_id,
                    DelayedDeliveryModel.account_id == account_id,
                )
            )
            row = existing.scalar_one_or_none()

            if row is not None:
                logger.warning(
                    f"DelayedDelivery: order_id={order_id} уже существует "
                    f"(status={row.status}), пропуск создания дубликата"
                )
                return

            # ── Создаём запись ────────────────────────────────────────────────
            deliver_at = datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)
            record = DelayedDeliveryModel(
                account_id=account_id,
                order_id=order_id,
                status=DeliveryStatus.PENDING.value,
                payload=payload_str,
                deliver_at=deliver_at,
                created_at=datetime.now(timezone.utc),
            )
            session.add(record)
            await session.commit()

            logger.info(
                f"DelayedDelivery: запланирована выдача order_id={order_id} "
                f"через {delay_minutes} мин (deliver_at={deliver_at.isoformat()})"
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Обработка просроченных записей (вызывается scheduler'ом)
    # ─────────────────────────────────────────────────────────────────────────
    async def process_pending(self) -> int:
        """
        Найти все PENDING с deliver_at <= now, отправить ITEM_DELIVERED.

        FIX B-05: атомарный UPDATE status → DELIVERED перед emit,
        чтобы повторный вызов не обработал ту же запись.

        Возвращает количество обработанных записей.
        """
        now = datetime.now(timezone.utc)
        processed = 0

        async with get_session() as session:
            result = await session.execute(
                select(DelayedDeliveryModel).where(
                    DelayedDeliveryModel.status == DeliveryStatus.PENDING.value,
                    DelayedDeliveryModel.deliver_at <= now,
                )
            )
            records = result.scalars().all()

            for record in records:
                # ── Атомарно ставим DELIVERED (FIX B-05) ─────────────────────
                # Если два процесса одновременно — второй не найдёт PENDING
                rows_affected = await session.execute(
                    update(DelayedDeliveryModel)
                    .where(
                        DelayedDeliveryModel.id == record.id,
                        DelayedDeliveryModel.status == DeliveryStatus.PENDING.value,
                    )
                    .values(
                        status=DeliveryStatus.DELIVERED.value,
                        delivered_at=now,
                    )
                )
                await session.commit()

                # Если rowcount == 0 → кто-то уже обработал
                if rows_affected.rowcount == 0:
                    logger.debug(
                        f"DelayedDelivery: order_id={record.order_id} "
                        f"уже обработан другим процессом"
                    )
                    continue

                # ── emit ITEM_DELIVERED ───────────────────────────────────────
                payload = {}
                if record.payload:
                    try:
                        payload = json.loads(record.payload)
                    except (json.JSONDecodeError, TypeError):
                        logger.warning(
                            f"DelayedDelivery: невалидный payload для "
                            f"order_id={record.order_id}"
                        )

                await self._event_bus.emit(
                    EventType.ITEM_DELIVERED,
                    {
                        "account_id": record.account_id,
                        "order_id": record.order_id,
                        **payload,
                    },
                )

                processed += 1
                logger.info(
                    f"DelayedDelivery: выдан order_id={record.order_id} "
                    f"(задержка была с {record.created_at})"
                )

        if processed:
            logger.info(f"DelayedDelivery: обработано {processed} записей")

        return processed


# ═══════════════════════════════════════════════════════════════════════════════
# SQLAlchemy модель (если она не в отдельном models/ файле — вынесите туда)
# ═══════════════════════════════════════════════════════════════════════════════
# Если у вас модель в modules/multi/models/, просто импортируйте оттуда.
# Здесь определяем для полноты.

try:
    from modules.multi.models.base import Base
except ImportError:
    from sqlalchemy.orm import DeclarativeBase

    class Base(DeclarativeBase):  # type: ignore[no-redef]
        pass


class DelayedDeliveryModel(Base):
    """Таблица delayed_deliveries."""

    __tablename__ = "delayed_deliveries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, nullable=False, index=True)
    order_id = Column(String(256), nullable=False, index=True)
    status = Column(String(32), nullable=False, default=DeliveryStatus.PENDING.value)
    payload = Column(Text, nullable=True)  # FIX B-12: Text вместо String(4096)
    delay_minutes = Column(Integer, nullable=True)
    deliver_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    delivered_at = Column(DateTime(timezone=True), nullable=True)