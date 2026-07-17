"""
Cardinal Bridge — генерация bridge-плагина для FunPayCardinal.

Фиксы:
  TC-046 — валидный account_id
  TC-047 — account_id строка "abc"
  TC-048 — account_id=0, 10000
  TC-129 — регенерация при смене primary
"""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path
from typing import Optional, Union

from loguru import logger

# ═══════════════════════════════════════════════════════════════════════════════
# Константы
# ═══════════════════════════════════════════════════════════════════════════════
PLUGINS_DIR = Path("plugins")
BRIDGE_PLUGIN_NAME = "cardinal_multi_bridge.py"
BRIDGE_PLUGIN_PATH = PLUGINS_DIR / BRIDGE_PLUGIN_NAME

MIN_ACCOUNT_ID = 1
MAX_ACCOUNT_ID = 9999

# Шаблон bridge-плагина
_BRIDGE_TEMPLATE = '''"""
Cardinal Multi Bridge Plugin (автогенерация).

Этот файл генерируется автоматически при запуске Cardinal_Multi.
НЕ РЕДАКТИРУЙТЕ ВРУЧНУЮ — изменения будут перезаписаны.

Account ID: {account_id}
"""

from __future__ import annotations

ACCOUNT_ID: int = {account_id}


def get_account_id() -> int:
    """Вернуть ID аккаунта, для которого генерирован плагин."""
    return ACCOUNT_ID
'''


# ═══════════════════════════════════════════════════════════════════════════════
# Валидация
# ═══════════════════════════════════════════════════════════════════════════════
def _validate_account_id(account_id: Union[int, str, None]) -> int:
    """
    Валидация и приведение account_id к int.

    TC-047: "abc" → ValueError
    TC-048: 0 / 10000 → ValueError
    """
    if account_id is None:
        raise ValueError("account_id не может быть None")

    try:
        aid = int(account_id)
    except (ValueError, TypeError):
        raise ValueError(
            f"account_id должен быть целым числом, получено: {account_id!r}"
        )

    if not (MIN_ACCOUNT_ID <= aid <= MAX_ACCOUNT_ID):
        raise ValueError(
            f"account_id должен быть в диапазоне "
            f"{MIN_ACCOUNT_ID}..{MAX_ACCOUNT_ID}, получено: {aid}"
        )

    return aid


# ═══════════════════════════════════════════════════════════════════════════════
# Генерация файла
# ═══════════════════════════════════════════════════════════════════════════════
def generate_plugin_file(
    account_id: Union[int, str, None] = 1,
    *,
    force: bool = False,
) -> Path:
    """
    Генерирует (или регенерирует) bridge-плагин.

    Атомарная запись: пишем во временный файл → os.replace().

    TC-129: если force=False и файл уже содержит правильный account_id —
    пропускаем генерацию.

    Returns:
        Path к сгенерированному файлу.

    Raises:
        ValueError: если account_id невалиден.
        OSError: если нет прав на запись в plugins/.
    """
    aid = _validate_account_id(account_id)

    # ── Создаём plugins/ если нет ────────────────────────────────────────────
    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)

    # ── TC-129: проверяем — может файл уже актуален? ─────────────────────────
    if not force and BRIDGE_PLUGIN_PATH.exists():
        try:
            content = BRIDGE_PLUGIN_PATH.read_text(encoding="utf-8")
            if f"ACCOUNT_ID: int = {aid}" in content:
                logger.debug(
                    f"Bridge plugin уже содержит account_id={aid}, пропуск"
                )
                return BRIDGE_PLUGIN_PATH
        except OSError:
            pass  # Не можем прочитать — перегенерим

    # ── Генерация через атомарную запись ──────────────────────────────────────
    plugin_content = _BRIDGE_TEMPLATE.format(account_id=aid)

    try:
        fd, tmp_path = tempfile.mkstemp(
            dir=str(PLUGINS_DIR),
            prefix=".bridge_tmp_",
            suffix=".py",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(plugin_content)
                f.flush()
                os.fsync(f.fileno())

            # Устанавливаем права (owner: rw, group/other: r)
            if os.name != "nt":
                os.chmod(tmp_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)

            # Атомарная замена
            os.replace(tmp_path, str(BRIDGE_PLUGIN_PATH))

        except Exception:
            # Чистим временный файл если что-то пошло не так
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    except OSError as exc:
        logger.error(f"Bridge plugin: не удалось создать файл — {exc}")
        raise

    logger.info(f"Bridge plugin сгенерирован: {BRIDGE_PLUGIN_PATH} (account_id={aid})")
    return BRIDGE_PLUGIN_PATH