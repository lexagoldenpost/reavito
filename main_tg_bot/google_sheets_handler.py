import asyncio
import json

import gspread
from dateutil import parser
from google.oauth2.service_account import Credentials

from common.config import Config
from common.logging_config import setup_logger

logger = setup_logger("google_sheets_handler")


class GoogleSheetsHandler:
  def __init__(self, spreadsheet_id):
    self.scope = [
      "https://www.googleapis.com/auth/spreadsheets",
      "https://www.googleapis.com/auth/drive"
    ]
    self.spreadsheet_id = spreadsheet_id
    self.credentials = None
    self.client = None
    self._initialize_client()

  def _initialize_client(self):
    """Инициализация клиента Google Sheets из переменных окружения"""
    try:
      creds_json = Config.SERVICE_ACCOUNT_FILE
      if not creds_json:
        raise ValueError(
            "GOOGLE_SHEETS_CREDENTIALS environment variable not set")

      if not self.spreadsheet_id:
        raise ValueError("SPREADSHEET_ID environment variable not set")

      creds_dict = json.loads(creds_json)

      self.credentials = Credentials.from_service_account_info(
          creds_dict, scopes=self.scope)
      self.client = gspread.authorize(self.credentials)
      logger.info("Google Sheets client initialized successfully")
    except Exception as e:
      logger.error(f"Error initializing Google Sheets client: {e}")
      raise

  async def save_booking(self, sheet_name, booking_data):
    """Асинхронное сохранение данных в указанный лист с сортировкой по дате заезда"""
    try:
      return await asyncio.get_event_loop().run_in_executor(
          None, self._sync_save_booking, sheet_name, booking_data)
    except Exception as e:
      logger.error(f"Error saving booking to {sheet_name}: {e}")
      return False

  def _parse_date(self, date_str):
    """Парсинг даты в формате ДД.ММ.ГГГГ в datetime объект"""
    try:
      if not date_str:
        return None
      return parser.parse(date_str, dayfirst=True)
    except Exception as e:
      logger.error(f"Error parsing date {date_str}: {e}")
      return None

  def _format_date(self, dt):
    """Форматирование datetime объекта в строку ДД.ММ.ГГГГ"""
    try:
      return dt.strftime("%d.%m.%Y") if dt else ""
    except Exception as e:
      logger.error(f"Error formatting date {dt}: {e}")
      return ""

  def _sync_save_booking(self, sheet_name, booking_data):
    """Синхронное сохранение данных в указанный лист с сортировкой по дате заезда"""
    try:
      logger.info(
          f"Attempting to save booking to spreadsheet {self.spreadsheet_id}, sheet {sheet_name}")

      # Открываем таблицу и лист
      try:
        spreadsheet = self.client.open_by_key(self.spreadsheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        logger.info(f"Successfully opened worksheet {sheet_name}")
      except gspread.SpreadsheetNotFound:
        logger.error(f"Spreadsheet {self.spreadsheet_id} not found")
        return False
      except gspread.WorksheetNotFound:
        logger.error(
            f"Worksheet {sheet_name} not found in spreadsheet {self.spreadsheet_id}")
        return False
      except Exception as e:
        logger.error(f"Error opening worksheet: {e}")
        return False

      # Получаем все данные из листа
      try:
        all_values = worksheet.get_all_values()
        headers = all_values[0] if all_values else []
        logger.info(
          f"Retrieved {len(all_values) - 1 if all_values else 0} existing records")
      except Exception as e:
        logger.error(f"Error retrieving existing records: {e}")
        return False

      # Подготавливаем данные для записи в соответствии с порядком столбцов
      check_in = booking_data.get("check_in", "")
      check_out = booking_data.get("check_out", "")
      booking_date = booking_data.get("booking_date", "")

      # Форматируем даты
      formatted_check_in = self._format_date(
        self._parse_date(check_in)) if check_in else ""
      formatted_check_out = self._format_date(
        self._parse_date(check_out)) if check_out else ""
      formatted_booking_date = self._format_date(
        self._parse_date(booking_date)) if booking_date else ""

      # Подготовка данных (17 столбцов без даты добавления)
      new_row = [
        booking_data.get("guest", ""),  # Гость
        formatted_booking_date,  # Дата бронирования
        formatted_check_in,  # Заезд
        formatted_check_out,  # Выезд
        booking_data.get("nights", ""),  # Количество ночей
        booking_data.get("monthly_sum", ""),  # Сумма по месяцам
        booking_data.get("total_sum", ""),  # СуммаБатты
        booking_data.get("advance", ""),  # Аванс Батты/Рубли
        booking_data.get("additional_payment", ""),  # Доплата Батты/Рубли
        booking_data.get("source", ""),  # Источник
        booking_data.get("extra_charges", ""),  # Дополнительные доплаты
        booking_data.get("expenses", ""),  # Расходы
        booking_data.get("payment_method", ""),  # Оплата
        booking_data.get("comment", ""),  # Комментарий
        booking_data.get("phone", ""),  # телефон
        booking_data.get("extra_phone", ""),  # дополнительный телефон
        booking_data.get("flights", ""),  # Рейсы
        booking_data.get("id", ""),  # ID
      ]

      # Определяем позицию для вставки на основе даты заезда
      try:
        if not formatted_check_in:
          logger.warning("No check_in date provided, appending to the end")
          insert_row = len(all_values) + 1 if all_values else 2
        else:
          # Находим столбец "Заезд" (индекс 2, если считать с 0)
          check_in_col_index = 2

          if len(headers) > check_in_col_index and headers[
            check_in_col_index].lower() == "заезд":
            current_check_in = self._parse_date(formatted_check_in)
            if current_check_in is None:
              logger.warning(
                "Invalid check_in date format, appending to the end")
              insert_row = len(all_values) + 1 if all_values else 2
            else:
              insert_row = 2  # Начинаем с первой строки данных
              for i, row in enumerate(all_values[1:], start=2):
                if len(row) > check_in_col_index:
                  row_date_str = row[check_in_col_index]
                  row_date = self._parse_date(row_date_str)
                  if row_date and current_check_in and row_date > current_check_in:
                    insert_row = i
                    break
                insert_row = i + 1
          else:
            logger.warning(
              "Column 'Заезд' not found at expected position, appending to the end")
            insert_row = len(all_values) + 1 if all_values else 2

        logger.info(f"Determined insert position: row {insert_row}")

        # Вставляем новую строку
        worksheet.insert_row(new_row, index=insert_row)
        logger.info(
            f"Successfully inserted booking at row {insert_row} in sheet {sheet_name}")
        process_google_sheets_to_db()

        return True

      except Exception as e:
        logger.error(f"Error inserting row at position {insert_row}: {e}")
        try:
          # Если вставка по позиции не удалась, пробуем просто добавить в конец
          worksheet.append_row(new_row)
          logger.warning(
              "Insert by position failed, appended to the end instead")
          return True
        except Exception as append_error:
          logger.error(f"Error appending row: {append_error}")
          return False

    except Exception as e:
      logger.error(f"Unexpected error in _sync_save_booking: {e}")
      return False