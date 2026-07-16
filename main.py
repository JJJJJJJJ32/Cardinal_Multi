"""
Cardinal_Multi — точка входа.

Pipeline запуска:
1. sys.path setup
2. Логгер (предварительный)
3. Настройки (.env)
4. Логгер (финальный с уровнем из .env)
5. Encryption (инициализация ключа)
6. init_db (создание всех таблиц)
7. Совместимость плагинов Cardinal
8. AccountManager (Модуль 1)
9. LolzteamModule (Модуль 2)
10. Cardinal Bridge (подключение хуков к Cardinal)
11. Rich dashboard / ожидание Ctrl+C
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# ── 1. sys.path ──────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── 2. Логгер (предварительный) ──────────────────────────────────
from modules.core.logger import setup_logger

setup_logger("DEBUG")

# ── 3. Настройки ─────────────────────────────────────────────────
from modules.core.config import get_settings

settings = get_settings()

# ── 4. Логгер (финальный) ────────────────────────────────────────
setup_logger(settings.log_level)

from loguru import logger

logger.info("Cardinal_Multi запускается...")

# ── 5. Encryption ────────────────────────────────────────────────
from modules.core.encryption import Encryption

Encryption()  # инициализация ключа (создаст data/secret.key если нет)
logger.info("Encryption инициализирован")

# ── 6. База данных ───────────────────────────────────────────────
from modules.core.database import init_db

# ── 7. Совместимость плагинов ────────────────────────────────────
from modules.cardinal_bridge.compatibility import check_all_plugins

# ── 8. AccountManager ────────────────────────────────────────────
from modules.multi.account_manager import AccountManager

# ── 9. LolzteamModule ────────────────────────────────────────────
from modules.lolzteam import LolzteamModule

# ── 10. Cardinal Bridge ──────────────────────────────────────────
from modules.cardinal_bridge.hooks import generate_plugin_file

# ── UI ───────────────────────────────────────────────────────────
from ui.console import ConsoleUI


async def main() -> None:
    """Основная точка входа Cardinal_Multi."""

    # ── БД: создать все таблицы ──────────────────────────────────
    logger.info("Инициализация базы данных...")
    await init_db()
    logger.info("База данных готова")

    # ── Совместимость плагинов Cardinal ──────────────────────────
    logger.info("Проверка совместимости плагинов...")
    try:
        check_all_plugins()
    except Exception as exc:
        logger.warning(f"Проверка совместимости: {exc}")

    # ── Cardinal Bridge: генерация plugin-файла ───────────────────
    logger.info("Генерация Cardinal bridge плагина...")
    try:
        generate_plugin_file()
        logger.info("Cardinal bridge плагин готов")
    except Exception as exc:
        logger.warning(f"Cardinal bridge: {exc}")

    # ── Модуль 1: AccountManager ──────────────────────────────────
    logger.info("Запуск AccountManager...")
    account_manager = AccountManager()
    try:
        await account_manager.setup()
        await account_manager.start()
        logger.info("AccountManager запущен")
    except Exception as exc:
        logger.error(f"AccountManager ошибка: {exc}", exc_info=True)
        # Не падаем — продолжаем запуск

    # ── Модуль 2: LolzteamModule ──────────────────────────────────
    lolzteam_module: LolzteamModule | None = None

    # Проверяем есть ли хоть один из Lolzteam credentials
    lolz_token = (
        getattr(settings, "lolz_api_token", None)
        or getattr(settings, "lolzteam_token", None)
    )
    lolz_login = getattr(settings, "lolz_login", None)
    lolz_password = getattr(settings, "lolz_password", None)

    if lolz_token or (lolz_login and lolz_password):
        logger.info("Запуск LolzteamModule...")
        lolzteam_module = LolzteamModule()
        try:
            await lolzteam_module.setup()
            await lolzteam_module.start()
            logger.info("LolzteamModule запущен")
        except Exception as exc:
            logger.error(
                f"LolzteamModule ошибка: {exc}", exc_info=True
            )
            lolzteam_module = None
    else:
        logger.warning(
            "LolzteamModule не запущен: "
            "не задан LOLZ_API_TOKEN или LOLZ_LOGIN + LOLZ_PASSWORD"
        )

    # ── UI / ожидание ─────────────────────────────────────────────
    logger.info("Cardinal_Multi запущен. Нажми Ctrl+C для остановки.")

    ui = ConsoleUI()
    try:
        await ui.run(
            account_manager=account_manager,
            lolzteam_module=lolzteam_module,
        )
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Получен сигнал остановки...")
    finally:
        await _shutdown(account_manager, lolzteam_module)


async def _shutdown(
    account_manager: AccountManager,
    lolzteam_module: LolzteamModule | None,
) -> None:
    """Корректная остановка всех модулей."""
    logger.info("Остановка Cardinal_Multi...")

    # Lolzteam
    if lolzteam_module is not None:
        try:
            await lolzteam_module.stop()
            logger.info("LolzteamModule остановлен")
        except Exception as exc:
            logger.error(f"LolzteamModule stop ошибка: {exc}")

    # AccountManager
    try:
        await account_manager.stop()
        logger.info("AccountManager остановлен")
    except Exception as exc:
        logger.error(f"AccountManager stop ошибка: {exc}")

    logger.info("Cardinal_Multi остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass