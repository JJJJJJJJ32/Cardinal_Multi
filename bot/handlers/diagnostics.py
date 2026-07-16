from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

router = Router(name="diagnostics")


async def fetch_diagnostics(account_id: int) -> dict:
    """
    Заглушка. В реальности:
    - данные от modules/diagnostics (когда будет готов)
    - или проверки состояния AccountWrapper (процесс жив?), доступности БД и т.д.
    """
    return {
        "FunPay API": True,
        "Lolzteam API": None,   # None = неизвестно
        "AI сервис": None,
        "База данных": True,
        "Cardinal процесс": None,
    }


@router.callback_query(F.data == "acc:diagnostics")
async def callback_diagnostics(call: CallbackQuery) -> None:
    data = await fetch_diagnostics(call.from_user.id)

    def icon(val) -> str:
        if val is True:
            return "✅"
        if val is False:
            return "❌"
        return "⚠️"  # None = неизвестно

    lines = "\n".join(
        f"{icon(v)} {service}" for service, v in data.items()
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Обновить", callback_data="acc:diagnostics")
    )
    builder.row(InlineKeyboardButton(text="🔙 Меню", callback_data="acc:menu"))

    await call.message.edit_text(
        f"🛠 <b>Диагностика сервисов</b>\n\n{lines}",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await call.answer()