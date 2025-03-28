from common.logging_config import setup_logger

logger = setup_logger("view_dates")

async def view_dates_handler(update, context):
    """Заглушка для функции просмотра бронирования"""
    logger.info("view_dates handler called")
    await update.message.reply_text("ТЕСТ: Функция просмотра бронирования")
    # Реальная реализация будет добавлена позже