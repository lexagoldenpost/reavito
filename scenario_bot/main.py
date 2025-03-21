import json
import logging
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from common.database import SessionLocal
from common.logging_config import setup_logger
from avito_message_in.models import Message
from intent_bot.main import IntentBot  # Предполагаем, что IntentBot уже реализован

# Настройка логгера
logger = setup_logger("scenario_bot")

class ScenarioBot:
    def __init__(self, user_id: int, msg_id: int, item_id: int, scenario_file: str = "scenario.json", stop_words_file: str = "stop_words.json"):
        """
        Инициализация бота.
        :param user_id: Идентификатор пользователя.
        :param msg_id: Идентификатор сообщения.
        :param item_id: Идентификатор товара (объявления).
        :param scenario_file: Путь к файлу сценария.
        :param stop_words_file: Путь к файлу стоп-слов.
        """
        self.user_id = user_id
        self.msg_id = msg_id
        self.item_id = item_id
        self.scenario_file = scenario_file
        self.stop_words_file = stop_words_file
        self.scenario = self._load_scenario()
        self.stop_words = self._load_stop_words()
        self.current_question_index = self._load_user_progress()  # Загружаем прогресс пользователя
        self.scenario_active = False
        self.scenario_start_time = datetime.now()  # Время начала сценария
        self.intent_bot = IntentBot("intents.json")  # Инициализация бота с намерениями

    def _load_scenario(self) -> Optional[List[Dict]]:
        """
        Загрузка сценария из файла.
        :return: Список вопросов с подсказками или None, если файл не найден.
        """
        try:
            with open(self.scenario_file, "r", encoding="utf-8") as file:
                scenario = json.load(file)
                logger.info(f"Сценарий успешно загружен из файла {self.scenario_file}.")
                return scenario.get("scenario", [])
        except FileNotFoundError:
            logger.error(f"Файл сценария {self.scenario_file} не найден.")
            return None
        except Exception as e:
            logger.error(f"Ошибка при загрузке сценария: {e}")
            return None

    def _load_stop_words(self) -> List[str]:
        """
        Загрузка стоп-слов из файла.
        :return: Список стоп-слов.
        """
        try:
            with open(self.stop_words_file, "r", encoding="utf-8") as file:
                stop_words = json.load(file)
                logger.info(f"Стоп-слова успешно загружены из файла {self.stop_words_file}.")
                return stop_words.get("stop_words", [])
        except FileNotFoundError:
            logger.error(f"Файл стоп-слов {self.stop_words_file} не найден.")
            return []
        except Exception as e:
            logger.error(f"Ошибка при загрузке стоп-слов: {e}")
            return []

    def _load_user_progress(self) -> int:
        """
        Загрузка прогресса пользователя (текущего шага сценария).
        :return: Индекс текущего вопроса.
        """
        db = SessionLocal()
        try:
            last_message = (
                db.query(Message)
                .filter(Message.user_id == self.user_id, Message.item_id == self.item_id)
                .order_by(Message.created.desc())
                .first()
            )
            if last_message and any(last_message.question == step["question"] for step in self.scenario):
                return next(
                    i for i, step in enumerate(self.scenario)
                    if step["question"] == last_message.question
                ) + 1
            return 0
        except Exception as e:
            logger.error(f"Ошибка при загрузке прогресса пользователя: {e}")
            return 0
        finally:
            db.close()

    def _save_response(self, db: Session, question: str, response: str):
        """
        Сохранение ответа пользователя в базу данных.
        :param db: Сессия базы данных.
        :param question: Вопрос.
        :param response: Ответ пользователя.
        """
        try:
            message = Message(
                user_id=self.user_id,
                msg_id=self.msg_id,
                item_id=self.item_id,
                question=question,
                response=response,
                sent=True  # Помечаем как отправленное
            )
            db.add(message)
            db.commit()
            logger.info(f"Ответ сохранен: {question} - {response}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении ответа: {e}")
            db.rollback()

    def _get_next_question(self) -> Optional[Dict]:
        """
        Получение следующего вопроса из сценария.
        :return: Следующий вопрос с подсказкой или None, если сценарий завершен.
        """
        if self.scenario and self.current_question_index < len(self.scenario):
            question = self.scenario[self.current_question_index]
            self.current_question_index += 1
            return question
        return None

    def _check_stop_word(self, text: str) -> bool:
        """
        Проверка, является ли текст стоп-словом.
        :param text: Входной текст.
        :return: True, если это стоп-слово, иначе False.
        """
        return text.lower() in self.stop_words

    def _check_scenario_timeout(self) -> bool:
        """
        Проверка, истекло ли время сценария (24 часа).
        :return: True, если время истекло, иначе False.
        """
        return datetime.now() - self.scenario_start_time > timedelta(hours=24)

    def start_scenario(self) -> str:
        """
        Запуск сценария.
        :return: Сообщение о завершении или ошибке.
        """
        if not self.scenario:
            return "Сценарий не найден."

        self.scenario_active = True
        logger.info(f"Начало сценария для пользователя {self.user_id}.")
        db = SessionLocal()

        try:
            # Приветствие с предложением отключить сценарий
            print("Ультрон: Здравствуйте! Если вы не хотите общаться, напишите 'стоп'.")

            while self.scenario_active:
                # Проверка, истекло ли время сценария
                if self._check_scenario_timeout():
                    logger.info("Сценарий автоматически завершен по истечении 24 часов.")
                    return "Сценарий автоматически завершен по истечении 24 часов."

                question_data = self._get_next_question()
                if not question_data:
                    logger.info("Сценарий завершен.")
                    return "Сценарий завершен."

                # Задаем вопрос пользователю с подсказкой
                print(f"Ультрон: {question_data['question']} ({question_data['hint']})")
                response = input("Вы: ")

                # Проверяем, не ввел ли пользователь стоп-слово
                if self._check_stop_word(response):
                    self.scenario_active = False
                    logger.info("Сценарий отключен пользователем.")
                    return "Сценарий отключен."

                # Сохраняем ответ
                self._save_response(db, question_data["question"], response)

                # Проверяем, если это первый вопрос и ответ "все занято"
                if question_data["question"] == "Здравствуйте, я Ультрон, ассисент Евгении! Я помогу Вам проверить свободны ли данные аппартаменты на Ваши даты и ответить на дополнительны вопросы. На какой период вам нужно жилье? Укажите даты заезда и выезда.":
                    if "все занято" in response.lower():
                        print("Ультрон: К сожалению, на указанные даты все занято. Могу предложить другие варианты.")
                        self.scenario_active = False
                        return "Сценарий завершен."

        except Exception as e:
            logger.error(f"Ошибка в работе бота: {e}")
            return f"Ошибка: {e}"
        finally:
            db.close()

    def process_message(self, text: str) -> str:
        """
        Обработка входящего сообщения.
        :param text: Входной текст.
        :return: Ответ бота.
        """
        if self.scenario_active:
            return "Пожалуйста, завершите текущий сценарий."

        # Если сценарий не активен, используем бота с намерениями
        return self.intent_bot.process_message(text)

# Пример использования
if __name__ == "__main__":
    user_id = 1  # Идентификатор пользователя
    msg_id = 123  # Идентификатор сообщения
    item_id = 456  # Идентификатор товара (объявления)
    bot = ScenarioBot(user_id, msg_id, item_id)

    # Запуск сценария
    result = bot.start_scenario()
    print(result)

    # Обработка сообщений после завершения сценария
    while True:
        user_input = input("Вы: ")
        if user_input.lower() == "выход":
            break
        response = bot.process_message(user_input)
        print(f"Ультрон: {response}")