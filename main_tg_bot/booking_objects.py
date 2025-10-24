# main_tg_bot/booking_objects.py
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from common.config import Config

# Корень проекта — родитель main_tg_bot/
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# Директории
BOOKING_DIR = PROJECT_ROOT / Config.BOOKING_DATA_DIR
BOOKING_DIR.mkdir(exist_ok=True)

# Только booking-файлы
SHEET_TO_FILENAME = {
    'HALO Title': 'halo_title.csv',
    'Citygate P311': 'citygate_p311.csv',
    'Citygate B209': 'citygate_b209.csv',
    'Palmetto Karon': 'palmetto_karon.csv',
    'Title Residence': 'title_residence.csv',
    'Halo JU701 двушка': 'halo_ju701_двушка.csv',
}

class BookingSheet:
    def __init__(self, sheet_name: str, filename: str):
        self.sheet_name = sheet_name
        self.filename = filename
        self.filepath = BOOKING_DIR / filename

    def save(self, df: pd.DataFrame):
        df.to_csv(self.filepath, index=False, encoding='utf-8')

    def load(self) -> pd.DataFrame:
        if not self.filepath.exists():
            return pd.DataFrame()
        return pd.read_csv(self.filepath, dtype=str).fillna('')

    def exists(self) -> bool:
        return self.filepath.exists()

    def __repr__(self):
        return f"BookingSheet(sheet_name='{self.sheet_name}', filepath='{self.filepath}')"


BOOKING_SHEETS: Dict[str, BookingSheet] = {
    sheet_name: BookingSheet(sheet_name, filename)
    for sheet_name, filename in SHEET_TO_FILENAME.items()
}

def get_booking_sheet(sheet_name: str) -> Optional[BookingSheet]:
    return BOOKING_SHEETS.get(sheet_name)