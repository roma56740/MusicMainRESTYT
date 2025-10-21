from aiogram import Router
from aiogram.types import Message, CallbackQuery
from keyboards.booking_kb import get_tariff_inline_kb, get_date_selection_kb
from aiogram.fsm.context import FSMContext
from db import get_booked_slots, add_booking
from aiogram.fsm.state import StatesGroup, State
from keyboards.booking_kb import generate_hour_buttons 
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from db import get_booked_slots
import sqlite3

from dotenv import load_dotenv
import os
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

class BookingState(StatesGroup):
    tariff = State()
    date = State()
    time_from = State()
    time_to = State()


router = Router()

@router.message(lambda m: m.text == "🎶 Записаться")
async def choose_tariff(message: Message):
    text = (
        "🎧 <b>Запись в музыкальную студию</b>\n\n"
        "Выберите <i>тариф</i>, который вам подходит:\n"
        "• <b>🕒 Почасовой</b> — с 10:00 до 22:00\n"
        "• <b>🌙 Ночной</b> — с 22:00 до 06:00\n\n" 
        "После выбора вы сможете выбрать удобную дату и время. ⏱️"
    )
    await message.answer(
        text,
        reply_markup=get_tariff_inline_kb(),
        parse_mode="HTML"
    )

@router.callback_query(lambda c: c.data in ["tariff_hourly", "tariff_night"])
async def handle_tariff_choice(callback: CallbackQuery):
    tariff = "hourly" if callback.data == "tariff_hourly" else "night"
    await callback.message.answer(
        f"📅 <b>Выберите день</b> для тарифа {'почасовой' if tariff == 'hourly' else 'ночной'}:",
        reply_markup=get_date_selection_kb(tariff),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("choose_date|"))
async def handle_date_choice(callback: CallbackQuery, state: FSMContext):
    _, tariff, date_str = callback.data.split("|")
    await state.update_data(tariff=tariff, date=date_str)

    # Покажем список часов "от"
    await callback.message.answer(
        f"✅ Дата выбрана: <b>{date_str}</b>\nТеперь выберите время <b>с какого часа</b> вы хотите записаться:",
        parse_mode="HTML"
    )

    slots_kb = generate_hour_buttons(date_str, tariff)
    await callback.message.answer("🕐 Выберите время начала:", reply_markup=slots_kb)
    await state.set_state(BookingState.time_from)

    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("time_from|"))
