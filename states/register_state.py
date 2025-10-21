# states/register_state.py

from aiogram.fsm.state import State, StatesGroup

class RegisterState(StatesGroup):
    name = State()        # Фамилия и имя
    birthday = State()    # Дата рождения
    phone = State()       # Номер телефона
    confirm = State()     # Подтверждение введённых данных
