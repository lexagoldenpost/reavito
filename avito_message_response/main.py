import requests
from requests.exceptions import RequestException
from typing import Dict, Any, Optional
from dataclasses import dataclass
from common.logging_config import setup_logger
from common.avito_auth import get_avito_token, refresh_avito_token
from common.config import Config
import json
import time

logger = setup_logger("avito_message_response")


@dataclass
class AvitoMessage:
  """Класс для представления сообщения в Авито"""
  text: str
  chat_id: str
  account_id: str = Config.AVITO_USER_ID


class AvitoMessenger:
  BASE_URL = Config.AVITO_SEND_CHAT_URL
  MAX_RETRIES = 2
  TOKEN_REFRESH_DELAY = 1  # Задержка перед обновлением токена в секундах

  def __init__(self):
    self._token = None
    self._init_session()

  def _init_session(self):
    """Инициализация сессии с актуальным токеном"""
    self.session = requests.Session()
    self._update_token()
    self.session.headers.update({
      'Content-Type': 'application/json'
    })

  def _update_token(self):
    """Обновление токена авторизации"""
    try:
      self._token = get_avito_token()
      if not self._token:
        raise ValueError("Получен пустой токен")

      self.session.headers.update({
        'Authorization': f'Bearer {self._token}'
      })
      logger.debug("Токен успешно обновлен")

    except Exception as e:
      logger.error(f"Ошибка получения токена: {str(e)}")
      raise RuntimeError("Не удалось получить токен авторизации") from e

  def _refresh_token(self):
    """Попытка обновить токен при ошибке авторизации"""
    time.sleep(self.TOKEN_REFRESH_DELAY)
    try:
      logger.info("Попытка обновить токен...")
      refresh_avito_token()  # Предполагаем, что эта функция обновляет токен
      self._update_token()
      return True
    except Exception as e:
      logger.error(f"Не удалось обновить токен: {str(e)}")
      return False

  def _format_error(self, error: RequestException, chat_id: str) -> str:
    """Форматирует сообщение об ошибке для логирования"""
    status_code = getattr(error.response, 'status_code', 'N/A')
    error_text = getattr(error.response, 'text', str(error))
    return (
      f"Ошибка отправки в чат {chat_id}. "
      f"Статус: {status_code}. "
      f"Ошибка: {error_text[:200]}"
    )

  def _make_request(self, method: str, url: str, payload: Dict) -> Dict:
    """Выполняет запрос с обработкой ошибок авторизации"""
    for attempt in range(self.MAX_RETRIES + 1):
      try:
        response = self.session.request(
            method,
            url,
            json=payload,
            timeout=10
        )

        # Если токен невалидный, пробуем обновить
        if response.status_code == 403 and attempt < self.MAX_RETRIES:
          if "invalid access token" in response.text.lower():
            if not self._refresh_token():
              continue
            raise RequestException("Не удалось обновить токен")

        response.raise_for_status()
        return response.json()

      except RequestException as e:
        if attempt == self.MAX_RETRIES:
          error_msg = self._format_error(e, url.split('/')[
            -2])  # Извлекаем chat_id из URL
          logger.error(error_msg)
          raise RequestException(error_msg) from e
        continue

  def send_message(self, message: AvitoMessage) -> Dict:
    """Отправляет сообщение с обработкой ошибок авторизации"""
    if not isinstance(message, AvitoMessage):
      raise ValueError("Некорректный объект сообщения")

    if not all([message.text.strip(), message.chat_id, message.account_id]):
      raise ValueError("Не заполнены обязательные поля сообщения")

    url = f"{self.BASE_URL}{message.account_id}/chats/{message.chat_id}/messages"
    payload = {
      "message": {"text": message.text},
      "type": "text"
    }

    try:
      result = self._make_request("POST", url, payload)
      logger.info(f"Сообщение отправлено в чат {message.chat_id}")
      return result

    except Exception as e:
      logger.error(f"Финальная ошибка отправки: {str(e)}")
      raise


def create_avito_messenger() -> Optional[AvitoMessenger]:
  """Фабрика для безопасного создания мессенджера"""
  try:
    return AvitoMessenger()
  except Exception as e:
    logger.critical(f"Не удалось инициализировать мессенджер: {str(e)}")
    return None


def send_avito_message(text: str, chat_id: str) -> Optional[Dict]:
  """
  Упрощенный интерфейс для отправки сообщений

  Пример использования:
  response = send_avito_message("Привет", "u2i-zuxHcNSwf_q3blK2HhJgAQ")
  """
  messenger = create_avito_messenger()
  if not messenger:
    return None

  try:
    message = AvitoMessage(text=text, chat_id=chat_id)
    return messenger.send_message(message)
  except Exception as e:
    logger.error(f"Ошибка отправки сообщения: {str(e)}")
    return None