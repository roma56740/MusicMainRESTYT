from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from keyboards.social_kb import social_links_kb
from urllib.parse import quote_plus
import os

router = Router()

@router.message(F.text == "🧺 Заказ вещей")
async def order_items_handler(message: Message):
    user_id = message.from_user.id

    # Проверяем регистрацию
    if not is_user_registered(user_id):
        await message.answer(
            "⚠️ <b>Вы ещё не зарегистрированы!</b>\n\n"
            "Чтобы заказать вещи, необходимо пройти регистрацию.\n\n"
            "👉 Нажмите кнопку <b>«📝 Регистрация»</b> в меню и завершите процесс.",
            parse_mode="HTML"
        )
        return

    # Текст для префилла
    prefill = (
        "Здравствуйте! Хочу заказать товар из Strawberry Studio. "
        "Опишите, пожалуйста, варианты и условия. Спасибо!"
    )
    deep_link = f"https://t.me/Strawberryrecords?text={quote_plus(prefill)}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✉️ Написать @Strawberryrecords", url=deep_link)]
    ])

    await message.answer(
        "<b>🧺 Заказ вещей</b>\n\n"
        "Нажмите кнопку ниже, чтобы открыть личный чат с "
        "<a href='https://t.me/Strawberryrecords'>@Strawberryrecords</a>.\n\n"
        "Если текст не подставился автоматически, просто отправьте сообщение вручную:\n\n"
        f"«{prefill}»",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.message(F.text == "📱 Соц. сети")
async def social_handler(message: Message):
    # Путь к изображению
    photo_path = "media/social.jpg"  # Помести файл сюда или измени путь

    # Текст сообщения
    caption = (
        "<b>STRAWBERRY STUDIO 🍓</b>\n\n"
        "🎧 Место, где рождается звук.\n\n"
        "🎙️ Мы создаём музыку, записываем вокал и делаем магию с каждой нотой.\n\n"
        "Подписывайтесь на нас в соцсетях 👇"
    )

    # Загрузка фото и отправка
    photo = FSInputFile(photo_path)
    await message.answer_photo(
        photo=photo,
        caption=caption,
        reply_markup=social_links_kb(),
        parse_mode="HTML"
    )

from db import get_user_coins
from db import is_user_registered
@router.message(lambda msg: msg.text == "🍓 Мои монеты")
async def my_coins_handler(message: Message):
    user_id = message.from_user.id

    if not is_user_registered(user_id):
        await message.answer(
            "<b>⚠️ Вы ещё не зарегистрированы!</b>\n\n"
            "Чтобы получить доступ к <b>STRAWBERRY Coin</b> и другим функциям, пожалуйста, пройдите регистрацию.",
            parse_mode="HTML"
        )
        return

    coins = get_user_coins(user_id)
    await message.answer(f"💰 У вас {coins} <b>STRAWBERRY Coin</b> 🍓")



from aiogram import Router, types
from aiogram.types import CallbackQuery, Message
from datetime import datetime, timedelta
from keyboards.admin_kb import get_statistics_period_keyboard
from db import get_db_connection

@router.message(lambda m: m.text == "📊 Статистика")
async def statistics_entry(message: Message):
    await message.answer(
        "📈 <b>За какой период вы хотите посмотреть статистику?</b>",
        reply_markup=get_statistics_period_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(lambda c: c.data.startswith("stats_"))
async def show_statistics(callback: CallbackQuery):
    from datetime import datetime, timedelta, date
    period_map = {
        "stats_1d": ("1 день", 1),
        "stats_7d": ("7 дней", 7),
        "stats_30d": ("30 дней", 30)
    }

    label, days = period_map.get(callback.data, ("Неизвестно", 1))
    since = (datetime.now() - timedelta(days=days)).date()
    today = date.today()

    conn = get_db_connection()
    c = conn.cursor()

    # Новые пользователи
    c.execute("SELECT COUNT(*) FROM users WHERE is_registered = 1 AND DATE(registration_date) >= ?", (since,))
    new_users = c.fetchone()[0]

    # Все записи
    c.execute("SELECT COUNT(*) FROM bookings WHERE DATE(date) >= ?", (since,))
    total_bookings = c.fetchone()[0]

    # Отменено
    c.execute("SELECT COUNT(*) FROM bookings WHERE confirmed = 0 AND DATE(date) < ? AND DATE(date) >= ?", (today, since))
    canceled = c.fetchone()[0]

    # В ожидании
    c.execute("SELECT COUNT(*) FROM bookings WHERE confirmed = 0 AND DATE(date) >= ? AND DATE(date) >= ?", (today, since))
    pending = c.fetchone()[0]

    bought = 0  # пока нет логики покупок

    conn.close()

    text = (
        f"📊 <b>Статистика за последние {label}:</b>\n\n"
        f"👤 <b>Новых пользователей:</b> {new_users}\n"
        f"🎟 <b>Всего записей:</b> {total_bookings}\n"  
        f"🛒 <b>Куплено товаров:</b> {bought}"
    )

    await callback.message.edit_text(text, parse_mode="HTML")



from aiogram import Router, types
from aiogram.types import Message, CallbackQuery
from keyboards.admin_kb import get_shop_management_keyboard
 

@router.message(lambda m: m.text == "🛍️ Магазин")
async def open_shop_settings(message: Message):
    await message.answer(
        "<b>🛍️ Настройки магазина</b>\n\n"
        "Выберите, что вы хотите сделать:",
        reply_markup=get_shop_management_keyboard(),
        parse_mode="HTML"
    )


from aiogram.fsm.context import FSMContext
from fsm.shop_states import ShopCreate, ShopEdit
from db import get_db_connection

@router.callback_query(lambda c: c.data == "shop_create")
async def start_shop_create(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📝 Введите <b>название товара</b>:", parse_mode="HTML")
    await state.set_state(ShopCreate.waiting_for_name)

@router.message(ShopCreate.waiting_for_name)
async def shop_set_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("✏️ Теперь введите <b>описание товара</b>:", parse_mode="HTML")
    await state.set_state(ShopCreate.waiting_for_description)

@router.message(ShopCreate.waiting_for_description)
async def shop_set_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("💰 Введите <b>стоимость товара</b> в <b>STRAWBERRY Coin</b> (только число):", parse_mode="HTML")
    await state.set_state(ShopCreate.waiting_for_price)

@router.message(ShopCreate.waiting_for_price)
async def shop_set_price(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❗ Введите корректное число.")
        return

    await state.update_data(price=int(message.text))
    data = await state.get_data()

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO shop_items (name, description, price) VALUES (?, ?, ?)", (
        data["name"], data["description"], data["price"]
    ))
    conn.commit()
    conn.close()

    await message.answer(
        f"✅ Товар <b>«{data['name']}»</b> успешно добавлен!\n"
        f"💰 Стоимость: {data['price']} <b>STRAWBERRY Coin</b>",
        parse_mode="HTML"
    )
    await state.clear()


@router.callback_query(lambda c: c.data == "shop_view")
async def show_shop_items(callback: CallbackQuery):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, description, price FROM shop_items")
    items = c.fetchall()
    conn.close()

    if not items:
        await callback.message.edit_text("📦 В магазине пока нет товаров.")
        return

    text = "<b>📦 Список товаров:</b>\n\n"
    for i, (item_id, name, description, price) in enumerate(items, start=1):
        text += (
            f"{i}. 🎁 <b>{name}</b>\n"
            f"   💬 {description}\n"
            f"   💰 <b>{price} STRAWBERRY Coin</b>\n\n"
        )

    await callback.message.edit_text(text.strip(), parse_mode="HTML")


from html import escape as quote_html
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_delete_item_keyboard(items):
    keyboard = []
    for item_id, name in items:
        button = InlineKeyboardButton(text=f"❌ {name}", callback_data=f"delete_item_{item_id}")
        keyboard.append([button])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@router.callback_query(lambda c: c.data == "shop_delete")
async def choose_item_to_delete(callback: CallbackQuery):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name FROM shop_items")
    items = c.fetchall()
    conn.close()

    if not items:
        await callback.message.edit_text("📦 В магазине пока нет товаров для удаления.")
        return

    await callback.message.edit_text(
        "❌ <b>Выберите товар, который хотите удалить:</b>",
        reply_markup=get_delete_item_keyboard(items),
        parse_mode="HTML"
    )

@router.callback_query(lambda c: c.data.startswith("delete_item_"))
async def delete_item(callback: CallbackQuery):
    item_id = int(callback.data.split("_")[2])

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT name FROM shop_items WHERE id = ?", (item_id,))
    row = c.fetchone()

    if row:
        name = row[0]
        c.execute("DELETE FROM shop_items WHERE id = ?", (item_id,))
        conn.commit()
        await callback.message.edit_text(f"❌ Товар <b>«{quote_html(name)}»</b> удалён из магазина.", parse_mode="HTML")
    else:
        await callback.message.edit_text("⚠️ Товар не найден.")
    conn.close()


@router.callback_query(lambda c: c.data == "shop_edit")
async def choose_item_to_edit(callback: CallbackQuery, state: FSMContext):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name FROM shop_items")
    items = c.fetchall()
    conn.close()

    if not items:
        await callback.message.edit_text("📦 В магазине пока нет товаров для редактирования.")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✏️ {name}", callback_data=f"edit_item_{item_id}")]
        for item_id, name in items
    ])

    await callback.message.edit_text(
        "✏️ <b>Выберите товар для редактирования:</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(lambda c: c.data.startswith("edit_item_"))
async def start_edit_item(callback: CallbackQuery, state: FSMContext):
    item_id = int(callback.data.split("_")[2])
    await state.update_data(item_id=item_id)
    await callback.message.edit_text("📝 Введите <b>новое название</b> или отправьте «Пропустить»", parse_mode="HTML")
    await state.set_state(ShopEdit.editing_name)


@router.message(ShopEdit.editing_name)
async def edit_name(message: Message, state: FSMContext):
    data = await state.get_data()
    if message.text.lower() != "пропустить":
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE shop_items SET name = ? WHERE id = ?", (message.text, data['item_id']))
        conn.commit()
        conn.close()
    await message.answer("💬 Введите <b>новое описание</b> или отправьте «Пропустить»", parse_mode="HTML")
    await state.set_state(ShopEdit.editing_description)

@router.message(ShopEdit.editing_description)
async def edit_description(message: Message, state: FSMContext):
    data = await state.get_data()
    if message.text.lower() != "пропустить":
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE shop_items SET description = ? WHERE id = ?", (message.text, data['item_id']))
        conn.commit()
        conn.close()
    await message.answer("💰 Введите <b>новую цену</b> или отправьте «Пропустить»", parse_mode="HTML")
    await state.set_state(ShopEdit.editing_price)

@router.message(ShopEdit.editing_price)
async def edit_price(message: Message, state: FSMContext):
    data = await state.get_data()
    if message.text.lower() != "пропустить":
        if not message.text.isdigit():
            await message.answer("❗ Пожалуйста, введите число или отправьте «Пропустить».")
            return
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE shop_items SET price = ? WHERE id = ?", (int(message.text), data['item_id']))
        conn.commit()
        conn.close()

    await message.answer("✅ Товар успешно обновлён!", parse_mode="HTML")
    await state.clear()
