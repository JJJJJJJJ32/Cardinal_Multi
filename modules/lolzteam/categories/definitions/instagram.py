"""Категория Instagram."""

from __future__ import annotations

from modules.lolzteam.categories.base_category import BaseCategory
from modules.lolzteam.categories.filter_field import FilterField


class InstagramCategory(BaseCategory):
    @property
    def url_path(self) -> str:
        return "instagram"

    @property
    def display_name(self) -> str:
        return "Instagram"

    @property
    def icon(self) -> str:
        return "📸"

    @property
    def specific_filters(self) -> list[FilterField]:
        return []