from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_orders_keyboard(
    orders: list[dict],
    page: int = 0,
    page_size: int = 10,
) -> InlineKeyboardMarkup:
    """
    Список активных заказов с пагинацией.
    orders — список словарей с ключами: id, lot_title, buyer, status.
    """
    builder = InlineKeyboardBuilder()
    total = len(orders)
    start = page * page_size
    end = min(start + page_size, total)
    page_orders = orders[start:end]

    for order in page_orders:
        label = (
            f"#{order['id']} | {order['lot_title'][:20]} | "
            f"{order['buyer']} | {order['status']}"
        )
        builder.row(
            InlineKeyboardButton(
                text=label,
                callback_data=f"order:detail:{order['id']}",
            )
        )

    # Пагинация
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="◀️ Назад", callback_data=f"orders:page:{page-1}")
        )
    nav_buttons.append(
        InlineKeyboardButton(
            text=f"{page+1}/{(total-1)//page_size+1}", callback_data="noop"
        )
    )
    if end < total:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Вперёд ▶️", callback_data=f"orders:page:{page+1}"
            )
        )
    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="🔙 Меню", callback_data="acc:menu"))
    return builder.as_markup()


def get_order_actions_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Действия с конкретным заказом."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Подтвердить выдачу", callback_data=f"order:confirm:{order_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="💬 Написать покупателю", callback_data=f"order:message:{order_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="⏸ Приостановить", callback_data=f"order:pause:{order_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(text="🔙 К заказам", callback_data="acc:orders")
    )
    return builder.as_markup()