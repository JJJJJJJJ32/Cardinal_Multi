from aiogram.fsm.state import State, StatesGroup


class TemplateSetupStates(StatesGroup):
    waiting_for_template_name = State()
    waiting_for_template_text = State()
    waiting_for_template_confirm = State()

    # Редактирование
    waiting_for_new_template_name = State()
    waiting_for_new_template_text = State()