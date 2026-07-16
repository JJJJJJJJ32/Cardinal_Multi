"""
ui/console.py
─────────────
Rich-дашборд Cardinal_Multi.

Отображает статус всех аккаунтов и модулей.
Обновляется каждые 3 секунды через Live.
Перехватывает ошибки — пользователь видит понятное сообщение,
а не traceback.

НЕ использует print(). Только rich.
"""

from __future__ import annotations

import asyncio
import time
from datetime import timedelta
from typing import Any, TYPE_CHECKING

from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import print as rprint

if TYPE_CHECKING:
    from modules.multi.account_manager import AccountManager

# ─── Глобальный консольный объект ────────────────────────────────────────────
console = Console(highlight=False)

# ─── Версия ────────────────────────────────────────────────────────────────────
APP_VERSION = "1.0.0"


# ─── Вспомогательные функции ───────────────────────────────────────────────────

def _format_uptime(seconds: int | None) -> str:
    """Форматирует uptime в читаемый вид."""
    if seconds is None:
        return "—"
    return str(timedelta(seconds=seconds))


def _state_indicator(state: str) -> Text:
    """Возвращает цветной индикатор состояния."""
    indicators = {
        "running":   Text("● Активен",   style="bold green"),
        "starting":  Text("◐ Запуск...", style="bold yellow"),
        "stopping":  Text("◑ Стоп...",   style="bold yellow"),
        "stopped":   Text("○ Остановлен",style="dim"),
        "error":     Text("✗ Ошибка",    style="bold red"),
        "restarting":Text("↻ Перезапуск",style="bold cyan"),
        "idle":      Text("○ Ожидание",  style="dim"),
    }
    return indicators.get(state, Text(state, style="white"))


def _module_indicator(active: bool | None, label: str) -> Text:
    """Возвращает цветной индикатор модуля."""
    if active is None:
        return Text(f"○ {label}", style="dim")
    if active:
        return Text(f"● {label}", style="bold green")
    return Text(f"✗ {label}", style="bold red")


# ─── Построение панелей ────────────────────────────────────────────────────────

def _build_header() -> Panel:
    """Строит заголовок дашборда."""
    title = Text(f"CARDINAL MULTI  v{APP_VERSION}", style="bold white", justify="center")
    subtitle = Text("FunPay мультиаккаунт менеджер", style="dim", justify="center")
    content = Align.center(
        Text.assemble(title, "\n", subtitle),
        vertical="middle",
    )
    return Panel(
        content,
        box=box.DOUBLE,
        style="bold blue",
        height=5,
    )


def _build_accounts_table(manager_status: dict[str, Any]) -> Panel:
    """
    Строит таблицу статусов аккаунтов.

    :param manager_status: результат AccountManager.status().
    :return: rich Panel с таблицей.
    """
    table = Table(
        show_header=True,
        header_style="bold cyan",
        box=box.SIMPLE,
        expand=True,
        show_edge=False,
    )

    table.add_column("ID",       style="dim",          width=4,  justify="right")
    table.add_column("Аккаунт",  style="white",         min_width=16)
    table.add_column("Статус",   style="white",         min_width=14)
    table.add_column("PID",      style="dim",           width=8,  justify="right")
    table.add_column("Uptime",   style="dim",           width=12, justify="right")
    table.add_column("Роль",     style="dim",           width=10)

    accounts: dict = manager_status.get("accounts", {})

    if not accounts:
        table.add_row(
            "—", Text("Нет аккаунтов", style="dim italic"), "—", "—", "—", "—"
        )
    else:
        for account_id, acc_status in sorted(accounts.items()):
            role = Text("Основной", style="bold yellow") if acc_status.get("is_primary") else Text("—", style="dim")
            username = acc_status.get("funpay_username") or acc_status.get("name", "—")
            display_name = f"@{username}" if username.startswith("@") else username

            table.add_row(
                str(account_id),
                display_name,
                _state_indicator(acc_status.get("state", "idle")),
                str(acc_status.get("pid") or "—"),
                _format_uptime(acc_status.get("uptime_seconds")),
                role,
            )

    total = manager_status.get("total_accounts", 0)
    running = manager_status.get("running", 0)
    summary = Text(
        f"  Всего: {total}   Активных: {running}   Остановлено: {total - running}",
        style="dim",
    )

    return Panel(
        table,
        title="[bold cyan]Аккаунты FunPay[/bold cyan]",
        subtitle=str(summary),
        box=box.ROUNDED,
        border_style="cyan",
    )


def _build_modules_panel(modules_status: dict[str, Any]) -> Panel:
    """
    Строит панель статусов модулей.

    :param modules_status: словарь {module_name: {active: bool, label: str}}.
    :return: rich Panel.
    """
    rows = []
    module_map = {
        "telegram":  ("Telegram",      modules_status.get("telegram")),
        "lolzteam":  ("Lolzteam",      modules_status.get("lolzteam")),
        "ai":        ("AI консультант", modules_status.get("ai")),
        "stats":     ("Статистика",     modules_status.get("stats")),
    }

    for key, (label, active) in module_map.items():
        rows.append(_module_indicator(active, label))

    grid = Table.grid(padding=(0, 2))
    grid.add_column()
    grid.add_column()
    grid.add_row(rows[0], rows[2])
    grid.add_row(rows[1], rows[3])

    return Panel(
        grid,
        title="[bold cyan]Модули[/bold cyan]",
        box=box.ROUNDED,
        border_style="cyan",
    )


