from common.logging_config import setup_logger

logger = setup_logger("edit_booking")

async def edit_booking_handler(update, context):
    """Заглушка для функции просмотра бронирования"""
    logger.info("edit_booking handler called")
    await update.message.reply_text("ТЕСТ: Функция просмотра бронирования")
    # Реальная реализация будет добавлена позже