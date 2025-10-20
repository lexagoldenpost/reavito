# sync_manager.py
import os
import json
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import hashlib
import uuid
from typing import Dict, List

from common.config import Config
from common.logging_config import setup_logger

logger = setup_logger("sync_manager")


class GoogleSheetsCSVSync:
    def __init__(self, data_folder: str = 'data'):
        self.data_folder = data_folder
        self.scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]

        os.makedirs(self.data_folder, exist_ok=True)

        self.sheets_config = {
            Config.BOOKING_SPREADSHEET_ID: {
                'HALO Title': 'halo_title.csv',
                'Citygate Р311': 'citygate_p311.csv',
                'Citygate B209': 'citygate_b209.csv',
                'Palmetto Karon': 'palmetto_karon.csv',
                'Title Residence': 'title_residence.csv',
                'Halo JU701 двушка': 'halo_ju701.csv',
            },
            Config.BOOKING_TASK_SPREADSHEET_ID: {
                'Задачи': 'tasks.csv',
                'Отправка бронирований': 'channels.csv',
                'Поиск в чатах': 'search_channels.csv'
            }
        }

        self.clients = {}
        self._initialize_clients()

    def _initialize_clients(self):
        try:
            creds_json = Config.SERVICE_ACCOUNT_FILE
            if not creds_json:
                raise ValueError("SERVICE_ACCOUNT_FILE not set")

            if os.path.exists(creds_json):
                with open(creds_json, 'r') as f:
                    creds_dict = json.load(f)
            else:
                creds_dict = json.loads(creds_json)

            credentials = Credentials.from_service_account_info(
                creds_dict, scopes=self.scope
            )

            for spreadsheet_id in self.sheets_config.keys():
                if spreadsheet_id:
                    client = gspread.authorize(credentials)
                    self.clients[spreadsheet_id] = client
                    logger.info(f"Google Sheets client initialized for spreadsheet: {spreadsheet_id}")
                else:
                    logger.warning("Empty spreadsheet_id in config")

        except Exception as e:
            logger.error(f"Error initializing Google Sheets clients: {e}")
            raise

    def _get_client_and_sheet_name(self, sheet_name: str):
        for spreadsheet_id, sheets in self.sheets_config.items():
            if sheet_name in sheets:
                return self.clients.get(spreadsheet_id), spreadsheet_id
        return None, None

    def _get_csv_path(self, sheet_name: str) -> str:
        for sheets in self.sheets_config.values():
            if sheet_name in sheets:
                return os.path.join(self.data_folder, sheets[sheet_name])
        raise ValueError(f"Unknown sheet name: {sheet_name}")

    def _ensure_sync_id(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        if '_sync_id' not in df.columns:
            df['_sync_id'] = [str(uuid.uuid4()) for _ in range(len(df))]
        else:
            def fill_empty(x):
                if pd.isna(x) or (isinstance(x, str) and x.strip() == ''):
                    return str(uuid.uuid4())
                return str(x)

            df['_sync_id'] = df['_sync_id'].apply(fill_empty)
        return df

    def _generate_row_hash(self, row: pd.Series) -> str:
        exclude = {'_sync_id', '_hash', '_sheet_name', '_last_sync'}
        cols = sorted([c for c in row.index if c not in exclude])
        parts = []
        for c in cols:
            val = row[c]
            if pd.notna(val) and str(val).strip() != '':
                parts.append(f"{c}:{str(val).strip()}")
        return hashlib.md5('|'.join(parts).encode('utf-8')).hexdigest()

    def load_local_csv(self, sheet_name: str) -> pd.DataFrame:
        csv_file = self._get_csv_path(sheet_name)
        if not os.path.exists(csv_file):
            return pd.DataFrame()

        try:
            df = pd.read_csv(csv_file, dtype=str)
            df = df.fillna('')
            df = self._ensure_sync_id(df)
            df['_sheet_name'] = sheet_name
            df['_last_sync'] = datetime.now().isoformat()
            df['_hash'] = df.apply(self._generate_row_hash, axis=1)
            logger.info(f"Loaded {len(df)} rows from local CSV: {csv_file}")
            return df
        except Exception as e:
            logger.error(f"Error loading local CSV {csv_file}: {e}")
            return pd.DataFrame()

    def save_local_csv(self, df: pd.DataFrame, sheet_name: str):
        csv_file = self._get_csv_path(sheet_name)
        try:
            save_df = df.drop(columns=['_hash', '_sheet_name', '_last_sync'], errors='ignore')
            save_df.to_csv(csv_file, index=False, encoding='utf-8')
            logger.info(f"Saved {len(save_df)} rows to local CSV: {csv_file}")
        except Exception as e:
            logger.error(f"Error saving to local CSV {csv_file}: {e}")

    def download_sheet(self, sheet_name: str) -> pd.DataFrame:
        try:
            client, spreadsheet_id = self._get_client_and_sheet_name(sheet_name)
            if not client or not spreadsheet_id:
                logger.error(f"No client found for sheet: {sheet_name}")
                return pd.DataFrame()

            spreadsheet = client.open_by_key(spreadsheet_id)
            worksheet = spreadsheet.worksheet(sheet_name)
            values = worksheet.get_all_values()

            if not values:
                return pd.DataFrame()

            headers = values[0]
            data = values[1:] if len(values) > 1 else []

            for i, row in enumerate(data):
                if len(row) < len(headers):
                    data[i] = row + [''] * (len(headers) - len(row))
                elif len(row) > len(headers):
                    data[i] = row[:len(headers)]

            df = pd.DataFrame(data, columns=headers)
            df = df.fillna('')
            df = self._ensure_sync_id(df)
            df['_sheet_name'] = sheet_name
            df['_last_sync'] = datetime.now().isoformat()
            df['_hash'] = df.apply(self._generate_row_hash, axis=1)

            logger.info(f"Downloaded {len(df)} rows from sheet: {sheet_name}")
            return df

        except Exception as e:
            logger.error(f"Error downloading sheet {sheet_name}: {e}")
            return pd.DataFrame()

    def update_google_sheet(self, sheet_name: str, df: pd.DataFrame) -> bool:
        try:
            if df.empty:
                logger.warning(f"No data to push to Google Sheet: {sheet_name}")
                return False

            client, spreadsheet_id = self._get_client_and_sheet_name(sheet_name)
            if not client or not spreadsheet_id:
                logger.error(f"No client found for sheet: {sheet_name}")
                return False

            spreadsheet = client.open_by_key(spreadsheet_id)
            worksheet = spreadsheet.worksheet(sheet_name)

            save_df = df.drop(columns=['_hash', '_sheet_name', '_last_sync'], errors='ignore')
            values = [save_df.columns.tolist()] + save_df.values.tolist()

            worksheet.clear()
            worksheet.update(values, value_input_option='RAW')

            logger.info(f"Updated Google Sheet '{sheet_name}' with {len(values)} rows")
            return True

        except Exception as e:
            logger.error(f"Error updating Google Sheet {sheet_name}: {e}")
            return False

    def sync_sheet(self, sheet_name: str, direction: str = 'auto') -> bool:
        """
        Синхронизация одного листа.

        Направления:
          - 'auto': если CSV не существует → google_to_csv, иначе двусторонне по времени
          - 'google_to_csv': только из Google в CSV
          - 'csv_to_google': только из CSV в Google
        """
        try:
            csv_file = self._get_csv_path(sheet_name)
            csv_exists = os.path.exists(csv_file)

            if direction == 'auto':
                if not csv_exists:
                    logger.info(f"Local CSV not found, using direction: google_to_csv")
                    direction = 'google_to_csv'
                else:
                    direction = 'bidirectional'

            logger.info(f"Syncing sheet '{sheet_name}' with direction: {direction}")

            if direction == 'google_to_csv':
                google_data = self.download_sheet(sheet_name)
                self.save_local_csv(google_data, sheet_name)
                logger.info(f"Synced Google → CSV for '{sheet_name}'")

            elif direction == 'csv_to_google':
                local_data = self.load_local_csv(sheet_name)
                if local_data.empty:
                    logger.warning(f"No local data to sync for '{sheet_name}'")
                    return False
                success = self.update_google_sheet(sheet_name, local_data)
                if success:
                    # Обновим _last_sync в локальном файле после отправки
                    local_data['_last_sync'] = datetime.now().isoformat()
                    self.save_local_csv(local_data, sheet_name)
                return success

            elif direction == 'bidirectional':
                google_data = self.download_sheet(sheet_name)
                local_data = self.load_local_csv(sheet_name)

                # Объединяем по _sync_id, выбирая более свежую версию строки целиком
                combined = pd.concat([google_data, local_data], ignore_index=True)
                if combined.empty:
                    self.save_local_csv(combined, sheet_name)
                    return True

                combined['_last_sync_ts'] = pd.to_datetime(combined['_last_sync'], errors='coerce')
                combined = combined.sort_values('_last_sync_ts', na_position='first')
                merged = combined.drop_duplicates(subset=['_sync_id'], keep='last')
                merged = merged.drop(columns=['_last_sync_ts'])

                self.save_local_csv(merged, sheet_name)
                self.update_google_sheet(sheet_name, merged)
                logger.info(f"Completed bidirectional sync for '{sheet_name}'")

            else:
                raise ValueError(f"Unknown direction: {direction}")

            return True

        except Exception as e:
            logger.error(f"Error syncing sheet '{sheet_name}': {e}")
            return False

    def sync_all_sheets(self, direction: str = 'auto') -> Dict[str, bool]:
        logger.info(f"Starting sync of all sheets (direction: {direction})")
        results = {}
        for sheets in self.sheets_config.values():
            for sheet_name in sheets.keys():
                results[sheet_name] = self.sync_sheet(sheet_name, direction=direction)
        success_count = sum(results.values())
        logger.info(f"Sync completed: {success_count}/{len(results)} sheets successful")
        return results

    def sync_selected_sheets(self, sheet_names: List[str], direction: str = 'auto') -> Dict[str, bool]:
        logger.info(f"Syncing selected sheets {sheet_names} (direction: {direction})")
        results = {}
        for sheet_name in sheet_names:
            sheet_exists = any(sheet_name in sheets for sheets in self.sheets_config.values())
            if sheet_exists:
                results[sheet_name] = self.sync_sheet(sheet_name, direction=direction)
            else:
                logger.error(f"Unknown sheet name: {sheet_name}")
                results[sheet_name] = False
        return results

    def get_available_sheets(self) -> List[str]:
        all_sheets = []
        for sheets in self.sheets_config.values():
            all_sheets.extend(sheets.keys())
        return all_sheets