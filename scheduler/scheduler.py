# scheduler/scheduler.py
import asyncio
import sys
from datetime import datetime, time, timedelta
from pathlib import Path

from common.logging_config import setup_logger
from main_tg_bot.booking_objects import PROJECT_ROOT
from common.config import Config

logger = setup_logger("simple_scheduler")
SCHEDULER_DIR = PROJECT_ROOT


class AsyncScheduler:
    def __init__(self):
        # Поддержка двух типов задач:
        # - interval: запуск каждые N секунд
        # - daily_at: запуск ежедневно в указанное время (формат "HH:MM")
        self.jobs = [
            {
                "name": "notifications_service",
                "script": SCHEDULER_DIR / Config.SCHEDULER_DATA_DIR / "notification_service.py",
                "daily_at": "14:00"
            },
          {
            "name": "update_message_counts",
            "script": SCHEDULER_DIR / "scheduler" / "update_last_message_info.py",
            "daily_at": "09:00"  # Запуск каждый день в 9:00 утра
          },
            # Пример интервальной задачи (раскомментируйте при необходимости):
            # {
            #     "name": "sync",
            #     "script": SCHEDULER_DIR / "main_tg_bot" / "google_sheets" / "sync.py",
            #     "interval": 60 * 60  # раз в час
            # },
            # Добавляйте сюда новые задачи любого типа
        ]


    async def run_script(self, script_path: Path):
        """Запускает скрипт в новом процессе (асинхронно)"""
        if not script_path.exists():
            logger.error(f"Script not found: {script_path}")
            return

        logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] Starting: {script_path}")
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable, str(script_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                logger.info(f"✅ Finished: {script_path}")
            else:
                logger.error(f"❌ Failed: {script_path}\n{stderr.decode().strip()}")
        except Exception as e:
            logger.exception(f"💥 Crash while running: {script_path} — {e}")

    async def wait_until_next_run(self, target_time_str: str) -> float:
        """Возвращает количество секунд до следующего запуска в формате 'HH:MM'"""
        now = datetime.now()
        try:
            hour, minute = map(int, target_time_str.split(":"))
            target_time = time(hour=hour, minute=minute)
        except ValueError:
            logger.error(f"Invalid time format in 'daily_at': {target_time_str}. Expected 'HH:MM'")
            return 24 * 3600  # fallback: повтор через сутки

        next_run = datetime.combine(now.date(), target_time)
        if now >= next_run:
            next_run += timedelta(days=1)

        seconds_to_wait = (next_run - now).total_seconds()
        return max(0.0, seconds_to_wait)

    async def run_daily_job(self, job: dict):
        """Запускает задачу ежедневно в указанное время"""
        script_path = job["script"]
        target_time_str = job["daily_at"]
        job_name = job["name"]

        while True:
            seconds = await self.wait_until_next_run(target_time_str)
            logger.info(f"🕒 '{job_name}' scheduled for {target_time_str}. Waiting {int(seconds)} seconds...")
            await asyncio.sleep(seconds)
            await self.run_script(script_path)

    async def run_interval_job(self, job: dict):
        """Запускает задачу с фиксированным интервалом (в секундах)"""
        script_path = job["script"]
        interval = job["interval"]
        job_name = job["name"]

        while True:
            await self.run_script(script_path)
            logger.info(f"🕒 '{job_name}' will run again in {interval} seconds")
            await asyncio.sleep(interval)

    async def run_job(self, job: dict):
        """Определяет тип задачи и запускает соответствующий цикл"""
        job_name = job.get("name", "unnamed")
        if "daily_at" in job:
            logger.info(f"📅 Job '{job_name}' configured for daily execution at {job['daily_at']}")
            await self.run_daily_job(job)
        elif "interval" in job:
            logger.info(f"🔁 Job '{job_name}' configured with interval {job['interval']} seconds")
            await self.run_interval_job(job)
        else:
            logger.error(f"Job '{job_name}' has no valid schedule: missing 'interval' or 'daily_at'")

    async def run(self):
        """Запускает все задачи параллельно"""
        logger.info("🚀 Async scheduler started")
        tasks = [self.run_job(job) for job in self.jobs]
        await asyncio.gather(*tasks)