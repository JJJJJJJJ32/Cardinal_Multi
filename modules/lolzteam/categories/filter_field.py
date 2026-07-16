"""
Описание одного фильтра категории Lolzteam.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FilterField:
    """
    Описание одного поля фильтра.

    Attributes:
        key:      Имя query-параметра для API Lolzteam.
        label:    Человекочитаемое название (для UI / Telegram).
        type:     Тип значения: int | float | bool | enum | array | str.
        options:  Варианты для type="enum".
        min_val:  Минимальное допустимое значение.
        max_val:  Максимальное допустимое значение.
        required: Обязательный ли фильтр.
        default:  Значение по умолчанию (None = не применять).
    """

    key: str
    label: str
    type: str = "str"
    options: list[Any] = field(default_factory=list)
    min_val: Any = None
    max_val: Any = None
    required: bool = False
    default: Any = None

    def validate(self, value: Any) -> tuple[bool, str]:
        """
        Валидировать значение для этого фильтра.

        Args:
            value: Значение из конфигурации лота.

        Returns:
            (True, "") если валидно,
            (False, "причина") если нет.
        """
        if value is None:
            if self.required:
                return False, f"Обязательное поле '{self.key}' не задано"
            return True, ""

        if self.type == "int":
            try:
                v = int(value)
            except (TypeError, ValueError):
                return False, f"'{self.key}' должен быть int"
            if self.min_val is not None and v < self.min_val:
                return False, f"'{self.key}' < {self.min_val}"
            if self.max_val is not None and v > self.max_val:
                return False, f"'{self.key}' > {self.max_val}"

        elif self.type == "float":
            try:
                v = float(value)
            except (TypeError, ValueError):
                return False, f"'{self.key}' должен быть float"
            if self.min_val is not None and v < self.min_val:
                return False, f"'{self.key}' < {self.min_val}"
            if self.max_val is not None and v > self.max_val:
                return False, f"'{self.key}' > {self.max_val}"

        elif self.type == "bool":
            if not isinstance(value, (bool, int)):
                return False, f"'{self.key}' должен быть bool"

        elif self.type == "enum":
            if value not in self.options:
                return (
                    False,
                    f"'{self.key}' должен быть одним из {self.options}",
                )

        elif self.type == "array":
            if not isinstance(value, list):
                return False, f"'{self.key}' должен быть list"

        return True, ""