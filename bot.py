import os
from flask import Flask, request
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# =========================
# ENV
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()  # якщо пусто -> polling (Worker)
PORT = int(os.getenv("PORT", "10000"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing. Set it in environment variables.")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)

# Проста памʼять для MVP (не зберігає дані назавжди)
USER_STATE = {}  # user_id -> "awaiting_order"

# =========================
# TEXTS (UA для клієнтів)
# =========================
SCREEN_HOME = (
    "👋 <b>Вітаю!</b>\n"
    "Я — AI-майстер для дистанційної діагностики.\n\n"
    "Обери, що потрібно:"
)

SCREEN_HOW_DIAG = (
    "🧠 <b>Як проходить діагностика</b>\n\n"
    "1) Ти описуєш проблему (коротко)\n"
    "2) Я ставлю уточнювальні питання\n"
    "3) Даю план перевірок / дій\n"
    "4) Якщо треба — підкажу, що саме зробити на місці\n\n"
    "Натисни «Назад», щоб повернутись."
)

SCREEN_PACKAGES = (
    "💰 <b>Вартість / пакети</b>\n\n"
    "✅ <b>Базовий</b> — консультація + план перевірки\n"
    "✅ <b>Стандарт</b> — супровід до результату\n"
    "✅ <b>Преміум</b> — повний супровід + контроль виконання\n\n"
    "Натисни «Назад», щоб повернутись."
)

SCREEN_HELP = (
    "🆘 <b>Допомога</b>\n\n"
    "Як почати:\n"
    "• натисни /start\n"
    "• обери пункт меню\n\n"
    "Якщо кнопки не реагують — напиши просто текстом, що потрібно.\n\n"
    "Натисни «Назад», щоб повернутись."
)

SCREEN_TASK = (
    "✅ <b>Як поставити задачу (швидко і правильно)</b>\n\n"
    "Скопіюй шаблон і заповни:\n\n"
    "<code>ЗАЯВКА:\n"
    "1) Марка/модель/рік (якщо авто) або пристрій\n"
    "2) Симптом (що саме не так)\n"
    "3) Коли зʼявилось / після чого\n"
    "4) Що вже пробував\n"
    "5) Фото/відео/помилки (якщо є)\n"
    "6) Місто/час, коли зручно бути на звʼязку</code>\n\n"
    "Натисни «Назад», щоб повернутись."
)

SCREEN_ORDER = (
    "🟢 <b>Замовити / Оплата</b>\n\n"
    "Працюємо так (MVP, без реквізитів у боті):\n"
    "1) Ти надсилаєш <b>заявку</b> за шаблоном\n"
    "2) Я підтверджую, що можу допомогти, і узгоджую пакет/суму\n"
    "3) <b>Реквізити для оплати</b> надсилаю <b>в особистому повідомленні</b>\n"
    "4) Після оплати — старт діагностики\n\n"
    "Натисни кнопку нижче або просто надішли заявку текстом."
)

ORDER_TEMPLATE = (
    "ЗАЯВКА:\n"
    "1) Марка/модель/рік або пристрій:\n"
    "2) Симптом (що саме не так):\n"
    "3) Коли зʼявилось / після чого:\n"
    "4) Що вже пробував:\n"
    "5) Фото/відео/помилки (якщо є):\n"
    "6) Місто/час для звʼязку:"
)

ACK_ORDER = (
    "✅ <b>Прийняв заявку.</b>\n"
    "Я зараз уточню пару питань і скажу наступний крок.\n\n"
    "Якщо зручно — одразу напиши, який пакет цікавить: "
    "<b>Базовий / Стандарт / Преміум</b>."
)

# =========================
# KEYBOARDS
# =========================
def kb_main() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🧠 Як проходить діагностика", callback_data="how_it_works"))
    kb.add(InlineKeyboardButton("💰 Вартість / пакети", callback_data="prices"))
    kb.add(InlineKeyboardButton("✅ Як поставити задачу", callback_data="task"))
    kb.add(InlineKeyboardButton("🟢 Замовити / Оплата", callback_data="order"))
    kb.add(InlineKeyboardButton("🆘 Допомога", callback_data="help"))
    return kb

def kb_back() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("↩️ Назад", callback_data="back"))
    return kb

def kb_order_actions() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📩 Надіслати заявку (шаблон)", callback_data="order_template"))
    kb.add(InlineKeyboardButton("↩️ Назад", callback_data="back"))
    return kb

# =========================
# HANDLERS
# =========================
@bot.message_handler(commands=["start"])
def cmd_start(message):
    USER_STATE.pop(message.from_user.id, None)
    bot.send_message(message.chat.id, SCREEN_HOME, reply_markup=kb_main())

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    data = (call.data or "").strip()

    if data == "how_it_works":
        bot.edit_message_text(
            text=SCREEN_HOW_DIAG,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=kb_back()
        )
        bot.answer_callback_query(call.id)
        return

    if data == "prices":
        bot.edit_message_text(
            text=SCREEN_PACKAGES,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=kb_back()
        )
        bot.answer_callback_query(call.id)
        return

    if data == "help":
        bot.edit_message_text(
            text=SCREEN_HELP,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=kb_back()
        )
        bot.answer_callback_query(call.id)
        return

    if data == "task":
        bot.edit_message_text(
            text=SCREEN_TASK,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=kb_back()
        )
        bot.answer_callback_query(call.id)
        return

    if data == "order":
        USER_STATE[call.from_user.id] = "awaiting_order"
        bot.edit_message_text(
            text=SCREEN_ORDER,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=kb_order_actions()
        )
        bot.answer_callback_query(call.id)
        return

    if data == "order_template":
        USER_STATE[call.from_user.id] = "awaiting_order"
        bot.send_message(call.message.chat.id, f"<code>{ORDER_TEMPLATE}</code>")
        bot.answer_callback_query(call.id)
        return

    if data == "back":
        USER_STATE.pop(call.from_user.id, None)
        bot.edit_message_text(
            text=SCREEN_HOME,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=kb_main()
        )
        bot.answer_callback_query(call.id)
        return

    bot.answer_callback_query(call.id, "Ок")

@bot.message_handler(func=lambda m: True, content_types=["text"])
def any_text(message):
    # Якщо користувач у режимі "оформлення заявки" — приймаємо будь-який текст як заявку
    state = USER_STATE.get(message.from_user.id)
    text = (message.text or "").strip()

    if text.startswith("/"):
        # інші команди ігноруємо тут
        return

    if state == "awaiting_order":
        USER_STATE.pop(message.from_user.id, None)
        bot.reply_to(message, ACK_ORDER)
        return

    # Якщо не в режимі заявки — відповідаємо нейтрально
    bot.reply_to(
        message,
        "Прийняв 👍\n"
        "Щоб почати — натисни /start або обери пункт меню.\n"
        "Якщо хочеш одразу замовити — натисни «🟢 Замовити / Оплата»."
    )

# =========================
# WEBHOOK (Render Web Service)
# =========================
@app.get("/")
def health():
    return "OK", 200

@app.post("/webhook")
def webhook():
    update = telebot.types.Update.de_json(request.data.decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200

def setup_webhook():
    bot.remove_webhook()
    if not WEBHOOK_URL:
        raise RuntimeError("WEBHOOK_URL is missing. Set it like https://<your-render-domain>")
    bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")

# =========================
# ENTRYPOINT
# =========================
if __name__ == "__main__":
    # Якщо WEBHOOK_URL задано — webhook (Web Service)
    if WEBHOOK_URL:
        setup_webhook()
        app.run(host="0.0.0.0", port=PORT)
    else:
        # Якщо WEBHOOK_URL нема — polling (Background Worker)
        print("Starting bot in polling mode (no WEBHOOK_URL)...")
        bot.remove_webhook()
        bot.infinity_polling(timeout=60, long_polling_timeout=60)