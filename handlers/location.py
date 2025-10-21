from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from keyboards.location_kb import location_kb

router = Router()

@router.message(F.text == "📍 Где мы")
async def location_handler(message: Message):
    # Путь к фотографии
    photo_path = "media/loc.jpg"  # Убедись, что фото есть по этому пути

    # Текст описания
    caption = (
        "<b>📍 Мы находимся здесь!</b>\n\n"
        "STRAWBERRY STUDIO — уютное пространство для творчества и записи.\n"
        "🎶 Заходите на запись, познакомиться или просто вдохновиться атмосферой!"
    )

    # Отправка фото + кнопка с адресом
    photo = FSInputFile(photo_path)
    await message.answer_photo(
        photo=photo,
        caption=caption,
        reply_markup=location_kb(),
        parse_mode="HTML"
    )



from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from datetime import datetime, timedelta, date
from db import get_db_connection
from keyboards.admin_kb import get_record_type_keyboard, get_record_period_keyboard
 



def normalize_hour(hour):
    hour = int(hour)
    if hour >= 24:
        return f"{hour - 24:02d}:00"
    return f"{hour:02d}:00"

@router.message(F.text == "📁 Все записи")
async def all_records_handler(message: Message):
    await message.answer(
        "📂 <b>Выберите тип записей:</b>",
        reply_markup=get_record_type_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("records_"))
async def choose_record_period(callback: CallbackQuery):
    record_type = callback.data.split("_")[1]  # past или future
    await callback.message.edit_text(
        "📆 <b>За какой период вас интересуют записи?</b>",
        reply_markup=get_record_period_keyboard(f"{record_type}"),
        parse_mode="HTML"
    )

@router.callback_query(F.data.regexp(r"^(past|future)_\d+d$"))
async def show_records(callback: CallbackQuery):
    conn = get_db_connection()
    c = conn.cursor()

    _, period = callback.data.split("_")
    days = int(period.replace("d", ""))
    since = datetime.now() - timedelta(days=days)
    today = date.today()

    is_future = callback.data.startswith("future")

    if is_future:
        c.execute("""
            SELECT b.date, b.time_from, b.time_to, b.tariff, b.confirmed, b.attended,
                   u.full_name, u.username
            FROM bookings b
            JOIN users u ON b.telegram_id = u.telegram_id
            WHERE DATE(b.date) >= ? AND b.confirmed != -1
            ORDER BY b.date, b.time_from
        """, (today.isoformat(),))
        label = "будущие"
    else:
        c.execute("""
            SELECT b.date, b.time_from, b.time_to, b.tariff, b.confirmed, b.attended,
                   u.full_name, u.username
            FROM bookings b
            JOIN users u ON b.telegram_id = u.telegram_id
            WHERE DATE(b.date) < ? AND DATE(b.date) >= ? AND b.confirmed != -1
            ORDER BY b.date DESC, b.time_from
        """, (today.isoformat(), (today - timedelta(days=days)).isoformat()))
        label = "прошедшие"

    rows = c.fetchall()
    conn.close()

    if not rows:
        await callback.message.edit_text(f"📂 <b>Нет {label} записей за выбранный период.</b>", parse_mode="HTML")
        return

    text = f"📋 <b>{label.capitalize()} записи за {days} дн.:</b>\n\n"
    for i, (date_, time_from, time_to, tariff, confirmed, attended, full_name, username) in enumerate(rows, start=1):
        # Определяем статус
        if confirmed == 2 or attended == 1:
            status = "🎉 Пройдена"
        elif confirmed == 1:
            status = "✅ Подтверждена"
        elif confirmed == 0:
            if datetime.strptime(date_, "%Y-%m-%d").date() >= today:
                status = "⏳ В ожидании"
            else:
                status = "❌ Отменена"
        else:
            status = "❌ Отменена"

        text += (
            f"<b>{i}. {date_}</b> — <b>{normalize_hour(time_from)}–{normalize_hour(time_to)}</b>\n"
            f"👤 {full_name} (@{username})\n"
            f"🎫 Тариф: {tariff.capitalize()}\n"
            f"📌 Статус: {status}\n\n"
        )

    await callback.message.edit_text(text.strip(), parse_mode="HTML")


from aiogram.fsm.state import StatesGroup, State

class CoinsFSM(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_action = State()
    waiting_for_amount = State()

from aiogram import Router
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from db import get_user_coins, update_user_coins


@router.message(lambda msg: msg.text == "🍓 Монеты")
async def handle_coins_button(message: Message, state: FSMContext):
    await message.answer("Введите Telegram ID пользователя:")
    await state.set_state(CoinsFSM.waiting_for_user_id)

@router.message(CoinsFSM.waiting_for_user_id)
async def process_user_id(message: Message, state: FSMContext):
    try:
        user_id = int(message.text)
        coins = get_user_coins(user_id)
        await state.update_data(user_id=user_id)
        await message.answer(
            f"У пользователя {user_id} сейчас {coins} <b>STRAWBERRY Coin</b>.\n"
            f"Что вы хотите сделать?",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="➕ Увеличить"), KeyboardButton(text="➖ Уменьшить")],
                ],
                resize_keyboard=True
            )
        )
        await state.set_state(CoinsFSM.waiting_for_action)
    except:
        await message.answer("Некорректный ID. Попробуйте снова.")


@router.message(CoinsFSM.waiting_for_action)
async def process_action(message: Message, state: FSMContext):
    action = message.text
    if action not in ("➕ Увеличить", "➖ Уменьшить"):
        await message.answer("Выберите действие с помощью кнопки.")
        return
    await state.update_data(action=action)
    await message.answer("Введите количество коинов:")
    await state.set_state(CoinsFSM.waiting_for_amount)

@router.message(CoinsFSM.waiting_for_amount)
async def process_amount(message: Message, state: FSMContext):
    from keyboards.admin_kb import admin_keyboard
    try:
        amount = int(message.text)
        data = await state.get_data()
        user_id = data["user_id"]
        action = data["action"]
        current = get_user_coins(user_id)
        if action == "➕ Увеличить":
            new = current + amount
        else:
            new = max(0, current - amount)
        update_user_coins(user_id, new)
        await message.answer(
            f"✅ У пользователя {user_id} теперь {new} <b>STRAWBERRY Coin</b>.",
            reply_markup=admin_keyboard
        )
        await state.clear()
    except:
        await message.answer("Ошибка. Введите целое число.")


from aiogram import Router
from aiogram.types import Message, FSInputFile
from dotenv import load_dotenv
import os
    
load_dotenv()
ADMIN_ID = int(os.getenv("ADMIN_ID"))
@router.message(lambda m: m.text == "/db_get")
async def send_db(message: Message):
    db_path = "users.db"
    if not os.path.exists(db_path):
        await message.answer("⚠️ Файл базы данных не найден.")
        return
    
    # Отправляем файл
    db_file = FSInputFile(db_path)
    await message.answer_document(db_file, caption="📂 Актуальная база данных")