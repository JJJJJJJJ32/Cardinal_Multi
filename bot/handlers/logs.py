from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

router = Router(name="logs")


def build_logs_menu() -> object:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👤 Поиск по клиенту", callback_data="logs:by_client")
    )
    builder.row(
        InlineKeyboardButton(text="📦 Поиск по заказу", callback_data="logs:by_order")
    )
    builder.row(
        InlineKeyboardButton(text="🤖 Ответы AI", callback_data="logs:ai_replies")
    )
    builder.row(InlineKeyboardButton(text="🔙 Меню", callback_data="acc:menu"))
    return builder.as_markup()


@router.callback_query(F.data == "acc:logs")
async def callback_logs_menu(call: CallbackQuery) -> None:
    await call.message.edit_text(
        "📜 <b>Логи</b>\n\nВыберите тип поиска:",
        parse_mode="HTML",
        reply_markup=build_logs_menu(),
    )
    await call.answer()


@router.callback_query(F.data == "logs:by_client")
async def callback_logs_by_client(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state("logs_client_search")
    await call.message.answer("👤 Введите имя клиента:")
    await call.answer()


@router.message(F.state == "logs_client_search")
async def handle_logs_client(message: Message, state: FSMContext) -> None:
    client = message.text.strip()
    await state.clear()
    # TODO: поиск в events_log по account_id + data.buyer = client
    await message.answer(
        f"📜 <b>Логи по клиенту {client}:</b>\n\n_Нет записей._",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "logs:by_order")
async def callback_logs_by_order(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state("logs_order_search")
    await call.message.answer("📦 Введите номер заказа:")
    await call.answer()


@router.message(F.state == "logs_order_search")
async def handle_logs_order(message: Message, state: FSMContext) -> None:
    order_id = message.text.strip()
    await state.clear()
    # TODO: поиск в events_log по data.order_id
    await message.answer(
        f"📜 <b>Логи по заказу #{order_id}:</b>\n\n_Нет записей._",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "logs:ai_replies")
async def callback_logs_ai_replies(call: CallbackQuery) -> None:
    # TODO: фильтр events_log по event_type содержащему AI
    await call.message.edit_text(
        "🤖 <b>Ответы AI</b>\n\n_Нет записей._",
        parse_mode="HTML",
        reply_markup=InlineKeyboardBuilder().row(
            InlineKeyboardButton(text="🔙 Назад", callback_data="acc:logs")
        ).as_markup(),
    )
    await call.answer()