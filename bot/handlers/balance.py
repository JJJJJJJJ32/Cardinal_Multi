from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

router = Router(name="balance")


async def fetch_balance(account_id: int) -> dict:
    """
    Заглушка.
    В реальности: FunPayAPI.get_balance() и Lolzteam API.
    """
    return {"funpay": 0.0, "lolzteam": 0.0, "threshold": None}


def build_balance_keyboard(threshold: float | None) -> object:
    builder = InlineKeyboardBuilder()
    notif_text = (
        f"🔔 Уведомлять ниже {threshold} руб" if threshold
        else "🔔 Уведомлять если ниже X руб"
    )
    builder.row(InlineKeyboardButton(text=notif_text, callback_data="balance:toggle_notif"))
    builder.row(
        InlineKeyboardButton(text="⚙️ Установить порог", callback_data="balance:set_threshold")
    )
    builder.row(InlineKeyboardButton(text="🔙 Меню", callback_data="acc:menu"))
    return builder.as_markup()


@router.callback_query(F.data == "acc:balance")
async def callback_balance(call: CallbackQuery) -> None:
    data = await fetch_balance(call.from_user.id)
    text = (
        f"💰 <b>Баланс</b>\n\n"
        f"FunPay: <b>{data['funpay']} руб</b>\n"
        f"Lolzteam: <b>{data['lolzteam']} руб</b>\n"
    )
    if data.get("threshold"):
        text += f"\n🔔 Порог уведомления: {data['threshold']} руб"

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=build_balance_keyboard(data.get("threshold")),
    )
    await call.answer()


@router.callback_query(F.data == "balance:set_threshold")
async def callback_set_threshold(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state("balance_threshold")
    await call.message.answer(
        "💰 Введите порог баланса в рублях (число):\n\nПри падении ниже этого значения придёт уведомление."
    )
    await call.answer()


@router.message(F.state == "balance_threshold")
async def handle_threshold(message: Message, state: FSMContext) -> None:
    try:
        threshold = float(message.text.strip())
        await state.clear()
        # TODO: сохранить порог в БД accounts.settings
        await message.answer(
            f"✅ Порог установлен: <b>{threshold} руб</b>",
            parse_mode="HTML",
        )
    except ValueError:
        await message.answer("⚠️ Введите корректное число:")