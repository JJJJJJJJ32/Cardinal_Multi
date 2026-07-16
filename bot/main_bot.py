"""
Точка запуска главного бота.
Управляет всей установкой Cardinal_Multi.
"""

import asyncio
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from loguru import logger

from modules.core.config import get_settings
from modules.core.database import get_session
from modules.multi.models.account import Account
from modules.multi.account_manager import AccountManager

from bot.middlewares.auth import AuthMiddleware
from bot.middlewares.throttling import ThrottlingMiddleware
from bot.keyboards.main_menu import get_main_bot_menu, get_accounts_menu
from bot.states.account_setup import AccountSetupStates

router = Router(name="main_bot")


# ─── Старт ────────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "🏠 <b>Cardinal_Multi — Главный бот</b>\n\n"
        "Управление всей установкой:",
        parse_mode="HTML",
        reply_markup=get_main_bot_menu(),
    )


@router.callback_query(F.data == "main:menu")
async def callback_main_menu(call: CallbackQuery) -> None:
    await call.message.edit_text(
        "🏠 <b>Главное меню</b>",
        parse_mode="HTML",
        reply_markup=get_main_bot_menu(),
    )
    await call.answer()


# ─── Аккаунты ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "main:accounts")
async def callback_accounts(call: CallbackQuery) -> None:
    await call.message.edit_text(
        "📱 <b>Аккаунты</b>",
        parse_mode="HTML",
        reply_markup=get_accounts_menu(),
    )
    await call.answer()


@router.callback_query(F.data == "accounts:list")
async def callback_accounts_list(
    call: CallbackQuery, account_manager: AccountManager
) -> None:
    status = account_manager.status()
    accounts = status.get("accounts", [])

    if not accounts:
        await call.message.edit_text(
            "📱 Аккаунтов нет.\n\nДобавьте первый аккаунт:",
            reply_markup=get_accounts_menu(),
        )
        await call.answer()
        return

    text = "📱 <b>Список аккаунтов:</b>\n\n"
    for acc in accounts:
        role = "⭐ Основной" if acc.get("is_primary") else "👤"
        state = "🟢" if acc.get("running") else "🔴"
        text += (
            f"{state} {role} <b>{acc['name']}</b>\n"
            f"   ID: {acc['id']} | PID: {acc.get('pid', '—')}\n\n"
        )

    builder = InlineKeyboardBuilder()
    for acc in accounts:
        builder.row(
            InlineKeyboardButton(
                text=f"⚙️ {acc['name']}",
                callback_data=f"account:manage:{acc['id']}",
            )
        )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="main:accounts"))

    await call.message.edit_text(
        text, parse_mode="HTML", reply_markup=builder.as_markup()
    )
    await call.answer()


@router.callback_query(F.data.startswith("account:manage:"))
async def callback_account_manage(
    call: CallbackQuery, account_manager: AccountManager
) -> None:
    account_id = int(call.data.split(":")[-1])

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🔄 Перезапустить",
            callback_data=f"account:restart:{account_id}",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="⭐ Сделать основным",
            callback_data=f"account:set_primary:{account_id}",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📄 Клонировать настройки из него",
            callback_data=f"account:clone_from:{account_id}",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🗑 Удалить",
            callback_data=f"account:delete:{account_id}",
        )
    )
    builder.row(InlineKeyboardButton(text="🔙 К списку", callback_data="accounts:list"))

    await call.message.edit_text(
        f"⚙️ <b>Управление аккаунтом #{account_id}</b>",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("account:restart:"))
async def callback_account_restart(
    call: CallbackQuery, account_manager: AccountManager
) -> None:
    account_id = int(call.data.split(":")[-1])
    success = await account_manager.restart_account(account_id)
    status = "✅ перезапущен" if success else "❌ ошибка перезапуска"
    await call.answer(f"Аккаунт #{account_id}: {status}", show_alert=True)


@router.callback_query(F.data.startswith("account:set_primary:"))
async def callback_set_primary(
    call: CallbackQuery, account_manager: AccountManager
) -> None:
    account_id = int(call.data.split(":")[-1])
    await account_manager.set_primary(account_id)
    await call.answer(f"⭐ Аккаунт #{account_id} стал основным", show_alert=True)


