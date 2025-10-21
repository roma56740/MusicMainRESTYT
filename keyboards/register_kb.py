from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_register"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_register")
    ]
])