from aiogram import Router
from aiogram.types import Message, FSInputFile
from aiogram.utils.markdown import hbold, hitalic
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import os

from keyboards.user_kb import get_user_keyboard
from keyboards.admin_kb import admin_keyboard
from db import user_exists, add_user, is_user_registered, get_username_by_id, add_referral_bonus
from aiogram.types import CallbackQuery
from dotenv import load_dotenv
from db import set_invited_by

router = Router()

load_dotenv()
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))


@router.message(lambda msg: msg.text and msg.text.startswith("/start"))
async def start_handler(message: Message):
    print(f"[DEBUG] message.text = {message.text}")

    telegram_id = message.from_user.id
    full_name = message.from_user.full_name
    username = message.from_user.username or ""

    inviter_id = None

    # Поддержка формата "/start 123456789" и "/start_123456789"
    if " " in message.text:
        try:
            inviter_id = int(message.text.split(" ", 1)[1])
        except ValueError:
            inviter_id = None
    elif "_" in message.text:
        try:
            inviter_id = int(message.text.split("_", 1)[1])
        except ValueError:
            inviter_id = None

    print(f"[START] Пользователь {telegram_id} запустил бота. Пригласил: {inviter_id}")

    # Приветствие для админа
    if telegram_id == ADMIN_ID:
        await message.answer(
            "👋 <b>Добро пожаловать в админ-панель.</b>",
            reply_markup=admin_keyboard,
            parse_mode="HTML"
        )
        return

    # Проверка: новый ли пользователь
    is_new = not user_exists(telegram_id)
    print(f"[START] Новый пользователь? {'Да' if is_new else 'Нет'}")

    if is_new:
        add_user(telegram_id, full_name, username, inviter_id)
        print(f"[START] Пользователь {telegram_id} добавлен. Пригласивший: {inviter_id}")

        if inviter_id:
            inviter_username = get_username_by_id(inviter_id)
            if inviter_username:
                await message.answer(f"🎉 Вы пришли по приглашению от @{inviter_username}!")
            else:
                await message.answer("🎉 Вы пришли по приглашению!")
    else:
        if inviter_id:
            was_set = set_invited_by(telegram_id, inviter_id)
            print(f"[START] Попытка установить пригласившего: {inviter_id} → {'успешно' if was_set else 'уже был установлен'}")
            if was_set:
                inviter_username = get_username_by_id(inviter_id)
                if inviter_username:
                    await message.answer(f"🎉 Вы пришли по приглашению от @{inviter_username}!")
                else:
                    await message.answer("🎉 Вы пришли по приглашению!")

    registered = is_user_registered(telegram_id)

    # Кнопка "Как работает бот"
    how_it_works_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎧 Как работает бот?", callback_data="how_it_works")]
    ])

    # Приветственное сообщение
    photo = FSInputFile("media/welcome.jpg")
    text = (
        f"{hbold('Добро пожаловать в STRAWBERRY STUDIO!')} 🎶\n\n"
        f"{hitalic('С нами ты сможешь легко записаться на сессии, отслеживать посещения, получать бонусы и многое другое. ')}\n\n"
        f"<code>Пройди регистрацию, чтобы получить доуступ к скидкам, реферальной программе, магазину бонусов и рассылке с новостями!</code>\n\n"
        f"Нажми кнопку ниже, чтобы узнать подробнее 👇"
    )

    await message.answer_photo(
        photo=photo,
        caption=text,
        reply_markup=how_it_works_kb,
        parse_mode="HTML"
    )

    await message.answer("📋 Главное меню:", reply_markup=get_user_keyboard(registered))




