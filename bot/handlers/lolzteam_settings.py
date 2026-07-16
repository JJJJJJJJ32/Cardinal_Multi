from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger

from bot.keyboards.lolzteam import (
    get_lolzteam_menu,
    get_lolzteam_lot_card_keyboard,
    get_delivery_mode_keyboard,
    get_bool_filter_keyboard,
    get_general_filters_keyboard,
)
from bot.states.lot_setup import LotSetupStates

router = Router(name="lolzteam")


# ─── Состояние (флаги) — в продакшне хранятся в БД ──────────────────────────
_lolz_enabled: dict[int, bool] = {}   # account_id → bool


def get_lolz_enabled(account_id: int) -> bool:
    return _lolz_enabled.get(account_id, False)


def toggle_lolz(account_id: int) -> bool:
    _lolz_enabled[account_id] = not get_lolz_enabled(account_id)
    return _lolz_enabled[account_id]


# ─── Главное меню Lolzteam ───────────────────────────────────────────────────

@router.callback_query(F.data == "acc:lolzteam")
async def callback_lolzteam_menu(call: CallbackQuery) -> None:
    enabled = get_lolz_enabled(call.from_user.id)
    status = "🟢 Включена" if enabled else "🔴 Выключена"
    await call.message.edit_text(
        f"🛒 <b>Lolzteam</b>\n\nАвтозакупка: {status}",
        parse_mode="HTML",
        reply_markup=get_lolzteam_menu(enabled),
    )
    await call.answer()


@router.callback_query(F.data == "lolz:toggle")
async def callback_lolz_toggle(call: CallbackQuery) -> None:
    enabled = toggle_lolz(call.from_user.id)
    status = "включена 🟢" if enabled else "выключена 🔴"
    # TODO: реальный toggle через модуль Lolzteam (когда будет готов)
    await call.message.edit_text(
        f"🛒 <b>Lolzteam</b>\n\nАвтозакупка: {'🟢 Включена' if enabled else '🔴 Выключена'}",
        parse_mode="HTML",
        reply_markup=get_lolzteam_menu(enabled),
    )
    await call.answer(f"Автозакупка {status}")


# ─── Настройки лотов: поиск ──────────────────────────────────────────────────

@router.callback_query(F.data == "lolz:lot_settings")
async def callback_lolz_lot_settings(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(LotSetupStates.waiting_for_lot_search)
    await call.message.answer(
        "🔍 Шаг 1/7 — <b>Поиск лота</b>\n\n"
        "Введите название лота для поиска:",
        parse_mode="HTML",
    )
    await call.answer()


@router.message(LotSetupStates.waiting_for_lot_search)
async def handle_lot_search(message: Message, state: FSMContext) -> None:
    query = message.text.strip()
    await state.update_data(lot_search_query=query)

    # TODO: реальный поиск лотов из account_lots
    found_lots: list[dict] = []  # заглушка

    if not found_lots:
        await message.answer(
            f"🔍 По запросу «{query}» лоты не найдены.\n"
            "Попробуйте другое название или /cancel."
        )
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    for lot in found_lots[:10]:
        builder.row(
            InlineKeyboardButton(
                text=f"📦 {lot['title'][:40]}",
                callback_data=f"lolz:lot_card:{lot['id']}",
            )
        )
    await message.answer(
        f"📋 Найдено лотов: {len(found_lots)}. Выберите:",
        reply_markup=builder.as_markup(),
    )


# ─── Карточка лота (Шаг 2) ───────────────────────────────────────────────────

@router.callback_query(F.data.startswith("lolz:lot_card:"))
async def callback_lolz_lot_card(call: CallbackQuery, state: FSMContext) -> None:
    lot_id = call.data.split(":")[-1]
    await state.update_data(current_lot_id=lot_id)

    # TODO: загрузить данные лота из БД
    lot_title = f"Лот #{lot_id}"
    lot_price = "—"
    is_enabled = False

    await call.message.edit_text(
        f"📋 <b>Лот: {lot_title}</b>\n"
        f"Цена FunPay: {lot_price} руб\n"
        f"Автозакупка: {'✅ Включена' if is_enabled else '❌ Выключена'}",
        parse_mode="HTML",
        reply_markup=get_lolzteam_lot_card_keyboard(lot_id, is_enabled),
    )
    await call.answer()


# ─── Шаг 3 — Выбор категории ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("lolz:lot_configure:"))
async def callback_lolz_configure(call: CallbackQuery, state: FSMContext) -> None:
    lot_id = call.data.split(":")[-1]
    await state.update_data(current_lot_id=lot_id)
    await state.set_state(LotSetupStates.waiting_for_category)

    # TODO: загрузить категории из CategoryRegistry модуля Lolzteam
    categories = [
        {"id": "steam", "name": "🎮 Steam"},
        {"id": "vk", "name": "📘 VKontakte"},
        {"id": "instagram", "name": "📸 Instagram"},
    ]

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    for cat in categories:
        builder.row(
            InlineKeyboardButton(
                text=cat["name"],
                callback_data=f"lolz:set_category:{lot_id}:{cat['id']}",
            )
        )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=f"lolz:lot_card:{lot_id}"))

    await call.message.edit_text(
        "📂 <b>Шаг 3/7 — Выберите категорию Lolzteam:</b>",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("lolz:set_category:"))
