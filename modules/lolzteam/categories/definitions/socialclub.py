"""Категория Social Club (Rockstar)."""

from __future__ import annotations

from modules.lolzteam.categories.base_category import BaseCategory
from modules.lolzteam.categories.filter_field import FilterField


class SocialClubCategory(BaseCategory):
    @property
    def url_path(self) -> str:
        return "socialclub"

    @property
    def display_name(self) -> str:
        return "Rockstar Social Club"

    @property
    def icon(self) -> str:
        return "🌟"

    @property
    def specific_filters(self) -> list[FilterField]:
        return [
            FilterField("email_login_data", "С данными email", "bool"),
        ]