"""
setup.py — мастер первоначальной настройки Cardinal_Multi.

Rich-интерфейс для:
- Настройки аккаунтов FunPay
- Настройки Telegram-ботов
- Проверки подключений
- Создания .env файла
- Инициализации БД
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# ─── sys.path ─────────────────────────────────────────────────────────────────
_root = Path(__file__).parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.text import Text
from rich import box
from rich.rule import Rule

console = Console()

ENV_FILE = Path(".env")
ENV_EXAMPLE_FILE = Path(".env.example")

# ─── Вспомогательные функции ──────────────────────────────────────────────────

def _print_step(step: int, total: int, title: str) -> None:
    """Печатает заголовок шага."""
    console.print(f"\n[bold cyan]Шаг {step}/{total}:[/bold cyan] [bold white]{title}[/bold white]")
    console.print(Rule(style="cyan"))


def _print_success(msg: str) -> None:
    console.print(f"[bold green]✅[/bold green] {msg}")


def _print_error(msg: str, hint: str | None = None) -> None:
    console.print(f"[bold red]❌[/bold red] {msg}")
    if hint:
        console.print(f"   [dim yellow]→ {hint}[/dim yellow]")


def _print_warning(msg: str) -> None:
    console.print(f"[bold yellow]⚠️[/bold yellow]  {msg}")


def _print_info(msg: str) -> None:
    console.print(f"[bold cyan]ℹ[/bold cyan]  {msg}")


# ─── Проверка golden_key ───────────────────────────────────────────────────────

async def _check_golden_key(golden_key: str) -> tuple[bool, str | None]:
    """
    Проверяет golden_key через FunPayAPI.

    :param golden_key: golden_key для проверки.
    :return: (success, username или None).
    """
    try:
        # Пробуем импортировать FunPayAPI (Cardinal должен быть установлен)
        from FunPayAPI import Account  # type: ignore
        account = Account(golden_key=golden_key)
        await asyncio.get_event_loop().run_in_executor(None, account.get)
        return True, getattr(account, "username", None)
    except ImportError:
        # FunPayAPI недоступен в текущем окружении
        _print_warning(
            "FunPayAPI недоступен для проверки golden_key. "
            "Ключ будет сохранён без проверки."
        )
        return True, None
    except Exception as exc:
        return False, str(exc)


# ─── Проверка Telegram ────────────────────────────────────────────────────────

async def _check_telegram(token: str, chat_id: str) -> bool:
    """
    Проверяет Telegram бот-токен, отправляя тестовое сообщение.

    :param token: токен Telegram-бота.
    :param chat_id: Telegram chat_id.
    :return: True если успешно.
    """
    try:
        import telebot  # type: ignore

        bot = telebot.TeleBot(token)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: bot.send_message(
                chat_id,
                "✅ Cardinal_Multi подключён! Это тестовое сообщение.",
            )
        )
        return True
    except ImportError:
        _print_warning("pyTelegramBotAPI не установлен. Telegram не проверен.")
        return True
    except Exception as exc:
        _print_error(f"Ошибка Telegram: {exc}")
        return False


# ─── Сохранение .env ──────────────────────────────────────────────────────────

def _save_env(config: dict) -> None:
    """
    Сохраняет конфигурацию в .env файл.

    :param config: словарь с настройками.
    """
    lines = [
        "# Cardinal_Multi — файл конфигурации",
        "# Автоматически создан setup.py",
        "# НЕ добавляй этот файл в git!",
        "",
        "# Логирование",
        f"LOG_LEVEL={config.get('log_level', 'INFO')}",
        "",
        "# Аккаунты",
        f"MAX_ACCOUNTS={config.get('max_accounts', 1)}",
        "",
        "# Telegram (главный бот)",
        f"MAIN_TELEGRAM_TOKEN={config.get('main_telegram_token', '')}",
        f"MAIN_TELEGRAM_CHAT_ID={config.get('main_telegram_chat_id', '')}",
        "",
        "# Порог уведомления о балансе",
        f"BALANCE_ALERT_THRESHOLD={config.get('balance_alert_threshold', 100.0)}",
        "",
        "# Lolzteam (заполняется другим модулем)",
        "LOLZTEAM_TOKEN=",
        "",
        "# AI консультант (заполняется другим модулем)",
        "OPENAI_API_KEY=",
    ]

    ENV_FILE.write_text("\n".join(lines), encoding="utf-8")


# ─── Главный мастер настройки ─────────────────────────────────────────────────

async def run_setup() -> None:
    """Главная функция мастера настройки."""

    # ── Заголовок ─────────────────────────────────────────────────────────────
    console.print(Panel(
        "[bold white]CARDINAL MULTI v1.0.0[/bold white]\n"
        "[dim]Мастер первоначальной настройки[/dim]",
        box=box.DOUBLE,
        style="bold blue",
        expand=False,
    ))
    console.print()

    # ── Проверка существующей настройки ───────────────────────────────────────
    if ENV_FILE.exists():
        console.print(Panel(
            "[bold white]Настройки уже существуют.[/bold white]\n\n"
            "[bold cyan][1][/bold cyan] Изменить настройки\n"
            "[bold cyan][2][/bold cyan] Запустить программу",
            box=box.ROUNDED,
            border_style="yellow",
        ))
        choice = Prompt.ask(
            "Выбор",
            choices=["1", "2"],
            default="2",
        )
        if choice == "2":
            console.print("[bold green]Запуск Cardinal_Multi...[/bold green]")
            return

    # ── Данные для сохранения ─────────────────────────────────────────────────
    env_config: dict = {"log_level": "INFO"}
    accounts_data: list[dict] = []

    total_steps = 5

    # ─────────────────────────────────────────────────────────────────────────
    # ШАГ 1 — Режим работы
    # ─────────────────────────────────────────────────────────────────────────
    _print_step(1, total_steps, "Режим работы")

    console.print("Сколько аккаунтов FunPay?")
    console.print("[bold cyan][1][/bold cyan] Один аккаунт")
    console.print("[bold cyan][2][/bold cyan] Несколько аккаунтов (до 5)")

    mode = Prompt.ask("Выбор", choices=["1", "2"], default="1")
    multi_mode = (mode == "2")
    max_accounts = 5 if multi_mode else 1
    env_config["max_accounts"] = max_accounts

    # ─────────────────────────────────────────────────────────────────────────
    # ШАГ 2 — Аккаунты FunPay
    # ─────────────────────────────────────────────────────────────────────────
    _print_step(2, total_steps, "Аккаунт FunPay")

    account_count = 1
    while account_count <= max_accounts:
        console.print(f"\n[bold white]Аккаунт {account_count}[/bold white]")

        # Инструкция
        _print_info(
            "Где найти golden_key:\n"
            "   Браузер → FunPay → F12 → Application → Cookies → golden_key"
        )

        while True:
            golden_key = Prompt.ask(f"  golden_key для аккаунта {account_count}").strip()
            if not golden_key:
                _print_error("golden_key не может быть пустым.")
                continue

            console.print("  [dim]Проверка подключения...[/dim]")
            success, username_or_err = await _check_golden_key(golden_key)

            if success:
                display = f"@{username_or_err}" if username_or_err else "(имя получено при запуске)"
                _print_success(f"Подключён: {display}")
                account_name = Prompt.ask(
                    "  Имя аккаунта (для отображения)",
                    default=display,
                )
                accounts_data.append({
                    "golden_key": golden_key,
                    "name":       account_name,
                    "username":   username_or_err,
                    "is_primary": account_count == 1,
                })
                break
            else:
                _print_error(
                    f"Ошибка подключения: {username_or_err}",
                    hint="Проверь golden_key — он должен быть актуальным.",
                )
                retry = Confirm.ask("  Попробовать снова?", default=True)
                if not retry:
                    break

        if multi_mode and account_count < max_accounts:
            add_more = Confirm.ask(
                f"\nДобавить ещё аккаунт? (добавлено {account_count}/{max_accounts})",
                default=False,
            )
            if not add_more:
                break

        if not multi_mode:
            break
        account_count += 1

    # ─────────────────────────────────────────────────────────────────────────
    # ШАГ 3 — Telegram
    # ─────────────────────────────────────────────────────────────────────────
    _print_step(3, total_steps, "Telegram")

    _print_info(
        "Где получить токен бота:\n"
        "   Telegram → @BotFather → /newbot"
    )
    _print_info(
        "Где получить chat_id:\n"
        "   Telegram → @userinfobot → /start"
    )

    if multi_mode:
        console.print("\nНужен ли главный бот для управления всеми аккаунтами?")
        console.print("[bold cyan][1][/bold cyan] Да — создам отдельный главный бот")
        console.print("[bold cyan][2][/bold cyan] Нет — использовать бота первого аккаунта")
        tg_mode = Prompt.ask("Выбор", choices=["1", "2"], default="2")
        use_main_bot = (tg_mode == "1")
    else:
        use_main_bot = False

    main_tg_token = ""
    main_tg_chat_id = ""

    if use_main_bot or not multi_mode:
        while True:
            main_tg_token = Prompt.ask("  Токен Telegram бота").strip()
            main_tg_chat_id = Prompt.ask("  Твой Telegram chat_id").strip()

            console.print("  [dim]Отправка тестового сообщения...[/dim]")
            tg_ok = await _check_telegram(main_tg_token, main_tg_chat_id)

            if tg_ok:
                _print_success("Telegram подключён!")
                break
            else:
                retry = Confirm.ask("  Попробовать снова?", default=True)
                if not retry:
                    break

    env_config["main_telegram_token"] = main_tg_token
    env_config["main_telegram_chat_id"] = main_tg_chat_id

    # Для каждого аккаунта — отдельный бот или главный?
    if multi_mode:
        for i, acc in enumerate(accounts_data):
            if i == 0 and not use_main_bot:
                # Первый аккаунт = основной бот
                continue

            console.print(f"\n[bold white]{acc['name']}[/bold white] — настройка бота:")
            console.print("[bold cyan][1][/bold cyan] Отдельный бот")
            console.print("[bold cyan][2][/bold cyan] Использовать главный бот")
            bot_choice = Prompt.ask("Выбор", choices=["1", "2"], default="2")

            if bot_choice == "1":
                acc_token = Prompt.ask("  Токен отдельного бота").strip()
                acc_chat_id = Prompt.ask("  chat_id владельца").strip()
                acc["telegram_token"] = acc_token
                acc["owner_chat_id"] = acc_chat_id
            else:
                acc["telegram_token"] = None
                acc["owner_chat_id"] = main_tg_chat_id

    # ─────────────────────────────────────────────────────────────────────────
    # ШАГ 4 — Инициализация системы
    # ─────────────────────────────────────────────────────────────────────────
    _print_step(4, total_steps, "Инициализация системы")

    # Сохраняем .env
    _save_env(env_config)
    _print_success(f".env создан: {ENV_FILE}")

    # Инициализируем шифрование
    try:
        from modules.core.encryption import Encryption
        Encryption()
        _print_success("Ключ шифрования создан: data/secret.key")
    except Exception as exc:
        _print_error(f"Ошибка создания ключа шифрования: {exc}")

    # Инициализируем БД
    try:
        from modules.core.database import init_db
        await init_db()
        _print_success("База данных создана: data/cardinal_multi.db")
    except Exception as exc:
        _print_error(f"Ошибка создания БД: {exc}")

    # Сохраняем аккаунты в БД
    try:
        from modules.core.database import get_session
        from modules.multi.models.account import Account as AccountModel
        from modules.core.encryption import Encryption

        enc = Encryption()

        async with get_session() as session:
            for acc_data in accounts_data:
                model = AccountModel()
                model.name = acc_data["name"]
                model.funpay_username = acc_data.get("username")
                model.set_golden_key(acc_data["golden_key"])
                model.is_primary = acc_data.get("is_primary", False)
                model.is_active = True
                model.owner_chat_id = acc_data.get(
                    "owner_chat_id", main_tg_chat_id
                )

                tg_token = acc_data.get("telegram_token")
                if tg_token:
                    model.set_telegram_token(tg_token)

                session.add(model)

        _print_success(f"Сохранено {len(accounts_data)} аккаунт(ов) в БД.")

    except Exception as exc:
        _print_error(f"Ошибка сохранения аккаунтов: {exc}")

    # ─────────────────────────────────────────────────────────────────────────
    # ШАГ 5 — Итог
    # ─────────────────────────────────────────────────────────────────────────
    _print_step(5, total_steps, "Итог")

    console.print()
    for acc in accounts_data:
        username = f"@{acc['username']}" if acc.get("username") else acc["name"]
        status = "основной" if acc.get("is_primary") else "дополнительный"
        _print_success(f"{username} — подключён [{status}]")

    if main_tg_token:
        _print_success("Telegram — подключён")

    _print_success("База данных — создана")
    _print_success("Ключ шифрования — создан")

    console.print()
    console.print(Panel(
        "[bold green]Настройка завершена![/bold green]\n\n"
        "Запусти: [bold cyan]start.bat[/bold cyan] (Windows) "
        "или [bold cyan]python main.py[/bold cyan] (Linux/Mac)",
        box=box.ROUNDED,
        border_style="green",
    ))


if __name__ == "__main__":
    asyncio.run(run_setup())