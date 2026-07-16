from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

router = Router(name="stats")


def build_stats_menu() -> object:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📅 Сегодня", callback_data="stats:today"))
    builder.row(InlineKeyboardButton(text="📆 7 дней", callback_data="stats:week"))
    builder.row(InlineKeyboardButton(text="🗓 30 дней", callback_data="stats:month"))
    builder.row(InlineKeyboardButton(text="📊 Всё время", callback_data="stats:all"))
    builder.row(InlineKeyboardButton(text="🔙 Меню", callback_data="acc:menu"))
    return builder.as_markup()


async def fetch_stats(account_id: int, period: str) -> dict:
    """
    Заглушка. В реальности:
    - обращается к modules/stats (когда модуль будет готов)
    - или читает events_log из БД с фильтром по дате.
    """
    return {
        "orders": 0,
        "revenue": 0.0,
        "purchased": 0,
        "messages": 0,
    }


@router.callback_query(F.data == "acc:stats")
async def callback_stats_menu(call: CallbackQuery) -> None:
    await call.message.edit_text(
        "📊 <b>Статистика</b>\n\nВыберите период:",
        parse_mode="HTML",
        reply_markup=build_stats_menu(),
    )
    await call.answer()


async def _show_stats(call: CallbackQuery, period: str, label: str) -> None:
    stats = await fetch_stats(call.from_user.id, period)
    text = (
        f"📊 <b>Статистика — {label}</b>\n\n"
        f"📦 Заказов: {stats['orders']}\n"
        f"💰 Выручка: {stats['revenue']} руб\n"
        f"🛒 Закуплено: {stats['purchased']} шт\n"
        f"💬 Сообщений: {stats['messages']}\n"
    )
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔙 К периодам", callback_data="acc:stats")
    )
    await call.message.edit_text(
        text, parse_mode="HTML", reply_markup=builder.as_markup()
    )
    await call.answer()


@router.callback_query(F.data == "stats:today")
async def callback_stats_today(call: CallbackQuery) -> None:
    await _show_stats(call, "today", "Сегодня")


@router.callback_query(F.data == "stats:week")
async def callback_stats_week(call: CallbackQuery) -> None:
    await _show_stats(call, "week", "7 дней")


@router.callback_query(F.data == "stats:month")
async def callback_stats_month(call: CallbackQuery) -> None:
    await _show_stats(call, "month", "30 дней")


@router.callback_query(F.data == "stats:all")
async def callback_stats_all(call: CallbackQuery) -> None:
    await _show_stats(call, "all", "Всё время")