async def handle_time_from(callback: CallbackQuery, state: FSMContext):
    _, from_hour = callback.data.split("|")
    from_hour = int(from_hour)

    data = await state.get_data()
    date = data.get("date")

    # Проверяем занятость
    booked_ranges = get_booked_slots(date)
    is_busy = any(int(start) <= from_hour < int(end) for start, end in booked_ranges)

    if is_busy:
        await callback.answer("❌ Это время уже занято! Выберите другое.", show_alert=True)
        return

    await state.update_data(time_from=from_hour)

    # Генерируем кнопки "до какого часа"
    buttons = []
    def getAfter_Hour(from_hour):
        return 23 if from_hour < 22 else 31
        
    for h in range(from_hour + 1, getAfter_Hour(from_hour)):  
        display_h = h if h < 24 else h - 24
        time_str = f"{display_h:02d}:00"
        buttons.append([InlineKeyboardButton(
            text=f"➡️ До {time_str}", callback_data=f"time_to|{h}"
        )])

    if from_hour > 23:
        from_hour -= 24

    text_msg = await callback.message.answer(
        f"🕓 Отлично! Вы начали с <b>{from_hour:02d}:00</b>.\nТеперь выберите <b>до какого</b> часа:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )

    # Сохраняем ID этого сообщения
    await state.update_data(delete_msg_ids=[text_msg.message_id, callback.message.message_id])

    await state.set_state(BookingState.time_to)
    await callback.answer()


# вфцвфц вфцвфц вфцвфц
@router.callback_query(lambda c: c.data.startswith("time_to|"))
async def handle_time_to(callback: CallbackQuery, state: FSMContext):
    _, to_hour = callback.data.split("|")
    to_hour = int(to_hour)

    data = await state.get_data()
    date = data['date']
    from_hour = data['time_from']
    tariff = data['tariff']
    user_id = callback.from_user.id

    # Пытаемся добавить
    success = add_booking(user_id, date, str(from_hour), str(to_hour), tariff)

    # Удалим старые сообщения с часами, если есть
    msg_ids = data.get("delete_msg_ids", [])
    for msg_id in msg_ids:
        try:
            await callback.bot.delete_message(chat_id=callback.from_user.id, message_id=msg_id)
        except:
            pass  # уже удалено или ошибка

    def format_hour(hour: int) -> str:
        return f"{hour % 24:02d}:00"

    if not success:
        await callback.message.answer("❌ Кто-то уже успел занять это время. Попробуйте другой интервал.")
        await state.clear()
        await callback.answer()
        return

    await callback.message.answer(
        f"🎉 Вы успешно записались на <b>{date}</b>\n"
        f"🕐 Время: <b>{format_hour(from_hour)} – {format_hour(to_hour)}</b>\n"
        f"📦 Тариф: <b>{'Почасовой' if tariff == 'hourly' else 'Ночной'}</b>",
        parse_mode="HTML"
    )

    await callback.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"📥 <b>Новая запись</b>\n\n"
            f"👤 Пользователь: @{callback.from_user.username or 'без username'} | <code>{callback.from_user.id}</code>\n"
            f"📅 Дата: <b>{date}</b>\n"
            f"⏰ Время: <b>{format_hour(from_hour)} – {format_hour(to_hour)}</b>\n"
            f"📦 Тариф: <b>{'Почасовой' if tariff == 'hourly' else 'Ночной'}</b>"
        ),
        parse_mode="HTML"
    )

    await state.clear()
    await callback.answer()



@router.callback_query(lambda c: c.data.startswith("confirm_booking|"))
async def confirm_booking(callback: CallbackQuery):
    _, booking_id = callback.data.split("|")
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE bookings SET confirmed = 1 WHERE id = ?", (booking_id,))
    conn.commit()
    conn.close()
    await callback.message.answer("✅ Вы подтвердили свою запись.")
    await callback.answer()


from keyboards.booking_kb import get_booking_status_kb

@router.message(lambda m: m.text == "📅 Мои записи")
async def my_bookings_menu(message: Message):
    await message.answer(
        "📋 <b>Выберите статус записи</b>",
        reply_markup=get_booking_status_kb(),
        parse_mode="HTML"
    )

from datetime import datetime

@router.callback_query(lambda c: c.data.startswith("bookings_"))
async def handle_booking_status(callback: CallbackQuery):
    user_id = callback.from_user.id
    status = callback.data.split("_")[1]

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    now = datetime.now()

    if status == "active":
        cursor.execute("""
            SELECT id, date, time_from, time_to FROM bookings
            WHERE telegram_id = ? AND confirmed >= 0
        """, (user_id,))
        results = cursor.fetchall()
        def format_hour(hour_str):
            return f"{int(hour_str) % 24:02d}:00"
        if not results:
            await callback.message.answer("<b>🟢 Ваши актуальные записи:</b>\n\nПока нет активных записей.", parse_mode="HTML")
        else:
            await callback.message.answer("<b>🟢 Ваши актуальные записи:</b>", parse_mode="HTML")
            for rec in results:
                b_id, date, t_from, t_to = rec
                dt_start = datetime.strptime(f"{date} {int(t_from) % 24:02d}:00", "%Y-%m-%d %H:%M")
                if dt_start > now:
                    text = f"📅 {date} | ⏰ {format_hour(t_from)}–{format_hour(t_to)}"
                    keyboard = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_{b_id}")]
                        ]
                    )
                    await callback.message.answer(text, reply_markup=keyboard)

    elif status == "cancelled":
        cursor.execute("""
            SELECT date, time_from, time_to FROM bookings
            WHERE telegram_id = ? AND confirmed = -1
        """, (user_id,))
        results = cursor.fetchall()
        text = "<b>🔴 Отменённые записи:</b>\n\n"
        text += "\n".join(
            [f"📅 {r[0]} | ⏰ {r[1]}:00–{r[2]}:00" for r in results]
        ) or "Нет отменённых записей."
        await callback.message.answer(text, parse_mode="HTML")

    elif status == "past":
        cursor.execute("""
            SELECT date, time_from, time_to FROM bookings
            WHERE telegram_id = ? AND confirmed = 2
        """, (user_id,))
        results = cursor.fetchall()
        text = "<b>⏳ Прошедшие записи:</b>\n\n"
        text += "\n".join(
            [f"📅 {r[0]} | ⏰ {r[1]}:00–{r[2]}:00" for r in results]
        ) or "Нет прошедших записей."
        await callback.message.answer(text, parse_mode="HTML")

    else:
        await callback.message.answer("Неизвестный статус.")

    conn.close()
    await callback.answer()

