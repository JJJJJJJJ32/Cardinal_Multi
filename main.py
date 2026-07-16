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
11. [МОДУЛЬ 5] Scheduler (APScheduler)
12. [МОДУЛЬ 5] EmergencyModule
13. [МОДУЛЬ 5] StatsModule
14. [МОДУЛЬ 5] BalanceModule
15. [МОДУЛЬ 5] DiagnosticsChecker
16. [МОДУЛЬ 5] UpdateChecker (проверка при старте)
17. Rich dashboard / ожидание Ctrl+C
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# ── 1. sys.path ──────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── 2. Логгер (предварительный) ──────────────────────────────────────────────
from modules.core.logger import setup_logger

setup_logger("DEBUG")

# ── 3. Настройки ─────────────────────────────────────────────────────────────
from modules.core.config import get_settings

settings = get_settings()

# ── 4. Логгер (финальный) ────────────────────────────────────────────────────
setup_logger(settings.log_level)

from loguru import logger

logger.info("Cardinal_Multi запускается...")

# ── 5. Encryption ────────────────────────────────────────────────────────────
from modules.core.encryption import Encryption

Encryption()  # инициализация ключа (создаст data/secret.key если нет)
logger.info("Encryption инициализирован")

# ── 6. База данных ───────────────────────────────────────────────────────────
from modules.core.database import init_db

# ── 7. Совместимость плагинов ────────────────────────────────────────────────
from modules.cardinal_bridge.compatibility import check_all_plugins

# ── 8. AccountManager ────────────────────────────────────────────────────────
from modules.multi.account_manager import AccountManager

# ── 9. LolzteamModule ────────────────────────────────────────────────────────
from modules.lolzteam import LolzteamModule

# ── 10. Cardinal Bridge ──────────────────────────────────────────────────────
from modules.cardinal_bridge.hooks import generate_plugin_file

# ── 11-16. Модуль 5 ──────────────────────────────────────────────────────────
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from modules.stats.module import StatsModule
from modules.balance.module import BalanceModule
from modules.emergency.module import EmergencyModule
from modules.diagnostics.checker import DiagnosticsChecker
from modules.updates.checker import UpdateChecker

# ── UI ───────────────────────────────────────────────────────────────────────
from ui.console import ConsoleUI


async def main() -> None:
    """Основная точка входа Cardinal_Multi."""

    # ── БД: создать все таблицы ──────────────────────────────────────────────
    logger.info("Инициализация базы данных...")
    await init_db()
    logger.info("База данных готова")

    # ── Совместимость плагинов Cardinal ──────────────────────────────────────
    logger.info("Проверка совместимости плагинов...")
    try:
        check_all_plugins()
    except Exception as exc:
        logger.warning(f"Проверка совместимости: {exc}")

    # ── Cardinal Bridge: генерация plugin-файла ───────────────────────────────
    logger.info("Генерация Cardinal bridge плагина...")
    try:
        generate_plugin_file()
        logger.info("Cardinal bridge плагин готов")
    except Exception as exc:
        logger.warning(f"Cardinal bridge: {exc}")

    # ── Модуль 1: AccountManager ──────────────────────────────────────────────
    logger.info("Запуск AccountManager...")
    account_manager = AccountManager()
    try:
        await account_manager.setup()
        await account_manager.start()
        logger.info("AccountManager запущен")
    except Exception as exc:
        logger.error(f"AccountManager ошибка: {exc}", exc_info=True)
        # Не падаем — продолжаем запуск

    # ── Модуль 2: LolzteamModule ──────────────────────────────────────────────
    lolzteam_module: LolzteamModule | None = None

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
            logger.error(f"LolzteamModule ошибка: {exc}", exc_info=True)
            lolzteam_module = None
    else:
        logger.warning(
            "LolzteamModule не запущен: "
            "не задан LOLZ_API_TOKEN или LOLZ_LOGIN + LOLZ_PASSWORD"
        )

    # =========================================================================
    # МОДУЛЬ 5: Scheduler + вспомогательные модули
    # =========================================================================

    # ── 11. APScheduler ───────────────────────────────────────────────────────
    logger.info("Запуск APScheduler...")
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.start()
    logger.info("APScheduler запущен")

    # ── 12. EmergencyModule ───────────────────────────────────────────────────
    # Стартуем первым — другие модули могут запрашивать is_paused()
    logger.info("Запуск EmergencyModule...")
    emergency_module = EmergencyModule()
    try:
        await emergency_module.setup()
        await emergency_module.start()
        logger.info("EmergencyModule запущен")
    except Exception as exc:
        logger.error(f"EmergencyModule ошибка: {exc}", exc_info=True)

    # ── 13. StatsModule ───────────────────────────────────────────────────────
    # Подписывается на ORDER_COMPLETED / ITEM_PURCHASED / ITEM_DELIVERED
    logger.info("Запуск StatsModule...")
    stats_module = StatsModule(scheduler=scheduler)
    try:
        await stats_module.setup()
        await stats_module.start()
        logger.info("StatsModule запущен")
    except Exception as exc:
        logger.error(f"StatsModule ошибка: {exc}", exc_info=True)

    # ── 14. BalanceModule ─────────────────────────────────────────────────────
    # Нужен accounts_getter — берём из account_manager
    logger.info("Запуск BalanceModule...")
    balance_module = BalanceModule(
        scheduler=scheduler,
        # get_active_accounts() — метод AccountManager,
        # возвращает List[Account] (активные аккаунты из БД)
        accounts_getter=account_manager.get_active_accounts,
    )
    try:
        await balance_module.setup()
        await balance_module.start()
        logger.info("BalanceModule запущен")
    except Exception as exc:
        logger.error(f"BalanceModule ошибка: {exc}", exc_info=True)

    # ── 15. DiagnosticsChecker ────────────────────────────────────────────────
    # Stateless — создаём, не стартуем (вызывается по запросу)
    logger.info("DiagnosticsChecker готов")
    diagnostics = DiagnosticsChecker()

    # ── 16. UpdateChecker ─────────────────────────────────────────────────────
    logger.info("Проверка обновлений Cardinal_Multi...")
    update_checker = UpdateChecker()
    try:
        await update_checker.check()  # 1 раз при старте
    except Exception as exc:
        logger.warning(f"UpdateChecker (старт): {exc}")

    # Повторная проверка раз в сутки
    scheduler.add_job(
        update_checker.check,
        trigger="interval",
        hours=24,
        id="update_check_daily",
        replace_existing=True,
    )
    logger.info("UpdateChecker: повторная проверка запланирована (каждые 24ч)")

    # =========================================================================
    # UI / ожидание Ctrl+C
    # =========================================================================
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
        await _shutdown(
            account_manager=account_manager,
            lolzteam_module=lolzteam_module,
            scheduler=scheduler,
            emergency_module=emergency_module,
            stats_module=stats_module,
            balance_module=balance_module,
        )