@router.callback_query(lambda c: c.data == "how_it_works")
async def how_it_works_handler(callback: CallbackQuery):
    text = (
        "🎧 <b>Как работает бот?</b>\n\n"
        "Этот бот поможет тебе пользоваться музыкальной студией легко и удобно:\n\n"
        "📅 <b>Запись на сессию</b> — выбери тариф и подходящее время, и всё готово!\n"
        "⏰ <b>Напоминания</b> — бот напомнит о записи заранее, чтобы ты не забыл.\n"
        "✅ <b>Подтверждение посещения</b> — за час до записи бот спросит, придёшь ли ты.\n"
        "🍓 <b>Монеты</b> — за каждый пришедший сеанс ты получаешь <b>STRAWBERRY Coin</b>.\n"
        "🛍 <b>Магазин</b> — трать монеты на бонусы и приятные подарки.\n"
        "👥 <b>Реферальная программа</b> — пригласи друзей и получи монеты (до 30)!\n"
        "💬 <b>Чат с админом</b> — задай вопрос или сообщи о проблеме напрямую.\n\n"
        "🚀 Всё просто, быстро и в пару кликов!"
    )

    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()





from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from keyboards.admin_kb import get_user_action_keyboard, get_purchase_action_keyboard
from db import (
    get_user_by_username,
    get_user_bookings,
    get_user_purchases,
    mark_purchase_as_used
)

searched_users = {}

def get_status_choice_keyboard(user_id: int):
    options = [
        ("⭐️ VIP", "VIP"),
        ("🟠 Пропускает записи", "SKIPS"),
        ("🟥 Жалоба", "COMPLAINT"),
        ("🟢 Постоянный", "REGULAR"),
        ("❌ Убрать статус", "")
    ]

    keyboard = [
        [InlineKeyboardButton(text=label, callback_data=f"set_status:{user_id}:{value}")]
        for label, value in options
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@router.message(F.text == "👥 Пользователи")
async def ask_for_username(msg: Message, state: FSMContext):
    await msg.answer("Введите @username пользователя для поиска.")

def normalize_hour(hour):
    hour = int(hour)
    if hour >= 24:
        return f"{hour - 24:02d}:00"
    return f"{hour:02d}:00"




@router.message(F.text.startswith("@"))
async def handle_username_search(msg: Message):
    username = msg.text.strip("@")
    user = get_user_by_username(username)

    if not user:
        await msg.answer("❌ Пользователь не найден.")
        return

    searched_users[msg.from_user.id] = user["telegram_id"]
    status = user.get('status') or '—'

    text = (
        f"👤 <b>{user['full_name']}</b>\n"
        f"🆔 <code>{user['telegram_id']}</code>\n"
        f"📛 Username: @{user['username']}\n"
        f"📞 Телефон: {user.get('phone', '—')}\n"
        f"🎂 Дата рождения: {user.get('birthdate', '—')}\n"
        f"🔢 Возраст: {user.get('age', '—')}\n"
        f"🍓 Монет: {user.get('coins', 0)}\n"
        f"🏷 Статус: {status}"
    )

    await msg.answer(text, reply_markup=get_user_action_keyboard(user["telegram_id"]), parse_mode="HTML")


@router.callback_query(F.data.startswith("user_records:"))
async def show_user_bookings(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    bookings = get_user_bookings(user_id)

    if not bookings:
        await callback.message.answer("📅 У пользователя нет записей.")
        return

    text = "📅 <b>Активные записи:</b>\n\n"
    for b in bookings:
        text += (
            f"🗓 {b['date']} | {normalize_hour(b['time_from'])}–{normalize_hour(b['time_to'])}\n"
            f"📌 Тариф: {b['tariff'].capitalize()}\n"
            f"✅ Подтверждена: {'Да' if b['confirmed'] else 'Нет'}\n\n"
        )

    await callback.message.answer(text, parse_mode="HTML")


@router.callback_query(F.data.startswith("user_purchases:"))
async def show_user_purchases(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    purchases = get_user_purchases(user_id)

    if not purchases:
        await callback.message.answer("🛒 У пользователя нет покупок.")
        return

    for p in purchases:
        status = "✅ Использовано" if p['status'] == 'used' else "🟡 Активно"
        text = (
            f"🛍 <b>{p['name']}</b>\n"
            f"💬 {p['description']}\n"
            f"🆔 Код: <code>{p['code']}</code>\n"
            f"📅 Дата: {p['timestamp']}\n"
            f"📌 Статус: {status}"
        )

        markup = None
        if p['status'] != 'used':
            markup = get_purchase_action_keyboard(p['id'])

        await callback.message.answer(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data.startswith("activate_purchase:"))
async def activate_purchase(callback: CallbackQuery):
    purchase_id = int(callback.data.split(":")[1])
    mark_purchase_as_used(purchase_id)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("✅ Покупка активирована")



import pandas as pd
from io import BytesIO
import sqlite3




def get_export_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👤 Пользователи", callback_data="export_users"),
            InlineKeyboardButton(text="📅 Записи", callback_data="export_bookings")
        ],
        [
            InlineKeyboardButton(text="🛒 Покупки", callback_data="export_purchases"),
            InlineKeyboardButton(text="🍓 История монет", callback_data="export_coin_history")
        ]
    ])

