"""
Реестр категорий Lolzteam Market.
Все категории регистрируются здесь и доступны по url_path.
"""

from __future__ import annotations

from loguru import logger

from .base_category import BaseCategory


class CategoryRegistry:
    """
    Синглтон-реестр категорий.

    Использование:
        registry = CategoryRegistry()
        registry.register(SteamCategory())
        cat = registry.get("steam")
        all_cats = registry.all()
    """

    _instance: CategoryRegistry | None = None
    _categories: dict[str, BaseCategory]

    def __new__(cls) -> "CategoryRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._categories = {}
        return cls._instance

    def register(self, category: BaseCategory) -> None:
        """
        Зарегистрировать категорию.

        Args:
            category: Экземпляр BaseCategory.
        """
        key = category.url_path
        if key in self._categories:
            logger.warning(
                f"[CategoryRegistry] Категория '{key}' уже зарегистрирована, "
                f"перезапись."
            )
        self._categories[key] = category
        logger.debug(
            f"[CategoryRegistry] Зарегистрирована: "
            f"{category.icon} {category.display_name} ({key})"
        )

    def get(self, url_path: str) -> BaseCategory | None:
        """
        Получить категорию по url_path.

        Args:
            url_path: Путь категории (например 'steam').

        Returns:
            BaseCategory или None если не найдена.
        """
        return self._categories.get(url_path)

    def all(self) -> list[BaseCategory]:
        """Список всех зарегистрированных категорий."""
        return list(self._categories.values())

    def keys(self) -> list[str]:
        """Список всех url_path."""
        return list(self._categories.keys())

    def __len__(self) -> int:
        return len(self._categories)

    def __contains__(self, url_path: str) -> bool:
        return url_path in self._categories