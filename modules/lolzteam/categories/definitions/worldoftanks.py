"""Категория World of Tanks."""

from __future__ import annotations

from modules.lolzteam.categories.base_category import BaseCategory
from modules.lolzteam.categories.filter_field import FilterField


class WorldOfTanksCategory(BaseCategory):
    @property
    def url_path(self) -> str:
        return "worldoftanks"

    @property
    def display_name(self) -> str:
        return "World of Tanks"

    @property
    def icon(self) -> str:
        return "🛡️"

    @property
    def specific_filters(self) -> list[FilterField]:
        return []