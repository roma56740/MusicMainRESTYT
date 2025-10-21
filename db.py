import sqlite3

def init_db():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            full_name TEXT DEFAULT '',
            username TEXT DEFAULT '',
            birth_date TEXT DEFAULT '',
            status TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            birthdate TEXT DEFAULT '',
            age INTEGER DEFAULT 0,
            underage INTEGER DEFAULT 0,
            coins INTEGER DEFAULT 0,
            invited_by INTEGER,
            invited_count INTEGER DEFAULT 0,
            is_registered INTEGER DEFAULT 0,
            referrals_count INTEGER DEFAULT 0,
            registration_date TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('referral_bonus', '10')")

    # Таблица магазина
    c.execute("""
        CREATE TABLE IF NOT EXISTS shop_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            price INTEGER
        )
    """)


    # Таблица записей
    c.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            notified_24h INTEGER DEFAULT 0,
            date TEXT,
            notified_1h INTEGER DEFAULT 0,
            time_from TEXT,
            time_to TEXT,
            tariff TEXT,
            confirmed INTEGER DEFAULT 0,
            attended INTEGER DEFAULT 0
        )
    """)

    # История монет
    c.execute("""
        CREATE TABLE IF NOT EXISTS coin_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            action TEXT,
            amount INTEGER,
            description TEXT,
            timestamp TEXT
        )
    """)

    # Покупки пользователя
    c.execute("""
    CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER,
        shop_item_id INTEGER,
        code TEXT,
        status TEXT DEFAULT 'active',
        timestamp TEXT
    )
    """)


    conn.commit()
    conn.close()

DB_NAME = "users.db"  # или путь к БД

def get_referral_bonus() -> int:
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = 'referral_bonus'")
    result = c.fetchone()
    conn.close()
    return int(result[0]) if result else 10  # fallback

def set_referral_bonus(amount: int):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("REPLACE INTO settings (key, value) VALUES ('referral_bonus', ?)", (str(amount),))
    conn.commit()
    conn.close()

def get_username_by_id(user_id: int) -> str | None:
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE telegram_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def get_user_coins(user_id):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT coins FROM users WHERE telegram_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def update_user_coins(user_id, new_amount):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("UPDATE users SET coins = ? WHERE telegram_id = ?", (new_amount, user_id))
    conn.commit()
    conn.close()


def add_referral_bonus(inviter_id: int):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    c.execute("SELECT invited_count FROM users WHERE telegram_id = ?", (inviter_id,))
    row = c.fetchone()
    if row:
        count = row[0]
        bonus = get_referral_bonus()
        if count < 3:
            c.execute("""
                UPDATE users
                SET coins = coins + ?,
                    invited_count = invited_count + 1
                WHERE telegram_id = ?
            """, (bonus, inviter_id))
            conn.commit()
            conn.close()
            return True
    conn.close()
    return False




def get_user_referral_stats(user_id):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT invited_count FROM users WHERE telegram_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def get_user(user_id: int):
    conn = sqlite3.connect("users.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE telegram_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return dict(result) if result else None



def get_referral_count(referrer_id: int) -> int:
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE invited_by = ?", (referrer_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

def user_exists(telegram_id: int) -> bool:
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT 1 FROM users WHERE telegram_id = ?", (telegram_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def add_user(telegram_id, full_name, username, invited_by=None):
    from datetime import datetime
    conn = sqlite3.connect("users.db")
    registration_date = datetime.now().date().isoformat()
    c = conn.cursor()

    c.execute("SELECT 1 FROM users WHERE telegram_id = ?", (telegram_id,))
    if c.fetchone():
        conn.close()
        return

    c.execute("""
        INSERT INTO users (telegram_id, full_name, username, invited_by, registration_date)
        VALUES (?, ?, ?, ?, ?)
    """, (telegram_id, full_name, username, invited_by, registration_date))

    if invited_by and invited_by != telegram_id:
        # Посчитаем уже приглашённых
        c.execute("SELECT invited_count FROM users WHERE telegram_id = ?", (invited_by,))
        row = c.fetchone()
        bonus = get_referral_bonus()
        if row:
            current_count = row[0]
            if current_count < 3:
                c.execute("""
                    UPDATE users
                    SET invited_count = invited_count + 1,
                        coins = coins + ?
                    WHERE telegram_id = ?
                """, (bonus, invited_by))

    conn.commit()
    conn.close()



# Тут
def is_user_registered(telegram_id: int) -> bool:
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT phone FROM users WHERE telegram_id = ?", (telegram_id,))
    result = c.fetchone()
    conn.close()

    if result[0] != '':
        return 1
    else:
        return 0

def get_booked_slots(date: str) -> list[tuple[str, str]]:
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT time_from, time_to FROM bookings WHERE date = ? AND confirmed != -1", (date,))
    result = c.fetchall()
    conn.close()
    return result

def add_booking(telegram_id: int, date: str, time_from: str, time_to: str, tariff: str) -> bool:
    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    # Проверка конфликта
    c.execute("""
        SELECT id, telegram_id FROM bookings
        WHERE date = ? AND confirmed >= 0
        AND NOT (time_to <= ? OR time_from >= ?)
    """, (date, time_from, time_to))
    conflicts = c.fetchall()

    # Если есть конфликт — не добавляем
    if conflicts:
        conn.close()
        return False

    # Добавление новой записи
    c.execute("""
        INSERT INTO bookings (telegram_id, date, time_from, time_to, tariff)
        VALUES (?, ?, ?, ?, ?)
    """, (telegram_id, date, time_from, time_to, tariff))
    conn.commit()
    conn.close()
    return True


def save_user(telegram_id, full_name, birth_date, phone, age, underage):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO users (telegram_id, full_name, birth_date, phone, age, underage)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (telegram_id, full_name, birth_date, phone, age, underage))
    conn.commit()
    conn.close()

def add_or_update_user(telegram_id: int, full_name: str, birthday: str, phone: str, underage: bool):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO users (telegram_id, full_name, birthday, phone, underage)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET
            full_name=excluded.full_name,
            birthday=excluded.birthday,
            phone=excluded.phone,
            underage=excluded.underage
    """, (telegram_id, full_name, birthday, phone, underage))

    conn.commit()
    conn.close()

