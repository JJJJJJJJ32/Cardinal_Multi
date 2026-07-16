"""
modules/stats/formatter.py
Форматирование статистики для вывода в Telegram.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def format_stats(
    data: Dict[str, Any],
    period_label: str,
    top_lots: Optional[List[Dict]] = None,
) -> str:
    """
    Форматировать агрегированную статистику в текст для Telegram.

    Args:
        data:         Результат StatsCollector.get_stats().
        period_label: "сегодня" / "7 дней" / "30 дней" / "всё время".
        top_lots:     Список {'name': str, 'count': int, 'profit': float}.

    Returns:
        Строка в HTML для отправки в Telegram.
    """
    revenue = data.get("revenue", 0.0)
    orders = data.get("orders_count", 0)
    expenses = data.get("lolz_expenses", 0.0)
    profit = data.get("profit", 0.0)
    avg_time = data.get("avg_delivery_time")

    avg_str = "—"
    if avg_time is not None:
        minutes = int(avg_time // 60)
        seconds = int(avg_time % 60)
        avg_str = f"{minutes} мин {seconds} сек"

    lines = [
        f"📊 <b>Статистика — {period_label}</b>",
        "",
        f"💰 Выручка: <b>{revenue:,.0f} руб</b>",
        f"📦 Заказов: <b>{orders}</b>",
        f"🛒 Расходы Lolzteam: <b>{expenses:,.0f} руб</b>",
        f"📈 Прибыль: <b>{profit:,.0f} руб</b>",
        f"⏱ Среднее время выдачи: <b>{avg_str}</b>",
    ]

    if top_lots:
        lines.append("")
        lines.append("🏆 <b>Топ лотов (по продажам):</b>")
        for i, lot in enumerate(top_lots[:5], start=1):
            lines.append(
                f"{i}. {lot['name']} — <b>{lot['count']} продаж</b>"
                + (f" / {lot['profit']:,.0f} руб" if lot.get("profit") else "")
            )

    return "\n".join(lines)


def format_balance_alert(
    account_name: str,
    funpay_balance: Optional[float],
    funpay_threshold: Optional[float],
    lolz_balance: Optional[float],
    lolz_threshold: Optional[float],
) -> str:
    """Форматировать уведомление о низком балансе."""
    lines = ["⚠️ <b>Низкий баланс!</b>", f"👤 Аккаунт: {account_name}", ""]

    if funpay_balance is not None and funpay_threshold is not None:
        status = "🔴" if funpay_balance < funpay_threshold else "🟢"
        lines.append(
            f"{status} FunPay: <b>{funpay_balance:,.0f} руб</b> "
            f"(порог: {funpay_threshold:,.0f} руб)"
        )

    if lolz_balance is not None and lolz_threshold is not None:
        status = "🔴" if lolz_balance < lolz_threshold else "🟢"
        lines.append(
            f"{status} Lolzteam: <b>{lolz_balance:,.0f} руб</b> "
            f"(порог: {lolz_threshold:,.0f} руб)"
        )

    return "\n".join(lines)