"""
modules/cardinal_bridge/hooks.py — patch: generate_plugin_file

ИЗМЕНЕНИЯ (security fix):
  - строгая валидация account_id: int() + диапазон [1..9999]
  - атомарная запись (tempfile → os.replace)
  - только числовая интерполяция в template (не строки)
  - chmod 0644 на сгенерированный файл
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Union

from loguru import logger

_log = logger.bind(name="cardinal_bridge")

PLUGIN_FILE = Path("plugins") / "cardinal_multi_bridge.py"

_MIN_ACCOUNT_ID = 1
_MAX_ACCOUNT_ID = 9_999


def generate_plugin_file(account_id: Union[int, str] = 1) -> None:
    """
    Создаёт файл плагина plugins/cardinal_multi_bridge.py.

    :param account_id: ID аккаунта (int, 1..9999)
    :raises ValueError: если account_id невалиден
    :raises OSError: если не удалось записать файл
    """
    # ── Жёсткая валидация ────────────────────────────────────────────────────
    try:
        account_id_int = int(account_id)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"account_id должен быть числом, получено: {type(account_id).__name__!r}"
        ) from exc

    if not (_MIN_ACCOUNT_ID <= account_id_int <= _MAX_ACCOUNT_ID):
        raise ValueError(
            f"account_id вне допустимого диапазона "
            f"[{_MIN_ACCOUNT_ID}..{_MAX_ACCOUNT_ID}], получено: {account_id_int}"
        )

    # ── Создаём директорию плагинов ──────────────────────────────────────────
    PLUGIN_FILE.parent.mkdir(parents=True, exist_ok=True)

    # ── Шаблон: только числовая интерполяция ─────────────────────────────────
    # Нет строковых вставок из внешнего источника → нет injection
    content = (
        '"""Cardinal_Multi Bridge Plugin\n'
        "\n"
        "Сгенерировано автоматически Cardinal_Multi.\n"
        'НЕ РЕДАКТИРУЙТЕ ВРУЧНУЮ — файл перезаписывается при запуске.\n'
        '"""\n'
        "\n"
        f"MULTI_ACCOUNT_ID: int = {account_id_int}\n"
        "\n"
        "\n"
        "def init_cardinal_multi(cardinal) -> None:\n"
        '    """Инициализация моста Cardinal_Multi."""\n'
        "    try:\n"
        "        from modules.cardinal_bridge.hooks import install_hooks\n"
        "        install_hooks(cardinal, MULTI_ACCOUNT_ID)\n"
        "    except Exception as exc:\n"
        "        import logging\n"
        '        logging.getLogger("FPC").error(\n'
        '            "[Cardinal_Multi] Не удалось установить хуки: %s", exc\n'
        "        )\n"
        "\n"
        "\n"
        "BIND_TO_PRE_INIT = [init_cardinal_multi]\n"
    )

    # ── Атомарная запись ──────────────────────────────────────────────────────
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
            dir=str(PLUGIN_FILE.parent),
            prefix=".tmp_bridge_",
            suffix=".py",
        ) as tf:
            tmp_path = tf.name
            tf.write(content)

        try:
            os.chmod(tmp_path, 0o644)
        except OSError:
            pass

        os.replace(tmp_path, str(PLUGIN_FILE))
        tmp_path = None

        _log.info(
            "Bridge plugin создан: {} (account_id={})",
            PLUGIN_FILE,
            account_id_int,
        )

    except OSError as exc:
        _log.error("Не удалось записать bridge plugin: {}", exc)
        raise
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass