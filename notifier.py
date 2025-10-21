# notifier.py
import asyncio
import sqlite3
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo  # стандартная библиотека (Py 3.9+)

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv

load_dotenv()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Раз в сколько секунд опрашивать БД
CHECK_INTERVAL_SEC = 60

# Жёстко работаем по МСК (UTC+3 без перехода)
TZ = ZoneInfo("Europe/Moscow")


async def check_bookings_loop(bot: Bot):
    """
    Главный цикл: на каждом тике проверяем:
      - конфликты (автоотмена дублей)
      - наступление точек напоминаний: -24 часа, -1 час
      - автоотмену за 10 минут до начала, если не подтвердили
      - статус прошедших для админа
    Срабатывание — по факту «пересечения точки» между прошлым и текущим тиком.
    """
    if not ADMIN_ID:
        print("[notifier] WARNING: ADMIN_ID не задан в .env")

    # Помним время прошлого прогона, чтобы ловить точное пересечение моментов
    last_tick = datetime.now(tz=TZ) - timedelta(seconds=CHECK_INTERVAL_SEC + 5)

    while True:
        now = datetime.now(tz=TZ)

        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()

        # --- Антиконфликт: если слоты пересекаются по часам, лишний помечаем как отменённый ---
        cursor.execute("""
            SELECT id, telegram_id, date, time_from, time_to
            FROM bookings
            WHERE confirmed >= 0
            ORDER BY date, time_from
        """)
        bookings = cursor.fetchall()

        booked_map: dict[tuple[str, int], int] = {}  # (date_str, hour) -> booking_id

        for b_id, user_id, date_str, t_from, t_to in bookings:
            try:
                h_from = int(t_from)
                h_to = int(t_to)
            except Exception:
                # Непредвиденные данные в БД – пропускаем запись
                continue

            for h in range(h_from, h_to):
                key = (date_str, h)
                if key in booked_map:
                    # Конфликт – отменяем текущую
                    cursor.execute("UPDATE bookings SET confirmed = -1 WHERE id = ?", (b_id,))
                    conn.commit()
                    try:
                        await bot.send_message(
                            user_id,
                            "⚠️ Ваша запись была автоматически отменена, т.к. это время уже занято."
                        )
                    except Exception as e:
                        print(f"[notifier] conflict notify error: {e}")
                    break
                else:
                    booked_map[key] = b_id

        # --- Загружаем записи для напоминаний ---
        cursor.execute("""
            SELECT id, telegram_id, date, time_from, time_to, confirmed, notified_24h, notified_1h
            FROM bookings
            WHERE confirmed >= 0
        """)
        rows = cursor.fetchall()

        for booking_id, user_id, date_str, time_from, time_to, confirmed, notified_24h, notified_1h in rows:
            # Корректно строим момент начала/конца с переносом суток при time_from/to >= 24
            try:
                base_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=TZ)
                h_from = int(time_from)
                h_to = int(time_to)
            except Exception:
                # Если дата/часы битые – пропускаем
                continue

            start_dt = base_date + timedelta(hours=h_from)
            end_dt = base_date + timedelta(hours=h_to)

            # Целевые моменты
            t_24h = start_dt - timedelta(hours=24)
            t_1h = start_dt - timedelta(hours=1)
            t_autocancel = start_dt - timedelta(minutes=10)

            # Для отображения «часы:минуты» в пределах суток
            tf_vis = h_from % 24
            tt_vis = h_to % 24
            date_vis = start_dt.date()  # фактическая дата начала с учётом переноса

            # 1) Ровно за 24 часа (одноразово)
            if confirmed >= 0 and (not notified_24h) and (last_tick < t_24h <= now):
                try:
                    await bot.send_message(
                        user_id,
                        f"📅 До вашей записи осталось 24 часа!\n"
                        f"Дата: {date_vis}, Время: {tf_vis:02d}:00–{tt_vis:02d}:00"
                    )
                    cursor.execute("UPDATE bookings SET notified_24h = 1 WHERE id = ?", (booking_id,))
                    conn.commit()
                except Exception as e:
                    print(f"[notifier] 24h notify error: {e}")

            # 2) За 1 час (одноразово, если ещё ждём подтверждения)
            elif confirmed == 0 and (not notified_1h) and (last_tick < t_1h <= now):
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Я приду", callback_data=f"confirm_booking|{booking_id}")]
                ])
                try:
                    await bot.send_message(
                        user_id,
                        "⏰ Ваша сессия скоро начнётся!\nПодтвердите, что вы придёте.",
                        reply_markup=kb
                    )
                    cursor.execute("UPDATE bookings SET notified_1h = 1 WHERE id = ?", (booking_id,))
                    conn.commit()
                except Exception as e:
                    print(f"[notifier] 1h notify error: {e}")

            # 3) Автоотмена за 10 минут до начала, если пользователь так и не подтвердил
            elif confirmed == 0 and (last_tick < t_autocancel <= now):
                cursor.execute("UPDATE bookings SET confirmed = -1 WHERE id = ?", (booking_id,))
                conn.commit()
                try:
                    await bot.send_message(
                        user_id,
                        "❌ Ваша запись была отменена, так как вы не подтвердили участие за 10 минут до начала."
                    )
                except Exception as e:
                    print(f"[notifier] autocancel notify error: {e}")

        # --- Админу: отмечаем прошедшие (confirmed=1 -> 3), когда слот уже закончился по МСК ---
        cursor.execute("""
            SELECT id, telegram_id, date, time_from, time_to
            FROM bookings
            WHERE confirmed = 1
        """)
        passed = cursor.fetchall()

        for b_id, user_id, date_str, t_from, t_to in passed:
            try:
                base_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=TZ)
                h_to = int(t_to)
                dt_end = base_date + timedelta(hours=h_to)
            except Exception:
                continue

            if dt_end <= now:
                cursor.execute("UPDATE bookings SET confirmed = 3 WHERE id = ?", (b_id,))
                conn.commit()

                try:
                    user = await bot.get_chat(user_id)
                    username = f"@{user.username}" if getattr(user, "username", None) else f"id:{user.id}"
                except Exception:
                    username = f"id:{user_id}"

                tf_vis = int(t_from) % 24
                tt_vis = int(t_to) % 24
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Пришёл", callback_data=f"user_came|{b_id}")]
                ])
                try:
                    if ADMIN_ID:
                        await bot.send_message(
                            chat_id=ADMIN_ID,
                            text=(
                                f"📌 <b>Прошла запись пользователя</b> {username}\n"
                                f"📅 {date_str} ⏰ {tf_vis:02d}:00–{tt_vis:02d}:00\n\n"
                                f"Нажмите, если он <b>пришёл</b> ⬇️"
                            ),
                            reply_markup=kb,
                            parse_mode="HTML"
                        )
                except Exception as e:
                    print(f"[notifier] admin notify error: {e}")

        conn.close()

        # Фиксируем момент тика и спим
        last_tick = now
        await asyncio.sleep(CHECK_INTERVAL_SEC)
