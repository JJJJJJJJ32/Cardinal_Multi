from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger

from bot.keyboards.lots import (
    get_lots_menu_keyboard,
    get_lots_keyboard,
    get_lot_actions_keyboard,
)

router = Router(name="lots")


async def search_lots(account_id: int, query: str = "") -> list[dict]:
    """Заглушка поиска лотов из БД account_lots."""
    return []


@router.callback_query(F.data == "acc:lots")
async def callback_lots_menu(call: CallbackQuery) -> None:
    await call.message.edit_text(
        "📋 <b>Лоты</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=get_lots_menu_keyboard(),
    )
    await call.answer()


@router.callback_query(F.data == "lots:search")
async def callback_lots_search_prompt(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state("lots_search")
    await call.message.answer(
        "🔍 Введите название лота для поиска (или /cancel):"
    )
    await call.answer()


@router.message(F.state == "lots_search")
async def handle_lots_search(message: Message, state: FSMContext) -> None:
    query = message.text.strip()
    await state.clear()

    # TODO: реальный поиск через БД
    lots = await search_lots(account_id=0, query=query)

    if not lots:
        await message.answer(f"🔍 По запросу «{query}» ничего не найдено.")
        return

    await message.answer(
        f"📋 Результаты поиска «{query}» ({len(lots)} лотов):",
        reply_markup=get_lots_keyboard(lots, page=0),
    )


@router.callback_query(F.data.startswith("lots:page:"))
async def callback_lots_page(call: CallbackQuery) -> None:
    page = int(call.data.split(":")[-1])
    lots = await search_lots(account_id=0, query="")
    await call.message.edit_reply_markup(
        reply_markup=get_lots_keyboard(lots, page=page)
    )
    await call.answer()


@router.callback_query(F.data.startswith("lot:detail:"))
async def callback_lot_detail(call: CallbackQuery) -> None:
    lot_id = call.data.split(":")[-1]
    # TODO: загрузить данные лота из БД
    await call.message.edit_text(
        f"📦 <b>Лот #{lot_id}</b>\n\nЦена: —\nСтатус: —",
        parse_mode="HTML",
        reply_markup=get_lot_actions_keyboard(lot_id),
    )
    await call.answer()


@router.callback_query(F.data == "lots:sync")
async def callback_lots_sync(call: CallbackQuery) -> None:
    # TODO: синхронизация лотов через FunPayAPI
    await call.answer("🔄 Синхронизация запущена (заглушка)", show_alert=True)


@router.callback_query(F.data == "lots:favorites")
async def callback_lots_favorites(call: CallbackQuery) -> None:
    # TODO: фильтр избранных из account_lots
    await call.message.edit_text(
        "⭐ <b>Избранные лоты</b>\n\n_Список пуст._",
        parse_mode="HTML",
        reply_markup=None,
    )
    await call.answer()