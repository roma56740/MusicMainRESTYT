from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
import locale
from db import get_booked_slots
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
MONTHS = {
    1: "янв", 2: "фев", 3: "мар", 4: "апр", 5: "мая", 6: "июн",
    7: "июл", 8: "авг", 9: "сен", 10: "окт", 11: "ноя", 12: "дек"
}

# Установим русскую локаль для дней недели (только если доступна)
try:
    locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
except:
    pass  # Windows может не поддерживать, тогда оставим англ

def get_tariff_inline_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🕒 Почасовой", callback_data="tariff_hourly"),
            InlineKeyboardButton(text="🌙 Ночной", callback_data="tariff_night")
        ]
    ])

def get_date_selection_kb(tariff_type: str) -> InlineKeyboardMarkup:
    buttons = []
    for i in range(7):
        day = datetime.now() + timedelta(days=i)
        weekday = WEEKDAYS[day.weekday()]
        month = MONTHS[day.month]
        day_text = f"📅 {weekday}, {day.day:02d} {month}"
        callback_data = f"choose_date|{tariff_type}|{day.strftime('%Y-%m-%d')}"
        buttons.append([InlineKeyboardButton(text=day_text, callback_data=callback_data)])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


from datetime import datetime, timedelta

def generate_hour_buttons(date_str: str, tariff: str) -> InlineKeyboardMarkup:
    now = datetime.now()
    today = now.strftime("%Y-%m-%d") == date_str

    booked = get_booked_slots(date_str)
    booked_ranges = [(int(f), int(t)) for f, t in booked]

    if tariff == "hourly":
        start_hour, end_hour = 10, 22
    else:  # night
        start_hour, end_hour = 22, 30  # 30 = 6 next day

    buttons = []
    for h in range(start_hour, end_hour):
        display_h = h if h < 24 else h - 24
        time_str = f"{display_h:02d}:00"

        if today and h <= now.hour + 1:
            continue  # пропустить прошедшее

        # Проверка занятости
        is_busy = any(start <= h < end for start, end in booked_ranges)
        emoji = "❌" if is_busy else "✅"
        cb_data = f"time_from|{h}"

        buttons.append([InlineKeyboardButton(text=f"{emoji} {time_str}", callback_data=cb_data)])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_booking_status_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟢 Актуальные", callback_data="bookings_active"),
            InlineKeyboardButton(text="🔴 Отменённые", callback_data="bookings_cancelled"),
            InlineKeyboardButton(text="⏳ Прошедшие", callback_data="bookings_past"),
        ]
    ])


from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_shop_management_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Создать", callback_data="shop_create"),
            InlineKeyboardButton(text="✏️ Редактировать", callback_data="shop_edit")
        ],
        [
            InlineKeyboardButton(text="🗑 Удалить", callback_data="shop_delete"),
            InlineKeyboardButton(text="📋 Посмотреть", callback_data="shop_view")
        ]
    ])