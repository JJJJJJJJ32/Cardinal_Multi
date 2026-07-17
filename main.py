
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════════
# 1. sys.path
# ═══════════════════════════════════════════════════════════════════════════════
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ═══════════════════════════════════════════════════════════════════════════════
# 2. Логгер (предварительный)
# ═══════════════════════════════════════════════════════════════════════════════
from modules.core.logger import setup_logger          # noqa: E402

setup_logger("DEBUG")

# ═══════════════════════════════════════════════════════════════════════════════
# 3. Настройки
# ═══════════════════════════════════════════════════════════════════════════════
from modules.core.config import get_settings           # noqa: E402

settings = get_settings()

# ═══════════════════════════════════════════════════════════════════════════════
# 4. Логгер (финальный)
# ═══════════════════════════════════════════════════════════════════════════════
setup_logger(settings.log_level)

from loguru import logger                              # noqa: E402

logger.info("Cardinal_Multi запускается …")

# ═══════════════════════════════════════════════════════════════════════════════
# 5. Encryption
# ═══════════════════════════════════════════════════════════════════════════════
from modules.core.encryption import Encryption         # noqa: E402

Encryption()
logger.info("Encryption инициализирован")

# ═══════════════════════════════════════════════════════════════════════════════
# 6–8. Импорты (ленивые) — чтобы не дублировать try/except на каждый import
# ═══════════════════════════════════════════════════════════════════════════════
from modules.core.database import init_db                          # noqa: E402
from modules.cardinal_bridge.compatibility import check_all_plugins  # noqa: E402
from modules.cardinal_bridge.hooks import generate_plugin_file       # noqa: E402
from modules.multi.account_manager import AccountManager             # noqa: E402
from modules.lolzteam import LolzteamModule                         # noqa: E402

from apscheduler.schedulers.asyncio import AsyncIOScheduler          # noqa: E402
from modules.stats.module import StatsModule                         # noqa: E402
from modules.balance.module import BalanceModule                     # noqa: E402
from modules.emergency.module import EmergencyModule                 # noqa: E402
from modules.diagnostics.checker import DiagnosticsChecker           # noqa: E402
from modules.updates.checker import UpdateChecker                    # noqa: E402
from ui.console import ConsoleUI                                     # noqa: E402


