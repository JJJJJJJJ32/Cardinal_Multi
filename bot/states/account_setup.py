from aiogram.fsm.state import State, StatesGroup


class AccountSetupStates(StatesGroup):
    # Шаг 1 — инструкция BotFather + ввод токена
    waiting_for_token = State()

    # Шаг 2 — ввод golden_key
    waiting_for_golden_key = State()

    # Шаг 3 — PIN код
    waiting_for_pin = State()

    # Шаг 4 — Lolzteam аккаунт
    waiting_for_lolzteam = State()

    # Шаг 5 — подтверждение и запуск
    waiting_for_confirm = State()