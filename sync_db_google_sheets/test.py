from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import Update

async def start(update: Update, context):
    await update.message.reply_text('Привет! Я бот.')

async def echo(update: Update, context):
    await update.message.reply_text(update.message.text)

application = Application.builder().token("7563341575:AAHx0_Tf9mVj7t5bEMKxgRyl2X9SmmVmN0k").build()

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

application.run_polling()