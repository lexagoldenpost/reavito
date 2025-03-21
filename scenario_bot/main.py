import json
from typing import List, Optional
from sqlalchemy.orm import Session
from common.database import SessionLocal
from common.logging_config import setup_logger
from scenario_bot.models import Message_Scenario

# Настройка логгера
logger = setup_logger("scenario_bot")

class ScenarioBot:
    def __init__(self, user_id: int, msg_id: int, scenario_file: str = "scenario.json"):
        """
        Инициализация бота.
        :param user_id: Идентификатор пользователя.
        :param msg_id: Идентификатор сообщения.
        :param scenario_file: Путь к файлу сценария.
        """
        self.user_id = user_id
        self.msg_id = msg_id
        self.scenario_file = scenario_file
        self.scenario = self._load_scenario()
        self.current_question_index = 0

    def _load_scenario(self) -> Optional[List[str]]:
        """
        Загрузка сценария из файла.
        :return: Список вопросов или None, если файл не найден.
        """
        try:
            with open(self.scenario_file, "r", encoding="utf-8") as file:
                scenario = json.load(file)
                logger.info(f"Сценарий успешно загружен из файла {self.scenario_file}.")
                return scenario
        except FileNotFoundError:
            logger.error(f"Файл сценария {self.scenario_file} не найден.")
            return None
        except Exception as e:
            logger.error(f"Ошибка при загрузке сценария: {e}")
            return None

    def _save_response(self, db: Session, question: str, response: str):
        """
        Сохранение ответа пользователя в базу данных.
        :param db: Сессия базы данных.
        :param question: Вопрос.
        :param response: Ответ пользователя.
        """
        try:
            message = Message_Scenario(
                user_id=self.user_id,
                msg_id=self.msg_id,
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

    def _get_next_question(self) -> Optional[str]:
        """
        Получение следующего вопроса из сценария.
        :return: Следующий вопрос или None, если сценарий завершен.
        """
        if self.scenario and self.current_question_index < len(self.scenario):
            question = self.scenario[self.current_question_index]
            self.current_question_index += 1
            return question
        return None

    def start_scenario(self) -> str:
        """
        Запуск сценария.
        :return: Сообщение о завершении или ошибке.
        """
        if not self.scenario:
            return "Сценарий не найден."

        logger.info(f"Начало сценария для пользователя {self.user_id}.")
        db = SessionLocal()

        try:
            while True:
                question = self._get_next_question()
                if not question:
                    logger.info("Сценарий завершен.")
                    return "Сценарий завершен."

                # Задаем вопрос пользователю
                print(f"Бот: {question}")
                response = input("Вы: ")

                # Сохраняем ответ
                self._save_response(db, question, response)

        except Exception as e:
            logger.error(f"Ошибка в работе бота: {e}")
            return f"Ошибка: {e}"
        finally:
            db.close()

# Пример использования
if __name__ == "__main__":
    user_id = 1  # Идентификатор пользователя
    msg_id = 123  # Идентификатор сообщения
    bot = ScenarioBot(user_id, msg_id)

    result = bot.start_scenario()
    print(result)