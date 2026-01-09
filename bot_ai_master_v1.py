# -*- coding: utf-8 -*-
"""
AI-Майстер — Bot V1 (окремий файл)
Клієнтська мова: Українська
Призначення: дистанційна діагностика/ремонт ПК (через бота як оператора)

ВАЖЛИВО:
- Токен НЕ пишемо в коді.
- Токен береться з Environment Variable: BOT_TOKEN
- На Render це задається в Environment, локально — через PowerShell ($env:BOT_TOKEN="...")
"""

import os
import time
import telebot
from telebot import types

# ======= 0) TOKEN =======
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не заданий. Додай змінну середовища BOT_TOKEN.")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

# ======= 1) RAM-стани V1 (простий FSM) =======
PENDING_DIAG = set()         # user_id очікуємо 1 повідомлення з описом проблеми
CHOSEN_PACKAGE = {}          # user_id -> "STANDARD"/"PRO"/"PRO_WIN"
DIAG_TEXT = {}               # user_id -> текст діагностики від клієнта
HAS_CONSENT = set()          # user_id погодився з політикою/умовами
HAS_ACCESS = set()           # user_id надав техдоступ (поки як статус, без перевірки)
WORK_STARTED = set()         # user_id -> майстер працює


# ======= 2) Тексти екранів (V1) =======

SCREEN_START = (
    "Привіт! Я — AI-Майстер ✅\n\n"
    "Я допомагаю з *діагностикою* та *ремонтом* ПК дистанційно.\n"
    "Ти нічого «не вивчаєш» — я веду крок за кроком.\n\n"
    "Обери дію нижче:"
)

SCREEN_DIAG_REQUEST = (
    "✅ Ок. Напиши ОДНИМ повідомленням:\n"
    "1) Що саме гальмує (запуск/браузер/все)\n"
    "2) Коли почалось (сьогодні/вчора/тиждень)\n"
    "3) Windows 10/11\n"
    "4) Чи були помилки/сині екрани\n\n"
    "Приклад:\n"
    "1) все\n"
    "2) тиждень\n"
    "3) 11\n"
    "4) ні\n"
    "Опис: при запуску екран блимає 3-4 рази, копіювання з затримкою."
)

SCREEN_DIAG_RESULT_TEMPLATE = (
    "✅ AI-діагностика завершена.\n\n"
    "🔎 Попередній висновок:\n{summary}\n\n"
    "Щоб перейти до ремонту — обери пакет нижче."
)

SCREEN_CONSENT_SHORT = (
    "🔐 Умови та конфіденційність (коротко)\n\n"
    "• Я працюю тільки для ремонту/діагностики.\n"
    "• Не збираю паролі/банківські дані, не читаю особисті чати.\n"
    "• Можу бачити тільки те, що ти показуєш під час сесії.\n"
    "• Логи/техдані потрібні лише для пошуку причини (можуть містити назви програм/системні помилки).\n"
    "• Після завершення сесії доступ закривається.\n\n"
    "Натисни «✅ Приймаю умови» щоб продовжити."
)

SCREEN_ACCESS_REQUEST = (
    "✅ Добре.\n\n"
    "Наступний крок — надати технічний доступ, щоб AI-Майстер міг виконати роботу.\n"
    "🔸 Це один раз: ти підтверджуєш, і я роблю все сам.\n\n"
    "Натисни кнопку нижче:"
)

SCREEN_WORKING = (
    "🛠 AI-Майстер працює…\n\n"
    "Статуси:\n"
    "1) Підготовка (перевірка системи)\n"
    "2) Усунення причин лагів\n"
    "3) Контрольний тест\n"
    "4) Фінальний звіт ✅\n\n"
    "Ти можеш просто чекати. Я напишу результат."
)

