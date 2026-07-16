import os
import shutil
import datetime
from pathlib import Path

from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from loguru import logger

router = Router(name="backups")

BACKUP_DIR = Path("data/backups")
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

ACCOUNTS_DIR = Path("data/accounts")


def build_backups_keyboard() -> object:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="💾 Создать резервную копию", callback_data="backup:create"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📂 Восстановить из копии", callback_data="backup:restore_list"
        )
    )
    builder.row(InlineKeyboardButton(text="🔙 Меню", callback_data="acc:menu"))
    return builder.as_markup()


@router.callback_query(F.data == "acc:backups")
async def callback_backups(call: CallbackQuery) -> None:
    await call.message.edit_text(
        "💾 <b>Резервные копии</b>",
        parse_mode="HTML",
        reply_markup=build_backups_keyboard(),
    )
    await call.answer()


@router.callback_query(F.data == "backup:create")
async def callback_backup_create(call: CallbackQuery) -> None:
    await call.answer("⏳ Создаю резервную копию...")

    try:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"backup_{ts}"
        shutil.copytree(ACCOUNTS_DIR, backup_path / "accounts", dirs_exist_ok=True)

        # Также бэкапируем БД
        db_source = Path("data/cardinal_multi.db")
        if db_source.exists():
            shutil.copy2(db_source, backup_path / "cardinal_multi.db")

        # Сжимаем в zip
        zip_path = shutil.make_archive(str(backup_path), "zip", backup_path)
        shutil.rmtree(backup_path)

        logger.info(f"Создан бэкап: {zip_path}")

        # Отправляем файл пользователю
        doc = FSInputFile(zip_path, filename=f"backup_{ts}.zip")
        await call.message.answer_document(
            document=doc,
            caption=f"✅ Резервная копия создана: <code>backup_{ts}.zip</code>",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Ошибка создания бэкапа: {e}")
        await call.message.answer(f"❌ Ошибка создания бэкапа: {e}")


@router.callback_query(F.data == "backup:restore_list")
async def callback_backup_restore_list(call: CallbackQuery) -> None:
    backups = sorted(BACKUP_DIR.glob("*.zip"), reverse=True)

    if not backups:
        await call.message.edit_text(
            "📂 Резервных копий нет.",
            reply_markup=build_backups_keyboard(),
        )
        await call.answer()
        return

    builder = InlineKeyboardBuilder()
    for bp in backups[:10]:
        builder.row(
            InlineKeyboardButton(
                text=f"🗂 {bp.name}",
                callback_data=f"backup:restore:{bp.stem}",
            )
        )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="acc:backups"))

    await call.message.edit_text(
        "📂 <b>Выберите резервную копию:</b>",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await call.answer()