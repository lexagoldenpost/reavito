import asyncio
from datetime import datetime, timedelta
import json
import os
from typing import Dict, List, Optional, Any
from common.logging_config import setup_logger
import random

from sync_db_google_sheets.new_halo_notification_service import send_halo_notifications
from sync_db_google_sheets.notification_service import check_notification_triggers

# Логирование (замените на вашу реализацию)
logger = setup_logger("scheduler")

# Константы
LAST_RUNS_FILE = "last_notification_runs.json"
CHECK_INTERVAL = 30 * 60  # 30 минут (проверка обычных уведомлений)
HALO_CHECK_INTERVAL = 5 * 60  # 5 минут (проверка HALO)
HALO_WEEKLY_INTERVAL = 7 * 24 * 60 * 60  # 1 неделя
MIN_NOTIFICATION_INTERVAL = 60 * 60  # 1 час (защита от дублирования)


class AsyncScheduler:
    def __init__(self):
        self.tasks: Dict[str, asyncio.Task] = {}
        self.last_runs = self.load_last_runs()

        self.jobs = [
            {
                'name': 'regular_notification_check',
                'coro': self.wrap_notification_check,
                'interval': CHECK_INTERVAL,
                'type': 'fixed',
                'min_interval': MIN_NOTIFICATION_INTERVAL
            },
            {
                'name': 'weekly_halo_notifications',
                'coro': self.wrap_halo_notifications,
                'interval': HALO_CHECK_INTERVAL,  # Проверка каждые 5 минут
                'type': 'weekly',
                'target_interval': HALO_WEEKLY_INTERVAL,  # Но отправка раз в неделю
                'additional_delay': 2 * 60  # Случайное смещение (2 минуты)
            }
        ]

    async def wrap_notification_check(self):
        """Обертка для проверки обычных уведомлений с защитой от дублирования"""
        last_run = self.last_runs.get('regular_notification_check')
        now = datetime.now()

        if last_run is None or (now - last_run).total_seconds() >= MIN_NOTIFICATION_INTERVAL:
            logger.info("Running regular notification check...")
            await check_notification_triggers()
            self.last_runs['regular_notification_check'] = now
            self.save_last_runs()
        else:
            logger.debug(f"Skipping regular notifications (last run: {last_run})")

    async def wrap_halo_notifications(self):
        """Обертка для HALO-уведомлений с еженедельным интервалом"""
        last_run = self.last_runs.get('weekly_halo_notifications')
        now = datetime.now()

        # Если никогда не запускалось или прошло больше недели
        if last_run is None or (now - last_run).total_seconds() >= HALO_WEEKLY_INTERVAL:
            logger.info("Starting HALO notification...")
            try:
                await send_halo_notifications("HALO Title")
                self.last_runs['weekly_halo_notifications'] = now
                self.save_last_runs()
                logger.info(f"HALO notification sent. Next run after: {now + timedelta(seconds=HALO_WEEKLY_INTERVAL)}")
            except Exception as e:
                logger.error(f"HALO notification failed: {str(e)}")
        else:
            next_run = last_run + timedelta(seconds=HALO_WEEKLY_INTERVAL)
            logger.debug(f"Skipping HALO (next run: {next_run})")

    def load_last_runs(self) -> Dict[str, datetime]:
        """Загружает время последних запусков из файла"""
        try:
            if os.path.exists(LAST_RUNS_FILE):
                with open(LAST_RUNS_FILE, 'r') as f:
                    data = json.load(f)
                    return {k: datetime.fromisoformat(v) for k, v in data.items()}
            return {}
        except Exception as e:
            logger.error(f"Error loading last runs: {e}")
            return {}

    def save_last_runs(self):
        """Сохраняет время последних запусков"""
        try:
            with open(LAST_RUNS_FILE, 'w') as f:
                json.dump(
                    {k: v.isoformat() for k, v in self.last_runs.items()},
                    f,
                    indent=4
                )
        except Exception as e:
            logger.error(f"Error saving last runs: {e}")

    async def _run_job_with_retry(self, coro, job_name: str, max_retries: int = 3, retry_delay: int = 5):
        """Запускает задачу с повторами при ошибках"""
        for attempt in range(1, max_retries + 1):
            try:
                await coro()
                return True
            except Exception as e:
                logger.error(f"Attempt {attempt}/{max_retries} failed for {job_name}: {str(e)}")
                if attempt < max_retries:
                    await asyncio.sleep(retry_delay * attempt)
        return False

    async def _schedule_fixed_job(self, job: dict):
        """Запускает задачу с фиксированным интервалом"""
        while True:
            try:
                success = await self._run_job_with_retry(job['coro'], job['name'])
                if not success:
                    logger.error(f"Failed {job['name']} after retries")
            except Exception as e:
                logger.error(f"Unexpected error in {job['name']}: {str(e)}")
            await asyncio.sleep(job['interval'])

    async def run(self):
        """Основной цикл планировщика"""
        logger.info("Starting scheduler...")

        # Логируем информацию о ближайших запусках
        next_halo = "Not scheduled yet"
        if 'weekly_halo_notifications' in self.last_runs:
            last_halo = self.last_runs['weekly_halo_notifications']
            next_halo = last_halo + timedelta(seconds=HALO_WEEKLY_INTERVAL)

        logger.info(f"Regular notifications every {CHECK_INTERVAL // 60} minutes")
        logger.info(f"HALO notifications next run: {next_halo}")

        # Запускаем все задачи
        self.tasks = {
            job['name']: asyncio.create_task(
                self._schedule_fixed_job(job)
            )
            for job in self.jobs
        }

        try:
            await asyncio.gather(*self.tasks.values())
        except asyncio.CancelledError:
            logger.info("Scheduler stopped")
        except Exception as e:
            logger.error(f"Scheduler error: {str(e)}", exc_info=True)
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Корректное завершение работы"""
        logger.info("Shutting down scheduler...")
        for task in self.tasks.values():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        logger.info("All tasks stopped")


async def main():
    scheduler = AsyncScheduler()
    try:
        await scheduler.run()
    except KeyboardInterrupt:
        await scheduler.shutdown()


if __name__ == '__main__':
    asyncio.run(main())