def _build_stats_panel(stats: dict[str, Any]) -> Panel:
    """
    Строит панель статистики.

    :param stats: словарь со статистикой.
    :return: rich Panel.
    """
    grid = Table.grid(padding=(0, 3))
    grid.add_column(style="dim", min_width=20)
    grid.add_column(style="bold white", justify="right")

    grid.add_row("Заказов сегодня:",  str(stats.get("orders_today", 0)))
    grid.add_row("Куплено сегодня:",  str(stats.get("purchased_today", 0)))
    grid.add_row("Сообщений сегодня:", str(stats.get("messages_today", 0)))

    return Panel(
        grid,
        title="[bold cyan]Статистика[/bold cyan]",
        box=box.ROUNDED,
        border_style="cyan",
    )


def _build_footer() -> Panel:
    """Строит подвал с подсказками управления."""
    text = Text(justify="center")
    text.append("[Ctrl+C]", style="bold yellow")
    text.append(" Остановить   ", style="dim")
    text.append("[R]", style="bold yellow")
    text.append(" Обновить", style="dim")
    return Panel(text, box=box.SIMPLE, style="dim")


def _build_layout(
    manager_status: dict[str, Any],
    modules_status: dict[str, Any],
    stats: dict[str, Any],
) -> Layout:
    """
    Строит полный layout дашборда.

    :param manager_status: статус AccountManager.
    :param modules_status: статус модулей.
    :param stats: статистика.
    :return: Layout для Rich Live.
    """
    layout = Layout()

    layout.split_column(
        Layout(name="header",   size=5),
        Layout(name="body",     ratio=1),
        Layout(name="footer",   size=3),
    )

    layout["body"].split_row(
        Layout(name="accounts", ratio=2),
        Layout(name="right",    ratio=1),
    )

    layout["right"].split_column(
        Layout(name="modules", ratio=1),
        Layout(name="stats",   ratio=1),
    )

    layout["header"].update(_build_header())
    layout["accounts"].update(_build_accounts_table(manager_status))
    layout["modules"].update(_build_modules_panel(modules_status))
    layout["stats"].update(_build_stats_panel(stats))
    layout["footer"].update(_build_footer())

    return layout


# ─── Публичный интерфейс ───────────────────────────────────────────────────────

def show_error(message: str, hint: str | None = None) -> None:
    """
    Отображает понятное сообщение об ошибке (без traceback).

    :param message: основное сообщение ошибки.
    :param hint: подсказка для решения проблемы.
    """
    text = Text()
    text.append("❌ ", style="bold red")
    text.append(message, style="red")

    if hint:
        text.append(f"\n   → {hint}", style="dim yellow")

    console.print(Panel(text, box=box.ROUNDED, border_style="red"))


def show_success(message: str) -> None:
    """
    Отображает сообщение об успехе.

    :param message: сообщение.
    """
    console.print(f"[bold green]✅[/bold green] {message}")


def show_warning(message: str) -> None:
    """
    Отображает предупреждение.

    :param message: сообщение.
    """
    console.print(f"[bold yellow]⚠️[/bold yellow]  {message}")


def show_info(message: str) -> None:
    """
    Отображает информационное сообщение.

    :param message: сообщение.
    """
    console.print(f"[bold cyan]ℹ[/bold cyan]  {message}")


async def run_dashboard(
    manager: "AccountManager",
    refresh_interval: float = 3.0,
) -> None:
    """
    Запускает живой Rich-дашборд.

    Обновляется каждые refresh_interval секунд.
    Блокирует до получения KeyboardInterrupt.

    :param manager: экземпляр AccountManager.
    :param refresh_interval: интервал обновления (секунды).
    """
    stats: dict[str, Any] = {
        "orders_today":    0,
        "purchased_today": 0,
        "messages_today":  0,
    }

    modules_status: dict[str, Any] = {
        "telegram": None,
        "lolzteam": None,
        "ai":       None,
        "stats":    None,
    }

    # Подписываемся на события для обновления статистики
    from modules.core.events import EventBus, EventType

    def on_new_order(event: EventType, data: Any) -> None:
        stats["orders_today"] += 1

    def on_new_message(event: EventType, data: Any) -> None:
        stats["messages_today"] += 1

    def on_item_purchased(event: EventType, data: Any) -> None:
        stats["purchased_today"] += 1

    bus = EventBus()
    bus.subscribe(EventType.NEW_ORDER, on_new_order)
    bus.subscribe(EventType.NEW_MESSAGE, on_new_message)
    bus.subscribe(EventType.ITEM_PURCHASED, on_item_purchased)

    try:
        with Live(
            console=console,
            refresh_per_second=1.0 / refresh_interval,
            screen=True,
        ) as live:
            while True:
                try:
                    manager_status = manager.status()
                    layout = _build_layout(manager_status, modules_status, stats)
                    live.update(layout)
                    await asyncio.sleep(refresh_interval)
                except Exception as exc:
                    # Ошибка дашборда не должна останавливать систему
                    from loguru import logger
                    logger.error("Ошибка обновления дашборда: {}", exc)
                    await asyncio.sleep(refresh_interval)
    except asyncio.CancelledError:
        pass
    finally:
        bus.unsubscribe(EventType.NEW_ORDER, on_new_order)
        bus.unsubscribe(EventType.NEW_MESSAGE, on_new_message)
        bus.unsubscribe(EventType.ITEM_PURCHASED, on_item_purchased)