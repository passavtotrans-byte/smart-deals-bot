import os
import sqlite3
from datetime import datetime
import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException
import time
def acquire_single_instance_lock():
    import fcntl

    lock_path = "/tmp/telegram_bot.lock"
    lock_file = open(lock_path, "w")

    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("Another instance is already running. Exit.")
        raise SystemExit(0)

    return lock_file

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

bot = telebot.TeleBot(TOKEN, threaded=False)
@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(
        message.chat.id,
        "Привіт! Я Smart Deals Assistant ✅\nОбери дію нижче:",
        reply_markup=main_menu_kb()
    )

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
        types.InlineKeyboardButton("🧪 Почати діагностику", callback_data="slow_pc_start"),
        types.InlineKeyboardButton("🧾 Як проходить діагностика", callback_data="diag_info"),
        types.InlineKeyboardButton("💰 Вартість / оплата", callback_data="pay_info"),
        types.InlineKeyboardButton("🆘 Допомога", callback_data="help"),
    )
    return kb

def back_kb():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("⬅ Назад", callback_data="menu"))
    return kb


# ---------- Handlers ----------
@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    data = call.data

    # ГОЛОВНЕ МЕНЮ (кнопка "Назад")
    if data == "menu":
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            "Обери дію нижче:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=main_menu_kb()
        )
        return

    # 🛠 Почати діагностику
    if data == "slow_pc_start":
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "✅ Ок. Напиши одним повідомленням:\n"
            "1) Що саме повільно (запуск/браузер/все)\n"
            "2) Коли почалось (сьогодні/вчора/тиждень)\n"
            "3) Windows 10/11\n"
            "4) Чи були помилки/сині екрани",
        )
        return

    # 📄 Як проходить діагностика
    if data == "diag_info":
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            "📄 Як проходить діагностика:\n"
            "1) Ти описуєш симптоми\n"
            "2) Я ставлю уточнюючі питання\n"
            "3) Даю кроки перевірки\n"
            "4) Узгоджуємо рішення",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=back_kb()
        )
        return

    # 💳 Вартість / оплата
    if data == "pay_info":
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            "💳 Вартість / оплата:\n"
            "• Спочатку узгоджуємо, що робимо і ціну\n"
            "• Оплата — перед роботою\n"
            "• Якщо онлайн не вирішу — чесно скажу",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=back_kb()
        )
        return

    # 🆘 Допомога
    if data == "help":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "🆘 Напиши /start щоб відкрити меню.")
        return

    # fallback
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

    while True:
        try:
            # long polling
            bot.infinity_polling(
                skip_pending=True,
                timeout=60,
                long_polling_timeout=60,
            )

        except ApiTelegramException as e:
            # 409 = Telegram бачить інший активний getUpdates (інший процес/інстанс)
            if getattr(e, "error_code", None) == 409:
                print("409 conflict (another getUpdates). Sleep 15s and retry...")
                time.sleep(15)
                continue

            # інші помилки Telegram — покажемо і дамо Render перезапустити (або побачимо в логах)
            print("Telegram API error:", e)
            raise

        except Exception as e:
            print("Unexpected error:", e)
            time.sleep(5)
            continue

    