@router.message(F.text == "📤 Экспорт Excel")
async def export_menu(msg: Message):
    await msg.answer("Что вы хотите экспортировать?", reply_markup=get_export_keyboard())


@router.callback_query(F.data.startswith("export_"))
async def export_table(callback: CallbackQuery):
    table = callback.data.replace("export_", "")
    db_path = "users.db"

    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
        conn.close()

        if df.empty:
            await callback.message.answer("❌ Таблица пуста.")
            return

        buffer = BytesIO()
        df.to_excel(buffer, index=False)
        buffer.seek(0)

        from aiogram.types import BufferedInputFile

        file = BufferedInputFile(buffer.read(), filename=f"{table}.xlsx")
        await callback.message.answer_document(
            document=file,
            caption=f"📄 Таблица: {table}"
        )
        await callback.answer()

    except Exception as e:
        await callback.message.answer(f"⚠️ Ошибка экспорта: {e}")





















from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton 

def get_reply_to_user_keyboard(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✉ Ответить", callback_data=f"reply_to_user:{user_id}")]
    ])

# 


class ChatWithAdmin(StatesGroup):
    waiting_user_message = State()
    waiting_admin_reply = State()


# --- Пользователь нажал "Чат с админом"
@router.message(F.text == "💬 Чат с админом")
async def start_chat_with_admin(msg: Message, state: FSMContext):
    now_houer = datetime.now().hour
    if (22 < now_houer < 23) or (now_houer < 11):
        await msg.answer("Сейчас студия закрыта, но мы ответим вам с 11:00 до 22:00 🎧")

    await msg.answer("✍ Напишите сообщение, которое будет отправлено администратору:")
    await state.set_state(ChatWithAdmin.waiting_user_message)


@router.message(ChatWithAdmin.waiting_user_message)
async def handle_user_message(msg: Message, state: FSMContext):
    await state.clear()

    text = (
        f"📩 Новое сообщение от пользователя:\n\n"
        f"<b>{msg.from_user.full_name}</b> (@{msg.from_user.username})\n"
        f"<code>{msg.from_user.id}</code>\n\n"
        f"{msg.text}"
    )

    await msg.answer("✅ Сообщение отправлено администратору.")
    await msg.bot.send_message(
        chat_id=ADMIN_ID,
        text=text,
        reply_markup=get_reply_to_user_keyboard(msg.from_user.id),
        parse_mode="HTML"
    )


# --- Админ нажал "Ответить"
@router.callback_query(F.data.startswith("reply_to_user:"))
async def ask_admin_for_reply(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split(":")[1])
    await state.update_data(reply_to=user_id)
    await callback.message.answer("✍ Введите сообщение, которое хотите отправить пользователю:")
    await state.set_state(ChatWithAdmin.waiting_admin_reply)
    await callback.answer()


# --- Админ ввёл текст — подтверждение
@router.message(ChatWithAdmin.waiting_admin_reply)
async def handle_admin_reply(msg: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("reply_to")

    if not user_id:
        await msg.answer("⚠️ Ошибка: не выбран пользователь.")
        await state.clear()
        return

    await state.update_data(reply_text=msg.text)

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📨 Подтвердить отправку", callback_data="confirm_admin_reply")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_admin_reply")]
    ])

    await msg.answer(
        f"🔔 Вы уверены, что хотите отправить пользователю сообщение:\n\n{msg.text}",
        reply_markup=markup
    )


