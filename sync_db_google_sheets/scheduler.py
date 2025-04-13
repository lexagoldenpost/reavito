# scheduler.py
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Coroutine, Optional
from common.logging_config import setup_logger
from notification_service import check_notification_triggers
from new_halo_notification_service import send_halo_notifications
from common.config import Config
import random
import os
import json

logger = setup_logger("scheduler")

# Константы
LAST_RUN_FILE = "last_halo_run.json"
DEFAULT_INTERVAL = 7 * 24 * 60  # 1 неделя в минутах
ADDITIONAL_DELAY = 2  # Дополнительные 2 минуты

class AsyncScheduler:
    def __init__(self):
        self.tasks: Dict[str, asyncio.Task] = {}
        self.jobs: List[dict] = [
            {
                'name': 'notification_check',
                'coro': check_notification_triggers,
                'interval': Config.SCHEDULER_PERIOD
            },
            {
                'name': 'send_halo_notifications',
                'coro': lambda: send_halo_notifications("HALO Title"),  # Wrap in a lambda
                'base_interval': 7 * 24 * 60,  # 1 неделя в минутах
                'additional_delay': 3,  # Дополнительные 3 минуты к интервалу
                'initial_delay': random.randint(0, 5),  # Случайное смещение 0-5 минут
                'last_run': None
            }
        ]
        self.last_run_time: Optional[datetime] = None
        self.scheduler_period = Config.SCHEDULER_PERIOD * 60

    def load_last_run_time(self) -> Optional[datetime]:
        """Загружает время последнего запуска из файла"""
        try:
            if os.path.exists(LAST_RUN_FILE):
                with open(LAST_RUN_FILE, 'r') as f:
                    data = json.load(f)
                    return datetime.fromisoformat(data['last_run'])
        except Exception as e:
            logger.error(f"Error loading last run time: {e}")
        return None

    def save_last_run_time(self, time: datetime):
        """Сохраняет время последнего запуска в файл"""
        try:
            with open(LAST_RUN_FILE, 'w') as f:
                json.dump({'last_run': time.isoformat()}, f)
        except Exception as e:
            logger.error(f"Error saving last run time: {e}")

    async def _run_with_retry(self, coro: Coroutine, task_name: str,
                            max_retries: int = 3) -> bool:
        """Запуск с повторами при ошибках"""
        for attempt in range(1, max_retries + 1):
            try:
                await coro
                return True
            except Exception as e:
                logger.error(
                    f"Attempt {attempt}/{max_retries} failed for {task_name}: {str(e)}")
                if attempt == max_retries:
                    return False
                await asyncio.sleep(5 * attempt)

    async def _should_run_job(self, job: dict) -> bool:
        """Определяет, нужно ли запускать задачу сейчас"""
        current_time = datetime.now()

        # Для обычных задач с фиксированным интервалом
        if 'base_interval' not in job:
            if self.last_run_time and (
                    current_time - self.last_run_time).total_seconds() < (
                    self.scheduler_period - 5):
                return False
            return True

        # Для еженедельных задач с дополнительным смещением
        if job['last_run'] is None:
            # Первый запуск - применяем initial_delay
            if (current_time - self._get_start_of_week()).total_seconds() / 60 >= job[
                'initial_delay']:
                return True
            return False

        # Последующие запуски - неделя + 3 минуты от последнего запуска
        next_run_time = job['last_run'] + timedelta(
            minutes=job['base_interval'] + job['additional_delay']
        )
        return current_time >= next_run_time

    def _get_start_of_week(self) -> datetime:
        """Возвращает начало текущей недели (понедельник 00:00)"""
        today = datetime.now()
        return today - timedelta(days=today.weekday(),
                               hours=today.hour,
                               minutes=today.minute,
                               seconds=today.second,
                               microseconds=today.microsecond)

    async def _run_all_tasks_once(self):
        """Запуск всех задач один раз"""
        current_time = datetime.now()
        run_regular = False

        # Проверяем нужно ли запускать регулярные задачи
        if self.last_run_time is None or (
                current_time - self.last_run_time).total_seconds() >= (
                self.scheduler_period - 5):
            run_regular = True
            self.last_run_time = current_time

        tasks_to_run = []
        for job in self.jobs:
            if await self._should_run_job(job):
                tasks_to_run.append(job)

        if not tasks_to_run:
            return

        logger.info(f"Starting {len(tasks_to_run)} tasks")

        results = await asyncio.gather(
            *[self._run_with_retry(job['coro'](), job['name'])
              for job in tasks_to_run],
            return_exceptions=True
        )

        for job, success in zip(tasks_to_run, results):
            if success:
                job['last_run'] = datetime.now()  # Обновляем время последнего запуска
                logger.info(f"Task {job['name']} succeeded at {job['last_run']}")
                if 'base_interval' in job:
                    next_run = job['last_run'] + timedelta(
                        minutes=job['base_interval'] + job['additional_delay']
                    )
                    logger.info(f"Next run scheduled at {next_run}")
            else:
                logger.error(f"Task {job['name']} failed")

    async def run(self):
        """Основной цикл планировщика"""
        logger.info("Starting scheduler")
        logger.info(f"Regular tasks interval: {Config.SCHEDULER_PERIOD} min")

        weekly_job = next(j for j in self.jobs if j.get('base_interval'))
        logger.info(
            f"Initial weekly task delay: {weekly_job['initial_delay']} min\n"
            f"Subsequent runs: every {weekly_job['base_interval']} min + "
            f"{weekly_job['additional_delay']} min from last run time"
        )

        try:
            while True:
                start_time = datetime.now()
                await self._run_all_tasks_once()

                # Рассчитываем время до следующего запуска
                elapsed = (datetime.now() - start_time).total_seconds()
                sleep_time = max(0, self.scheduler_period - elapsed)

                logger.debug(f"Next regular check in {sleep_time:.1f} seconds")
                await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            logger.info("Scheduler stopped")
        except Exception as e:
            logger.error(f"Scheduler error: {str(e)}", exc_info=True)
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Корректное завершение работы"""
        logger.info("Shutting down...")
        for task_name, task in self.tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                logger.info(f"Cancelled task: {task_name}")


async def main():
    scheduler = AsyncScheduler()
    try:
        await scheduler.run()
    except KeyboardInterrupt:
        await scheduler.shutdown()


if __name__ == '__main__':
    asyncio.run(main())