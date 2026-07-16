"""
modules/core — ядро Cardinal_Multi.

Экспортирует основные компоненты для использования в других модулях.
"""

from modules.core.logger import setup_logger, get_logger
from modules.core.encryption import Encryption, EncryptionError
from modules.core.database import Base, get_session, init_db, close_db
from modules.core.events import EventBus, EventType
from modules.core.config import get_settings, get_cardinal_cfg, MultiSettings
from modules.core.base_module import BaseModule, ModuleStatus

__all__ = [
    # Logger
    "setup_logger",
    "get_logger",
    # Encryption
    "Encryption",
    "EncryptionError",
    # Database
    "Base",
    "get_session",
    "init_db",
    "close_db",
    # Events
    "EventBus",
    "EventType",
    # Config
    "get_settings",
    "get_cardinal_cfg",
    "MultiSettings",
    # Base module
    "BaseModule",
    "ModuleStatus",
]