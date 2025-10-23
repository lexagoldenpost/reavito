# booking_objects.py
import os
import pandas as pd
from typing import Dict, Optional

# Убедимся, что папка существует
BOOKING_DIR = 'booking'
os.makedirs(BOOKING_DIR, exist_ok=True)

# Словарь соответствия: имя листа → имя файла
SHEET_TO_FILENAME = {
    'HALO Title': 'halo_title.csv',
    'Citygate Р311': 'citygate_p311.csv',
    'Citygate B209': 'citygate_b209.csv',
    'Palmetto Karon': 'palmetto_karon.csv',
    'Title Residence': 'title_residence.csv',
    'Halo JU701 двушка': 'halo_ju701_двушка.csv',
}

class BookingSheet:
    def __init__(self, sheet_name: str, filename: str):
        self.sheet_name = sheet_name
        self.filename = filename
        self.filepath = os.path.join(BOOKING_DIR, filename)

    def save(self, df: pd.DataFrame):
        """Сохраняет DataFrame в CSV-файл."""
        df.to_csv(self.filepath, index=False, encoding='utf-8')

    def load(self) -> pd.DataFrame:
        """Загружает данные из CSV-файла. Возвращает пустой DataFrame, если файла нет."""
        if not os.path.exists(self.filepath):
            return pd.DataFrame()
        return pd.read_csv(self.filepath, dtype=str).fillna('')

    def exists(self) -> bool:
        """Проверяет, существует ли файл локально."""
        return os.path.exists(self.filepath)

    def __repr__(self):
        return f"BookingSheet(sheet_name='{self.sheet_name}', filepath='{self.filepath}')"


# Создаём глобальный словарь объектов: по имени листа → объект BookingSheet
BOOKING_SHEETS: Dict[str, BookingSheet] = {
    sheet_name: BookingSheet(sheet_name, filename)
    for sheet_name, filename in SHEET_TO_FILENAME.items()
}

# Удобная функция для получения объекта по имени листа
def get_booking_sheet(sheet_name: str) -> Optional[BookingSheet]:
    return BOOKING_SHEETS.get(sheet_name)