@router.callback_query(F.data.startswith("account:delete:"))
async def callback_account_delete(
    call: CallbackQuery, account_manager: AccountManager
) -> None:
    account_id = int(call.data.split(":")[-1])
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Да, удалить",
            callback_data=f"account:delete_confirm:{account_id}",
        ),
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=f"account:manage:{account_id}",
        ),
    )
    await call.message.edit_text(
        f"⚠️ Удалить аккаунт #{account_id}?\n\nЭто действие необратимо!",
        reply_markup=builder.as_markup(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("account:delete_confirm:"))
async def callback_account_delete_confirm(
    call: CallbackQuery, account_manager: AccountManager
) -> None:
    account_id = int(call.data.split(":")[-1])
    try:
        await account_manager.remove_account(account_id)
        await call.message.edit_text(
            f"✅ Аккаунт #{account_id} удалён.",
            reply_markup=get_accounts_menu(),
        )
    except Exception as e:
        await call.answer(f"❌ Ошибка: {e}", show_alert=True)


# ─── Мастер добавления аккаунта (FSM) ────────────────────────────────────────

@router.callback_query(F.data == "accounts:add")
async def callback_add_account(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AccountSetupStates.waiting_for_token)
    await call.message.answer(
        "🔧 <b>Мастер добавления аккаунта — Шаг 1/5</b>\n\n"
        "1️⃣ Откройте @BotFather в Telegram\n"
        "2️⃣ Создайте нового бота командой /newbot\n"
        "3️⃣ Скопируйте токен бота\n\n"
        "Введите токен бота для нового аккаунта:",
        parse_mode="HTML",
    )
    await call.answer()


@router.message(AccountSetupStates.waiting_for_token)
async def handle_account_token(message: Message, state: FSMContext) -> None:
    token = message.text.strip()
    # Базовая валидация формата токена
    if ":" not in token or len(token) < 30:
        await message.answer("⚠️ Неверный формат токена. Попробуйте ещё раз:")
        return
    await state.update_data(new_bot_token=token)
    await state.set_state(AccountSetupStates.waiting_for_golden_key)
    await message.answer(
        "✅ Токен принят!\n\n"
        "🔧 <b>Шаг 2/5 — Golden Key</b>\n\n"
        "Введите golden_key FunPay аккаунта\n"
        "(можно найти в cookie браузера, значение ключа 'golden_key'):",
        parse_mode="HTML",
    )


@router.message(AccountSetupStates.waiting_for_golden_key)
async def handle_account_golden_key(message: Message, state: FSMContext) -> None:
    golden_key = message.text.strip()
    if len(golden_key) < 10:
        await message.answer("⚠️ Слишком короткий golden_key. Попробуйте ещё раз:")
        return
    await state.update_data(golden_key=golden_key)
    await state.set_state(AccountSetupStates.waiting_for_pin)
    await message.answer(
        "✅ Golden key принят!\n\n"
        "🔧 <b>Шаг 3/5 — PIN код</b>\n\n"
        "Введите PIN код для защиты аккаунта (4-8 цифр):",
        parse_mode="HTML",
    )


@router.message(AccountSetupStates.waiting_for_pin)
async def handle_account_pin(message: Message, state: FSMContext) -> None:
    pin = message.text.strip()
    if not pin.isdigit() or not (4 <= len(pin) <= 8):
        await message.answer("⚠️ PIN должен быть числом от 4 до 8 цифр:")
        return
    await state.update_data(pin=pin)
    await state.set_state(AccountSetupStates.waiting_for_lolzteam)
    await message.answer(
        "✅ PIN сохранён!\n\n"
        "🔧 <b>Шаг 4/5 — Lolzteam</b>\n\n"
        "Введите токен Lolzteam аккаунта\n"
        "(или напишите /skip для пропуска):",
        parse_mode="HTML",
    )


@router.message(AccountSetupStates.waiting_for_lolzteam)
async def handle_account_lolzteam(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    lolzteam_token = None if text.lower() == "/skip" else text
    await state.update_data(lolzteam_token=lolzteam_token)
    await state.set_state(AccountSetupStates.waiting_for_confirm)

    data = await state.get_data()

    confirm_text = (
        "🔧 <b>Шаг 5/5 — Подтверждение</b>\n\n"
        f"✅ Токен бота: <code>{data['new_bot_token'][:20]}...</code>\n"
        f"✅ Golden Key: <code>{data['golden_key'][:10]}...</code>\n"
        f"✅ PIN: {'*' * len(data['pin'])}\n"
        f"✅ Lolzteam: {'Настроен' if lolzteam_token else 'Пропущен'}\n\n"
        "Всё верно? Запустить аккаунт?"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🚀 Запустить", callback_data="account:setup_confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="account:setup_cancel"),
    )

    await message.answer(
        confirm_text, parse_mode="HTML", reply_markup=builder.as_markup()
    )


@router.callback_query(
    AccountSetupStates.waiting_for_confirm, F.data == "account:setup_confirm"
)
async def callback_account_setup_confirm(
    call: CallbackQuery, state: FSMContext, account_manager: AccountManager
) -> None:
    data = await state.get_data()
    await state.clear()

    try:
        account = await account_manager.add_account(
            golden_key=data["golden_key"],
            name=f"Аккаунт {data['golden_key'][:5]}…",
            telegram_token=data.get("new_bot_token"),
            owner_chat_id=str(call.from_user.id),
        )
        await call.message.edit_text(
            f"✅ <b>Аккаунт добавлен!</b>\n\n"
            f"ID: {account.id}\n"
            f"Запуск Cardinal...",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Ошибка добавления аккаунта: {e}")
        await call.message.edit_text(f"❌ Ошибка: {e}")

    await call.answer()


@router.callback_query(
    AccountSetupStates.waiting_for_confirm, F.data == "account:setup_cancel"
)
async def callback_account_setup_cancel(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text(
        "❌ Добавление аккаунта отменено.",
        reply_markup=get_accounts_menu(),
    )
    await call.answer()


# ─── Экстренная пауза ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "main:emergency_pause")
async def callback_emergency_pause(
    call: CallbackQuery, account_manager: AccountManager
) -> None:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="⛔ Да, остановить ВСЕ", callback_data="main:pause_confirm"
        ),
        InlineKeyboardButton(text="❌ Отмена", callback_data="main:menu"),
    )
    await call.message.edit_text(
        "⚠️ <b>Экстренная остановка</b>\n\nОстановить ВСЕ аккаунты?",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await call.answer()


@router.callback_query(F.data == "main:pause_confirm")
async def callback_pause_confirm(
    call: CallbackQuery, account_manager: AccountManager
) -> None:
    await account_manager.stop()
    await call.message.edit_text(
        "⛔ <b>Все аккаунты остановлены.</b>",
        parse_mode="HTML",
        reply_markup=get_main_bot_menu(),
    )
    await call.answer("Все аккаунты остановлены", show_alert=True)


# ─── Статистика и обновления ──────────────────────────────────────────────────

@router.callback_query(F.data == "main:stats")
async def callback_main_stats(call: CallbackQuery) -> None:
    # TODO: агрегация статистики по всем аккаунтам из modules/stats
    await call.message.edit_text(
        "📊 <b>Общая статистика</b>\n\n_Модуль stats в разработке._",
        parse_mode="HTML",
        reply_markup=InlineKeyboardBuilder().row(
            InlineKeyboardButton(text="🔙 Меню", callback_data="main:menu")
        ).as_markup(),
    )
    await call.answer()


@router.callback_query(F.data == "main:updates")
async def callback_main_updates(call: CallbackQuery) -> None:
    # TODO: данные от modules/updates
    await call.message.edit_text(
        "🔔 <b>Версии и обновления</b>\n\n_Модуль updates в разработке._",
        parse_mode="HTML",
        reply_markup=InlineKeyboardBuilder().row(
            InlineKeyboardButton(text="🔙 Меню", callback_data="main:menu")
        ).as_markup(),
    )
    await call.answer()


# ─── Запуск главного бота ─────────────────────────────────────────────────────

async def run_main_bot(account_manager: AccountManager) -> None:
    settings = get_settings()

    if not settings.main_telegram_token:
        logger.error("MAIN_TELEGRAM_TOKEN не задан в .env")
        return

    if not settings.main_telegram_chat_id:
        logger.error("MAIN_TELEGRAM_CHAT_ID не задан в .env")
        return

    bot = Bot(token=settings.main_telegram_token)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Middleware
    allowed_ids = [int(settings.main_telegram_chat_id)]
    dp.update.middleware(AuthMiddleware(allowed_ids=allowed_ids))
    dp.message.middleware(ThrottlingMiddleware(rate_limit=1.0))
    dp.callback_query.middleware(ThrottlingMiddleware(rate_limit=1.0))

    # Передаём account_manager через data
    dp["account_manager"] = account_manager

    dp.include_router(router)

    async def on_shutdown() -> None:
        logger.info("Главный бот останавливается...")
        await bot.session.close()

    dp.shutdown.register(on_shutdown)

    logger.info("Главный бот запущен. Polling...")
    try:
        await dp.start_polling(
            bot, allowed_updates=dp.resolve_used_update_types()
        )
    finally:
        await bot.session.close()


if __name__ == "__main__":
    import asyncio
    from modules.core.database import init_db

    async def main():
        await init_db()
        manager = AccountManager()
        await manager.setup()
        await run_main_bot(manager)

    asyncio.run(main())