from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_ai_menu(is_enabled: bool, mode: str = "standard") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    toggle_text = "🔴 Выключить AI" if is_enabled else "🟢 Включить AI"
    builder.row(InlineKeyboardButton(text=toggle_text, callback_data="ai:toggle"))

    mode_text = "⚠️ Осторожный" if mode == "careful" else "🔵 Стандартный"
    builder.row(
        InlineKeyboardButton(
            text=f"Режим: {mode_text}", callback_data="ai:toggle_mode"
        )
    )
    builder.row(InlineKeyboardButton(text="📄 Шаблоны", callback_data="ai:templates"))
    builder.row(
        InlineKeyboardButton(
            text="🚫 Запрещённые темы", callback_data="ai:forbidden_topics"
        )
    )
    builder.row(
        InlineKeyboardButton(text="📜 История диалогов", callback_data="ai:history")
    )
    builder.row(InlineKeyboardButton(text="🔙 Меню", callback_data="acc:menu"))
    return builder.as_markup()


def get_ai_mode_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="⚠️ Осторожный", callback_data="ai:set_mode:careful"
        ),
        InlineKeyboardButton(
            text="🔵 Стандартный", callback_data="ai:set_mode:standard"
        ),
    )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="acc:ai"))
    return builder.as_markup()


def get_templates_keyboard(templates: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for tpl in templates:
        builder.row(
            InlineKeyboardButton(
                text=f"📝 {tpl['name']}",
                callback_data=f"ai:template:view:{tpl['id']}",
            )
        )
    builder.row(
        InlineKeyboardButton(text="➕ Создать шаблон", callback_data="ai:template:create")
    )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="acc:ai"))
    return builder.as_markup()


def get_template_actions_keyboard(template_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✏️ Изменить", callback_data=f"ai:template:edit:{template_id}"
        ),
        InlineKeyboardButton(
            text="🗑 Удалить", callback_data=f"ai:template:delete:{template_id}"
        ),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 К шаблонам", callback_data="ai:templates")
    )
    return builder.as_markup()


def get_forbidden_topics_keyboard(topics: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for topic in topics:
        builder.row(
            InlineKeyboardButton(
                text=f"🚫 {topic['name']}",
                callback_data=f"ai:topic:delete:{topic['id']}",
            )
        )
    builder.row(
        InlineKeyboardButton(
            text="➕ Добавить тему", callback_data="ai:topic:add"
        )
    )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="acc:ai"))
    return builder.as_markup()