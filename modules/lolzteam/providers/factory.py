"""
Фабрика провайдеров Lolzteam.
Выбирает API или Playwright в зависимости от наличия токена.
"""

from __future__ import annotations

from loguru import logger

from .base import LolzteamProvider
from .api_provider import LolzteamApiProvider
from .playwright_provider import LolzteamPlaywrightProvider


class LolzteamFactory:
    """
    Создаёт нужный провайдер по конфигурации.

    Если api_token задан → LolzteamApiProvider.
    Иначе               → LolzteamPlaywrightProvider.
    """

    @staticmethod
    def create(
        *,
        api_token: str | None = None,
        login: str | None = None,
        password: str | None = None,
    ) -> LolzteamProvider:
        """
        Создать провайдер.

        Args:
            api_token: API токен Lolzteam (если есть).
            login:     Логин для Playwright режима.
            password:  Пароль для Playwright режима.

        Returns:
            Экземпляр LolzteamProvider (API или Playwright).

        Raises:
            ValueError: Если нет ни токена, ни логина/пароля.
        """
        if api_token:
            logger.info("[Lolzteam] Используется API провайдер")
            return LolzteamApiProvider(api_token=api_token)

        if login and password:
            logger.warning(
                "[Lolzteam] Используется Playwright провайдер. "
                "⚠️ Для стабильной работы получи API токен: "
                "lolz.live/account/api/get-token"
            )
            return LolzteamPlaywrightProvider(
                login=login, password=password
            )

        raise ValueError(
            "Lolzteam: нужен LOLZ_API_TOKEN или "
            "LOLZ_LOGIN + LOLZ_PASSWORD"
        )