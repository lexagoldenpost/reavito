import os
import gspread
from google.oauth2.service_account import Credentials
from common.logging_config import setup_logger
import asyncio
from datetime import datetime
import json
from common.config import Config

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
    """Асинхронное сохранение данных в указанный лист"""
    try:
      return await asyncio.get_event_loop().run_in_executor(
          None, self._sync_save_booking, sheet_name, booking_data)
    except Exception as e:
      logger.error(f"Error saving booking to {sheet_name}: {e}")
      return False

  def _sync_save_booking(self, sheet_name, booking_data):
    """Синхронное сохранение данных в указанный лист"""
    try:
      logger.info(
        f"Saving to spreadsheet {self.spreadsheet_id}, sheet {sheet_name}")

      # Открываем таблицу и лист
      try:
        spreadsheet = self.client.open_by_key(self.spreadsheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
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

      # Подготавливаем данные для записи
      row_data = [
        booking_data.get("guest", ""),
        booking_data.get("booking_date", ""),
        booking_data.get("check_in", ""),
        booking_data.get("check_out", ""),
        booking_data.get("nights", ""),
        booking_data.get("monthly_sum", ""),
        booking_data.get("total_sum", ""),
        booking_data.get("advance", ""),
        booking_data.get("additional_payment", ""),
        booking_data.get("source", ""),
        booking_data.get("extra_charges", ""),
        booking_data.get("expenses", ""),
        booking_data.get("payment_method", ""),
        booking_data.get("comment", ""),
        booking_data.get("phone", ""),
        booking_data.get("extra_phone", ""),
        booking_data.get("flights", ""),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
      ]

      # Добавляем новую строку
      try:
        worksheet.append_row(row_data)
        logger.info(f"Successfully saved booking to sheet {sheet_name}")
        return True
      except Exception as e:
        logger.error(f"Error appending row: {e}")
        return False

    except Exception as e:
      logger.error(f"Error in _sync_save_booking: {e}")
      return False