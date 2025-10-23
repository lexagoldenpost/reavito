from datetime import datetime, timedelta
from typing import Dict

import requests

from common.config import Config
from common.logging_config import setup_logger

# Настройка логгера
logger = setup_logger("avito_auth")

# Конфигурационные параметры
AVITO_CLIENT_ID = Config.AVITO_CLIENT_ID
AVITO_CLIENT_SECRET = Config.AVITO_CLIENT_SECRET
AVITO_TOKEN_URL = Config.AVITO_TOKEN_URL
AVITO_REFRESH_TOKEN_URL = Config.AVITO_REFRESH_TOKEN_URL

# Глобальное хранилище токенов
_token_data = None
_token_expiry = None


def _save_token_data(token_response: Dict) -> None:
  """Сохраняет данные токена и время его истечения"""
  global _token_data, _token_expiry

  _token_data = {
    'access_token': token_response['access_token'],
    'refresh_token': token_response.get('refresh_token', ''),
    'expires_in': token_response['expires_in']
  }

  # Устанавливаем время истечения с запасом в 30 секунд
  _token_expiry = datetime.now() + timedelta(
    seconds=token_response['expires_in'] - 30)
  logger.debug(f"Токен сохранен, истекает в {_token_expiry}")


def _is_token_valid() -> bool:
  """Проверяет, действителен ли текущий токен"""
  return _token_data is not None and datetime.now() < _token_expiry


def _request_new_token() -> Dict:
  """Запрашивает новый токен с использованием client_credentials"""
  payload = {
    'grant_type': 'client_credentials',
    'client_id': AVITO_CLIENT_ID,
    'client_secret': AVITO_CLIENT_SECRET
  }

  try:
    response = requests.post(AVITO_TOKEN_URL, data=payload, timeout=10)
    response.raise_for_status()
    token_data = response.json()
    _save_token_data(token_data)
    logger.info("Успешно получен новый токен")
    return token_data
  except requests.RequestException as e:
    logger.error(f"Ошибка получения токена: {str(e)}")
    raise RuntimeError("Не удалось получить токен") from e


def _refresh_existing_token() -> Dict:
  """Обновляет токен с использованием refresh_token"""
  if not _token_data or not _token_data.get('refresh_token'):
    raise ValueError("Нет refresh_token для обновления")

  payload = {
    'grant_type': 'refresh_token',
    'client_id': AVITO_CLIENT_ID,
    'client_secret': AVITO_CLIENT_SECRET,
    'refresh_token': _token_data['refresh_token']
  }

  try:
    response = requests.post(AVITO_REFRESH_TOKEN_URL, data=payload, timeout=10)
    response.raise_for_status()
    token_data = response.json()
    _save_token_data(token_data)
    logger.info("Токен успешно обновлен")
    return token_data
  except requests.RequestException as e:
    logger.error(f"Ошибка обновления токена: {str(e)}")
    raise RuntimeError("Не удалось обновить токен") from e


def get_avito_token() -> str:
  """
    Возвращает текущий действительный access_token.
    При необходимости обновляет токен автоматически.
    """
  global _token_data

  try:
    # Если токен не существует или истек
    if not _is_token_valid():
      if _token_data and _token_data.get('refresh_token'):
        try:
          _refresh_existing_token()
        except Exception:
          logger.warning("Не удалось обновить токен, запрашиваем новый")
          _request_new_token()
      else:
        _request_new_token()

    logger.debug(f"Используется токен, истекает в {_token_expiry}")
    return _token_data['access_token']
  except Exception as e:
    logger.critical(f"Критическая ошибка получения токена: {str(e)}")
    raise


def refresh_avito_token() -> bool:
  """
    Принудительно обновляет токен.
    Возвращает True при успешном обновлении.
    """
  try:
    if _token_data and _token_data.get('refresh_token'):
      _refresh_existing_token()
      return True
    else:
      _request_new_token()
      return True
  except Exception as e:
    logger.error(f"Ошибка принудительного обновления токена: {str(e)}")
    return False


def clear_token_cache() -> None:
  """Очищает кеш токенов (для тестирования)"""
  global _token_data, _token_expiry
  _token_data = None
  _token_expiry = None
  logger.info("Кеш токенов очищен")


# Инициализация токена при старте модуля
try:
  get_avito_token()
except Exception as e:
  logger.error(f"Не удалось инициализировать токен при старте: {str(e)}")