SCREEN_PAYMENT = (
    "💳 Оплата послуги\n\n"
    "Ви отримали результат роботи AI-Майстра.\n"
    "Для завершення сесії та гарантії підтримки — потрібно підтвердити оплату.\n\n"
    "📌 Без оплати — сесія завершується, доступ закривається автоматично."
)

# ======= 3) Пакети/ціни =======
PACKAGES_TEXT = (
    "📦 Пакети:\n\n"
    "✅ STANDARD — 1000 грн\n"
    "• базове усунення лагів/автозапуск/очистка\n\n"
    "✅ PRO — 1700 грн\n"
    "• глибша діагностика + системні правки + контрольний тест\n\n"
    "✅ PRO + Windows — (PRO + ліцензія Windows)\n"
    "• якщо без перевстановлення/оновлення Windows не вирішити\n"
)

# ======= 4) Клавіатури =======

def kb_main():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🧰 Почати діагностику", callback_data="diag_start"),
        types.InlineKeyboardButton("ℹ️ Як проходить діагностика", callback_data="how_it_works"),
        types.InlineKeyboardButton("💰 Вартість / пакети", callback_data="prices"),
        types.InlineKeyboardButton("🆘 Допомога", callback_data="help"),
    )
    return kb

def kb_back():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("↩️ Назад", callback_data="back"))
    return kb

def kb_packages():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("✅ STANDARD — 1000 грн", callback_data="pkg_STANDARD"),
        types.InlineKeyboardButton("✅ PRO — 1700 грн", callback_data="pkg_PRO"),
        types.InlineKeyboardButton("✅ PRO + Windows", callback_data="pkg_PRO_WIN"),
        types.InlineKeyboardButton("↩️ Назад", callback_data="back"),
    )
    return kb

def kb_consent():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("✅ Приймаю умови", callback_data="consent_yes"),
        types.InlineKeyboardButton("↩️ Назад", callback_data="back"),
    )
    return kb

def kb_access():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🔐 Я надаю доступ", callback_data="access_yes"),
        types.InlineKeyboardButton("↩️ Назад", callback_data="back"),
    )
    return kb

def kb_payment():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("💰 Оплатити пакет", callback_data="pay"),
        types.InlineKeyboardButton("↩️ Назад", callback_data="back"),
    )
    return kb


# ======= 5) Логіка (V1) =======

@bot.message_handler(commands=["start"])
def cmd_start(message):
    bot.send_message(message.chat.id, SCREEN_START, reply_markup=kb_main())

@bot.message_handler(func=lambda m: True)
def on_text(message): 

    raw = (message.text or "").strip()

    # ====== МЕНЮ (ReplyKeyboard) ======
    if raw.startswith("🧰") or "Почати діагностику" in raw:
        uid = message.from_user.id
        PENDING_DIAG.add(uid)
        bot.send_message(
            message.chat.id,
            "🧪 Опиши проблему одним повідомленням.\n\n"
            "Наприклад:\n"
            "• гальмує браузер\n"
            "• повільно вмикається ПК\n"
            "• шумить кулер\n\n"
            "Я аналізую і дам висновок 👇"
        )
        return

    if raw.startswith("📘") or "Як проходить діагностика" in raw:
        bot.send_message(
            message.chat.id,
            SCREEN_HOW_DIAG
        )
        return

    if raw.startswith("💰") or "Вартість" in raw:
        bot.send_message(
            message.chat.id,
            SCREEN_PACKAGES
        )
        return

    if raw.startswith("🆘") or "Допомога" in raw:
        bot.send_message(
            message.chat.id,
            "🆘 Напиши /start щоб повернутись у меню"
        )
        return
