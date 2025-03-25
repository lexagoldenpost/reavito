import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import make_pipeline
from common.logging_config import setup_logger
from common.config import Config

# Настройка логгера
logger = setup_logger("intent_bot")


class IntentBot:
  """Класс для определения намерений на основе текстовых сообщений."""

  def __init__(self, intents_file: str = None):
    """
        Инициализация бота с загрузкой намерений.

        Args:
            intents_file: Путь к JSON-файлу с намерениями. Если None, будет использован путь по умолчанию.
        """
    self.config = Config()
    self.intents_file = self._resolve_intents_path(intents_file)
    self.intents: Dict[str, List[str]] = self._load_intents()
    self.model = self._train_model()

  def _resolve_intents_path(self, intents_file: Optional[str]) -> str:
    """Определяет путь к файлу с намерениями."""
    if intents_file and os.path.exists(intents_file):
      return intents_file

    # Варианты путей по умолчанию
    possible_paths = [
      os.path.join(Path(__file__).parent.parent, "intent_bot", "intents.json"),
      os.path.join(Path(__file__).parent, "intents.json"),
      os.path.join("intent_bot", "intents.json"),
      getattr(self.config, "INTENTS_FILE_PATH", "intents.json")  # Изменено с config.get на getattr
    ]

    for path in possible_paths:
      if os.path.exists(path):
        logger.info(f"Найден файл намерений: {path}")
        return path

    raise FileNotFoundError("Не удалось найти файл с намерениями")

  def _load_intents(self) -> Dict[str, List[str]]:
    """Загружает намерения из JSON-файла."""
    try:
      with open(self.intents_file, "r", encoding="utf-8") as file:
        intents = json.load(file)
        if not isinstance(intents, dict):
          raise ValueError("Некорректный формат файла намерений")

        logger.info(f"Успешно загружено {len(intents)} намерений")
        return intents

    except json.JSONDecodeError as e:
      logger.error(f"Ошибка формата JSON в файле {self.intents_file}: {e}")
      raise
    except Exception as e:
      logger.error(f"Ошибка при загрузке намерений: {e}")
      raise

  def _train_model(self):
    """Обучает модель классификации намерений."""
    if not self.intents:
      logger.error("Нет данных для обучения")
      return None

    try:
      texts, labels = [], []
      for intent, examples in self.intents.items():
        if not examples:
          logger.warning(f"Нет примеров для намерения '{intent}'")
          continue
        texts.extend(examples)
        labels.extend([intent] * len(examples))

      if not texts:
        logger.error("Нет текстов для обучения")
        return None

      model = make_pipeline(
          TfidfVectorizer(),
          MultinomialNB()
      )
      model.fit(texts, labels)
      logger.info(f"Модель обучена на {len(texts)} примерах")
      return model

    except Exception as e:
      logger.error(f"Ошибка при обучении модели: {e}")
      return None

  def predict_intent(self, text: str) -> str:
    """Определяет намерение для заданного текста."""
    if not text or not isinstance(text, str):
      logger.warning("Получен пустой или некорректный текст")
      return "unknown"

    if not self.model:
      logger.error("Модель не обучена")
      return "unknown"

    try:
      intent = self.model.predict([text])[0]
      logger.debug(
        f"Определено намерение '{intent}' для текста: {text[:50]}...")
      return intent
    except Exception as e:
      logger.error(f"Ошибка предсказания: {e}")
      return "unknown"

  def process_message(self, text: str) -> str:
    """Обрабатывает сообщение и возвращает ответ."""
    intent = self.predict_intent(text)

    # Специальные обработчики для некоторых намерений
    handlers = {
      "greeting": "Добро пожаловать! Чем могу помочь?",
      "thanks": "Пожалуйста! Обращайтесь ещё!",
      "goodbye": "До свидания! Хорошего дня!"
    }

    if intent in handlers:
      return handlers[intent]

    # Стандартный ответ из примеров
    if intent in self.intents and self.intents[intent]:
      return self.intents[intent][0]

    return "Извините, я не совсем понял ваш вопрос. Можете переформулировать?"


def create_bot(intents_file: Optional[str] = None) -> IntentBot:
  """Фабричная функция для создания экземпляра бота с обработкой ошибок."""
  try:
    return IntentBot(intents_file)
  except Exception as e:
    logger.critical(f"Не удалось инициализировать бота: {e}")
    raise


# Инициализация бота при импорте (опционально)
try:
  bot = create_bot()
except Exception:
  # Для случаев, когда бот не критичен для работы модуля
  bot = None
  logger.warning("Бот не инициализирован, некоторые функции будут недоступны")

if __name__ == "__main__":
  # Тестовый режим работы
  logger.info("Бот инициализирован")
  # test_bot = create_bot()
  # if test_bot:
  #   while True:
  #     message = input("Введите сообщение: ")
  #     if message.lower() in ("exit", "quit"):
  #       break
  #     print(f"Ответ: {test_bot.process_message(message)}")