# --- Подтверждение отправки
@router.callback_query(F.data == "confirm_admin_reply")
async def confirm_admin_reply(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("reply_to")
    reply_text = data.get("reply_text")

    if not user_id or not reply_text:
        await callback.message.answer("⚠️ Ошибка при подтверждении.")
        await state.clear()
        return

    try:
        await callback.bot.send_message(
            chat_id=user_id,
            text=f"📬 Сообщение от администратора:\n\n{reply_text}"
        )
        await callback.message.edit_text("✅ Сообщение успешно отправлено пользователю.")
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка при отправке: {e}")

    await state.clear()
    await callback.answer()


# --- Отмена отправки
@router.callback_query(F.data == "cancel_admin_reply")
async def cancel_admin_reply(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Отправка сообщения отменена.")
    await callback.answer()


from aiogram.fsm.state import StatesGroup, State

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from keyboards.register_kb import confirm_kb
from db import add_user_after_register, get_user
from datetime import datetime
import re

class EditUserState(StatesGroup):
    full_name = State()
    birth_date = State()
    phone = State()

class EditProfileState(StatesGroup):
    full_name = State()
    birthday = State()
    phone = State()
    confirm = State()



@router.callback_query(F.data.startswith("user_edit:"))
async def edit_user_start(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split(":")[1])
    print("✅ confirm_edit вызван")
    await state.update_data(user_id=user_id)
    await callback.message.answer("✏️ Введите новое <b>ФИО</b> пользователя:", parse_mode="HTML")
    await state.set_state(EditProfileState.full_name)


@router.message(EditProfileState.full_name)
async def edit_full_name(msg: Message, state: FSMContext):
    text = msg.text.strip()
    parts = text.split()

    if len(parts) < 2 or not all(p.isalpha() for p in parts):
        await msg.answer("❌ Введите <b>Фамилию и Имя</b>, разделяя пробелом.")
        return

    formatted_name = ' '.join(part.capitalize() for part in parts)
    await state.update_data(full_name=formatted_name)
    await msg.answer("📆 Введите <b>дату рождения</b> в формате ДД.ММ.ГГГГ:", parse_mode="HTML")
    await state.set_state(EditProfileState.birthday)


@router.message(EditProfileState.birthday)
async def edit_birthday(msg: Message, state: FSMContext):
    try:
        b_date = datetime.strptime(msg.text.strip(), "%d.%m.%Y")
        today = datetime.today()
        age = today.year - b_date.year - ((today.month, today.day) < (b_date.month, b_date.day))

        if age < 0 or age > 100:
            await msg.answer("❌ Пожалуйста, введите корректную дату рождения.")
            return

        await state.update_data(birth_date=b_date.strftime("%Y-%m-%d"), age=age)
        await msg.answer("📞 Введите <b>номер телефона</b> в формате +7XXXXXXXXXX:", parse_mode="HTML")
        await state.set_state(EditProfileState.phone)

    except ValueError:
        await msg.answer("❌ Неверный формат даты. Введите в формате ДД.ММ.ГГГГ")

def get_confirm_edit_keyboard(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_edit:{user_id}")]
    ])

@router.message(EditProfileState.phone)
async def edit_phone(msg: Message, state: FSMContext):
    phone = msg.text.strip()
    if not re.fullmatch(r"\+7\d{10}", phone):
        await msg.answer("❌ Введите корректный номер телефона в формате +7XXXXXXXXXX")
        return

    await state.update_data(phone=phone)
    data = await state.get_data()

    text = (
        f"<b>Проверьте данные перед сохранением:</b>\n\n"
        f"👤 ФИО: {data['full_name']}\n"
        f"🎂 Дата рождения: {data['birth_date']}\n"
        f"📞 Телефон: {data['phone']}"
    )

    data = await state.get_data()
    user_id = data.get("user_id")
    await msg.answer(text, reply_markup=get_confirm_edit_keyboard(user_id), parse_mode="HTML")
    await state.set_state(EditProfileState.confirm)

def update_user(telegram_id, full_name, birth_date, phone, age, underage):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("""
        UPDATE users SET
            full_name = ?,
            birthdate  = ?,
            phone = ?,
            age = ?,
            underage = ?
        WHERE telegram_id = ?
    """, (full_name, birth_date, phone, age, underage, telegram_id))
    conn.commit()
    conn.close()

@router.callback_query(F.data.startswith("confirm_edit:"))
async def confirm_edit(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split(":")[1])
    data = await state.get_data()

    full_name = data.get("full_name")
    birth_date = data.get("birth_date")
    phone = data.get("phone")
    age = data.get("age")

    if not (full_name and birth_date and phone and age):
        await callback.message.answer("⚠️ Ошибка: неполные данные для обновления.")
        await state.clear()
        await callback.answer()
        return

    underage = int(age < 14)

    update_user(
        telegram_id=user_id,
        full_name=full_name,
        birth_date=birth_date,
        phone=phone,
        age=age,
        underage=underage
    )

    await callback.message.delete()
    await callback.message.answer(
        "✅ Данные успешно обновлены!",
        reply_markup=get_user_action_keyboard(user_id)
    )
    await state.clear()
    await callback.answer()

def get_delete_confirm_keyboard(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete:{user_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete")
        ]
    ])

