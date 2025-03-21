import json
from typing import Dict, List, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import make_pipeline
from common.logging_config import setup_logger
from common.config import Config

# Настройка логгера
logger = setup_logger("intent_bot")

# Загрузка конфигурации
config = Config()

class IntentBot:
    def __init__(self, intents_file: str):
        """
        Инициализация бота с загрузкой намерений из JSON-файла.
        :param intents_file: Путь к JSON-файлу с намерениями.
        """
        self.intents_file = intents_file
        self.intents: Dict[str, List[str]] = self._load_intents()
        self.model = self._train_model()

    def _load_intents(self) -> Dict[str, List[str]]:
        """
        Загрузка намерений из JSON-файла.
        :return: Словарь с намерениями и примерами фраз.
        """
        try:
            with open(self.intents_file, "r", encoding="utf-8") as file:
                intents = json.load(file)
                logger.info(f"Намерения успешно загружены из файла {self.intents_file}")
                return intents
        except Exception as e:
            logger.error(f"Ошибка при загрузке намерений: {e}")
            return {}

    def _train_model(self):
        """
        Обучение модели на основе загруженных намерений.
        :return: Обученная модель.
        """
        try:
            # Подготовка данных для обучения
            texts = []
            labels = []
            for intent, examples in self.intents.items():
                texts.extend(examples)
                labels.extend([intent] * len(examples))

            # Создание и обучение модели
            model = make_pipeline(TfidfVectorizer(), MultinomialNB())
            model.fit(texts, labels)
            logger.info("Модель успешно обучена.")
            return model
        except Exception as e:
            logger.error(f"Ошибка при обучении модели: {e}")
            return None

    def predict_intent(self, text: str) -> str:
        """
        Предсказание намерения для введенного текста.
        :param text: Входной текст.
        :return: Предсказанное намерение.
        """
        if not self.model:
            logger.error("Модель не обучена.")
            return "unknown"

        try:
            intent = self.model.predict([text])[0]
            logger.info(f"Предсказано намерение: {intent} для текста: {text}")
            return intent
        except Exception as e:
            logger.error(f"Ошибка при предсказании намерения: {e}")
            return "unknown"

    def process_message(self, text: str) -> str:
        """
        Обработка входящего сообщения и возврат ответа.
        :param text: Входной текст.
        :return: Ответ в зависимости от намерения.
        """
        intent = self.predict_intent(text)

        # Конкретная фраза для приветствия
        if intent == "greeting":
            return "Добро пожаловать! Чем могу помочь?"

        # Поиск ответа из файла для других намерений
        if intent in self.intents:
            # Возвращаем первый пример фразы для данного намерения
            return self.intents[intent][0]

        # Если намерение не распознано
        return "Я не понял вопроса."

# Пример JSON-файла с намерениями
INTENTS_FILE = "intents.json"

# Инициализация бота
bot = IntentBot(INTENTS_FILE)

# Пример использования бота
if __name__ == "__main__":
    logger.info("Бот готов к ответу.")

    # Примеры запросов
    # test_phrases = [
    #     "Привет",
    #     "Как дела?",
    #     "Спасибо",
    #     "Что такое искусственный интеллект?"
    # ]

    # for phrase in test_phrases:
    #     response = bot.process_message(phrase)
    #     print(f"Вопрос: {phrase}\nОтвет: {response}\n")