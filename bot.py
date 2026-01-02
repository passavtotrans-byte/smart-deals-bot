import os
import sqlite3
from datetime import datetime
import telebot
from telebot import types
import time
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

bot = telebot.TeleBot(TOKEN, threaded=False)

# ---------- DB (SQLite) ----------
DB_PATH = "bot.db"

def db_init():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id     INTEGER PRIMARY KEY,
        first_name  TEXT,
        username    TEXT,
        joined_at   TEXT,
        referrer_id INTEGER
    )
    """)

    # додаємо поле bonus_taken, якщо його ще немає
    try:
        cur.execute("ALTER TABLE users ADD COLUMN bonus_taken INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    cur.execute("""
    CREATE TABLE IF NOT EXISTS referrals (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER NOT NULL,
        user_id     INTEGER NOT NULL,
        created_at  TEXT NOT NULL,
        UNIQUE(referrer_id, user_id)
    )
    """)

    conn.commit()
    conn.close()
def upsert_user(u, referrer_id=None):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT referrer_id FROM users WHERE user_id = ?", (u.id,))
    row = cur.fetchone()

    # Якщо користувача ще нема — вставляємо
    if row is None:
        cur.execute("""
            INSERT INTO users(user_id, first_name, username, joined_at, referrer_id)
            VALUES(?,?,?,?,?)
        """, (u.id, u.first_name or "", u.username or "", datetime.utcnow().isoformat(), referrer_id))
    else:
        # Оновлюємо ім’я/юзернейм, але referrer_id НЕ перезаписуємо, якщо вже є
        existing_ref = row[0]
        final_ref = existing_ref if existing_ref is not None else referrer_id
        cur.execute("""
            UPDATE users
            SET first_name=?, username=?, referrer_id=?
            WHERE user_id=?
        """, (u.first_name or "", u.username or "", final_ref, u.id))

    conn.commit()
    conn.close()

def try_add_referral(referrer_id: int, user_id: int):
    """Додає рефералку один раз. Повертає True якщо додали, False якщо не додали."""
    if referrer_id == user_id:
        return False

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Якщо у цього юзера вже є referrer — не чіпаємо (щоб не можна було "переприв'язати")
    cur.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if row is not None and row[0] is not None:
        conn.close()
        return False

    try:
        cur.execute("""
            INSERT OR IGNORE INTO referrals(referrer_id, user_id, created_at)
            VALUES(?,?,?)
        """, (referrer_id, user_id, datetime.utcnow().isoformat()))
        added = (cur.rowcount == 1)

        # Якщо реально додали — зафіксуємо referrer_id у users
        if added:
            cur.execute("UPDATE users SET referrer_id=? WHERE user_id=?", (referrer_id, user_id))

        conn.commit()
        conn.close()
        return added
    except Exception:
        conn.close()
        return False

def count_referrals(referrer_id: int) -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (referrer_id,))
    n = cur.fetchone()[0]
    conn.close()
    return n

def get_referrer(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT referrer_id FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


# ---------- UI helpers ----------
def main_menu_kb():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🔥 Доступні знижки", callback_data="deals"),
        types.InlineKeyboardButton("🎁 Отримати бонус", callback_data="bonus"),
        types.InlineKeyboardButton("👤 Мій профіль", callback_data="profile"),
        types.InlineKeyboardButton("🔗 Мій реферальний лінк", callback_data="reflink"),
        types.InlineKeyboardButton("ℹ️ Допомога", callback_data="help"),
       # ✅ НОВА КНОПКА
    kb.add(types.InlineKeyboardButton("🖥 Повільно працює", callback_data="slow_pc"))    
    )
    return kb

def back_kb():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="menu"))
    return kb


# ---------- Handlers ----------
@bot.message_handler(commands=["start"])
def start(message):
    parts = message.text.split(maxsplit=1)
    ref_payload = parts[1].strip() if len(parts) > 1 else ""

    print("TEXT:", message.text)
    print("PAYLOAD:", ref_payload)

    # ✅ Вхід з Google Sites: ?start=win
    if ref_payload == "win":
        send_windows_entry(message.chat.id)
        return  # ⛔ ВАЖЛИВО: далі код НЕ йде

    # --- стандартний старт ---
    bot.send_message(
        message.chat.id,
        "Привіт! Я Smart Deals Assistant ✅\nОбери дію нижче:",
        reply_markup=main_menu_kb()
    )

    
def slow_pc_kb():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("✅ Почати діагностику", callback_data="slow_pc_start"),
        types.InlineKeyboardButton("🔎 Як проходить діагностика", callback_data="diag_info"),
        types.InlineKeyboardButton("💳 Вартість і оплата", callback_data="pay_info"),
        types.InlineKeyboardButton("⬅️ Назад", callback_data="menu"),
    )
    return kb
@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    data = call.data
    uid = call.from_user.id
    upsert_user(call.from_user)  # оновимо ім'я/username

    if data == "menu":
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            "Обери дію нижче:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=main_menu_kb()
        )

    elif data == "deals":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "🔥 Тут будуть знижки та акції (далі підключимо джерело).", reply_markup=back_kb())
    elif data == "slow_pc":
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        "🖥 Комп’ютер працює повільно.\n\n"
        "Я допоможу зібрати симптоми і зрозуміти:\n"
        "— чи можна вирішити онлайн\n"
        "— чи краще не витрачати час\n\n"
        "Обери дію 👇",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=slow_pc_kb()
    elif data == "diag_info":
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        "🔎 Як проходить діагностика\n\n"
        "1️⃣ Ти коротко описуєш проблему\n"
        "2️⃣ Я уточнюю симптоми\n"
        "3️⃣ Кажу: можна вирішити онлайн чи ні\n"
        "4️⃣ Якщо можна — озвучую вартість\n\n"
        "❗ Я нічого не лагоджу без твоєї згоди.",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=slow_pc_kb()
    )
    elif data == "profile":
        bot.answer_callback_query(call.id)
        refs = count_referrals(uid)
        ref_by = get_referrer(uid)
        ref_by_text = f"{ref_by}" if ref_by else "—"
        bot.send_message(
            call.message.chat.id,
            f"👤 Профіль:\nID: {uid}\nІмʼя: {call.from_user.first_name}\n\n👥 Запросив: {refs}\n🔗 Хто запросив: {ref_by_text}",
            reply_markup=back_kb()
        )

    elif data == "reflink":
        bot.answer_callback_query(call.id)
        me = bot.get_me()
        link = f"https://t.me/{me.username}?start=ref_{uid}"
        bot.send_message(
            call.message.chat.id,
            f"🔗 Твій реферальний лінк:\n{link}\n\nСкопіюй і відправ друзям 😉",
            reply_markup=back_kb()
        )

    elif data == "help":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "ℹ️ Напиши /start щоб відкрити меню.", reply_markup=back_kb())

    else:
        bot.answer_callback_query(call.id, "Невідома дія")

# (Поки що) ігноруємо звичайний текст, щоб бот не спамив ехо
# @bot.message_handler(func=lambda m: True)
#def ignore_text(message):
    # Можна або мовчати, або підказувати /start — як захочеш
#    bot.send_message(message.chat.id, "Напиши /start щоб відкрити меню.")

# -------- Start --------
if __name__ == "__main__":
    db_init()
    print("Bot is running...")

    # ВАЖНО: никаких while True, никаких retry внутри кода.
    # Если будет ошибка (в т.ч. 409) — процесс упадёт, Render сам перезапустит.
    bot.polling(
        none_stop=True,
        skip_pending=True,
        timeout=60,
        long_polling_timeout=60,
        threaded=False
    )