def get_db_connection():
    return sqlite3.connect(DB_NAME)


def add_user_after_register(telegram_id, full_name, birth_date, phone, age, underage):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("""
        UPDATE users
        SET full_name = ?, birthdate = ?, phone = ?, age = ?, underage = ?, is_registered = 1
        WHERE telegram_id = ?
    """, (full_name, birth_date, phone, age, underage, telegram_id))
    conn.commit()
    conn.close()




def add_referral_reward(referrer_id: int):
    conn = get_db_connection()
    c = conn.cursor()
    # Увеличим монеты и количество рефералов
    bonus = get_referral_bonus()
    c.execute("""
        UPDATE users
        SET coins = coins + ?,
            referrals_count = referrals_count + 1
        WHERE telegram_id = ?
    """, (bonus, referrer_id))
    conn.commit()
    conn.close()


def set_invited_by(telegram_id: int, inviter_id: int):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT invited_by FROM users WHERE telegram_id = ?", (telegram_id,))
    result = c.fetchone()

    if result and result[0] is None and inviter_id != telegram_id:
        c.execute("UPDATE users SET invited_by = ? WHERE telegram_id = ?", (inviter_id, telegram_id))

        # Попробуем начислить бонус
        c.execute("SELECT invited_count FROM users WHERE telegram_id = ?", (inviter_id,))
        row = c.fetchone()
        bonus = get_referral_bonus()
        if row:
            current_count = row[0]
            if current_count < 3:
                c.execute("""
                    UPDATE users
                    SET invited_count = invited_count + 1,
                        coins = coins + ?
                    WHERE telegram_id = ?
                """, (bonus, inviter_id))

        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

import random
import string
from datetime import datetime

def generate_code():
    return f"{''.join(random.choices(string.ascii_uppercase + string.digits, k=5))}-" \
           f"{''.join(random.choices(string.ascii_uppercase + string.digits, k=5))}"

def purchase_item(user_id, item_id):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    # Получим товар
    c.execute("SELECT name, price, description FROM shop_items WHERE id = ?", (item_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False, "❌ Товар не найден."

    name, price, desc = row

    # Проверим монеты
    c.execute("SELECT coins FROM users WHERE telegram_id = ?", (user_id,))
    user_row = c.fetchone()
    if not user_row or user_row[0] < price:
        conn.close()
        return False, "❌ Недостаточно монет."

    # Вычтем монеты
    c.execute("UPDATE users SET coins = coins - ? WHERE telegram_id = ?", (price, user_id))

    # Добавим в покупки
    code = generate_code()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("""
        INSERT INTO purchases (telegram_id, shop_item_id, code, timestamp)
        VALUES (?, ?, ?, ?)
    """, (user_id, item_id, code, timestamp))

    # Добавим в историю
    c.execute("""
        INSERT INTO coin_history (telegram_id, action, amount, description, timestamp)
        VALUES (?, 'purchase', ?, ?, ?)
    """, (user_id, -price, f"Покупка: {name}", timestamp))

    conn.commit()
    conn.close()
    return True, f"✅ Вы купили '{name}' за {price} монет."


def get_coin_history(user_id: int) -> list[dict]:
    conn = sqlite3.connect("users.db")
    conn.row_factory = sqlite3.Row  # Чтобы получить доступ к полям по имени
    c = conn.cursor()

    c.execute("""
        SELECT action, amount, description, timestamp
        FROM coin_history
        WHERE telegram_id = ?
        ORDER BY timestamp DESC
    """, (user_id,))
    
    rows = c.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_active_purchases(user_id: int) -> list[dict]:
    conn = sqlite3.connect("users.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        SELECT p.id, p.shop_item_id, p.code, p.status, p.timestamp, s.name, s.description
        FROM purchases p
        JOIN shop_items s ON p.shop_item_id = s.id
        WHERE p.telegram_id = ? AND p.status = 'active'
        ORDER BY p.timestamp DESC
    """, (user_id,))

    rows = c.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_all_shop_items() -> list[dict]:
    conn = sqlite3.connect("users.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT id, name, description, price FROM shop_items ORDER BY id")
    rows = c.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_user_by_username(username: str) -> dict | None:
    conn = sqlite3.connect("users.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    conn.close()
    return dict(result) if result else None


def get_user_bookings(telegram_id: int) -> list[dict]:
    conn = sqlite3.connect("users.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT * FROM bookings 
        WHERE telegram_id = ? AND confirmed != -1
        ORDER BY date, time_from
    """, (telegram_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_user_purchases(telegram_id: int) -> list[dict]:
    conn = sqlite3.connect("users.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT p.id, p.shop_item_id, p.code, p.status, p.timestamp, s.name, s.description
        FROM purchases p
        JOIN shop_items s ON p.shop_item_id = s.id
        WHERE p.telegram_id = ?
        ORDER BY p.timestamp DESC
    """, (telegram_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def mark_purchase_as_used(purchase_id: int):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("""
        UPDATE purchases
        SET status = 'used'
        WHERE id = ?
    """, (purchase_id,))
    conn.commit()
    conn.close()