# ═══════════════════════════════════════════════════════════════════════════════
# Утилита: обработчик «тихой смерти» asyncio.Task  ← FIX B-09
# ═══════════════════════════════════════════════════════════════════════════════
def _task_exception_handler(task: asyncio.Task) -> None:
    """Callback для фоновых задач: логирует необработанное исключение."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error(
            f"Фоновая задача [{task.get_name()}] упала с ошибкой: {exc!r}",
            exc_info=exc,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
async def main() -> None:
    """Основная корутина Cardinal_Multi."""

    # ── 6. БД ────────────────────────────────────────────────────────────────
    logger.info("Инициализация базы данных …")
    await init_db()
    logger.info("База данных готова")

    # ── 7. Совместимость плагинов ─────────────────────────────────────────────
    logger.info("Проверка совместимости плагинов …")
    try:
        check_all_plugins()
    except Exception as exc:
        logger.warning(f"Проверка совместимости: {exc}")

    # ── 8. Cardinal Bridge ───────────────────────────────────────────────────
    logger.info("Генерация Cardinal bridge-плагина …")
    try:
        generate_plugin_file()
        logger.info("Cardinal bridge-плагин готов")
    except Exception as exc:
        logger.warning(f"Cardinal bridge: {exc}")

    # ── 9. AccountManager ────────────────────────────────────────────────────
    logger.info("Запуск AccountManager …")
    account_manager = AccountManager()
    try:
        await account_manager.setup()
        await account_manager.start()
        logger.info("AccountManager запущен")
    except Exception as exc:
        logger.error(f"AccountManager: {exc}", exc_info=True)

    # ══════════════════════════════════════════════════════════════════════════
    # 10. BotManager (Telegram)  ← FIX B-02
    # ══════════════════════════════════════════════════════════════════════════
    bot_manager = None
    bot_manager_task: asyncio.Task | None = None

    try:
        from bot.bot_manager import BotManager  # noqa: E402  (aiogram)

        bot_manager = BotManager()
        # Передаём ОБЩИЙ экземпляр AccountManager (shared reference)
        bot_manager.account_manager = account_manager

        # BotManager.start() блокирует (polling) → запускаем как Task
        bot_manager_task = asyncio.create_task(
            bot_manager.start(),
            name="bot_manager",
        )
        # FIX B-09: при падении Task логируем, а не теряем молча
        bot_manager_task.add_done_callback(_task_exception_handler)

        logger.info("BotManager (Telegram) запущен в фоне")
    except ImportError:
        logger.warning(
            "BotManager не найден (bot/bot_manager.py отсутствует) — "
            "Telegram-управление недоступно"
        )
    except Exception as exc:
        logger.warning(f"BotManager не запущен: {exc}")

    # ── 11. LolzteamModule ───────────────────────────────────────────────────
    lolzteam_module: LolzteamModule | None = None

    lolz_token = getattr(settings, "lolz_api_token", None) or getattr(
        settings, "lolzteam_token", None
    )
    lolz_login = getattr(settings, "lolz_login", None)
    lolz_password = getattr(settings, "lolz_password", None)

    if lolz_token or (lolz_login and lolz_password):
        logger.info("Запуск LolzteamModule …")
        lolzteam_module = LolzteamModule()
        try:
            await lolzteam_module.setup()
            await lolzteam_module.start()
            logger.info("LolzteamModule запущен")
        except Exception as exc:
            logger.error(f"LolzteamModule: {exc}", exc_info=True)
            lolzteam_module = None
    else:
        logger.warning(
            "LolzteamModule не запущен: "
            "не задан LOLZ_API_TOKEN / (LOLZ_LOGIN + LOLZ_PASSWORD)"
        )

    # ══════════════════════════════════════════════════════════════════════════
    # 12–17. Scheduler + модули
    # ══════════════════════════════════════════════════════════════════════════

    # ── 12. APScheduler ──────────────────────────────────────────────────────
    logger.info("Запуск APScheduler …")
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.start()
    logger.info("APScheduler запущен")

    # ── 13. EmergencyModule ──────────────────────────────────────────────────
    logger.info("Запуск EmergencyModule …")
    emergency_module = EmergencyModule()
    try:
        await emergency_module.setup()
        await emergency_module.start()
        logger.info("EmergencyModule запущен")
    except Exception as exc:
        logger.error(f"EmergencyModule: {exc}", exc_info=True)

    # ── 14. StatsModule ──────────────────────────────────────────────────────
    logger.info("Запуск StatsModule …")
    stats_module = StatsModule(scheduler=scheduler)
    try:
        await stats_module.setup()
        await stats_module.start()
        logger.info("StatsModule запущен")
    except Exception as exc:
        logger.error(f"StatsModule: {exc}", exc_info=True)

    # ── 15. BalanceModule ────────────────────────────────────────────────────
    logger.info("Запуск BalanceModule …")
    balance_module = BalanceModule(
        scheduler=scheduler,
        accounts_getter=account_manager.get_active_accounts,
    )
    try:
        await balance_module.setup()
        await balance_module.start()
        logger.info("BalanceModule запущен")
    except Exception as exc:
        logger.error(f"BalanceModule: {exc}", exc_info=True)

    # ── 16. DiagnosticsChecker ───────────────────────────────────────────────
    logger.info("DiagnosticsChecker готов")
    _diagnostics = DiagnosticsChecker()  # noqa: F841

    # ── 17. UpdateChecker ────────────────────────────────────────────────────
    logger.info("Проверка обновлений …")
    update_checker = UpdateChecker()
    try:
        await update_checker.check()
    except Exception as exc:
        logger.warning(f"UpdateChecker (первый запуск): {exc}")

    scheduler.add_job(
        update_checker.check,
        trigger="interval",
        hours=24,
        id="update_check_daily",
        replace_existing=True,
    )
    logger.info("UpdateChecker: следующая проверка через 24 ч")

    # ══════════════════════════════════════════════════════════════════════════
    # 18. Rich Console UI / Ctrl+C
    # ══════════════════════════════════════════════════════════════════════════
    logger.info("Cardinal_Multi полностью запущен. Ctrl+C для остановки.")

    ui = ConsoleUI()
    try:
        await ui.run(
            account_manager=account_manager,
            lolzteam_module=lolzteam_module,
        )
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Получен сигнал остановки …")
    finally:
        await _shutdown(
            account_manager=account_manager,
            lolzteam_module=lolzteam_module,
            scheduler=scheduler,
            emergency_module=emergency_module,
            stats_module=stats_module,
            balance_module=balance_module,
            bot_manager=bot_manager,
            bot_manager_task=bot_manager_task,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SHUTDOWN
# ═══════════════════════════════════════════════════════════════════════════════
async def _shutdown(
    *,
    account_manager: AccountManager,
    lolzteam_module: LolzteamModule | None,
    scheduler: AsyncIOScheduler,
    emergency_module: EmergencyModule,
    stats_module: StatsModule,
    balance_module: BalanceModule,
    bot_manager,
    bot_manager_task: asyncio.Task | None,
) -> None:
    """
    Graceful shutdown в обратном порядке запуска.

    Порядок:
      0. BotManager  (иначе будет дёргать account_manager после его остановки)
      1. BalanceModule
      2. StatsModule
      3. EmergencyModule
      4. APScheduler
      5. LolzteamModule
      6. AccountManager
    """
    logger.info("Остановка Cardinal_Multi …")

    # ── 0. BotManager ────────────────────────────────────────────────────────
    if bot_manager is not None:
        try:
            await bot_manager.stop()
            logger.info("BotManager остановлен")
        except Exception as exc:
            logger.error(f"BotManager stop: {exc}")

    if bot_manager_task is not None and not bot_manager_task.done():
        bot_manager_task.cancel()
        try:
            await bot_manager_task
        except (asyncio.CancelledError, Exception):
            pass

    # ── 1. BalanceModule ─────────────────────────────────────────────────────
    try:
        await balance_module.stop()
        logger.info("BalanceModule остановлен")
    except Exception as exc:
        logger.error(f"BalanceModule stop: {exc}")

    # ── 2. StatsModule ───────────────────────────────────────────────────────
    try:
        await stats_module.stop()
        logger.info("StatsModule остановлен")
    except Exception as exc:
        logger.error(f"StatsModule stop: {exc}")

    # ── 3. EmergencyModule ───────────────────────────────────────────────────
    try:
        await emergency_module.stop()
        logger.info("EmergencyModule остановлен")
    except Exception as exc:
        logger.error(f"EmergencyModule stop: {exc}")

    # ── 4. APScheduler ───────────────────────────────────────────────────────
    try:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler остановлен")
    except Exception as exc:
        logger.error(f"APScheduler: {exc}")

    # ── 5. LolzteamModule ────────────────────────────────────────────────────
    if lolzteam_module is not None:
        try:
            await lolzteam_module.stop()
            logger.info("LolzteamModule остановлен")
        except Exception as exc:
            logger.error(f"LolzteamModule stop: {exc}")

    # ── 6. AccountManager ────────────────────────────────────────────────────
    try:
        await account_manager.stop()
        logger.info("AccountManager остановлен")
    except Exception as exc:
        logger.error(f"AccountManager stop: {exc}")

    logger.info("Cardinal_Multi остановлен. До свидания!")


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass