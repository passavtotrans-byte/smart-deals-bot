import os
from flask import Flask, request
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# =========================
# ENV
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()  # напр. https://your-service.onrender.com
PORT = int(os.getenv("PORT", "10000"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing. Set it in environment variables.")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)

# =========================
# TEXTS (UA для клієнтів)
# =========================
SCREEN_HOME = (
    "👋 <b>Вітаю!</b>\n"
    "Я допоможу швидко пройти діагностику та обрати пакет.\n\n"
    "Обери, що потрібно:"
)

SCREEN_HOW_DIAG = (
    "🧠 <b>Як проходить діагностика</b>\n\n"
    "1) Ти описуєш проблему (коротко)\n"
    "2) Я ставлю уточнювальні питання\n"
    "3) Даю план перевірок / дій\n"
    "4) Якщо треба — підказую, що саме зробити на місці\n\n"
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

# =========================
# KEYBOARDS
# =========================
def kb_main() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🧠 Як проходить діагностика", callback_data="how_it_works"))
    kb.add(InlineKeyboardButton("💰 Вартість / пакети", callback_data="prices"))
    kb.add(InlineKeyboardButton("🆘 Допомога", callback_data="help"))
    return kb

def kb_back() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("↩️ Назад", callback_data="back"))
    return kb

# =========================
# HANDLERS
# =========================
@bot.message_handler(commands=["start"])
def cmd_start(message):
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

    if data == "back":
        bot.edit_message_text(
            text=SCREEN_HOME,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=kb_main()
        )
        bot.answer_callback_query(call.id)
        return

    bot.answer_callback_query(call.id, "Ок")

# =========================
# WEBHOOK (Render)
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
    # чистимо старі вебхуки і ставимо новий
    bot.remove_webhook()
    if not WEBHOOK_URL:
        raise RuntimeError("WEBHOOK_URL is missing. Set it like https://<your-render-domain>")
    bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")

# =========================
# ENTRYPOINT
# =========================
if __name__ == "__main__":
    # Для Render: webhook + Flask
    setup_webhook()
    app.run(host="0.0.0.0", port=PORT)