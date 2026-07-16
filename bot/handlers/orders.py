from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from loguru import logger

from bot.keyboards.orders import get_orders_keyboard, get_order_actions_keyboard

router = Router(name="orders")

# ─── Заглушки для данных (до подключения реальных модулей) ────────────────────

async def fetch_active_orders(account_id: int) -> list[dict]:
    """
    Заглушка. В реальной реализации:
    - читает из БД (events_log / account_lots)
    - или обращается к FunPayAPI через wrapper аккаунта.
    """
    return []


# ─── Хендлеры ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "acc:orders")
async def callback_orders(call: CallbackQuery) -> None:
    """Показать список заказов (страница 0)."""
    account_id = call.from_user.id  # TODO: достать из middleware / состояния

    orders = await fetch_active_orders(account_id)

    if not orders:
        await call.message.edit_text(
            text="📦 Активных заказов нет.\n\n_Данные обновляются автоматически._",
            parse_mode="Markdown",
            reply_markup=None,
        )
        await call.answer()
        return

    await call.message.edit_text(
        text=f"📦 <b>Активные заказы</b> ({len(orders)} шт.):",
        parse_mode="HTML",
        reply_markup=get_orders_keyboard(orders, page=0),
    )
    await call.answer()


@router.callback_query(F.data.startswith("orders:page:"))
async def callback_orders_page(call: CallbackQuery) -> None:
    """Пагинация заказов."""
    page = int(call.data.split(":")[-1])
    account_id = call.from_user.id

    orders = await fetch_active_orders(account_id)
    await call.message.edit_text(
        text=f"📦 <b>Активные заказы</b> ({len(orders)} шт.):",
        parse_mode="HTML",
        reply_markup=get_orders_keyboard(orders, page=page),
    )
    await call.answer()


@router.callback_query(F.data.startswith("order:detail:"))
async def callback_order_detail(call: CallbackQuery) -> None:
    """Карточка конкретного заказа."""
    order_id = call.data.split(":")[-1]

    # TODO: загрузить детали заказа из БД
    text = (
        f"📦 <b>Заказ #{order_id}</b>\n\n"
        f"Лот: —\n"
        f"Покупатель: —\n"
        f"Статус: —\n"
        f"Время: —\n"
    )
    await call.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=get_order_actions_keyboard(order_id),
    )
    await call.answer()


@router.callback_query(F.data.startswith("order:confirm:"))
async def callback_order_confirm(call: CallbackQuery) -> None:
    order_id = call.data.split(":")[-1]
    # TODO: вызов подтверждения выдачи через AccountWrapper
    await call.answer(f"✅ Выдача заказа #{order_id} подтверждена (заглушка)", show_alert=True)


@router.callback_query(F.data.startswith("order:pause:"))
async def callback_order_pause(call: CallbackQuery) -> None:
    order_id = call.data.split(":")[-1]
    # TODO: пауза заказа
    await call.answer(f"⏸ Заказ #{order_id} приостановлен (заглушка)", show_alert=True)