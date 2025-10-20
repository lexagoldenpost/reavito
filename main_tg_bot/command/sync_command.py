# main_tg_bot/command/sync_command.py

from telegram import Update
from telegram.ext import ContextTypes
from main_tg_bot.google_sheets.sync_manager import GoogleSheetsCSVSync
from common.logging_config import setup_logger

logger = setup_logger("sync_command")


async def sync_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик команды /sync_booking — синхронизация Google Таблиц ↔ локальные CSV.
    При первом запуске (нет CSV) — только из Google в CSV.
    В остальных случаях — двусторонняя синхронизация по времени последнего изменения.
    """
    try:
        if not update.message:
            return

        await update.message.reply_text("🔁 Запуск синхронизации данных...")

        # Создаём экземпляр синхронизатора
        sync_manager = GoogleSheetsCSVSync(data_folder='booking_data')

        # Выполняем синхронизацию
        results = sync_manager.sync_all_sheets(direction='google_to_csv')

        # Формируем отчёт
        success_count = sum(results.values())
        total_count = len(results)
        status_lines = [f"{'✅' if ok else '❌'} {sheet}" for sheet, ok in results.items()]

        report = (
            f"✅ Синхронизация завершена!\n"
            f"Успешно: {success_count}/{total_count}\n\n"
            + "\n".join(status_lines)
        )
        await update.message.reply_text(report)

    except Exception as e:
        logger.error(f"Ошибка при синхронизации: {e}", exc_info=True)
        error_msg = f"❌ Ошибка при синхронизации:\n{str(e)[:500]}"  # ограничим длину
        await update.message.reply_text(error_msg)