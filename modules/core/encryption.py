"""
modules/core/encryption.py
──────────────────────────
Симметричное шифрование данных через Fernet (AES-128-CBC + HMAC-SHA256).
Все секреты (golden_key, токены Telegram) хранятся в БД в зашифрованном виде.

Ключ: ./data/secret.key
- Если файл существует — читается оттуда.
- Если нет — генерируется новый и сохраняется.
"""

from __future__ import annotations

from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from loguru import logger


# ─── Константы ────────────────────────────────────────────────────────────────
DATA_DIR = Path("data")
KEY_FILE = DATA_DIR / "secret.key"


class EncryptionError(Exception):
    """Ошибка шифрования/дешифровки."""
    pass


class Encryption:
    """
    Менеджер Fernet-шифрования.

    Синглтон: один экземпляр на весь процесс.
    Ключ загружается/генерируется при первом обращении.

    Пример использования::

        enc = Encryption()
        encrypted = enc.encrypt("my_golden_key_value")
        original  = enc.decrypt(encrypted)
    """

    _instance: "Encryption | None" = None
    _fernet: Fernet | None = None

    def __new__(cls) -> "Encryption":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    # ──────────────────────────────────────────────────────────────────────────
    # Инициализация
    # ──────────────────────────────────────────────────────────────────────────

    def _initialize(self) -> None:
        """Загружает или создаёт ключ шифрования."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        if KEY_FILE.exists():
            key = self._load_key()
            logger.debug("Ключ шифрования загружен из {}", KEY_FILE)
        else:
            key = self._generate_key()
            logger.info("Новый ключ шифрования создан: {}", KEY_FILE)

        self._fernet = Fernet(key)

    def _generate_key(self) -> bytes:
        """
        Генерирует новый Fernet-ключ и сохраняет в файл.

        :return: bytes ключ.
        :raises EncryptionError: если не удалось записать файл.
        """
        key = Fernet.generate_key()
        try:
            KEY_FILE.write_bytes(key)
            # Ограничиваем права на файл (только чтение/запись владельца)
            KEY_FILE.chmod(0o600)
        except OSError as exc:
            raise EncryptionError(
                f"Не удалось сохранить ключ шифрования в {KEY_FILE}: {exc}"
            ) from exc
        return key

    def _load_key(self) -> bytes:
        """
        Загружает ключ из файла.

        :return: bytes ключ.
        :raises EncryptionError: если файл повреждён или недоступен.
        """
        try:
            key = KEY_FILE.read_bytes().strip()
            if not key:
                raise EncryptionError(f"Файл ключа {KEY_FILE} пуст.")
            return key
        except OSError as exc:
            raise EncryptionError(
                f"Не удалось прочитать ключ шифрования из {KEY_FILE}: {exc}"
            ) from exc

    # ──────────────────────────────────────────────────────────────────────────
    # Публичный API
    # ──────────────────────────────────────────────────────────────────────────

    def encrypt(self, text: str) -> str:
        """
        Шифрует строку и возвращает base64-encoded шифротекст.

        :param text: открытый текст для шифрования.
        :return: зашифрованная строка (base64).
        :raises EncryptionError: при ошибке шифрования.

        Пример::

            token_encrypted = Encryption().encrypt("1234567890:ABCdef...")
        """
        if self._fernet is None:
            raise EncryptionError("Fernet не инициализирован.")
        try:
            return self._fernet.encrypt(text.encode("utf-8")).decode("utf-8")
        except Exception as exc:
            raise EncryptionError(f"Ошибка шифрования: {exc}") from exc

    def decrypt(self, token: str) -> str:
        """
        Дешифрует base64-encoded шифротекст.

        :param token: зашифрованная строка (base64).
        :return: открытый текст.
        :raises EncryptionError: при ошибке дешифровки (неверный ключ / повреждённые данные).

        Пример::

            golden_key = Encryption().decrypt(encrypted_golden_key)
        """
        if self._fernet is None:
            raise EncryptionError("Fernet не инициализирован.")
        try:
            return self._fernet.decrypt(token.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise EncryptionError(
                "Не удалось расшифровать данные. "
                "Возможно, ключ шифрования был изменён или данные повреждены."
            ) from exc
        except Exception as exc:
            raise EncryptionError(f"Ошибка дешифровки: {exc}") from exc

    def rotate_key(self) -> None:
        """
        Генерирует новый ключ. Вызывать ТОЛЬКО если старый скомпрометирован.
        После вызова все зашифрованные данные в БД станут нечитаемы.

        .. warning::
            Метод не перешифровывает данные в БД автоматически.
        """
        logger.warning(
            "Ротация ключа шифрования! Все зашифрованные данные необходимо перезаписать."
        )
        key = self._generate_key()
        self._fernet = Fernet(key)