async def _shutdown(
    account_manager: AccountManager,
    lolzteam_module: LolzteamModule | None,
    scheduler: AsyncIOScheduler,
    emergency_module: EmergencyModule,
    stats_module: StatsModule,
    balance_module: BalanceModule,
) -> None:
    """
    Корректная остановка всех модулей.

    Порядок остановки (обратный порядку запуска):
    1. BalanceModule      — останавливаем фоновые проверки
    2. StatsModule        — останавливаем автоочистку
    3. EmergencyModule    — снимаем все паузы
    4. APScheduler        — останавливаем планировщик
    5. LolzteamModule     — закрываем сессии Lolzteam
    6. AccountManager     — останавливаем subprocess Cardinal
    """
    logger.info("Остановка Cardinal_Multi...")

    # ── BalanceModule ─────────────────────────────────────────────────────────
    try:
        await balance_module.stop()
        logger.info("BalanceModule остановлен")
    except Exception as exc:
        logger.error(f"BalanceModule stop ошибка: {exc}")

    # ── StatsModule ───────────────────────────────────────────────────────────
    try:
        await stats_module.stop()
        logger.info("StatsModule остановлен")
    except Exception as exc:
        logger.error(f"StatsModule stop ошибка: {exc}")

    # ── EmergencyModule ───────────────────────────────────────────────────────
    try:
        await emergency_module.stop()
        logger.info("EmergencyModule остановлен")
    except Exception as exc:
        logger.error(f"EmergencyModule stop ошибка: {exc}")

    # ── APScheduler ───────────────────────────────────────────────────────────
    try:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler остановлен")
    except Exception as exc:
        logger.error(f"APScheduler shutdown ошибка: {exc}")

    # ── LolzteamModule ────────────────────────────────────────────────────────
    if lolzteam_module is not None:
        try:
            await lolzteam_module.stop()
            logger.info("LolzteamModule остановлен")
        except Exception as exc:
            logger.error(f"LolzteamModule stop ошибка: {exc}")

    # ── AccountManager ────────────────────────────────────────────────────────
    try:
        await account_manager.stop()
        logger.info("AccountManager остановлен")
    except Exception as exc:
        logger.error(f"AccountManager stop ошибка: {exc}")

    logger.info("Cardinal_Multi остановлен. До свидания!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass