# scheduler/scheduler.py
import asyncio
import sys
from datetime import datetime, time, timedelta
from pathlib import Path
from telega.telegram_client import \
  telegram_client  # Используем существующий клиент

from common.logging_config import setup_logger
from main_tg_bot.booking_objects import PROJECT_ROOT
from common.config import Config

logger = setup_logger("simple_scheduler")
SCHEDULER_DIR = PROJECT_ROOT


class AsyncScheduler:
  def __init__(self):
    self.jobs = [
      {
        "name": "notifications_service",
        "script": SCHEDULER_DIR / Config.SCHEDULER_DATA_DIR / "notification_service.py",
        "daily_at": "14:00"
      },
      {
        "name": "update_message_counts",
        "module": "scheduler.update_last_message_tg_info",
        # Используем модуль вместо файла
        "function": "main",
        "daily_at": "13:00"
      },
    ]
    self.running = True

  async def run_module_function(self, module_path: str, function_name: str):
    """Запускает функцию из модуля в текущем процессе"""
    try:
      logger.info(f"🔄 Starting module function: {module_path}.{function_name}")

      # Импортируем модуль
      module = __import__(module_path, fromlist=[function_name])
      function = getattr(module, function_name)

      # Запускаем функцию
      if asyncio.iscoroutinefunction(function):
        await function()
      else:
        function()

      logger.info(f"✅ Finished module function: {module_path}.{function_name}")

    except Exception as e:
      logger.error(
        f"❌ Error in module function {module_path}.{function_name}: {e}")

  async def run_script(self, script_path: Path, job: dict):
    """Запускает скрипт в новом процессе (для независимых скриптов)"""
    if not script_path.exists():
      logger.error(f"Script not found: {script_path}")
      return

    logger.info(
      f"[{datetime.now().strftime('%H:%M:%S')}] Starting: {script_path}")
    try:
      process = await asyncio.create_subprocess_exec(
          sys.executable, str(script_path),
          stdout=asyncio.subprocess.PIPE,
          stderr=asyncio.subprocess.PIPE
      )

      stdout, stderr = await process.communicate()

      if process.returncode == 0:
        logger.info(f"✅ Finished: {script_path}")
        if stdout:
          logger.debug(f"STDOUT: {stdout.decode().strip()}")
      else:
        logger.error(f"❌ Failed: {script_path}\n{stderr.decode().strip()}")
    except Exception as e:
      logger.exception(f"💥 Crash while running: {script_path} — {e}")

  async def wait_until_next_run(self, target_time_str: str) -> float:
    """Возвращает количество секунд до следующего запуска"""
    now = datetime.now()
    try:
      hour, minute = map(int, target_time_str.split(":"))
      target_time = time(hour=hour, minute=minute)
    except ValueError:
      logger.error(
        f"Invalid time format in 'daily_at': {target_time_str}. Expected 'HH:MM'")
      return 24 * 3600

    next_run = datetime.combine(now.date(), target_time)
    if now >= next_run:
      next_run += timedelta(days=1)

    seconds_to_wait = (next_run - now).total_seconds()
    return max(0.0, seconds_to_wait)

  async def run_daily_job(self, job: dict):
    """Запускает задачу ежедневно в указанное время"""
    job_name = job["name"]
    target_time_str = job["daily_at"]

    while self.running:
      seconds = await self.wait_until_next_run(target_time_str)
      logger.info(
        f"🕒 '{job_name}' scheduled for {target_time_str}. Waiting {int(seconds)} seconds...")

      # Ждем без блокировки других задач
      await asyncio.sleep(seconds)

      if not self.running:
        break

      # Запускаем задачу
      if "module" in job and "function" in job:
        await self.run_module_function(job["module"], job["function"])
      elif "script" in job:
        await self.run_script(job["script"], job)
      else:
        logger.error(f"Job '{job_name}' has no valid execution method")

  async def run(self):
    """Запускает все задачи параллельно"""
    logger.info("🚀 Async scheduler started in main process")
    tasks = [self.run_daily_job(job) for job in self.jobs]
    await asyncio.gather(*tasks, return_exceptions=True)

  def stop(self):
    """Останавливает планировщик"""
    self.running = False
    logger.info("🛑 Scheduler stopping...")

if __name__ == "__main__":
    try:
        logger.info("🔧 Ручной запуск планировщика")
        scheduler = AsyncScheduler()
        asyncio.run(scheduler.run())
    except KeyboardInterrupt:
        logger.info("Планировщик остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка при работе планировщика: {e}", exc_info=True)