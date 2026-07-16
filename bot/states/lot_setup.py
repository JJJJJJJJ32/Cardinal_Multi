from aiogram.fsm.state import State, StatesGroup


class LotSetupStates(StatesGroup):
    # Шаг 1 — поиск лота
    waiting_for_lot_search = State()

    # Шаг 3 — выбор категории (Шаг 2 — карточка лота, без ввода)
    waiting_for_category = State()

    # Шаг 4 — общие фильтры
    waiting_for_min_price = State()
    waiting_for_max_price = State()
    waiting_for_min_rating = State()
    waiting_for_min_reviews = State()
    waiting_for_required_words = State()
    waiting_for_forbidden_words = State()

    # Шаг 5 — специфические фильтры (динамические)
    waiting_for_specific_filter = State()

    # Шаг 6 — режим выдачи
    waiting_for_delivery_mode = State()

    # Шаг 7 — подтверждение после тестового поиска
    waiting_for_confirm = State()