@bot.callback_query_handler(func=lambda call: True)
def on_cb(call):
    uid = call.from_user.id
    data = call.data



    if data == "back":
        bot.edit_message_text(
    text=SCREEN_START,
    chat_id=call.message.chat.id,
    message_id=call.message.message_id,
    reply_markup=kb_main(),
        )
        return

    if data == "how_it_works":
        text = (
            "🧭 Як проходить діагностика:\n\n"
            "1) Ти описуєш проблему одним повідомленням\n"
            "2) AI робить попередній висновок\n"
            "3) Ти обираєш пакет\n"
            "4) Погоджуєш умови\n"
            "5) Надаєш техдоступ\n"
            "6) AI-Майстер працює та дає результат ✅"
        )
        bot.edit_message_text(call.message.chat.id, call.message.message_id, text, reply_markup=kb_back())
        return

    if data == "prices":
        bot.edit_message_text(call.message.chat.id, call.message.message_id, PACKAGES_TEXT, reply_markup=kb_back())
        return

    if data == "help":
        text = (
            "🆘 Допомога\n\n"
            "• Напиши /start щоб відкрити меню\n"
            "• Якщо кнопки не натискаються — онови чат або повтори /start\n"
        )
        bot.edit_message_text(call.message.chat.id, call.message.message_id, text, reply_markup=kb_back())
        return

    if data == "diag_start":
        PENDING_DIAG.add(uid)
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, SCREEN_DIAG_REQUEST)
        return

    if data.startswith("pkg_"):
        pkg = data.replace("pkg_", "")
        CHOSEN_PACKAGE[uid] = pkg
        bot.edit_message_text(
            call.message.chat.id,
            call.message.message_id,
            SCREEN_CONSENT_SHORT,
            reply_markup=kb_consent(),
        )
        return

    if data == "consent_yes":
        HAS_CONSENT.add(uid)
        bot.edit_message_text(
            call.message.chat.id,
            call.message.message_id,
            SCREEN_ACCESS_REQUEST,
            reply_markup=kb_access(),
        )
        return

    if data == "access_yes":
        HAS_ACCESS.add(uid)
        bot.edit_message_text(
            call.message.chat.id,
            call.message.message_id,
            SCREEN_WORKING,
            reply_markup=kb_back(),
        )
        # Симуляція роботи (V1). У V2 тут буде справжня логіка/агент.
        WORK_STARTED.add(uid)
        bot.send_message(call.message.chat.id, "⏳ Працюю… (V1 тест)")

        time.sleep(2)
        bot.send_message(call.message.chat.id, "✅ Готово. Попередній результат: вимкнули зайвий автозапуск / оптимізували браузер.")

        bot.send_message(call.message.chat.id, SCREEN_PAYMENT, reply_markup=kb_payment())
        return

    if data == "pay":
        bot.answer_callback_query(call.id, "Оплата буде підключена у V2 ✅")
        bot.send_message(call.message.chat.id, "✅ Дякую! У V2 тут буде реальна кнопка оплати.")
        return

    bot.answer_callback_query(call.id, "Невідома дія")


@bot.message_handler(func=lambda m: True)
def on_text(message):
    uid = message.from_user.id
    if uid in PENDING_DIAG:
        PENDING_DIAG.discard(uid)
        DIAG_TEXT[uid] = (message.text or "").strip()

        # V1: дуже простий "висновок"
        raw = DIAG_TEXT[uid].lower()
        if "брауз" in raw or "chrome" in raw:
            summary = "Схоже на проблему з браузером/розширеннями або апаратним прискоренням."
        elif "запуск" in raw or "автозапуск" in raw:
            summary = "Схоже на перевантажений автозапуск або системні служби."
        else:
            summary = "Схоже на навантаження системи (автозапуск/диск/служби)."

        text = SCREEN_DIAG_RESULT_TEMPLATE.format(summary=summary)
        bot.send_message(message.chat.id, text, reply_markup=kb_packages())
        return

    # Якщо користувач пише не в режимі діагностики
    bot.send_message(message.chat.id, "Напиши /start щоб відкрити меню ✅")


if __name__ == "__main__":
    print("AI-Майстер V1 запущено…")
    bot.infinity_polling(timeout=60, long_polling_timeout=60)