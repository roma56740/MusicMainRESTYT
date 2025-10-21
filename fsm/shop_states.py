from aiogram.fsm.state import State, StatesGroup

class ShopCreate(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_price = State()

class ShopEdit(StatesGroup):
    choosing_item = State()
    editing_name = State()
    editing_description = State()
    editing_price = State()