async def callback_lolz_set_category(call: CallbackQuery, state: FSMContext) -> None:
    parts = call.data.split(":")
    lot_id = parts[2]
    category = parts[3]
    await state.update_data(selected_category=category)
    await state.set_state(LotSetupStates.waiting_for_min_price)

    data = await state.get_data()
    current_filters = data.get("filters", {})

    await call.message.edit_text(
        f"⚙️ <b>Шаг 4/7 — Общие фильтры</b>\n\nКатегория: <b>{category}</b>\n\n"
        "Нажмите на параметр для изменения:",
        parse_mode="HTML",
        reply_markup=get_general_filters_keyboard(lot_id, current_filters),
    )
    await call.answer()


# ─── Шаг 4 — Общие фильтры (редактирование по одному) ───────────────────────

@router.callback_query(F.data.startswith("lolz:edit_filter:"))
async def callback_edit_filter(call: CallbackQuery, state: FSMContext) -> None:
    parts = call.data.split(":")
    lot_id = parts[2]
    filter_key = parts[3]

    FILTER_PROMPTS = {
        "min_price": "💰 Введите минимальную цену (число):",
        "max_price": "💰 Введите максимальную цену (число):",
        "min_rating": "⭐ Введите минимальный рейтинг продавца в % (0-100):",
        "min_reviews": "💬 Введите минимальное количество отзывов (число):",
        "required_words": "📝 Введите обязательные слова (через запятую):",
        "forbidden_words": "🚫 Введите запрещённые слова (через запятую):",
    }

    await state.update_data(editing_filter=filter_key, current_lot_id=lot_id)

    state_map = {
        "min_price": LotSetupStates.waiting_for_min_price,
        "max_price": LotSetupStates.waiting_for_max_price,
        "min_rating": LotSetupStates.waiting_for_min_rating,
        "min_reviews": LotSetupStates.waiting_for_min_reviews,
        "required_words": LotSetupStates.waiting_for_required_words,
        "forbidden_words": LotSetupStates.waiting_for_forbidden_words,
    }

    await state.set_state(state_map.get(filter_key))
    await call.message.answer(
        FILTER_PROMPTS.get(filter_key, "Введите значение:")
    )
    await call.answer()


async def _save_filter_and_show(message: Message, state: FSMContext, value) -> None:
    """Общая логика: сохранить значение фильтра и вернуть карточку фильтров."""
    data = await state.get_data()
    filter_key = data.get("editing_filter")
    lot_id = data.get("current_lot_id")
    filters = data.get("filters", {})
    filters[filter_key] = value
    await state.update_data(filters=filters)
    await state.set_state(LotSetupStates.waiting_for_min_price)  # возврат к фильтрам

    await message.answer(
        f"✅ Фильтр <b>{filter_key}</b> = <code>{value}</code> сохранён.\n\n"
        "Изменить другой или нажмите «Далее»:",
        parse_mode="HTML",
        reply_markup=get_general_filters_keyboard(lot_id, filters),
    )


@router.message(LotSetupStates.waiting_for_min_price)
async def handle_min_price(message: Message, state: FSMContext) -> None:
    try:
        value = float(message.text.strip())
        await _save_filter_and_show(message, state, value)
    except ValueError:
        await message.answer("⚠️ Введите число:")


