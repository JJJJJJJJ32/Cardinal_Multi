"""
setup.py — мастер первоначальной настройки Cardinal_Multi.

Запуск: python setup.py

Выполняет:
1) Сбор настроек от пользователя через Rich-интерфейс
2) Best-effort проверку golden_key (FunPayAPI) и Telegram-токена
3) Запись .env
4) Инициализацию Encryption (data/secret.key)
5) Создание БД (data/cardinal_multi.db)
6) Сохранение аккаунтов в БД (с шифрованием golden_key)
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.rule import Rule

# ── sys.path: чтобы работали импорты из корня проекта ────────────────────────
ROOT = Path(__file__).parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

console = Console()

ENV_FILE = ROOT / ".env"


# ─── UI-helpers ──────────────────────────────────────────────────────────────
def _step(n: int, total: int, title: str) -> None:
    console.print(f"\n[bold cyan]Шаг {n}/{total}:[/bold cyan] [bold white]{title}[/bold white]")
    console.print(Rule(style="cyan"))


def _ok(msg: str) -> None:
    console.print(f"[bold green]✅[/bold green] {msg}")


def _warn(msg: str) -> None:
    console.print(f"[bold yellow]⚠[/bold yellow]  {msg}")


def _err(msg: str) -> None:
    console.print(f"[bold red]❌[/bold red] {msg}")


def _ask_float(prompt: str, default: float, min_val: float = 0.0) -> float:
    """Запрашивает float с валидацией."""
    while True:
        raw = Prompt.ask(prompt, default=str(default)).strip()
        try:
            v = float(raw)
            if v < min_val:
                _err(f"Значение должно быть >= {min_val}.")
                continue
            return v
        except ValueError:
            _err("Введи число (например: 1.5)")


def _ask_int(prompt: str, default: int, min_val: int = 1, max_val: int = 5) -> int:
    """Запрашивает int с валидацией диапазона."""
    while True:
        raw = Prompt.ask(prompt, default=str(default)).strip()
        try:
            v = int(raw)
            if not min_val <= v <= max_val:
                _err(f"Введи число от {min_val} до {max_val}.")
                continue
            return v
        except ValueError:
            _err("Введи целое число.")


# ─── Проверки подключения ────────────────────────────────────────────────────
async def _check_golden_key(golden_key: str) -> tuple[bool, str | None]:
    """
    Best-effort проверка golden_key через FunPayAPI.
    Возвращает (успех, username или сообщение об ошибке).
    """
    try:
        from FunPayAPI import Account  # type: ignore

        account = Account(golden_key=golden_key)
        await asyncio.to_thread(account.get)
        username: str | None = getattr(account, "username", None)
        return True, username
    except ImportError:
        _warn("FunPayAPI не найден — golden_key принят без проверки.")
        return True, None
    except Exception as exc:
        return False, str(exc)


async def _check_telegram(token: str, chat_id: int) -> bool:
    """
    Best-effort проверка Telegram-токена.
    Отправляет тестовое сообщение через pyTelegramBotAPI (sync).
    """
    try:
        import telebot  # type: ignore

        bot = telebot.TeleBot(token)
        await asyncio.to_thread(
            bot.send_message,
            chat_id,
            "✅ Cardinal_Multi подключён! Это тестовое сообщение от setup.py.",
        )
        return True
    except ImportError:
        _warn("pyTelegramBotAPI не установлен — Telegram проверка пропущена.")
        return True
    except Exception as exc:
        _err(f"Telegram ошибка: {exc}")
        return False


# ─── Запись .env ─────────────────────────────────────────────────────────────
def _save_env(cfg: dict[str, Any]) -> None:
    """Сохраняет собранные настройки в .env."""
    lines: list[str] = [
        "# Cardinal_Multi — конфигурация",
        "# Создан автоматически setup.py",
        "# НЕ добавляй этот файл в git!",
        "",
        "# Система",
        f"LOG_LEVEL={cfg.get('log_level', 'INFO')}",
        f"MAX_ACCOUNTS={cfg.get('max_accounts', 1)}",
        f"REQUEST_DELAY={cfg.get('request_delay', 1.0)}",
        "",
        "# Telegram",
        f"MAIN_TELEGRAM_TOKEN={cfg.get('main_telegram_token', '')}",
        f"MAIN_TELEGRAM_CHAT_ID={cfg.get('main_telegram_chat_id', '')}",
        "",
        "# Мониторинг баланса (рубли)",
        f"BALANCE_ALERT_THRESHOLD={cfg.get('balance_alert_threshold', 100.0)}",
        "",
        "# OpenAI (опционально)",
        "OPENAI_API_KEY=",
        "",
        "# Lolzteam (заполни один из способов или оба оставь пустыми)",
        "LOLZ_API_TOKEN=",
        "LOLZ_LOGIN=",
        "LOLZ_PASSWORD=",
        "LOLZ_CLIENT_ID=",
        "LOLZ_CLIENT_SECRET=",
        "LOLZ_SECRET_PHRASE=",
        "",
    ]
    ENV_FILE.write_text("\n".join(lines), encoding="utf-8")


# ─── Главный сценарий ────────────────────────────────────────────────────────
async def run_setup() -> None:
    console.print(Rule("[bold magenta]Cardinal_Multi — мастер настройки[/bold magenta]"))

    # Проверка: .env уже существует
    if ENV_FILE.exists():
        overwrite = Confirm.ask(
            f"[yellow].env уже существует ({ENV_FILE}). Перезаписать?[/yellow]",
            default=False,
        )
        if not overwrite:
            _warn("Отмена. .env не изменён.")
            return

    TOTAL = 5
    cfg: dict[str, Any] = {}

    # ── Шаг 1: Базовые настройки ─────────────────────────────────────────────
    _step(1, TOTAL, "Базовые настройки")

    cfg["log_level"] = Prompt.ask(
        "Уровень логирования",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
    )

    console.print("\nКоличество аккаунтов FunPay:")
    console.print("  [cyan]1[/cyan] — Один аккаунт")
    console.print("  [cyan]2..5[/cyan] — Несколько аккаунтов")

    max_accounts = _ask_int(
        "Максимум аккаунтов [1-5]",
        default=1,
        min_val=1,
        max_val=5,
    )
    cfg["max_accounts"] = max_accounts

    cfg["request_delay"] = _ask_float(
        "Задержка между запросами к FunPay (сек)",
        default=1.0,
        min_val=0.0,
    )

    cfg["balance_alert_threshold"] = _ask_float(
        "Порог уведомления о балансе (рубли, 0 = отключить)",
        default=100.0,
        min_val=0.0,
    )

    # ── Шаг 2: Аккаунты FunPay ───────────────────────────────────────────────
    _step(2, TOTAL, "Аккаунты FunPay")

    accounts_data: list[dict[str, Any]] = []

    for idx in range(1, max_accounts + 1):
        console.print(f"\n[bold white]Аккаунт {idx} из {max_accounts}[/bold white]")

        # Запрос golden_key с повтором при ошибке
        while True:
            golden_key = Prompt.ask("  golden_key").strip()
            if not golden_key:
                _err("golden_key не может быть пустым.")
                continue

            console.print("  [dim]Проверка подключения к FunPay...[/dim]")
            ok, user_or_err = await _check_golden_key(golden_key)

            if ok:
                display = f"@{user_or_err}" if user_or_err else f"Account {idx}"
                _ok(f"Подключение OK: {display}")
                break

            _err(f"Ошибка: {user_or_err}")
            if not Confirm.ask("  Попробовать снова?", default=True):
                _warn("Аккаунт пропущен.")
                golden_key = None  # type: ignore[assignment]
                break

        if golden_key is None:
            continue

        name = Prompt.ask(
            "  Имя аккаунта (для отображения)",
            default=f"@{user_or_err}" if user_or_err else f"Account {idx}",
        ).strip()

        accounts_data.append(
            {
                "golden_key": golden_key,
                "name": name,
                "username": user_or_err,
                "is_primary": idx == 1,
            }
        )

        # Предлагаем добавить следующий аккаунт (только если лимит не достигнут)
        if idx < max_accounts:
            if not Confirm.ask("  Добавить следующий аккаунт?", default=True):
                break

    if not accounts_data:
        _err("Не добавлено ни одного аккаунта. Настройка прервана.")
        return

    # Обновляем max_accounts под реальное количество добавленных
    cfg["max_accounts"] = len(accounts_data)

    # ── Шаг 3: Telegram ──────────────────────────────────────────────────────
    _step(3, TOTAL, "Telegram — главный бот")

    need_tg = Confirm.ask(
        "Настроить главный Telegram-бот для управления?",
        default=(len(accounts_data) > 1),
    )

    cfg["main_telegram_token"] = ""
    cfg["main_telegram_chat_id"] = ""

    if need_tg:
        token = Prompt.ask("  MAIN_TELEGRAM_TOKEN").strip()
        chat_id_raw = Prompt.ask("  MAIN_TELEGRAM_CHAT_ID (числовой)").strip()

        # Валидация chat_id
        try:
            chat_id = int(chat_id_raw)
        except ValueError:
            _err(f"MAIN_TELEGRAM_CHAT_ID должен быть числом, получено: '{chat_id_raw}'")
            _warn("Telegram не настроен. Можно задать вручную в .env позже.")
            token = ""
            chat_id = 0

        if token and chat_id:
            console.print("  [dim]Проверка Telegram...[/dim]")
            tg_ok = await _check_telegram(token, chat_id)
            if tg_ok:
                _ok("Telegram OK — тестовое сообщение отправлено.")
            else:
                _warn("Telegram проверка не прошла. Токен сохранён — проверь вручную.")

            cfg["main_telegram_token"] = token
            cfg["main_telegram_chat_id"] = chat_id

    # ── Шаг 4: Запись .env + Encryption + БД ─────────────────────────────────
    _step(4, TOTAL, "Создание .env, ключа шифрования и БД")

    _save_env(cfg)
    _ok(f".env создан: {ENV_FILE}")

    # Encryption
    try:
        from modules.core.encryption import Encryption

        Encryption()
        _ok("Ключ шифрования: data/secret.key")
    except Exception as exc:
        _err(f"Encryption: {exc}")
        return

    # DB
    try:
        from modules.core.database import init_db

        await init_db()
        _ok("База данных: data/cardinal_multi.db")
    except Exception as exc:
        _err(f"Ошибка создания БД: {exc}")
        return

    # Сохранение аккаунтов в БД
    try:
        from modules.core.database import get_session
        from modules.multi.models.account import Account as AccountModel

        saved = 0
        async with get_session() as session:
            for acc in accounts_data:
                model = AccountModel()
                model.name = acc["name"]
                model.funpay_username = acc.get("username")
                model.is_primary = bool(acc.get("is_primary", False))
                model.is_active = True
                model.owner_chat_id = (
                    str(cfg["main_telegram_chat_id"])
                    if cfg.get("main_telegram_chat_id")
                    else None
                )
                model.set_golden_key(acc["golden_key"])
                session.add(model)
                saved += 1

        _ok(f"Сохранено аккаунтов в БД: {saved}")
    except Exception as exc:
        _err(f"Ошибка сохранения аккаунтов: {exc}")
        return

    # ── Шаг 5: Итог ──────────────────────────────────────────────────────────
    _step(5, TOTAL, "Готово!")

    console.print("\n[bold green]Настройка завершена успешно![/bold green]\n")
    console.print("Следующие шаги:")
    console.print("  [cyan]1)[/cyan] Если нужен Lolzteam — заполни LOLZ_API_TOKEN в .env")
    console.print("  [cyan]2)[/cyan] Запуск: [bold]python main.py[/bold]")
    console.print()


if __name__ == "__main__":
    try:
        asyncio.run(run_setup())
    except KeyboardInterrupt:
        console.print("\n[yellow]Настройка прервана.[/yellow]")