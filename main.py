"""
main.py — точка входа Cardinal_Multi.

Порядок запуска:
    1. Инициализация логгера (loguru → файл)
    2. Загрузка настроек из .env
    3. Инициализация шифрования
    4. Инициализация БД (создание таблиц)
    5. Проверка совместимости с плагинами Cardinal
    6. Запуск AccountManager
    7. Запуск Rich-дашборда
    8. Ожидание Ctrl+C
    9. Корректное завершение

Ничего из Cardinal не изменяется.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# ─── Добавляем корень проекта в sys.path ──────────────────────────────────────
_root = Path(__file__).parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


async def main() -> None:
    """Главная async-функция Cardinal_Multi."""

    # ── 1. Logger ─────────────────────────────────────────────────────────────
    from modules.core.logger import setup_logger
    from modules.core.config import get_settings

    # Временно инициализируем с DEBUG до загрузки настроек
    setup_logger("DEBUG")

    from loguru import logger
    logger.info("=" * 60)
    logger.info("Cardinal_Multi v1.0.0 — запуск")
    logger.info("=" * 60)

    # ── 2. Настройки ──────────────────────────────────────────────────────────
    from ui.console import console, show_error, show_info

    try:
        settings = get_settings()
        # Переинициализируем логгер с правильным уровнем
        setup_logger(settings.log_level)
        show_info("Настройки загружены.")
    except SystemExit as exc:
        show_error(
            str(exc),
            hint="Запусти setup.py для первоначальной настройки: python setup.py",
        )
        sys.exit(1)

    # ── 3. Шифрование ─────────────────────────────────────────────────────────
    from modules.core.encryption import Encryption, EncryptionError
    try:
        Encryption()  # инициализация (создаёт ключ если нет)
        show_info("Шифрование инициализировано.")
    except EncryptionError as exc:
        show_error(f"Ошибка шифрования: {exc}")
        sys.exit(1)

    # ── 4. БД ─────────────────────────────────────────────────────────────────
    from modules.core.database import init_db, close_db
    try:
        await init_db()
        show_info("База данных готова.")
    except RuntimeError as exc:
        show_error(
            str(exc),
            hint="Проверь права на папку data/ и попробуй снова.",
        )
        sys.exit(1)

    # ── 5. Совместимость с плагинами Cardinal ─────────────────────────────────
    from modules.cardinal_bridge.compatibility import (
        check_all_plugins,
        log_compatibility_report,
    )
    compat_results = check_all_plugins()
    log_compatibility_report(compat_results)

    # ── 6. Генерируем плагин-мост для основного Cardinal ─────────────────────
    from modules.cardinal_bridge.hooks import generate_plugin_file
    try:
        generate_plugin_file(account_id=1)
        show_info("Плагин-мост Cardinal создан (plugins/cardinal_multi_bridge.py).")
    except Exception as exc:
        logger.warning("Не удалось создать плагин-мост: {}", exc)

    # ── 7. AccountManager ─────────────────────────────────────────────────────
    from modules.multi.account_manager import AccountManager

    manager = AccountManager()

    try:
        await manager.setup()
        show_info(f"AccountManager инициализирован.")
    except Exception as exc:
        show_error(
            f"Ошибка инициализации AccountManager: {exc}",
            hint="Проверь логи: logs/cardinal_multi.log",
        )
        sys.exit(1)

    try:
        await manager.start()
    except Exception as exc:
        show_error(
            f"Ошибка запуска аккаунтов: {exc}",
            hint="Проверь golden_key аккаунтов в настройках.",
        )
        await close_db()
        sys.exit(1)

    # ── 8. Дашборд + ожидание ─────────────────────────────────────────────────
    from ui.console import run_dashboard

    try:
        # Запускаем дашборд как задачу
        dashboard_task = asyncio.create_task(
            run_dashboard(manager),
            name="cardinal_multi_dashboard",
        )

        # Ждём Ctrl+C
        await dashboard_task

    except KeyboardInterrupt:
        pass
    except Exception as exc:
        logger.error("Критическая ошибка: {}", exc)
    finally:
        # ── 9. Корректное завершение ──────────────────────────────────────────
        console.print("\n[bold yellow]Остановка Cardinal_Multi...[/bold yellow]")

        try:
            await manager.stop()
        except Exception as exc:
            logger.error("Ошибка при остановке менеджера: {}", exc)

        await close_db()
        logger.info("Cardinal_Multi завершён.")
        console.print("[bold green]Завершено.[/bold green]")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass