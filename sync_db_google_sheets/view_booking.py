from common.logging_config import setup_logger

logger = setup_logger("view_booking")

async def view_booking_handler(update, context):
    """Заглушка для функции просмотра бронирования"""
    logger.info("View booking handler called")
    await update.message.reply_text("ТЕСТ: Функция просмотра бронирования")
    # Реальная реализация будет добавлена позже