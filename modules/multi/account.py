"""
modules/multi/account.py — patch: update_golden_key_in_config

ИЗМЕНЕНИЯ (security fix):
  - chmod 0700 на директорию configs/
  - атомарная запись: tempfile → os.replace (нет неполного файла)
  - chmod 0600 на _main.cfg
  - golden_key НЕ попадает в логи ни при каких условиях
"""

from __future__ import annotations

import configparser
import io
import os
import tempfile
from pathlib import Path


def update_golden_key_in_config(self) -> None:
    """
    Записывает golden_key аккаунта в configs/_main.cfg.

    Thread-safety: использует os.replace (атомарная операция на POSIX).
    Security: chmod 0600 на файл, 0700 на директорию.
    """
    cfg_path    = self.account_dir / "configs" / "_main.cfg"
    configs_dir = cfg_path.parent

    # Создаём директорию если нет
    configs_dir.mkdir(parents=True, exist_ok=True)

    # Hardening прав на директорию
    try:
        configs_dir.chmod(0o700)
    except OSError as e:
        self._log.warning("Не удалось выставить права на {}: {}", configs_dir, e)

    if not cfg_path.exists():
        self._log.warning(
            "Файл _main.cfg не найден для аккаунта {}. "
            "Cardinal создаст его при первом запуске.",
            self.account_id,
        )
        return

    # Получаем golden_key через метод шифрования (не логируем!)
    try:
        golden_key: str = self.model.get_golden_key()
    except Exception:
        self._log.error(
            "Не удалось получить golden_key для аккаунта {}. "
            "Конфиг не обновлён.",
            self.account_id,
        )
        return

    # Читаем существующий конфиг
    config = configparser.ConfigParser()
    config.read(str(cfg_path), encoding="utf-8")

    if "Credentials" not in config:
        config["Credentials"] = {}

    config["Credentials"]["golden_key"] = golden_key

    # Сериализуем в строку
    buf = io.StringIO()
    config.write(buf)
    serialized = buf.getvalue()

    # Атомарная запись: пишем в temp → os.replace (atomic on POSIX)
    tmp_path: Optional[str] = None
    try:
        # Temp файл в той же директории (нужно для атомарности os.replace)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
            dir=str(configs_dir),
            prefix=".tmp_cfg_",
            suffix=".cfg",
        ) as tf:
            tmp_path = tf.name
            tf.write(serialized)

        # chmod до переименования
        try:
            os.chmod(tmp_path, 0o600)
        except OSError as e:
            self._log.warning("Не удалось выставить права на temp файл: {}", e)

        # Атомарное переименование
        os.replace(tmp_path, str(cfg_path))
        tmp_path = None  # Файл успешно перемещён, cleanup не нужен

        # chmod на итоговый файл (на случай если платформа сбросила)
        try:
            cfg_path.chmod(0o600)
        except OSError as e:
            self._log.warning("Не удалось выставить права на {}: {}", cfg_path, e)

        self._log.debug(
            "golden_key записан в конфиг аккаунта {} (chmod 0600).",
            self.account_id,
        )

    except OSError as exc:
        self._log.error(
            "Ошибка записи конфига аккаунта {}: {}",
            self.account_id,
            type(exc).__name__,   # Только тип ошибки, без потенциальных деталей
        )
    finally:
        # Cleanup temp файла если os.replace не выполнился
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass