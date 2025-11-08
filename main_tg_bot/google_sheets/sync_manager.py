# main_tg_bot/sync_manager.py
import hashlib
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

from common.config import Config
from common.logging_config import setup_logger
# Импортируем booking-объекты
from main_tg_bot.booking_objects import BOOKING_SHEETS, PROJECT_ROOT
from main_tg_bot.google_sheets.ftp_client import FTPClient

logger = setup_logger("sync_manager")


class GoogleSheetsCSVSync:
    def __init__(self):
        self.scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]

        # Определяем корень проекта
        self.project_root = PROJECT_ROOT

        # Директории
        self.booking_dir = self.project_root / Config.BOOKING_DATA_DIR
        self.task_dir = self.project_root / Config.TASK_DATA_DIR

        self.booking_dir.mkdir(exist_ok=True)
        self.task_dir.mkdir(exist_ok=True)

        # Non-booking sheets → task_dir
        self.other_sheets = {
            'Задачи': 'tasks.csv',
            'Отправка бронирований': 'channels.csv',
            'Поиск в чатах': 'search_channels.csv',
            'Сумма помесячно Citygate P311': 'citygate_p311_price.csv',
            'Сумма помесячно HALO Title': 'halo_title_price.csv'
        }

        # Маппинги
        self.sheet_to_spreadsheet: Dict[str, str] = {}
        self.sheet_to_filepath: Dict[str, Path] = {}

        # 1. Booking sheets — из booking_objects
        for sheet_name, booking_obj in BOOKING_SHEETS.items():
            self.sheet_to_spreadsheet[sheet_name] = Config.BOOKING_SPREADSHEET_ID
            self.sheet_to_filepath[sheet_name] = booking_obj.filepath

        # 2. Other sheets — в task_dir
        for sheet_name, filename in self.other_sheets.items():
            self.sheet_to_spreadsheet[sheet_name] = Config.BOOKING_TASK_SPREADSHEET_ID
            self.sheet_to_filepath[sheet_name] = self.task_dir / filename

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

            for spreadsheet_id in {Config.BOOKING_SPREADSHEET_ID, Config.BOOKING_TASK_SPREADSHEET_ID}:
                if spreadsheet_id:
                    client = gspread.authorize(credentials)
                    self.clients[spreadsheet_id] = client
                    logger.info(f"Google Sheets client initialized for spreadsheet: {spreadsheet_id}")

        except Exception as e:
            logger.error(f"Error initializing Google Sheets clients: {e}")
            raise

    def _get_csv_path(self, sheet_name: str) -> Path:
        if sheet_name in self.sheet_to_filepath:
            return self.sheet_to_filepath[sheet_name]
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

    def _is_row_empty(self, row: pd.Series) -> bool:
        """Возвращает True, если строка пустая (все значимые поля — пустые)."""
        exclude = {'_sync_id', '_hash', '_sheet_name', '_last_sync'}
        for col in row.index:
            if col in exclude:
                continue
            val = row[col]
            if pd.notna(val) and str(val).strip() != '':
                return False
        return True

    def load_local_csv(self, sheet_name: str) -> pd.DataFrame:
        csv_file = self._get_csv_path(sheet_name)
        if not csv_file.exists():
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
            spreadsheet_id = self.sheet_to_spreadsheet.get(sheet_name)
            client = self.clients.get(spreadsheet_id)
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

            spreadsheet_id = self.sheet_to_spreadsheet.get(sheet_name)
            client = self.clients.get(spreadsheet_id)
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
        try:
            csv_file = self._get_csv_path(sheet_name)
            csv_exists = csv_file.exists()

            if direction == 'auto':
                # Всегда по умолчанию из гугла тянет в локал
                direction = 'google_to_csv' if not csv_exists else 'google_to_csv'

            logger.info(f"Syncing sheet '{sheet_name}' with direction: {direction}")

            if direction == 'google_to_csv':
                google_data = self.download_sheet(sheet_name)
                google_data = self._sort_dataframe_by_check_in(google_data, sheet_name)
                self.save_local_csv(google_data, sheet_name)
                logger.info(f"Synced Google → CSV for '{sheet_name}'")

            elif direction == 'csv_to_google':
                local_data = self.load_local_csv(sheet_name)
                if local_data.empty:
                    logger.warning(f"No local data to sync for '{sheet_name}'")
                    return False
                local_data = self._sort_dataframe_by_check_in(local_data, sheet_name)
                success = self.update_google_sheet(sheet_name, local_data)
                if success:
                    local_data['_last_sync'] = datetime.now().isoformat()
                    self.save_local_csv(local_data, sheet_name)
                    # ➕ Отправка на FTP после успешного сохранения
                    self._upload_sheet_to_ftp(sheet_name)
                return success
            elif direction == 'bidirectional':
                google_data = self.download_sheet(sheet_name)
                local_data = self.load_local_csv(sheet_name)
                # Индексация
                google_indexed = {row['_sync_id']: row for _, row in
                                  google_data.iterrows()} if not google_data.empty else {}
                local_indexed = {row['_sync_id']: row for _, row in
                                 local_data.iterrows()} if not local_data.empty else {}
                # Получаем все _sync_id в порядке: сначала из local (более свежие), потом новые из google
                # Но лучше — собрать все и потом отсортировать ПОСЛЕ объединения
                all_sync_ids = set(google_indexed.keys()) | set(local_indexed.keys())
                merged_rows = []
                for sync_id in all_sync_ids:
                    google_row = google_indexed.get(sync_id)
                    local_row = local_indexed.get(sync_id)
                    if google_row is not None and local_row is not None:
                        google_ts = pd.to_datetime(google_row['_last_sync'], errors='coerce')
                        local_ts = pd.to_datetime(local_row['_last_sync'], errors='coerce')
                        if pd.isna(local_ts) or (not pd.isna(google_ts) and google_ts > local_ts):
                            chosen = google_row
                        else:
                            chosen = local_row
                        merged_rows.append(chosen)
                    elif google_row is not None:
                        merged_rows.append(google_row)
                    else:
                        merged_rows.append(local_row)
                if merged_rows:
                    final_df = pd.DataFrame(merged_rows)
                else:
                    final_df = pd.DataFrame()
                final_df = self._ensure_sync_id(final_df)
                final_df['_sheet_name'] = sheet_name
                final_df['_last_sync'] = datetime.now().isoformat()
                final_df['_hash'] = final_df.apply(self._generate_row_hash, axis=1)
                # 🔥 Главное: сортируем ПОСЛЕ объединения и ПЕРЕД сохранением
                final_df = self._sort_dataframe_by_check_in(final_df, sheet_name)
                self.save_local_csv(final_df, sheet_name)
                self.update_google_sheet(sheet_name, final_df)
                self._upload_sheet_to_ftp(sheet_name)
                logger.info(f"Completed bidirectional sync for '{sheet_name}': {len(final_df)} rows")
            else:
                raise ValueError(f"Unknown direction: {direction}")

            return True

        except Exception as e:
            logger.error(f"Error syncing sheet '{sheet_name}': {e}")
            return False

    def _sort_dataframe_by_check_in(self, df: pd.DataFrame, sheet_name: str) -> pd.DataFrame:
        if sheet_name not in BOOKING_SHEETS or df.empty:
            return df

        check_in_col = 'Заезд'
        if check_in_col not in df.columns:
            logger.warning(f"Column '{check_in_col}' not found in sheet '{sheet_name}', skipping sort")
            return df

        df = df.copy()

        def parse_date(val):
            if pd.isna(val) or str(val).strip() == '':
                return pd.NaT
            val = str(val).strip()
            for fmt in ('%d.%m.%Y', '%Y-%m-%d'):
                try:
                    return pd.to_datetime(val, format=fmt)
                except ValueError:
                    continue
            return pd.NaT

        df['_sort_check_in'] = df[check_in_col].apply(parse_date)

        # Сортируем сначала по дате, потом по _sync_id для стабильности
        df = df.sort_values(
            by=['_sort_check_in', '_sync_id'],
            na_position='last',
            kind='mergesort'  # стабильная сортировка
        )
        df = df.drop(columns=['_sort_check_in'])
        return df

    def sync_all_sheets(self, direction: str = 'auto') -> Dict[str, bool]:
        logger.info(f"Starting sync of all sheets (direction: {direction})")
        results = {}
        for sheet_name in self.sheet_to_filepath.keys():
            results[sheet_name] = self.sync_sheet(sheet_name, direction=direction)
        success_count = sum(results.values())
        logger.info(f"Sync completed: {success_count}/{len(results)} sheets successful")
        return results

    def sync_selected_sheets(self, sheet_names: List[str], direction: str = 'auto') -> Dict[str, bool]:
        logger.info(f"Syncing selected sheets {sheet_names} (direction: {direction})")
        results = {}
        for sheet_name in sheet_names:
            if sheet_name in self.sheet_to_filepath:
                results[sheet_name] = self.sync_sheet(sheet_name, direction=direction)
            else:
                logger.error(f"Unknown sheet name: {sheet_name}")
                results[sheet_name] = False
        return results

    def get_available_sheets(self) -> List[str]:
        return list(self.sheet_to_filepath.keys())

    def upload_synced_files_via_ftp(self, ftp_host: str, ftp_user: str, ftp_password: str,
                                    port: int = 21, use_ftps: bool = False) -> bool:
        """
        Отправляет все синхронизированные CSV файлы на FTP сервер
        Автоматически определяет remote_path для каждого файла

        Args:
            ftp_host: FTP хост
            ftp_user: FTP пользователь
            ftp_password: FTP пароль
            port: FTP порт
            use_ftps: Использовать FTPS

        Returns:
            bool: True если все файлы успешно отправлены
        """
        ftp_client = FTPClient()

        try:
            # Подключаемся к FTP серверу
            if not ftp_client.connect(ftp_host, ftp_user, ftp_password, port, use_ftps):
                return False

            all_success = True

            # Отправляем каждый файл в свою директорию
            for sheet_name, file_path in self.sheet_to_filepath.items():
                if not file_path.exists():
                    logger.warning(f"Файл {file_path} не существует, пропускаем")
                    all_success = False
                    continue

                # Автоматически определяем remote_path
                remote_path = self._get_remote_path_for_sheet(sheet_name)

                # Отправляем файл
                success = ftp_client.upload_file(file_path, remote_path=remote_path)
                if not success:
                    all_success = False

            return all_success

        except Exception as e:
            logger.error(f"Ошибка при отправке файлов на FTP: {e}")
            return False
        finally:
            ftp_client.disconnect()

    def upload_selected_sheets_via_ftp(self, sheet_names: List[str], ftp_host: str,
                                       ftp_user: str, ftp_password: str,
                                       port: int = 21, use_ftps: bool = False) -> bool:
        """
        Отправляет только выбранные CSV файлы на FTP сервер
        Автоматически определяет remote_path для каждого файла

        Args:
            sheet_names: Список названий листов для отправки
            ftp_host: FTP хост
            ftp_user: FTP пользователь
            ftp_password: FTP пароль
            port: FTP порт
            use_ftps: Использовать FTPS

        Returns:
            bool: True если все выбранные файлы успешно отправлены
        """
        ftp_client = FTPClient()

        try:
            # Подключаемся к FTP серверу
            if not ftp_client.connect(ftp_host, ftp_user, ftp_password):
                return False

            all_success = True

            # Отправляем каждый выбранный файл в свою директорию
            for sheet_name in sheet_names:
                if sheet_name not in self.sheet_to_filepath:
                    logger.error(f"Неизвестное название листа: {sheet_name}")
                    all_success = False
                    continue

                file_path = self.sheet_to_filepath[sheet_name]
                if not file_path.exists():
                    logger.warning(f"Файл {file_path} не существует, пропускаем")
                    all_success = False
                    continue

                # Автоматически определяем remote_path
                remote_path = self._get_remote_path_for_sheet(sheet_name)

                # Отправляем файл
                success = ftp_client.upload_file(file_path, remote_path=remote_path)
                if not success:
                    all_success = False

            return all_success

        except Exception as e:
            logger.error(f"Ошибка при отправке выбранных файлов на FTP: {e}")
            return False
        finally:
            ftp_client.disconnect()

    def sync_and_upload_all(self, ftp_host: str, ftp_user: str, ftp_password: str,
                            sync_direction: str = 'auto', port: int = 21,
                            use_ftps: bool = False) -> Dict[str, bool]:
        """
        Выполняет синхронизацию всех листов и сразу отправляет на FTP сервер

        Args:
            ftp_host: FTP хост
            ftp_user: FTP пользователь
            ftp_password: FTP пароль
            sync_direction: Направление синхронизации
            port: FTP порт
            use_ftps: Использовать FTPS

        Returns:
            Dict[str, bool]: Результаты операций
        """
        results = {}

        # Синхронизируем все листы
        sync_results = self.sync_all_sheets(direction=sync_direction)
        results['sync'] = sync_results

        # Отправляем на FTP
        upload_success = self.upload_synced_files_via_ftp(
            ftp_host=ftp_host,
            ftp_user=ftp_user,
            ftp_password=ftp_password,
            port=port,
            use_ftps=use_ftps
        )
        results['upload'] = upload_success

        return results

    def sync_and_upload_selected(self, sheet_names: List[str], ftp_host: str,
                                 ftp_user: str, ftp_password: str,
                                 sync_direction: str = 'auto', port: int = 21,
                                 use_ftps: bool = False) -> Dict[str, bool]:
        """
        Выполняет синхронизацию выбранных листов и сразу отправляет на FTP сервер

        Args:
            sheet_names: Список названий листов
            ftp_host: FTP хост
            ftp_user: FTP пользователь
            ftp_password: FTP пароль
            sync_direction: Направление синхронизации
            port: FTP порт
            use_ftps: Использовать FTPS

        Returns:
            Dict[str, bool]: Результаты операций
        """
        results = {}

        # Синхронизируем выбранные листы
        sync_results = self.sync_selected_sheets(sheet_names, direction=sync_direction)
        results['sync'] = sync_results

        # Отправляем на FTP
        upload_success = self.upload_selected_sheets_via_ftp(
            sheet_names=sheet_names,
            ftp_host=ftp_host,
            ftp_user=ftp_user,
            ftp_password=ftp_password,
            port=port,
            use_ftps=use_ftps
        )
        results['upload'] = upload_success

        return results

    def _get_remote_path_for_sheet(self, sheet_name: str) -> str:
        """
        Определяет удаленный путь для листа на основе его типа

        Args:
            sheet_name: Название листа

        Returns:
            str: Удаленный путь на FTP сервере
        """
        # Используем REMOTE_FILE_PATH из конфигурации как корень
        remote_root = Config.REMOTE_FILE_PATH.strip('/')
        if sheet_name in BOOKING_SHEETS:
            return f"/{remote_root}/{Config.BOOKING_DATA_DIR}"
        else:
            return f"/{remote_root}/{Config.TASK_DATA_DIR}"

    def _get_remote_path_for_file(self, file_path: Path) -> str:
        """
        Определяет удаленный путь для файла на основе его расположения

        Args:
            file_path: Путь к файлу

        Returns:
            str: Удаленный путь на FTP сервере
        """
        remote_root = Config.REMOTE_FILE_PATH.strip('/')
        if self.booking_dir in file_path.parents:
            return f"/{remote_root}/{Config.BOOKING_DATA_DIR}"
        elif self.task_dir in file_path.parents:
            return f"/{remote_root}/{Config.TASK_DATA_DIR}"
        else:
            return f"/{remote_root}/other"

    def _upload_sheet_to_ftp(self, sheet_name: str) -> bool:
        """Отправляет один синхронизированный файл на FTP"""
        if sheet_name not in self.sheet_to_filepath:
            logger.error(f"Cannot upload unknown sheet: {sheet_name}")
            return False

        file_path = self.sheet_to_filepath[sheet_name]
        if not file_path.exists():
            logger.warning(f"File {file_path} does not exist, skipping FTP upload")
            return False

        remote_path = self._get_remote_path_for_sheet(sheet_name)
        ftp_client = FTPClient()
        try:
            if not ftp_client.connect(
                    Config.FTP_HOST,
                    Config.FTP_USER,
                    Config.FTP_PASSWORD
            ):
                return False
            success = ftp_client.upload_file(file_path, remote_path=remote_path)
            return success
        except Exception as e:
            logger.error(f"FTP upload failed for {sheet_name}: {e}")
            return False
        finally:
            ftp_client.disconnect()


if __name__ == "__main__":
    sync_manager = GoogleSheetsCSVSync()
    print("Синхронизация всех листов...")
    results = sync_manager.sync_all_sheets()
    print(f"Результаты: {results}")