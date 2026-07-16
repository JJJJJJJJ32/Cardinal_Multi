from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger

from bot.keyboards.ai_consultant import (
    get_ai_menu,
    get_ai_mode_keyboard,
    get_templates_keyboard,
    get_template_actions_keyboard,
    get_forbidden_topics_keyboard,
)
from bot.states.template_setup import TemplateSetupStates

router = Router(name="ai_consultant")

# ─── Состояния в памяти (в продакшне — БД) ───────────────────────────────────
_ai_state: dict[int, dict] = {}

def get_ai_state(uid: int) -> dict:
    return _ai_state.setdefault(uid, {"enabled": False, "mode": "standard"})


@router.callback_query(F.data == "acc:ai")
async def callback_ai_menu(call: CallbackQuery) -> None:
    s = get_ai_state(call.from_user.id)
    await call.message.edit_text(
        "🤖 <b>AI Консультант</b>",
        parse_mode="HTML",
        reply_markup=get_ai_menu(s["enabled"], s["mode"]),
    )
    await call.answer()


@router.callback_query(F.data == "ai:toggle")
async def callback_ai_toggle(call: CallbackQuery) -> None:
    s = get_ai_state(call.from_user.id)
    s["enabled"] = not s["enabled"]
    status = "включён 🟢" if s["enabled"] else "выключен 🔴"
    await call.message.edit_text(
        f"🤖 <b>AI Консультант</b>",
        parse_mode="HTML",
        reply_markup=get_ai_menu(s["enabled"], s["mode"]),
    )
    await call.answer(f"AI {status}")


@router.callback_query(F.data == "ai:toggle_mode")
async def callback_ai_toggle_mode(call: CallbackQuery) -> None:
    await call.message.edit_text(
        "🔵 <b>Выберите режим AI:</b>",
        parse_mode="HTML",
        reply_markup=get_ai_mode_keyboard(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("ai:set_mode:"))
async def callback_ai_set_mode(call: CallbackQuery) -> None:
    mode = call.data.split(":")[-1]
    s = get_ai_state(call.from_user.id)
    s["mode"] = mode
    await call.message.edit_text(
        "🤖 <b>AI Консультант</b>",
        parse_mode="HTML",
        reply_markup=get_ai_menu(s["enabled"], s["mode"]),
    )
    await call.answer(f"Режим: {'Осторожный' if mode == 'careful' else 'Стандартный'}")


# ─── Шаблоны ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "ai:templates")
async def callback_ai_templates(call: CallbackQuery) -> None:
    # TODO: загрузить шаблоны из БД
    templates: list[dict] = []
    await call.message.edit_text(
        "📄 <b>Шаблоны AI</b>",
        parse_mode="HTML",
        reply_markup=get_templates_keyboard(templates),
    )
    await call.answer()


@router.callback_query(F.data == "ai:template:create")
async def callback_ai_template_create(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TemplateSetupStates.waiting_for_template_name)
    await call.message.answer(
        "📝 <b>Создание шаблона</b>\n\nВведите название шаблона:",
        parse_mode="HTML",
    )
    await call.answer()


@router.message(TemplateSetupStates.waiting_for_template_name)
async def handle_template_name(message: Message, state: FSMContext) -> None:
    await state.update_data(template_name=message.text.strip())
    await state.set_state(TemplateSetupStates.waiting_for_template_text)
    await message.answer("✍️ Теперь введите текст шаблона:")


@router.message(TemplateSetupStates.waiting_for_template_text)
async def handle_template_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    name = data.get("template_name")
    text = message.text.strip()

    await state.update_data(template_text=text)
    await state.set_state(TemplateSetupStates.waiting_for_template_confirm)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Сохранить", callback_data="ai:template:save"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="ai:templates"),
    )

    await message.answer(
        f"📝 <b>Шаблон готов:</b>\n\n"
        f"<b>Название:</b> {name}\n"
        f"<b>Текст:</b> {text}",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(
    TemplateSetupStates.waiting_for_template_confirm, F.data == "ai:template:save"
)
async def callback_template_save(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    name = data.get("template_name")
    text = data.get("template_text")
    await state.clear()

    # TODO: сохранить в БД
    logger.info(f"Сохранён шаблон AI: {name}")

    await call.message.edit_text(
        f"✅ Шаблон <b>{name}</b> сохранён!",
        parse_mode="HTML",
    )
    await call.answer()


# ─── Запрещённые темы ────────────────────────────────────────────────────────

@router.callback_query(F.data == "ai:forbidden_topics")
async def callback_forbidden_topics(call: CallbackQuery) -> None:
    # TODO: загрузить из БД
    topics: list[dict] = []
    await call.message.edit_text(
        "🚫 <b>Запрещённые темы</b>",
        parse_mode="HTML",
        reply_markup=get_forbidden_topics_keyboard(topics),
    )
    await call.answer()


@router.callback_query(F.data == "ai:topic:add")
async def callback_topic_add(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state("ai_add_topic")
    await call.message.answer("➕ Введите запрещённую тему:")
    await call.answer()


@router.message(F.state == "ai_add_topic")
async def handle_topic_add(message: Message, state: FSMContext) -> None:
    topic = message.text.strip()
    await state.clear()
    # TODO: сохранить в БД
    logger.info(f"Добавлена запрещённая тема: {topic}")
    await message.answer(f"✅ Тема «{topic}» добавлена.")


# ─── История диалогов ────────────────────────────────────────────────────────

@router.callback_query(F.data == "ai:history")
async def callback_ai_history(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state("ai_history_search")
    await call.message.answer(
        "🔍 Введите имя покупателя для поиска истории:"
    )
    await call.answer()


@router.message(F.state == "ai_history_search")
async def handle_ai_history_search(message: Message, state: FSMContext) -> None:
    buyer = message.text.strip()
    await state.clear()
    # TODO: поиск в events_log по buyer
    await message.answer(
        f"📜 <b>История диалогов с {buyer}:</b>\n\n_Нет записей._",
        parse_mode="HTML",
    )