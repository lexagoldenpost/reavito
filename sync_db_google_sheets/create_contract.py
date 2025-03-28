from common.logging_config import setup_logger

logger = setup_logger("create_contract")

async def create_contract_handler(update, context):
    """Заглушка для функции просмотра бронирования"""
    logger.info("create_contract handler called")
    await update.message.reply_text("ТЕСТ: Функция просмотра бронирования")
    # Реальная реализация будет добавлена позже