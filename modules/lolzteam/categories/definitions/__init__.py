"""
Все определения категорий Lolzteam Market.
Импорт этого пакета регистрирует все категории в CategoryRegistry.
"""

from modules.lolzteam.categories.registry import CategoryRegistry

from .steam import SteamCategory
from .fortnite import FortniteCategory
from .riot import RiotCategory
from .epicgames import EpicGamesCategory
from .battlenet import BattlenetCategory
from .minecraft import MinecraftCategory
from .worldoftanks import WorldOfTanksCategory
from .wotblitz import WotBlitzCategory
from .origin import OriginCategory
from .socialclub import SocialClubCategory
from .uplay import UplayCategory
from .warface import WarfaceCategory
from .roblox import RobloxCategory
from .escapefromtarkov import EscapeFromTarkovCategory
from .mihoyo import MihoyoCategory
from .supercell import SupercellCategory
from .hytale import HytaleCategory
from .telegram_accounts import TelegramAccountsCategory
from .tiktok import TikTokCategory
from .instagram import InstagramCategory
from .discord import DiscordCategory
from .llm import LlmCategory
from .vpn import VpnCategory
from .gifts import GiftsCategory
from .other import OtherCategory


def register_all() -> None:
    """Зарегистрировать все категории в CategoryRegistry."""
    registry = CategoryRegistry()
    _all = [
        SteamCategory(),
        FortniteCategory(),
        RiotCategory(),
        EpicGamesCategory(),
        BattlenetCategory(),
        MinecraftCategory(),
        WorldOfTanksCategory(),
        WotBlitzCategory(),
        OriginCategory(),
        SocialClubCategory(),
        UplayCategory(),
        WarfaceCategory(),
        RobloxCategory(),
        EscapeFromTarkovCategory(),
        MihoyoCategory(),
        SupercellCategory(),
        HytaleCategory(),
        TelegramAccountsCategory(),
        TikTokCategory(),
        InstagramCategory(),
        DiscordCategory(),
        LlmCategory(),
        VpnCategory(),
        GiftsCategory(),
        OtherCategory(),
    ]
    for cat in _all:
        registry.register(cat)


__all__ = ["register_all"]