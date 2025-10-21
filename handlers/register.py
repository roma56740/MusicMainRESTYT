# handlers/register.py

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from keyboards.register_kb import confirm_kb
from db import add_user_after_register, is_user_registered
from datetime import datetime
from keyboards.user_kb import get_user_keyboard
import re

from keyboards.admin_kb import admin_keyboard
router = Router()

class RegisterState(StatesGroup):
    full_name = State()
    birthday = State()
    phone = State()
    confirm = State()

@router.message(F.text == "📝 Регистрация")
async def start_register(message: Message, state: FSMContext):
    if is_user_registered(message.from_user.id):
        await message.answer("✅ Вы уже зарегистрированы.")
        return

    await state.set_state(RegisterState.full_name)
    await message.answer("Введите вашу <b>Фамилию и Имя</b>:", parse_mode="HTML")


@router.message(RegisterState.full_name)
async def get_full_name(message: Message, state: FSMContext):
    text = message.text.strip()
    parts = text.split()

    if len(parts) < 2 or not all(p.isalpha() for p in parts):
        await message.answer("❌ Введите <b>Фамилию и Имя</b>, разделяя пробелом.")
        return

    formatted_name = ' '.join(part.capitalize() for part in parts)
    await state.update_data(full_name=formatted_name)
    await state.set_state(RegisterState.birthday)
    await message.answer("Введите <b>дату рождения</b> в формате ДД.ММ.ГГГГ:", parse_mode="HTML")


import sqlite3

def is_phone_exists(phone: str) -> bool:
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT 1 FROM users WHERE phone = ?", (phone,))
    exists = c.fetchone() is not None
    conn.close()
    return exists

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

@router.message(RegisterState.birthday)
async def get_birthday(message: Message, state: FSMContext):
    try:
        b_date = datetime.strptime(message.text.strip(), "%d.%m.%Y")
        today = datetime.today()
        age = today.year - b_date.year - ((today.month, today.day) < (b_date.month, b_date.day))

        if age < 14:    
            await state.update_data(birth_date=b_date.strftime("%Y-%m-%d"), age=age)
            check_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔎 Проверка у админа", callback_data="underage_check")]
            ])
            await message.answer("❌ Вам ещё нет 14 лет.\nНажмите кнопку ниже, чтобы отправить запрос на проверку администратору.", reply_markup=check_kb)
            return
        if age > 100:
            await message.answer("❌ Пожалуйста, введите корректную дату рождения (максимум 100 лет).")
            return

        await state.update_data(birth_date=b_date.strftime("%Y-%m-%d"), age=age)
        await state.set_state(RegisterState.phone)
        await message.answer("Введите <b>номер телефона</b> в формате +7XXXXXXXXXX:", parse_mode="HTML")

    except ValueError:
        await message.answer("❌ Неверный формат даты. Введите в формате ДД.ММ.ГГГГ")


@router.message(RegisterState.phone)
async def get_phone(message: Message, state: FSMContext):
    phone = message.text.strip()

    if not re.fullmatch(r"\+7\d{10}", phone):
        await message.answer("❌ Введите корректный номер телефона в формате <b>+7XXXXXXXXXX</b>")
        return

    if is_phone_exists(phone):
        await message.answer("❌ Этот номер телефона уже зарегистрирован. Пожалуйста, используйте другой.")
        return

    await state.update_data(phone=phone, user_id=message.from_user.id)  # ← добавили user_id
    data = await state.get_data()

    confirm_text = (
        f"<b>Проверьте введённые данные:</b>\n\n"
        f"👤 ФИО: {data['full_name']}\n"
        f"🎂 Дата рождения: {data['birth_date']}\n"
        f"📞 Телефон: {data['phone']}\n"
    )
    await message.answer(confirm_text, reply_markup=confirm_kb, parse_mode="HTML")
    await state.set_state(RegisterState.confirm)


def update_user(telegram_id, full_name, birth_date, phone, age, underage):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    # Проверка — есть ли такой пользователь
    c.execute("SELECT 1 FROM users WHERE telegram_id = ?", (telegram_id,))
    if not c.fetchone():
        print(f"[!] Пользователь {telegram_id} не найден, создаю...")
        c.execute("""
            INSERT INTO users (telegram_id, full_name, birth_date, phone, age, underage)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (telegram_id, full_name, birth_date, phone, age, underage))
    else:
        print(f"[✓] Обновление пользователя {telegram_id}")
        c.execute("""
            UPDATE users SET
                full_name = ?,
                birth_date = ?,
                phone = ?,
                age = ?,
                underage = ?
            WHERE telegram_id = ?
        """, (full_name, birth_date, phone, age, underage, telegram_id))

    conn.commit()
    print("ROWCOUNT:", c.rowcount)
    conn.close()

@router.callback_query(F.data == "confirm_register")
async def confirm_register(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    telegram_id = callback.from_user.id

    underage = int(data['age'] < 14)
    print(telegram_id, data['full_name'], data['birth_date'], data['phone'], data['age'], underage)
    # Сохраняем в БД



    update_user(
        telegram_id=telegram_id,
        full_name=data['full_name'],
        birth_date=data['birth_date'],
        phone=data['phone'],
        age=data['age'],
        underage=underage
    )

    await callback.message.delete()

    
    if telegram_id == ADMIN_ID:
        await callback.message.answer(
            "✅ Данные аккаунты обновлены!",
            reply_markup=admin_keyboard
        )
    else:
        await callback.message.answer(
            "✅ Данные аккаунты зарегистрированы!",
            reply_markup=get_user_keyboard(registered=True)
        )
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "cancel_register")
async def cancel_register(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("❌ Регистрация отменена.")
    await state.clear()
    await callback.answer()


from dotenv import load_dotenv
import os
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

@router.callback_query(F.data == "underage_check")
async def request_admin_check(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = callback.from_user.id

    approve_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_underage:{user_id}")]
    ])

    await callback.message.edit_text("⏳ Запрос отправлен администратору. Ожидайте ответа.")
    await callback.answer()

    await callback.bot.send_message(
        ADMIN_ID,
        f"👤 Пользователь @{callback.from_user.username or 'без username'} ({user_id}) просит подтвердить, что ему есть 14 лет.\n"
        f"ФИО: {data.get('full_name')}\n"
        f"Дата рождения: {data.get('birth_date')}",
        reply_markup=approve_kb
    )


@router.callback_query(F.data.startswith("approve_underage:"))
async def approve_underage(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split(":")[1])

    await callback.bot.send_message(
        user_id,
        "✅ Администратор подтвердил ваш возраст. Теперь вы можете повторно пройти регистрацию."
    )
    await callback.message.edit_text("✅ Возраст подтверждён. Пользователю отправлено уведомление.")
    await callback.answer()



from keyboards.admin_kb import admin_keyboard

@router.message(F.text == "/restart")
async def restart_command(message: Message, state: FSMContext):
    await state.clear()
    
    if message.from_user.id == ADMIN_ID:
        await message.answer("🔄 Перезапуск...\n\nДобро пожаловать в админ-панель.", reply_markup=admin_keyboard)
    elif is_user_registered(message.from_user.id):
        await message.answer("🔄 Перезапуск...\n\nВот ваше главное меню:", reply_markup=get_user_keyboard(registered=True))
    else:
        await message.answer("🔄 Перезапуск...\n\nПожалуйста, сначала пройдите регистрацию: нажмите кнопку 📝 Регистрация.")