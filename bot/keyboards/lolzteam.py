from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_lolzteam_menu(is_enabled: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    toggle_text = "🔴 Выключить автозакупку" if is_enabled else "🟢 Включить автозакупку"
    builder.row(
        InlineKeyboardButton(text=toggle_text, callback_data="lolz:toggle")
    )
    builder.row(
        InlineKeyboardButton(text="⚙️ Настройки лотов", callback_data="lolz:lot_settings")
    )
    builder.row(
        InlineKeyboardButton(text="🔍 Активные поиски", callback_data="lolz:active_searches")
    )
    builder.row(
        InlineKeyboardButton(text="📰 Журнал закупок", callback_data="lolz:journal")
    )
    builder.row(
        InlineKeyboardButton(text="👤 Lolzteam аккаунты", callback_data="lolz:accounts")
    )
    builder.row(InlineKeyboardButton(text="🔙 Меню", callback_data="acc:menu"))
    return builder.as_markup()


def get_lolzteam_lot_card_keyboard(
    lot_id: str, is_enabled: bool = False
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    toggle_text = "✅ Включена" if is_enabled else "❌ Выключена"
    builder.row(
        InlineKeyboardButton(
            text=f"Автозакупка: {toggle_text}",
            callback_data=f"lolz:lot_toggle:{lot_id}",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="⚙️ Настроить", callback_data=f"lolz:lot_configure:{lot_id}"
        ),
        InlineKeyboardButton(
            text="🗑 Сбросить", callback_data=f"lolz:lot_reset:{lot_id}"
        ),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 К лотам", callback_data="lolz:lot_settings")
    )
    return builder.as_markup()


def get_delivery_mode_keyboard(lot_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🚀 Автоматически",
            callback_data=f"lolz:delivery_mode:{lot_id}:auto",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="👀 С подтверждением",
            callback_data=f"lolz:delivery_mode:{lot_id}:manual",
        )
    )
    return builder.as_markup()


def get_bool_filter_keyboard(filter_key: str, lot_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Есть", callback_data=f"lolz:filter:{lot_id}:{filter_key}:true"
        ),
        InlineKeyboardButton(
            text="❌ Нет", callback_data=f"lolz:filter:{lot_id}:{filter_key}:false"
        ),
        InlineKeyboardButton(
            text="🔀 Любой",
            callback_data=f"lolz:filter:{lot_id}:{filter_key}:any",
        ),
    )
    return builder.as_markup()


def get_general_filters_keyboard(lot_id: str, current: dict) -> InlineKeyboardMarkup:
    """Inline кнопки редактирования общих фильтров."""
    builder = InlineKeyboardBuilder()

    def val(key: str) -> str:
        v = current.get(key)
        return str(v) if v is not None else "—"

    builder.row(
        InlineKeyboardButton(
            text=f"💰 Мин. цена: {val('min_price')}",
            callback_data=f"lolz:edit_filter:{lot_id}:min_price",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"💰 Макс. цена: {val('max_price')}",
            callback_data=f"lolz:edit_filter:{lot_id}:max_price",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"⭐ Мин. рейтинг: {val('min_rating')}%",
            callback_data=f"lolz:edit_filter:{lot_id}:min_rating",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"💬 Мин. отзывов: {val('min_reviews')}",
            callback_data=f"lolz:edit_filter:{lot_id}:min_reviews",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"📝 Обяз. слова: {val('required_words')}",
            callback_data=f"lolz:edit_filter:{lot_id}:required_words",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"🚫 Запрещ. слова: {val('forbidden_words')}",
            callback_data=f"lolz:edit_filter:{lot_id}:forbidden_words",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="➡️ Далее (специф. фильтры)",
            callback_data=f"lolz:next_specific:{lot_id}",
        )
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data=f"lolz:lot_configure:{lot_id}")
    )
    return builder.as_markup()