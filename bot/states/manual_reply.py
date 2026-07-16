from aiogram.fsm.state import State, StatesGroup


class ManualReplyStates(StatesGroup):
    waiting_for_reply_text = State()
    waiting_for_reply_confirm = State()