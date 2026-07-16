"""
modules/emergency/pause.py
Логика экстренной паузы аккаунтов.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Dict, Optional, Set

from loguru import logger
from sqlalchemy import select

from modules.core.database import get_session
from modules.core.events import EventBus, EventType
from modules.emergency.models.emergency_pause import EmergencyPause


class PauseManager:
    """
    Управляет флагами паузы для аккаунтов.

    Архитектура:
    - _paused_accounts: set из account_id которые сейчас на паузе.
    - _global_pause: флаг глобальной паузы всех аккаунтов.
    - Другие модули вызывают is_paused(account_id) перед выполнением действий.
    - При resume() обрабатываются накопившиеся события из очереди.
    """

    def __init__(self) -> None:
        self._paused_accounts: Set[int] = set()
        self._global_pause: bool = False
        self._pending_events: Dict[int, list] = {}  # account_id → список отложенных данных
        self._log = logger.bind(module="PauseManager")

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    async def pause(
        self,
        account_id: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> None:
        """
        Поставить на паузу.

        Args:
            account_id: ID аккаунта или None (глобальная пауза).
            reason:     Причина паузы (для журнала).
        """
        if account_id is None:
            self._global_pause = True
            self._log.warning(f"🔴 ГЛОБАЛЬНАЯ ПАУЗА. Причина: {reason or '—'}")
        else:
            self._paused_accounts.add(account_id)
            if account_id not in self._pending_events:
                self._pending_events[account_id] = []
            self._log.warning(
                f"🔴 Пауза аккаунта #{account_id}. Причина: {reason or '—'}"
            )

        # Записать в журнал
        async with get_session() as session:
            record = EmergencyPause(
                account_id=account_id,
                is_global=(account_id is None),
                paused_at=datetime.utcnow(),
                reason=reason,
            )
            session.add(record)
            await session.commit()

        # Уведомить EventBus о паузе (другие модули могут подписаться)
        EventBus().emit(
            EventType.SYSTEM_ERROR,
            {
                "type": "emergency_pause",
                "account_id": account_id,
                "is_global": account_id is None,
                "reason": reason,
            },
        )

    async def resume(self, account_id: Optional[int] = None) -> None:
        """
        Снять паузу и обработать накопившиеся события.

        Args:
            account_id: ID аккаунта или None (снять глобальную паузу).
        """
        if account_id is None:
            self._global_pause = False
            self._log.info("🟢 Глобальная пауза снята.")
            # Обработать накопившиеся события всех аккаунтов
            for acc_id in list(self._pending_events.keys()):
                await self._flush_pending(acc_id)
        else:
            self._paused_accounts.discard(account_id)
            self._log.info(f"🟢 Пауза аккаунта #{account_id} снята.")
            await self._flush_pending(account_id)

        # Обновить запись в журнале (resumed_at)
        async with get_session() as session:
            result = await session.execute(
                select(EmergencyPause)
                .where(
                    EmergencyPause.account_id == account_id,
                    EmergencyPause.resumed_at == None,
                )
                .order_by(EmergencyPause.paused_at.desc())
                .limit(1)
            )
            record = result.scalar_one_or_none()
            if record:
                record.resumed_at = datetime.utcnow()
                await session.commit()

    def is_paused(self, account_id: int) -> bool:
        """
        Проверить, на паузе ли аккаунт.
        Другие модули вызывают это перед любым действием.
        """
        return self._global_pause or account_id in self._paused_accounts

    def is_global_paused(self) -> bool:
        return self._global_pause

    def add_pending_event(self, account_id: int, event_data: dict) -> None:
        """
        Записать событие в очередь ожидания пока аккаунт на паузе.
        Вызывается из других модулей если is_paused() → True.
        """
        if account_id not in self._pending_events:
            self._pending_events[account_id] = []
        self._pending_events[account_id].append(event_data)
        self._log.debug(
            f"Событие поставлено в очередь паузы аккаунта #{account_id}. "
            f"Всего в очереди: {len(self._pending_events[account_id])}"
        )

    # ──────────────────────────────────────────────
    # Internals
    # ──────────────────────────────────────────────

    async def _flush_pending(self, account_id: int) -> None:
        """Обработать накопившиеся события после снятия паузы."""
        events = self._pending_events.pop(account_id, [])
        if not events:
            return

        self._log.info(
            f"Обработка {len(events)} отложенных событий аккаунта #{account_id}..."
        )
        for event_data in events:
            try:
                # Повторно эмитим оригинальное событие
                event_type_raw = event_data.pop("_original_event_type", None)
                if event_type_raw:
                    EventBus().emit(EventType(event_type_raw), event_data)
                await asyncio.sleep(0.05)  # не перегружать
            except Exception as e:
                self._log.error(f"Ошибка обработки отложенного события: {e}")

    def get_status(self) -> dict:
        return {
            "global_pause": self._global_pause,
            "paused_accounts": list(self._paused_accounts),
            "pending_events_count": {
                k: len(v) for k, v in self._pending_events.items()
            },
        }