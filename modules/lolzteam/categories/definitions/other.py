"""Прочие категории (fallback)."""

from __future__ import annotations

from modules.lolzteam.categories.base_category import BaseCategory
from modules.lolzteam.categories.filter_field import FilterField


class OtherCategory(BaseCategory):
    @property
    def url_path(self) -> str:
        return "other"

    @property
    def display_name(self) -> str:
        return "Прочее"

    @property
    def icon(self) -> str:
        return "📦"

    @property
    def specific_filters(self) -> list[FilterField]:
        return []