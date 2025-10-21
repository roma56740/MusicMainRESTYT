# keyboards/social_kb.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def social_links_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Telegram", url="https://t.me/Strawberryrec"),
            InlineKeyboardButton(text="ВКонтакте", url="https://vk.com/strawberryrec")
        ]
    ])
