from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_user_keyboard(registered: bool = True) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="🎶 Записаться"), KeyboardButton(text="📅 Мои записи")],
        [KeyboardButton(text="🍓 Мои монеты"), KeyboardButton(text="💬 Чат с админом")],
        [KeyboardButton(text="🤝 Моя реферальная ссылка"), KeyboardButton(text="🛒 Магазин")],
        [KeyboardButton(text="📱 Соц. сети"), KeyboardButton(text="📍 Где мы")],
        [KeyboardButton(text="🧺 Заказ вещей")],
    ]
    if not registered:
        buttons.append([KeyboardButton(text="📝 Регистрация")])

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def back_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
    ])