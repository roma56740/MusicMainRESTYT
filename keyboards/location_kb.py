from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def location_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📍 Открыть на карте",
                    url="https://clck.ru/3N5dMj"
                )
            ]
        ]
    )
