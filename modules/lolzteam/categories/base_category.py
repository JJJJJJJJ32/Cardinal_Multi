"""
Абстрактный базовый класс категории Lolzteam Market.
Каждая категория — отдельный файл в definitions/.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .filter_field import FilterField


class BaseCategory(ABC):
    """
    Категория товаров на Lolzteam Market.

    Атрибуты подкласса:
        url_path:        str — путь в API (steam, fortnite, ...).
        display_name:    str — название для UI.
        icon:            str — эмодзи.
        specific_filters: list[FilterField] — специфичные фильтры.
    """

    @property
    @abstractmethod
    def url_path(self) -> str:
        """Путь в Lolzteam API (например 'steam')."""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Отображаемое название категории."""
        ...

    @property
    @abstractmethod
    def icon(self) -> str:
        """Эмодзи-иконка категории."""
        ...

    @property
    @abstractmethod
    def specific_filters(self) -> list[FilterField]:
        """Список специфичных фильтров категории."""
        ...

    def get_all_filter_keys(self) -> list[str]:
        """Список всех ключей специфичных фильтров."""
        return [f.key for f in self.specific_filters]

    def get_filter(self, key: str) -> FilterField | None:
        """Найти FilterField по ключу."""
        for f in self.specific_filters:
            if f.key == key:
                return f
        return None

    def __repr__(self) -> str:
        return (
            f"<Category {self.icon} {self.display_name} "
            f"path='{self.url_path}'>"
        )