@router.callback_query(F.data.startswith("user_delete:"))
async def ask_delete_confirmation(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    await callback.message.answer(
        f"❗️Вы уверены, что хотите удалить пользователя с ID <code>{user_id}</code>?",
        reply_markup=get_delete_confirm_keyboard(user_id),
        parse_mode="HTML"
    )
    await callback.answer()

import sqlite3

def delete_user(telegram_id: int):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))
    c.execute("DELETE FROM bookings WHERE telegram_id = ?", (telegram_id,))
    c.execute("DELETE FROM purchases WHERE telegram_id = ?", (telegram_id,))
    c.execute("DELETE FROM coin_history WHERE telegram_id = ?", (telegram_id,))
    conn.commit()
    conn.close()

@router.callback_query(F.data.startswith("confirm_delete:"))
async def confirm_delete_user(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    delete_user(user_id)
    await callback.message.edit_text(f"✅ Пользователь <code>{user_id}</code> был удалён.", parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "cancel_delete")
async def cancel_delete_user(callback: CallbackQuery):
    await callback.message.edit_text("❌ Удаление отменено.")
    await callback.answer()


from db import get_coin_history

@router.callback_query(F.data.startswith("user_coins:"))
async def show_user_coin_history(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    history = get_coin_history(user_id)

    if not history:
        await callback.message.answer("💰 У пользователя нет истории монет.")
        return

    text = "💰 <b>История монет:</b>\n\n"
    for entry in history[:20]:  # ограничим до 20 последних записей
        amount = entry['amount']
        sign = "➕" if amount > 0 else "➖"
        text += (
            f"{sign} <b>{abs(amount)}</b> монет — {entry['description']}\n"
            f"📅 {entry['timestamp']}\n\n"
        )

    await callback.message.answer(text, parse_mode="HTML")


@router.callback_query(F.data.startswith("user_referrals:"))
async def show_user_referrals(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    
    conn = sqlite3.connect("users.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT full_name, username, registration_date
        FROM users
        WHERE invited_by = ?
        ORDER BY registration_date DESC
    """, (user_id,))
    referrals = c.fetchall()
    conn.close()

    if not referrals:
        await callback.message.answer("👥 У пользователя нет приглашённых.")
        return

    text = "👥 <b>Приглашённые пользователи:</b>\n\n"
    for r in referrals:
        username = f"@{r['username']}" if r['username'] else "—"
        reg_date = r['registration_date'] or "—"
        text += f"👤 <b>{r['full_name']}</b> ({username})\n📅 {reg_date}\n\n"

    await callback.message.answer(text.strip(), parse_mode="HTML")

@router.callback_query(F.data.startswith("set_status:"))
async def set_user_status(callback: CallbackQuery):
    _, user_id_str, status_value = callback.data.split(":")
    user_id = int(user_id_str)

    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("UPDATE users SET status = ? WHERE telegram_id = ?", (status_value, user_id))
    conn.commit()
    conn.close()

    display = status_value if status_value else "без статуса"
    await callback.message.answer(f"✅ Статус пользователя обновлён на: <b>{display}</b>", parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("user_status:"))
async def choose_status(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    await callback.message.answer("Выберите новый статус пользователя:", reply_markup=get_status_choice_keyboard(user_id))
    await callback.answer()