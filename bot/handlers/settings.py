from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.settings import get_settings_menu, get_notifications_keyboard

router = Router(name="settings")

# Состояния уведомлений (в продакшне — accounts.settings в БД)
_notif_states: dict[int, dict] = {}

def get_notif_states(uid: int) -> dict:
    return _notif_states.setdefault(uid, {
        "NEW_ORDER": True,
        "SEARCH_STARTED": True,
        "ITEM_PURCHASED": True,
        "ITEM_DELIVERED": True,
        "ACCOUNT_ERROR": True,
        "BALANCE_LOW": True,
        "NEW_MESSAGE": True,
    })


@router.callback_query(F.data == "acc:settings")
async def callback_settings(call: CallbackQuery) -> None:
    await call.message.edit_text(
        "⚙️ <b>Настройки аккаунта</b>",
        parse_mode="HTML",
        reply_markup=get_settings_menu(),
    )
    await call.answer()


@router.callback_query(F.data == "settings:notifications")
async def callback_notifications(call: CallbackQuery) -> None:
    states = get_notif_states(call.from_user.id)
    await call.message.edit_text(
        "🔔 <b>Уведомления</b>\n\nНажмите чтобы включить/выключить:",
        parse_mode="HTML",
        reply_markup=get_notifications_keyboard(states),
    )
    await call.answer()


@router.callback_query(F.data.startswith("notif:toggle:"))
async def callback_notif_toggle(call: CallbackQuery) -> None:
    event_type = call.data.split(":")[-1]
    states = get_notif_states(call.from_user.id)
    states[event_type] = not states.get(event_type, True)
    # TODO: сохранить в accounts.settings в БД

    await call.message.edit_reply_markup(
        reply_markup=get_notifications_keyboard(states)
    )
    status = "включены 🟢" if states[event_type] else "выключены 🔴"
    await call.answer(f"{event_type}: {status}")


@router.callback_query(F.data == "settings:funpay")
async def callback_settings_funpay(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state("change_golden_key")
    await call.message.answer(
        "🔑 Введите новый <b>golden_key</b> FunPay:\n\n"
        "⚠️ Будьте осторожны! Ключ будет перезаписан.",
        parse_mode="HTML",
    )
    await call.answer()


@router.message(F.state == "change_golden_key")
async def handle_change_golden_key(message: Message, state: FSMContext) -> None:
    new_key = message.text.strip()
    await state.clear()
    # TODO: обновить Account.set_golden_key(new_key) в БД + перезапуск Cardinal
    await message.answer(
        "✅ Golden key обновлён. Требуется перезапуск аккаунта.\n\n"
        "Выполните: /restart или ⚙️ → 🔄 Перезапустить"
    )