@router.message(LotSetupStates.waiting_for_max_price)
async def handle_max_price(message: Message, state: FSMContext) -> None:
    try:
        value = float(message.text.strip())
        await _save_filter_and_show(message, state, value)
    except ValueError:
        await message.answer("⚠️ Введите число:")


@router.message(LotSetupStates.waiting_for_min_rating)
async def handle_min_rating(message: Message, state: FSMContext) -> None:
    try:
        value = float(message.text.strip())
        if not 0 <= value <= 100:
            raise ValueError
        await _save_filter_and_show(message, state, value)
    except ValueError:
        await message.answer("⚠️ Введите число от 0 до 100:")


@router.message(LotSetupStates.waiting_for_min_reviews)
async def handle_min_reviews(message: Message, state: FSMContext) -> None:
    try:
        value = int(message.text.strip())
        await _save_filter_and_show(message, state, value)
    except ValueError:
        await message.answer("⚠️ Введите целое число:")


@router.message(LotSetupStates.waiting_for_required_words)
async def handle_required_words(message: Message, state: FSMContext) -> None:
    words = [w.strip() for w in message.text.split(",") if w.strip()]
    await _save_filter_and_show(message, state, words)


@router.message(LotSetupStates.waiting_for_forbidden_words)
async def handle_forbidden_words(message: Message, state: FSMContext) -> None:
    words = [w.strip() for w in message.text.split(",") if w.strip()]
    await _save_filter_and_show(message, state, words)


# ─── Шаг 6 — Режим выдачи ────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("lolz:next_specific:"))
async def callback_lolz_next_specific(call: CallbackQuery, state: FSMContext) -> None:
    lot_id = call.data.split(":")[-1]
    await state.set_state(LotSetupStates.waiting_for_delivery_mode)

    await call.message.edit_text(
        "🚚 <b>Шаг 6/7 — Режим выдачи товара:</b>",
        parse_mode="HTML",
        reply_markup=get_delivery_mode_keyboard(lot_id),
    )
    await call.answer()


@router.callback_query(F.data.startswith("lolz:delivery_mode:"))
async def callback_delivery_mode(call: CallbackQuery, state: FSMContext) -> None:
    parts = call.data.split(":")
    lot_id = parts[2]
    mode = parts[3]
    await state.update_data(delivery_mode=mode)
    await state.set_state(LotSetupStates.waiting_for_confirm)

    # Шаг 7 — Тестовый поиск
    await call.message.edit_text(
        "🔍 <b>Шаг 7/7 — Тестовый поиск</b>\n\nИщу по заданным фильтрам...",
        parse_mode="HTML",
    )
    await call.answer()

    # TODO: реальный тестовый поиск через Lolzteam модуль
    top_results: list[dict] = []  # заглушка

    result_text = "🔍 <b>Результаты тестового поиска:</b>\n\n"
    if top_results:
        for i, item in enumerate(top_results[:3], 1):
            result_text += f"{i}. {item.get('title', '—')} — {item.get('price', '—')} руб\n"
    else:
        result_text += "_По заданным фильтрам ничего не найдено._"

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Сохранить настройки",
            callback_data=f"lolz:save_settings:{lot_id}",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="✏️ Изменить фильтры",
            callback_data=f"lolz:lot_configure:{lot_id}",
        )
    )

    await call.message.edit_text(
        result_text,
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data.startswith("lolz:save_settings:"))
async def callback_lolz_save(call: CallbackQuery, state: FSMContext) -> None:
    lot_id = call.data.split(":")[-1]
    data = await state.get_data()
    filters = data.get("filters", {})
    category = data.get("selected_category", "—")
    delivery_mode = data.get("delivery_mode", "auto")
    await state.clear()

    # TODO: сохранить в БД account_lots.settings
    logger.info(
        f"Сохранены настройки Lolzteam для лота {lot_id}: "
        f"category={category}, delivery={delivery_mode}, filters={filters}"
    )

    await call.message.edit_text(
        f"✅ Настройки лота #{lot_id} сохранены!\n\n"
        f"Категория: {category}\n"
        f"Режим выдачи: {'Авто 🚀' if delivery_mode == 'auto' else 'С подтверждением 👀'}",
        parse_mode="HTML",
    )
    await call.answer("✅ Сохранено!")