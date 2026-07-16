"""
Абстрактный базовый класс провайдера Lolzteam Market.
Оба режима (API и Playwright) реализуют этот интерфейс.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LolzteamProvider(ABC):
    """
    Абстракция над Lolzteam Market.
    Позволяет менять реализацию (API / Playwright)
    без изменения бизнес-логики.
    """

    # ── Поиск ────────────────────────────────────────────────────

    @abstractmethod
    async def search(
        self,
        category: str,
        filters: dict,
    ) -> list[dict]:
        """
        Поиск товаров в категории.

        Args:
            category: Путь категории (steam, fortnite, ...).
            filters:  Query-параметры для API.

        Returns:
            Список словарей с данными товаров.
        """
        ...

    # ── Товар ────────────────────────────────────────────────────

    @abstractmethod
    async def get_item(self, item_id: int) -> dict:
        """
        Получить полные данные товара по ID.

        Args:
            item_id: ID товара на Lolzteam Market.

        Returns:
            Словарь с данными товара.
        """
        ...

    # ── Покупка ──────────────────────────────────────────────────

    @abstractmethod
    async def fast_buy(
        self,
        item_id: int,
        price: float,
        balance_id: int,
    ) -> dict:
        """
        Быстрая покупка товара (fast-buy).
        При retry_request — повторять до 100 раз.

        Args:
            item_id:    ID товара.
            price:      Цена (float).
            balance_id: ID баланса Lolzteam.

        Returns:
            Результат покупки от API.
        """
        ...

    @abstractmethod
    async def confirm_buy(
        self,
        item_id: int,
        price: int,
        balance_id: int,
    ) -> dict:
        """
        Подтверждение покупки (fallback если fast-buy недоступен).

        Args:
            item_id:    ID товара.
            price:      Цена (int).
            balance_id: ID баланса Lolzteam.

        Returns:
            Результат от API.
        """
        ...

    # ── Счёт ─────────────────────────────────────────────────────

    @abstractmethod
    async def get_balances(self) -> list[dict]:
        """
        Получить список балансов аккаунта.

        Returns:
            Список словарей с полями id, currency, value.
        """
        ...

    # ── Профиль ──────────────────────────────────────────────────

    @abstractmethod
    async def get_profile(self) -> dict:
        """
        Получить профиль аккаунта Lolzteam.
        Используется для проверки соединения.

        Returns:
            Словарь с данными профиля.
        """
        ...