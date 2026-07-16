"""
modules/core/database.py
────────────────────────
Асинхронный движок SQLAlchemy 2.x + aiosqlite.
Файл БД: ./data/cardinal_multi.db

Предоставляет:
- async engine
- async session factory (get_session)
- базовую модель Base для всех таблиц
- функцию init_db() для создания схемы
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, MappedColumn, mapped_column
from sqlalchemy import DateTime, func
from loguru import logger


# ─── Константы ────────────────────────────────────────────────────────────────
DATA_DIR = Path("data")
DB_FILE = DATA_DIR / "cardinal_multi.db"
DB_URL = f"sqlite+aiosqlite:///{DB_FILE}"


# ─── Базовая модель ────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """
    Базовый класс для всех ORM-моделей Cardinal_Multi.

    Все таблицы автоматически получают:
    - created_at: время создания записи (UTC, auto-generated)
    - updated_at: время последнего обновления (UTC, auto-updated)
    """

    created_at: MappedColumn[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: MappedColumn[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ─── Движок и фабрика сессий ──────────────────────────────────────────────────

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_engine() -> AsyncEngine:
    """Возвращает (создаёт при первом вызове) async engine."""
    global _engine
    if _engine is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        _engine = create_async_engine(
            DB_URL,
            echo=False,             # SQL-запросы не в консоль
            pool_pre_ping=True,     # проверка соединения перед использованием
            connect_args={
                "check_same_thread": False,  # нужно для asyncio
                "timeout": 30,
            },
        )
        logger.debug("Async DB engine создан: {}", DB_URL)
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Возвращает фабрику async-сессий."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=_get_engine(),
            expire_on_commit=False,     # объекты не инвалидируются после commit
            autoflush=True,
            autocommit=False,
        )
    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager для получения DB-сессии.

    Автоматически коммитит при успехе и роллбечит при исключении.

    Пример использования::

        async with get_session() as session:
            result = await session.execute(select(Account))
            accounts = result.scalars().all()
    """
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """
    Создаёт все таблицы в БД (если не существуют).

    Вызывать один раз при старте приложения.
    Использует metadata из Base — автоматически подхватывает
    все импортированные модели.

    :raises RuntimeError: если не удалось создать таблицы.
    """
    # Импортируем модели для регистрации в metadata
    # (необходимо до вызова create_all)
    from modules.multi.models.account import Account          # noqa: F401
    from modules.multi.models.account_lot import AccountLot  # noqa: F401

    # ── НОВЫЕ ИМПОРТЫ МОДУЛЯ 5 ──────────────────────────────
    from modules.stats.models.stats_daily import StatsDaily              # noqa: F401
    from modules.stats.models.balance_history import BalanceHistory      # noqa: F401
    from modules.balance.models.balance_alert import BalanceAlert        # noqa: F401
    from modules.balance.models.delayed_delivery import DelayedDelivery  # noqa: F401
    from modules.emergency.models.emergency_pause import EmergencyPause  # noqa: F401
    from modules.updates.models.update_check import UpdateCheck          # noqa: F401
    
    engine = _get_engine()
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("БД инициализирована: {}", DB_FILE)
    except Exception as exc:
        logger.error("Ошибка инициализации БД: {}", exc)
        raise RuntimeError(f"Не удалось инициализировать БД: {exc}") from exc


async def close_db() -> None:
    """
    Корректно закрывает пул соединений с БД.
    Вызывать при остановке приложения.
    """
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.debug("DB engine закрыт.")