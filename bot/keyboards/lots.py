from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_lots_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔍 Поиск лота", callback_data="lots:search")
    )
    builder.row(
        InlineKeyboardButton(text="⭐ Избранные лоты", callback_data="lots:favorites")
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Синхронизировать", callback_data="lots:sync")
    )
    builder.row(InlineKeyboardButton(text="🔙 Меню", callback_data="acc:menu"))
    return builder.as_markup()


def get_lots_keyboard(
    lots: list[dict],
    page: int = 0,
    page_size: int = 10,
    callback_prefix: str = "lot:detail",
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    total = len(lots)
    start = page * page_size
    end = min(start + page_size, total)

    for lot in lots[start:end]:
        builder.row(
            InlineKeyboardButton(
                text=f"📦 {lot['title'][:35]}",
                callback_data=f"{callback_prefix}:{lot['id']}",
            )
        )

    nav = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(text="◀️", callback_data=f"lots:page:{page-1}")
        )
    nav.append(
        InlineKeyboardButton(
            text=f"{page+1}/{max(1,(total-1)//page_size+1)}", callback_data="noop"
        )
    )
    if end < total:
        nav.append(
            InlineKeyboardButton(text="▶️", callback_data=f"lots:page:{page+1}")
        )
    if nav:
        builder.row(*nav)

    builder.row(InlineKeyboardButton(text="🔙 Лоты", callback_data="acc:lots"))
    return builder.as_markup()


def get_lot_actions_keyboard(lot_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="⭐ В избранное", callback_data=f"lot:favorite:{lot_id}"
        ),
        InlineKeyboardButton(
            text="✏️ Изменить цену", callback_data=f"lot:edit_price:{lot_id}"
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="⏸ Деактивировать", callback_data=f"lot:deactivate:{lot_id}"
        )
    )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="lots:search"))
    return builder.as_markup()