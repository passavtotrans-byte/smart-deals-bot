import telebot

TOKEN = "8526507861:AAFJCO7KNmQDaGERZPiQegR5k8auPrYShGc"
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(message.chat.id, "Привет! Я запустился ✅ Напиши любой текст.")

@bot.message_handler(func=lambda m: True)
def echo(message):
    bot.send_message(message.chat.id, "Ты написал: " + message.text)

print("Bot is running...")
bot.infinity_polling()


