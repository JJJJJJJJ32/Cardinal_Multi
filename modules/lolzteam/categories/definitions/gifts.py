"""Категория Gift-карты и подарки."""

from __future__ import annotations

from modules.lolzteam.categories.base_category import BaseCategory
from modules.lolzteam.categories.filter_field import FilterField


class GiftsCategory(BaseCategory):
    @property
    def url_path(self) -> str:
        return "gifts"

    @property
    def display_name(self) -> str:
        return "Подарки и gift-карты"

    @property
    def icon(self) -> str:
        return "🎁"

    @property
    def specific_filters(self) -> list[FilterField]:
        return []