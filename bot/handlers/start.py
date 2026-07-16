from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from loguru import logger

from bot.keyboards.main_menu import get_account_bot_menu, get_back_to_main_keyboard

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    logger.info(f"Пользователь {message.from_user.id} запустил бота аккаунта.")
    await message.answer(
        text=(
            "👋 Добро пожаловать в панель управления аккаунтом!\n\n"
            "Выберите раздел:"
        ),
        reply_markup=get_account_bot_menu(),
    )


@router.callback_query(F.data == "acc:menu")
async def callback_main_menu(call: CallbackQuery) -> None:
    await call.message.edit_text(
        text="🏠 Главное меню. Выберите раздел:",
        reply_markup=get_account_bot_menu(),
    )
    await call.answer()


@router.callback_query(F.data == "noop")
async def callback_noop(call: CallbackQuery) -> None:
    """Заглушка для кнопок-индикаторов (страница пагинации и т.п.)"""
    await call.answer()


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    help_text = (
        "❓ <b>Помощь по боту Cardinal_Multi</b>\n\n"
        "📦 <b>Заказы</b> — список активных заказов FunPay\n"
        "🤖 <b>AI Консультант</b> — настройка AI-ответов\n"
        "🛒 <b>Lolzteam</b> — автоматическая закупка аккаунтов\n"
        "📋 <b>Лоты</b> — управление лотами FunPay\n"
        "💬 <b>Сообщения</b> — диалоги с покупателями\n"
        "📊 <b>Статистика</b> — сводка продаж\n"
        "💰 <b>Баланс</b> — текущий баланс + пороги\n"
        "📜 <b>Логи</b> — журнал событий\n"
        "⚙️ <b>Настройки</b> — конфигурация аккаунта\n"
        "🛠 <b>Диагностика</b> — состояние сервисов\n"
        "💾 <b>Резервные копии</b> — backup и restore\n\n"
        "По вопросам: /start"
    )
    await message.answer(help_text, parse_mode="HTML")