"""
Модуль автозакупки Lolzteam для Cardinal_Multi.

Использование:
    from modules.lolzteam import LolzteamModule

    module = LolzteamModule()
    await module.setup()
    await module.start()
"""

from .module import LolzteamModule

__all__ = ["LolzteamModule"]