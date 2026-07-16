from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_settings_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔑 FunPay (golden_key)", callback_data="settings:funpay")
    )
    builder.row(
        InlineKeyboardButton(text="🤖 AI настройки", callback_data="settings:ai")
    )
    builder.row(
        InlineKeyboardButton(
            text="🛒 Lolzteam настройки", callback_data="settings:lolzteam"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔔 Уведомления", callback_data="settings:notifications"
        )
    )
    builder.row(InlineKeyboardButton(text="🔙 Меню", callback_data="acc:menu"))
    return builder.as_markup()


def get_notifications_keyboard(notification_states: dict) -> InlineKeyboardMarkup:
    """
    notification_states — словарь {event_type: bool}
    Пример: {"NEW_ORDER": True, "BALANCE_LOW": False, ...}
    """
    builder = InlineKeyboardBuilder()

    labels = {
        "NEW_ORDER": "📦 Новый заказ",
        "SEARCH_STARTED": "🔍 Начало поиска",
        "ITEM_PURCHASED": "🛒 Покупка выполнена",
        "ITEM_DELIVERED": "✅ Товар выдан",
        "ACCOUNT_ERROR": "❌ Ошибка аккаунта",
        "BALANCE_LOW": "💸 Баланс ниже порога",
        "NEW_MESSAGE": "💬 Новое сообщение",
    }

    for event_type, label in labels.items():
        is_on = notification_states.get(event_type, True)
        status = "🟢" if is_on else "🔴"
        builder.row(
            InlineKeyboardButton(
                text=f"{status} {label}",
                callback_data=f"notif:toggle:{event_type}",
            )
        )

    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="acc:settings"))
    return builder.as_markup()