@router.message(lambda m: m.text and m.text.startswith("/cancel_"))
async def cancel_booking(message: Message):
    try:
        booking_id = int(message.text.replace("/cancel_", ""))
        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        c.execute("UPDATE bookings SET confirmed = -1 WHERE id = ?", (booking_id,))
        conn.commit()
        conn.close()
        await message.answer("❌ Запись отменена.")
    except:
        await message.answer("Ошибка при отмене.")


@router.callback_query(lambda c: c.data.startswith("user_came|"))
async def mark_user_came(callback: CallbackQuery):
    # Парсинг booking_id
    try:
        _, raw_id = callback.data.split("|", 1)
        booking_id = int(raw_id)
    except Exception:
        await callback.answer("Некорректные данные кнопки.", show_alert=True)
        return

    conn = sqlite3.connect("users.db")
    cur = conn.cursor()

    # Берём юзера и статус attended по записи
    cur.execute("SELECT telegram_id, attended FROM bookings WHERE id = ?", (booking_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        await callback.answer("Запись не найдена.", show_alert=True)
        return

    user_id, attended = row
    if attended:  # уже отмечали — не начисляем повторно
        conn.close()
        await callback.answer("Уже отмечено ранее.")
        return

    # Отмечаем посещение атомарно и переводим в завершённые
    cur.execute(
        "UPDATE bookings SET attended = 1, confirmed = 3 WHERE id = ? AND attended = 0",
        (booking_id,)
    )
    if cur.rowcount == 0:
        conn.close()
        await callback.answer("Уже отмечено ранее.")
        return

    # Начисляем бонус
    bonus = 2
    cur.execute("UPDATE users SET coins = COALESCE(coins,0) + ? WHERE telegram_id = ?", (bonus, user_id))

    # Лог в историю монет
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
        INSERT INTO coin_history (telegram_id, action, amount, description, timestamp)
        VALUES (?, 'attendance', ?, 'Начисление за посещение сеанса', ?)
    """, (user_id, bonus, ts))

    conn.commit()
    conn.close()

    # Обновим сообщение у админа
    try:
        await callback.message.edit_text("✅ Отмечено: пользователь пришёл. Бонус начислён.")
    except Exception:
        await callback.message.answer("✅ Отмечено: пользователь пришёл. Бонус начислён.")

    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("cancel_") and c.data.split("_")[1].isdigit())
async def handle_cancel_booking(callback: CallbackQuery):
    booking_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # Проверим, принадлежит ли бронь пользователю и ещё не отменена
    cursor.execute("""
        SELECT id FROM bookings 
        WHERE id = ? AND telegram_id = ? AND confirmed >= 0
    """, (booking_id, user_id))
    booking = cursor.fetchone()

    if booking:
        cursor.execute("""
            UPDATE bookings SET confirmed = -1 WHERE id = ?
        """, (booking_id,))
        conn.commit()
        await callback.message.edit_text("❌ Запись успешно отменена.")
    else:
        await callback.answer("Эта запись уже отменена или не существует.", show_alert=True)

    conn.close()
    await callback.answer()