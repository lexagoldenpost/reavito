# scheduler.py
import asyncio
from datetime import datetime, timedelta  # Добавляем импорт timedelta
from typing import Dict, List, Coroutine, Optional
from common.logging_config import setup_logger
from notification_service import check_notification_triggers
from common.config import Config

logger = setup_logger("scheduler")


class AsyncScheduler:
  def __init__(self):
    self.tasks: Dict[str, asyncio.Task] = {}
    self.jobs: List[dict] = [
      {
        'name': 'notification_check',
        'coro': check_notification_triggers,
        'interval': Config.SCHEDULER_PERIOD
      }
      # Можно добавить другие задачи здесь
      # ,
      # {
      #     'name': 'another_task',
      #     'coro': another_module.task_function,
      #     'interval': 5  # будет запускаться каждые 5 минут
      # }
    ]
    self.last_run_time: Optional[datetime] = None
    self.scheduler_period = Config.SCHEDULER_PERIOD * 60

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

  async def _run_all_tasks_once(self):
    """Запуск всех задач один раз"""
    current_time = datetime.now()
    if self.last_run_time and (
        current_time - self.last_run_time).total_seconds() < (
        self.scheduler_period - 5):
      return

    logger.info(f"Starting tasks (period: {Config.SCHEDULER_PERIOD} min)")
    self.last_run_time = current_time

    results = await asyncio.gather(
        *[self._run_with_retry(job['coro'](), job['name'])
          for job in self.jobs],
        return_exceptions=True
    )

    for job, success in zip(self.jobs, results):
      if success:
        logger.info(f"Task {job['name']} succeeded")
      else:
        logger.error(f"Task {job['name']} failed")

  async def run(self):
    """Основной цикл планировщика"""
    logger.info(f"Starting scheduler (interval: {Config.SCHEDULER_PERIOD} min)")

    try:
      while True:
        start_time = datetime.now()
        await self._run_all_tasks_once()

        # Рассчитываем время до следующего запуска
        elapsed = (datetime.now() - start_time).total_seconds()
        sleep_time = max(0, self.scheduler_period - elapsed)

        logger.debug(f"Next run in {sleep_time:.1f} seconds")
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