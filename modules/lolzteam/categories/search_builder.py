"""
Построитель query-параметров для поиска на Lolzteam Market.
Валидирует фильтры из конфигурации лота и формирует dict для API.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from .base_category import BaseCategory
from .filter_field import FilterField

# Общие фильтры, присутствующие во всех категориях
_COMMON_FILTER_KEYS = {
    "pmin", "pmax", "page", "title", "order_by",
    "nsb", "currency", "eg",
}


class SearchQueryBuilder:
    """
    Строит dict query-параметров для Lolzteam API.

    Принимает:
      - common_filters  — из LotLolzteamSettings.common_filters
      - specific_filters — из LotLolzteamSettings.specific_filters
      - category        — BaseCategory (для валидации specific)

    Возвращает:
      - dict готовый для передачи в provider.search()
    """

    def __init__(self, category: BaseCategory) -> None:
        self._category = category

    def build(
        self,
        common_filters: dict[str, Any],
        specific_filters: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Собрать query-параметры.

        Args:
            common_filters:   Общие фильтры (pmin, pmax, ...).
            specific_filters: Специфичные фильтры (steam-only, etc.).

        Returns:
            Валидный dict query-параметров для API.
        """
        params: dict[str, Any] = {}

        # ── Общие фильтры ─────────────────────────────────────────
        for key, value in common_filters.items():
            if value is None or value == "":
                continue
            params[key] = value

        # ── Специфичные фильтры ──────────────────────────────────
        for field in self._category.specific_filters:
            raw = specific_filters.get(field.key)
            if raw is None:
                if field.default is not None:
                    params[field.key] = field.default
                continue

            ok, reason = field.validate(raw)
            if not ok:
                logger.warning(
                    f"[SearchBuilder] Невалидный фильтр "
                    f"'{field.key}'={raw}: {reason}. Пропущен."
                )
                continue

            # Массивы → key[]=val1&key[]=val2
            if field.type == "array":
                params[f"{field.key}[]"] = raw
            else:
                params[field.key] = raw

        # Всегда сортировать по возрастанию цены
        params["order_by"] = "price_to_up"

        logger.debug(
            f"[SearchBuilder] Собраны params для "
            f"/{self._category.url_path}: {params}"
        )
        return params