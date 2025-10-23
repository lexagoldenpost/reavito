# scheduler/scheduler.py
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

from common.logging_config import setup_logger
from main_tg_bot.booking_objects import PROJECT_ROOT
from common.config import Config

logger = setup_logger("simple_scheduler")
SCHEDULER_DIR = PROJECT_ROOT

class AsyncScheduler:
    def __init__(self):
        # Просто список задач: имя, путь к скрипту, интервал в секундах
        self.jobs = [
            {"name": "notifications_service", "script": SCHEDULER_DIR / Config.SCHEDULER_DATA_DIR / "notification_service.py", "interval": 30 * 60}
           # {"name": "notifications", "script": "sync_db_google_sheets/check_notifications.py", "interval": 30 * 60},
          #  {"name": "sync", "script": "main_tg_bot/google_sheets/sync.py", "interval": 60 * 60},
            # Добавляйте сюда новые задачи
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

    async def run_job(self, job: dict):
        """Запускает одну задачу по расписанию"""
        while True:
            await self.run_script(job["script"])
            await asyncio.sleep(job["interval"])

    async def run(self):
        """Запускает все задачи параллельно"""
        logger.info("🚀 Simple scheduler started")
        tasks = [self.run_job(job) for job in self.jobs]
        await asyncio.gather(*tasks)