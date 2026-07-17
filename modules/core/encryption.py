"""
Encryption — Fernet шифрование секретов.

Фиксы:
  TC-006 — создание ключа при первом запуске
  TC-007 — загрузка существующего ключа
  TC-091 — удаление ключа в runtime
  TC-092 — замена ключа → InvalidToken при расшифровке
  TC-093 — битый шифртекст
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from loguru import logger

# ═══════════════════════════════════════════════════════════════════════════════
# Константы
# ═══════════════════════════════════════════════════════════════════════════════
DATA_DIR = Path("data")
KEY_FILE = DATA_DIR / "secret.key"


class EncryptionError(Exception):
    """Ошибка шифрования/дешифрования."""
    pass


class Encryption:
    """
    Singleton для Fernet-шифрования.

    Гарантии:
      - ключ создаётся автоматически если не существует
      - ключ хранится в data/secret.key с правами 600
      - decrypt при невалидном ключе/шифртексте → EncryptionError (не crash)
    """

    _instance: Optional["Encryption"] = None
    _fernet: Optional[Fernet] = None

    def __new__(cls) -> "Encryption":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_key()
        return cls._instance

    def _init_key(self) -> None:
        """Загрузить или создать ключ шифрования."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        if KEY_FILE.exists():
            # TC-007: загрузка существующего ключа
            try:
                key = KEY_FILE.read_bytes().strip()
                self._fernet = Fernet(key)
                logger.debug("Encryption: ключ загружен из secret.key")
            except Exception as exc:
                logger.error(f"Encryption: не удалось загрузить ключ — {exc}")
                raise EncryptionError(
                    f"Невалидный ключ в {KEY_FILE}. "
                    f"Удалите файл для генерации нового (данные будут потеряны)."
                ) from exc
        else:
            # TC-006: создание нового ключа
            key = Fernet.generate_key()
            KEY_FILE.write_bytes(key)

            # Права 600 (owner only) — Linux/Mac
            if os.name != "nt":
                try:
                    KEY_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)
                except OSError:
                    pass

            self._fernet = Fernet(key)
            logger.info("Encryption: новый ключ создан и сохранён")

    # ─────────────────────────────────────────────────────────────────────────
    # Публичные методы
    # ─────────────────────────────────────────────────────────────────────────
    def encrypt(self, plaintext: str) -> str:
        """
        Зашифровать строку → base64 Fernet token.

        TC-091: если ключ был удалён после init — используем ключ из памяти.
        """
        if self._fernet is None:
            raise EncryptionError("Encryption не инициализирован (ключ отсутствует)")

        try:
            return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")
        except Exception as exc:
            raise EncryptionError(f"Ошибка шифрования: {exc}") from exc

    def decrypt(self, ciphertext: str) -> str:
        """
        Расшифровать Fernet token → исходная строка.

        TC-092: InvalidToken если ключ подменён.
        TC-093: InvalidToken если шифртекст битый.
        """
        if self._fernet is None:
            raise EncryptionError("Encryption не инициализирован (ключ отсутствует)")

        try:
            return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            raise EncryptionError(
                "Не удалось расшифровать данные: ключ не совпадает или данные повреждены. "
                "Возможно, файл secret.key был заменён."
            )
        except Exception as exc:
            raise EncryptionError(f"Ошибка дешифрования: {exc}") from exc

    @staticmethod
    def is_initialized() -> bool:
        """Проверить, инициализирован ли Encryption."""
        return Encryption._instance is not None and Encryption._fernet is not None