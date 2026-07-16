from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from loguru import logger

from bot.states.manual_reply import ManualReplyStates

router = Router(name="messages")


async def fetch_dialogs(account_id: int) -> list[dict]:
    """
    Заглушка получения диалогов.
    В реальности: FunPayAPI.get_chats() через AccountWrapper.
    """
    return []


async def fetch_dialog_history(account_id: int, buyer_username: str) -> list[dict]:
    """Заглушка: последние 10 сообщений диалога."""
    return []


@router.callback_query(F.data == "acc:messages")
async def callback_messages(call: CallbackQuery) -> None:
    """Список диалогов с покупателями."""
    account_id = call.from_user.id
    dialogs = await fetch_dialogs(account_id)

    if not dialogs:
        await call.message.edit_text(
            "💬 Нет активных диалогов.",
        )
        await call.answer()
        return

    builder = InlineKeyboardBuilder()
    for dialog in dialogs[:10]:
        builder.row(
            InlineKeyboardButton(
                text=f"💬 {dialog['buyer']} — {dialog['last_message'][:30]}",
                callback_data=f"msg:dialog:{dialog['buyer']}",
            )
        )
    builder.row(InlineKeyboardButton(text="🔙 Меню", callback_data="acc:menu"))

    await call.message.edit_text(
        "💬 <b>Диалоги с покупателями:</b>",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("msg:dialog:"))
async def callback_dialog(call: CallbackQuery) -> None:
    """История диалога с покупателем."""
    buyer = call.data.split(":")[-1]
    account_id = call.from_user.id
    messages = await fetch_dialog_history(account_id, buyer)

    history_text = f"💬 <b>Диалог с {buyer}</b>\n\n"
    if messages:
        for msg in messages[-10:]:
            sender = "Вы" if msg.get("is_mine") else buyer
            history_text += f"<b>{sender}:</b> {msg['text']}\n"
    else:
        history_text += "_Нет сообщений._"

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✏️ Ответить", callback_data=f"msg:reply:{buyer}"
        )
    )
    builder.row(InlineKeyboardButton(text="🔙 К диалогам", callback_data="acc:messages"))

    await call.message.edit_text(
        text=history_text,
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("msg:reply:"))
async def callback_reply_start(call: CallbackQuery, state: FSMContext) -> None:
    """Начало FSM ручного ответа."""
    buyer = call.data.split(":")[-1]
    await state.update_data(reply_to=buyer)
    await state.set_state(ManualReplyStates.waiting_for_reply_text)

    await call.message.answer(
        f"✏️ Введите ответ покупателю <b>{buyer}</b>:\n\n"
        f"(или /cancel для отмены)",
        parse_mode="HTML",
    )
    await call.answer()


@router.message(ManualReplyStates.waiting_for_reply_text)
async def handle_reply_text(message: Message, state: FSMContext) -> None:
    """Получен текст ответа — просим подтверждение."""
    text = message.text.strip()
    if not text:
        await message.answer("⚠️ Сообщение не может быть пустым. Введите текст:")
        return

    await state.update_data(reply_text=text)
    await state.set_state(ManualReplyStates.waiting_for_reply_confirm)

    data = await state.get_data()
    buyer = data.get("reply_to", "—")

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Отправить", callback_data="msg:send_confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="msg:send_cancel"),
    )

    await message.answer(
        f"📤 Отправить покупателю <b>{buyer}</b>:\n\n"
        f"<i>{text}</i>",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(
    ManualReplyStates.waiting_for_reply_confirm, F.data == "msg:send_confirm"
)
async def callback_send_confirm(call: CallbackQuery, state: FSMContext) -> None:
    """Подтверждение и отправка."""
    data = await state.get_data()
    buyer = data.get("reply_to")
    text = data.get("reply_text")
    await state.clear()

    # TODO: вызов modules.ai.send_manual_reply(buyer, text)
    logger.info(f"Ручной ответ покупателю {buyer}: {text}")

    await call.message.edit_text(
        f"✅ Сообщение отправлено покупателю <b>{buyer}</b>.",
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(
    ManualReplyStates.waiting_for_reply_confirm, F.data == "msg:send_cancel"
)
async def callback_send_cancel(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text("❌ Отправка отменена.")
    await call.answer()