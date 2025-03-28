from datetime import datetime
from typing import Dict, Any
from common.config import Config
from common.logging_config import setup_logger
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
  Application,
  CommandHandler,
  MessageHandler,
  CallbackQueryHandler,
  filters,
  ConversationHandler,
  ContextTypes,
)

# Настройка логирования
logger = setup_logger("add_booking_bot")

# Константы для состояний разговора
(
  SELECT_SHEET,
  GUEST_NAME,
  BOOKING_DATE,
  CHECK_IN,
  CHECK_OUT,
  NIGHTS,
  MONTHLY_SUM,
  TOTAL_SUM,
  ADVANCE,
  ADDITIONAL_PAYMENT,
  SOURCE,
  EXTRA_CHARGES,
  EXPENSES,
  PAYMENT_METHOD,
  COMMENT,
  PHONE,
  EXTRA_PHONE,
  FLIGHTS,
  CONFIRM,
) = range(19)

# Названия листов в таблице
SHEETS = {
  "HALO Title": "HALO Title",
  "Citygate Р311": "Citygate Р311",
  "Citygate B209": "Citygate B209",
  "Palmetto Karon": "Palmetto Karon",
  "Title Residence": "Title Residence",
}


class BookingBot:
  def __init__(self, token: str, spreadsheet_id: str,
      credentials: Dict[str, Any], allowed_usernames: list):
    self.google_sheet_key = spreadsheet_id
    self.credentials_json = credentials
    self.bot_token = token
    self.allowed_usernames = [u.lower() for u in allowed_usernames]
    self.active_sessions = set()
    logger.info(
      f"BookingBot initialized with {len(self.allowed_usernames)} allowed users")

  async def check_user_permission(self, update: Update) -> bool:
    """Проверяет доступ по username пользователя."""
    user = update.effective_user
    if not user.username:
      logger.warning(f"User {user.id} has no username set")
      await update.message.reply_text(
          "Извините, у вас не установлен username в Telegram.")
      return False

    if user.username.lower() not in self.allowed_usernames:
      logger.warning(
        f"Unauthorized access attempt by {user.username} (ID: {user.id})")
      await update.message.reply_text(
          "Извините, у вас нет доступа к этому боту.")
      return False

    logger.debug(f"User {user.username} authorized successfully")
    return True

  def connect_to_google_sheets(self):
    """Подключается к Google Sheets API."""
    try:
      scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
      ]
      creds = ServiceAccountCredentials.from_json_keyfile_dict(
          self.credentials_json, scope
      )
      client = gspread.authorize(creds)
      logger.info("Successfully connected to Google Sheets API")
      return client.open_by_key(self.google_sheet_key)
    except Exception as e:
      logger.error(f"Error connecting to Google Sheets: {str(e)}")
      raise

  async def start(self, update: Update,
      context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает разговор."""
    user_id = update.effective_user.id
    logger.info(f"Start command received from user ID: {user_id}")

    if user_id in self.active_sessions:
      logger.warning(f"User {user_id} already has an active session")
      await update.message.reply_text(
          "У вас уже есть активная сессия. Закончите текущее бронирование "
          "или нажмите /cancel для отмены."
      )
      return ConversationHandler.END

    if not await self.check_user_permission(update):
      return ConversationHandler.END

    self.active_sessions.add(user_id)
    logger.debug(f"Active sessions: {self.active_sessions}")

    keyboard = [
      [InlineKeyboardButton(sheet, callback_data=sheet)] for sheet in
      SHEETS.values()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Привет! Я помогу добавить новое бронирование.\n"
        "Пожалуйста, выберите лист для добавления:",
        reply_markup=reply_markup,
    )

    return SELECT_SHEET

  async def select_sheet(self, update: Update,
      context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор листа."""
    query = update.callback_query
    await query.answer()

    selected_sheet = query.data
    context.user_data["sheet"] = selected_sheet
    logger.info(f"User {query.from_user.id} selected sheet: {selected_sheet}")

    await query.edit_message_text(
        text=f"Выбран лист: {selected_sheet}\n\nВведите имя гостя:")

    return GUEST_NAME

  async def guest_name(self, update: Update,
      context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод имени гостя."""
    if not await self.check_user_permission(update):
      return ConversationHandler.END

    guest_name = update.message.text
    context.user_data["guest"] = guest_name
    logger.debug(f"Guest name set: {guest_name}")

    await update.message.reply_text("Введите дату бронирования (ДД.ММ.ГГГГ):")
    return BOOKING_DATE

  async def booking_date(self, update: Update,
      context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод даты бронирования."""
    if not await self.check_user_permission(update):
      return ConversationHandler.END

    try:
      date = datetime.strptime(update.message.text, "%d.%m.%Y").date()
      formatted_date = date.strftime("%Y-%m-%d 00:00:00")
      context.user_data["booking_date"] = formatted_date
      logger.debug(f"Booking date set: {formatted_date}")

      await update.message.reply_text("Введите дату заезда (ДД.ММ.ГГГГ):")
      return CHECK_IN
    except ValueError:
      logger.warning(f"Invalid date format received: {update.message.text}")
      await update.message.reply_text(
          "Неверный формат даты. Пожалуйста, введите дату в формате ДД.ММ.ГГГГ:")
      return BOOKING_DATE

  async def check_in(self, update: Update,
      context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод даты заезда."""
    if not await self.check_user_permission(update):
      return ConversationHandler.END

    try:
      date = datetime.strptime(update.message.text, "%d.%m.%Y").date()
      formatted_date = date.strftime("%Y-%m-%d 00:00:00")
      context.user_data["check_in"] = formatted_date
      logger.debug(f"Check-in date set: {formatted_date}")

      await update.message.reply_text("Введите дату выезда (ДД.ММ.ГГГГ):")
      return CHECK_OUT
    except ValueError:
      logger.warning(f"Invalid date format received: {update.message.text}")
      await update.message.reply_text(
          "Неверный формат даты. Пожалуйста, введите дату в формате ДД.ММ.ГГГГ:")
      return CHECK_IN

  async def check_out(self, update: Update,
      context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод даты выезда."""
    if not await self.check_user_permission(update):
      return ConversationHandler.END

    try:
      date = datetime.strptime(update.message.text, "%d.%m.%Y").date()
      formatted_date = date.strftime("%Y-%m-%d 00:00:00")
      context.user_data["check_out"] = formatted_date
      logger.debug(f"Check-out date set: {formatted_date}")

      await update.message.reply_text(
          "Введите количество ночей (например, '10' или '10 (4 + 6)'):")
      return NIGHTS
    except ValueError:
      logger.warning(f"Invalid date format received: {update.message.text}")
      await update.message.reply_text(
          "Неверный формат даты. Пожалуйста, введите дату в формате ДД.ММ.ГГГГ:")
      return CHECK_OUT

  async def nights(self, update: Update,
      context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод количества ночей."""
    if not await self.check_user_permission(update):
      return ConversationHandler.END

    nights = update.message.text
    context.user_data["nights"] = nights
    logger.debug(f"Nights set: {nights}")

    await update.message.reply_text(
        "Введите сумму по месяцам (например, 'Окт 5800 Ноя 11000' или 'Ноя 20170'):")
    return MONTHLY_SUM

  async def monthly_sum(self, update: Update,
      context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод суммы по месяцам."""
    if not await self.check_user_permission(update):
      return ConversationHandler.END

    monthly_sum = update.message.text
    context.user_data["monthly_sum"] = monthly_sum
    logger.debug(f"Monthly sum set: {monthly_sum}")

    await update.message.reply_text("Введите общую сумму в баттах:")
    return TOTAL_SUM

  async def total_sum(self, update: Update,
      context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод общей суммы."""
    if not await self.check_user_permission(update):
      return ConversationHandler.END

    total_sum = update.message.text
    context.user_data["total_sum"] = total_sum
    logger.debug(f"Total sum set: {total_sum}")

    await update.message.reply_text(
        "Введите аванс в баттах/рублях (например, '4350 / 11180' или '5600.0'):")
    return ADVANCE

  async def advance(self, update: Update,
      context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод аванса."""
    if not await self.check_user_permission(update):
      return ConversationHandler.END

    advance = update.message.text
    context.user_data["advance"] = advance
    logger.debug(f"Advance set: {advance}")

    await update.message.reply_text(
        "Введите доплату в баттах/рублях (например, '13450.0' или '14570.0'):")
    return ADDITIONAL_PAYMENT

  async def additional_payment(self, update: Update,
      context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод доплаты."""
    if not await self.check_user_permission(update):
      return ConversationHandler.END

    additional_payment = update.message.text
    context.user_data["additional_payment"] = additional_payment
    logger.debug(f"Additional payment set: {additional_payment}")

    await update.message.reply_text(
        "Введите источник бронирования (например, 'Авито (вотс ап)' или 'Телеграмм'):")
    return SOURCE

  async def source(self, update: Update,
      context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод источника бронирования."""
    if not await self.check_user_permission(update):
      return ConversationHandler.END

    source = update.message.text
    context.user_data["source"] = source
    logger.debug(f"Source set: {source}")

    await update.message.reply_text(
        "Введите дополнительные доплаты (например, 'Поздний выезд после 18:00 +1000 батт' "
        "или 'Свет, вода по счетчику! Уборка.'):"
    )
    return EXTRA_CHARGES

  async def extra_charges(self, update: Update,
      context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод дополнительных доплат."""
    if not await self.check_user_permission(update):
      return ConversationHandler.END

    extra_charges = update.message.text
    context.user_data["extra_charges"] = extra_charges
    logger.debug(f"Extra charges set: {extra_charges}")

    await update.message.reply_text(
        "Введите расходы (например, 'Уборка 1200' или оставьте пустым):")
    return EXPENSES

  async def expenses(self, update: Update,
      context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод расходов."""
    if not await self.check_user_permission(update):
      return ConversationHandler.END

    expenses = update.message.text
    context.user_data["expenses"] = expenses
    logger.debug(f"Expenses set: {expenses}")

    await update.message.reply_text(
        "Введите метод оплаты (например, 'Альфа-Банк' или 'Т-Банк'):")
    return PAYMENT_METHOD

  async def payment_method(self, update: Update,
      context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод метода оплаты."""
    if not await self.check_user_permission(update):
      return ConversationHandler.END

    payment_method = update.message.text
    context.user_data["payment_method"] = payment_method
    logger.debug(f"Payment method set: {payment_method}")

    await update.message.reply_text(
        "Введите комментарий (например, 'Запрашивал трансфер +350 батт. Летит через Китай.' "
        "или оставьте пустым):"
    )
    return COMMENT

  async def comment(self, update: Update,
      context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод комментария."""
    if not await self.check_user_permission(update):
      return ConversationHandler.END

    comment = update.message.text
    context.user_data["comment"] = comment
    logger.debug(f"Comment set: {comment}")

    await update.message.reply_text(
        "Введите основной телефон (например, '89213101406 Вячеслав'):")
    return PHONE

  async def phone(self, update: Update,
      context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод телефона."""
    if not await self.check_user_permission(update):
      return ConversationHandler.END

    phone = update.message.text
    context.user_data["phone"] = phone
    logger.debug(f"Phone set: {phone}")

    await update.message.reply_text(
        "Введите дополнительный телефон (или оставьте пустым):")
    return EXTRA_PHONE

  async def extra_phone(self, update: Update,
      context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод дополнительного телефона."""
    if not await self.check_user_permission(update):
      return ConversationHandler.END

    extra_phone = update.message.text
    context.user_data["extra_phone"] = extra_phone
    logger.debug(f"Extra phone set: {extra_phone}")

    await update.message.reply_text(
        "Введите информацию о рейсах (например, 'S7 6303 Иркутск - Пхукет 20:40' "
        "или оставьте пустым):"
    )
    return FLIGHTS

  async def flights(self, update: Update,
      context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод информации о рейсах и показывает подтверждение."""
    if not await self.check_user_permission(update):
      return ConversationHandler.END

    flights = update.message.text
    context.user_data["flights"] = flights
    logger.debug(f"Flights info set: {flights}")

    # Формируем сообщение с собранными данными
    data = context.user_data
    message = (
      f"Проверьте данные перед сохранением:\n\n"
      f"Лист: {data['sheet']}\n"
      f"Гость: {data['guest']}\n"
      f"Дата бронирования: {data['booking_date']}\n"
      f"Заезд: {data['check_in']}\n"
      f"Выезд: {data['check_out']}\n"
      f"Количество ночей: {data['nights']}\n"
      f"Сумма по месяцам: {data['monthly_sum']}\n"
      f"Общая сумма: {data['total_sum']}\n"
      f"Аванс: {data['advance']}\n"
      f"Доплата: {data['additional_payment']}\n"
      f"Источник: {data['source']}\n"
      f"Доп. доплаты: {data['extra_charges']}\n"
      f"Расходы: {data['expenses']}\n"
      f"Оплата: {data['payment_method']}\n"
      f"Комментарий: {data['comment']}\n"
      f"Телефон: {data['phone']}\n"
      f"Доп. телефон: {data['extra_phone']}\n"
      f"Рейсы: {data['flights']}\n"
    )

    logger.info("All data collected, showing confirmation")

    # Кнопки подтверждения
    keyboard = [
      [
        InlineKeyboardButton("✅ Сохранить", callback_data="save"),
        InlineKeyboardButton("❌ Отменить", callback_data="cancel"),
      ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(message, reply_markup=reply_markup)
    return CONFIRM

  async def save_data(self, update: Update,
      context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет данные в Google Sheets."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if query.data == "cancel":
      if user_id in self.active_sessions:
        self.active_sessions.remove(user_id)
        logger.info(f"User {user_id} canceled the booking")
      await query.edit_message_text(text="❌ Добавление бронирования отменено.")
      return ConversationHandler.END

    try:
      data = context.user_data
      sheet_name = data["sheet"]
      logger.info(f"Attempting to save data to sheet: {sheet_name}")

      gc = self.connect_to_google_sheets()
      worksheet = gc.worksheet(sheet_name)

      # Формируем новую запись (без ID)
      new_record = [
        data["guest"],  # Гость
        data["booking_date"],  # Дата бронирования
        data["check_in"],  # Заезд
        data["check_out"],  # Выезд
        data["nights"],  # Количество ночей
        data["monthly_sum"],  # Сумма по месяцам
        data["total_sum"],  # СуммаБатты
        data["advance"],  # Аванс Батты/Рубли
        data["additional_payment"],  # Доплата Батты/Рубли
        data["source"],  # Источник
        data["extra_charges"],  # Дополнительные доплаты
        data["expenses"],  # Расходы
        data["payment_method"],  # Оплата
        data["comment"],  # Комментарий
        data["phone"],  # телефон
        data["extra_phone"],  # дополнительный телефон
        data["flights"],  # Рейсы
        # ID не добавляем
      ]

      logger.debug(f"New record prepared: {new_record}")

      # Находим место для вставки по дате заезда
      records = worksheet.get_all_records()
      check_in_date = datetime.strptime(data["check_in"], "%Y-%m-%d 00:00:00")
      insert_row = 2  # После заголовка

      for i, record in enumerate(records, start=2):
        record_check_in = datetime.strptime(record["Заезд"],
                                            "%Y-%m-%d 00:00:00")
        if check_in_date < record_check_in:
          insert_row = i
          break
      else:
        insert_row = len(records) + 2

      logger.debug(f"Inserting record at row: {insert_row}")
      worksheet.insert_row(new_record, insert_row)

      if user_id in self.active_sessions:
        self.active_sessions.remove(user_id)
        logger.debug(f"Active sessions after removal: {self.active_sessions}")

      logger.info("Data successfully saved to Google Sheet")
      await query.edit_message_text(
          text="✅ Данные успешно сохранены в таблицу!\n"
               "Нажмите /start чтобы добавить новое бронирование."
      )

    except Exception as e:
      logger.error(f"Error saving data: {str(e)}", exc_info=True)
      if user_id in self.active_sessions:
        self.active_sessions.remove(user_id)
      await query.edit_message_text(
          text="❌ Произошла ошибка при сохранении. Пожалуйста, попробуйте позже."
      )

    return ConversationHandler.END

  async def handle_cancel(self, update: Update,
      context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает команду /cancel."""
    user_id = update.effective_user.id
    if user_id in self.active_sessions:
      self.active_sessions.remove(user_id)
      logger.info(f"User {user_id} canceled the session via /cancel command")

    await update.message.reply_text(
        "❌ Текущее действие отменено. Нажмите /start чтобы начать заново.")
    return ConversationHandler.END

  async def unauthorized_handler(self, update: Update,
      context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает сообщения от неавторизованных пользователей."""
    user = update.effective_user
    logger.warning(
      f"Unauthorized access attempt by user ID: {user.id}, username: {user.username}")
    await update.message.reply_text("Извините, у вас нет доступа к этому боту.")
    return ConversationHandler.END

  def setup_handlers(self, application: Application):
    """Настраивает обработчики для бота."""
    logger.info("Setting up bot handlers")

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", self.start)],
        states={
          SELECT_SHEET: [CallbackQueryHandler(self.select_sheet)],
          GUEST_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.guest_name)],
          BOOKING_DATE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.booking_date)],
          CHECK_IN: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.check_in)],
          CHECK_OUT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.check_out)],
          NIGHTS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.nights)],
          MONTHLY_SUM: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.monthly_sum)],
          TOTAL_SUM: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.total_sum)],
          ADVANCE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.advance)],
          ADDITIONAL_PAYMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                              self.additional_payment)],
          SOURCE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.source)],
          EXTRA_CHARGES: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                         self.extra_charges)],
          EXPENSES: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.expenses)],
          PAYMENT_METHOD: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                          self.payment_method)],
          COMMENT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.comment)],
          PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.phone)],
          EXTRA_PHONE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.extra_phone)],
          FLIGHTS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.flights)],
          CONFIRM: [CallbackQueryHandler(self.save_data)],
        },
        fallbacks=[
          CommandHandler("cancel", self.handle_cancel),
          MessageHandler(filters.ALL, self.unauthorized_handler)
        ],
        per_message=False,
        per_chat=True,
        per_user=True
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("cancel", self.handle_cancel))
    logger.info("Handlers setup completed")

  def run(self):
    """Запускает бота."""
    logger.info("Starting the bot")

    # Добавим логирование конфигурации
    logger.debug(f"Bot token: {'set' if self.bot_token else 'not set'}")
    logger.debug(f"Spreadsheet ID: {self.google_sheet_key}")
    logger.debug(f"Allowed usernames: {self.allowed_usernames}")

    application = Application.builder().token(self.bot_token).build()
    self.setup_handlers(application)

    logger.info("Bot is ready and polling for updates")
    print("Бот запущен. Отправьте /start для начала работы")
    application.run_polling()


if __name__ == "__main__":
  # Замените эти значения на свои
  BOT_TOKEN = Config.TELEGRAM_BOOKING_BOT_TOKEN
  SPREADSHEET_ID = Config.SAMPLE_SPREADSHEET_ID
  SERVICE_ACCOUNT_CREDS = Config.SERVICE_ACCOUNT_FILE

  # Получаем список разрешенных пользователей из конфига
  try:
    ALLOWED_USERNAMES = Config.ALLOWED_TELEGRAM_USERNAMES
    logger.info(
      f"Loaded {len(ALLOWED_USERNAMES)} allowed usernames from config")
  except AttributeError as e:
    logger.error(
      "Failed to load ALLOWED_TELEGRAM_USERNAMES from config, using fallback list")
    ALLOWED_USERNAMES = ["polyakov_aleks", "RepoJENNY", "JENNY_Repo"]

  # Проверьте в коде:
  logger.debug(f"Токен бота: {Config.TELEGRAM_BOT_TOKEN}")
  logger.debug(
    f"Разрешенные пользователи: {Config.ALLOWED_TELEGRAM_USERNAMES if hasattr(Config, 'ALLOWED_TELEGRAM_USERNAMES') else 'NOT FOUND'}")

  bot = BookingBot(
      token=BOT_TOKEN,
      spreadsheet_id=SPREADSHEET_ID,
      credentials=SERVICE_ACCOUNT_CREDS,
      allowed_usernames=ALLOWED_USERNAMES
  )
  bot.run()