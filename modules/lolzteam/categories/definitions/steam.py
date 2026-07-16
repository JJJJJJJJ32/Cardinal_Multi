"""Категория Steam."""

from __future__ import annotations

from modules.lolzteam.categories.base_category import BaseCategory
from modules.lolzteam.categories.filter_field import FilterField


class SteamCategory(BaseCategory):
    """Steam аккаунты на Lolzteam Market."""

    @property
    def url_path(self) -> str:
        return "steam"

    @property
    def display_name(self) -> str:
        return "Steam"

    @property
    def icon(self) -> str:
        return "🎮"

    @property
    def specific_filters(self) -> list[FilterField]:
        return [
            FilterField("lmin", "Уровень от", "int", min_val=0),
            FilterField("lmax", "Уровень до", "int", min_val=0),
            FilterField("gmin", "Игр от", "int", min_val=0),
            FilterField("gmax", "Игр до", "int", min_val=0),
            FilterField("no_vac", "Без VAC", "bool"),
            FilterField("mafile", "Есть mafile", "bool"),
            FilterField("trade_ban", "С трейд баном", "bool"),
            FilterField("trade_limit", "С трейд лимитом", "bool"),
            FilterField("balance_min", "Баланс от", "float", min_val=0),
            FilterField("balance_max", "Баланс до", "float", min_val=0),
            FilterField("friends_min", "Друзей от", "int", min_val=0),
            FilterField("friends_max", "Друзей до", "int", min_val=0),
            FilterField("inv_min", "Инвентарь от ($)", "float", min_val=0),
            FilterField("inv_max", "Инвентарь до ($)", "float", min_val=0),
            FilterField("inv_game", "Игра инвентаря", "str"),
            FilterField("reg", "Год регистрации", "int", min_val=2003),
            FilterField("reg_period", "Период регистрации", "str"),
            FilterField("rmin", "Ранг CS от", "int", min_val=1, max_val=18),
            FilterField("rmax", "Ранг CS до", "int", min_val=1, max_val=18),
            FilterField("elo_min", "ELO от", "int", min_val=0),
            FilterField("elo_max", "ELO до", "int", min_val=0),
            FilterField("no_trans", "Без переводов", "bool"),
            FilterField("country[]", "Страны", "array"),
            FilterField("not_country[]", "Исключить страны", "array"),
            FilterField("daybreak", "Перерыв в днях", "int", min_val=0),
            FilterField("faceit_lvl_min", "FACEIT уровень от", "int", min_val=1, max_val=10),
            FilterField("faceit_lvl_max", "FACEIT уровень до", "int", min_val=1, max_val=10),
            FilterField("solommr_min", "Solo MMR от", "int", min_val=0),
            FilterField("solommr_max", "Solo MMR до", "int", min_val=0),
            FilterField("email_login_data", "С данными email", "bool"),
            FilterField("points_min", "Steam Points от", "int", min_val=0),
            FilterField("points_max", "Steam Points до", "int", min_val=0),
            FilterField("has_faceit", "Есть FACEIT", "bool"),
            FilterField("recently_hours_min", "Часов за 2 нед. от", "int", min_val=0),
            FilterField("recently_hours_max", "Часов за 2 нед. до", "int", min_val=0),
            FilterField("d2_game_count_min", "Игр в D2 от", "int", min_val=0),
            FilterField("d2_game_count_max", "Игр в D2 до", "int", min_val=0),
            FilterField("d2_win_count_min", "Побед в D2 от", "int", min_val=0),
            FilterField("d2_win_count_max", "Побед в D2 до", "int", min_val=0),
            FilterField("rust_kills_min", "Rust kills от", "int", min_val=0),
            FilterField("rust_kills_max", "Rust kills до", "int", min_val=0),
            FilterField("rust_deaths_min", "Rust deaths от", "int", min_val=0),
            FilterField("rust_deaths_max", "Rust deaths до", "int", min_val=0),
            FilterField("cards_min", "Карточек от", "int", min_val=0),
            FilterField("cards_max", "Карточек до", "int", min_val=0),
            FilterField("medal_id[]", "Медали", "array"),
            FilterField("gift[]", "Подарки", "array"),
            FilterField("purchase_min", "Трат от ($)", "float", min_val=0),
            FilterField("purchase_max", "Трат до ($)", "float", min_val=0),
            FilterField("wingman_rmin", "Wingman ранг от", "int"),
            FilterField("wingman_rmax", "Wingman ранг до", "int"),
            FilterField("cs2_profile_rank_min", "CS2 ранг профиля от", "int"),
            FilterField("cs2_profile_rank_max", "CS2 ранг профиля до", "int"),
            FilterField("has_activated_keys", "С активированными ключами", "bool"),
            FilterField("last_trans_date", "Дата последнего трансфера", "str"),
            FilterField("last_trans_date_period", "Период трансфера", "str"),
            FilterField("pending_balance_min", "Ожид. баланс от", "float"),
            FilterField("pending_balance_max", "Ожид. баланс до", "float"),
            FilterField("skip_vac_inv", "Скрыть VAC инвентари", "bool"),
            FilterField("market", "Market", "bool"),
        ]