from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_main_bot_menu() -> InlineKeyboardMarkup:
    """Клавиатура главного меню главного бота."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📱 Аккаунты", callback_data="main:accounts")
    )
    builder.row(
        InlineKeyboardButton(text="📊 Общая статистика", callback_data="main:stats")
    )
    builder.row(
        InlineKeyboardButton(
            text="⛔ Экстренная пауза ВСЕХ", callback_data="main:emergency_pause"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔔 Уведомления о версии", callback_data="main:updates"
        )
    )
    builder.row(
        InlineKeyboardButton(text="⚙️ Настройки установки", callback_data="main:settings")
    )
    return builder.as_markup()


def get_accounts_menu() -> InlineKeyboardMarkup:
    """Подменю управления аккаунтами."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="➕ Добавить аккаунт", callback_data="accounts:add"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📋 Список аккаунтов", callback_data="accounts:list"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📄 Клонировать настройки", callback_data="accounts:clone"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🗑 Удалить аккаунт", callback_data="accounts:delete"
        )
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="main:menu")
    )
    return builder.as_markup()


def get_account_bot_menu() -> InlineKeyboardMarkup:
    """Главное меню бота аккаунта."""
    builder = InlineKeyboardBuilder()

    buttons = [
        ("📦 Заказы", "acc:orders"),
        ("🤖 AI Консультант", "acc:ai"),
        ("🛒 Lolzteam", "acc:lolzteam"),
        ("📋 Лоты", "acc:lots"),
        ("💬 Сообщения", "acc:messages"),
        ("📊 Статистика", "acc:stats"),
        ("💰 Баланс", "acc:balance"),
        ("📜 Логи", "acc:logs"),
        ("⚙️ Настройки", "acc:settings"),
        ("🛠 Диагностика", "acc:diagnostics"),
        ("💾 Резервные копии", "acc:backups"),
        ("📤 Экспорт настроек", "acc:export"),
        ("📥 Импорт настроек", "acc:import"),
        ("⏸ Экстренная пауза", "acc:pause"),
        ("🔄 Перезапустить", "acc:restart"),
        ("❓ Помощь", "acc:help"),
    ]

    for text, callback in buttons:
        builder.row(InlineKeyboardButton(text=text, callback_data=callback))

    return builder.as_markup()


def get_back_to_main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="acc:menu"))
    return builder.as_markup()