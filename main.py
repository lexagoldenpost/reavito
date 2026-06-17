#!/usr/bin/env python3
# main.py - единая точка входа

import asyncio
import multiprocessing
import signal
import sys
import time
from pathlib import Path

root_dir = Path(__file__).parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from common.logging_config import setup_logger
from common.config import Config

logger = setup_logger("main_launcher")


def run_booking_bot():
    """Запуск бота (использует Bot API)"""
    try:
        from main_tg_bot.booking_bot import BookingBot
        bot = BookingBot()
        bot.run()
    except Exception as e:
        logger.error(f"💥 Booking bot crashed: {e}", exc_info=True)


def run_scheduler():
    """Запуск планировщика (использует пользовательский аккаунт для отправки)"""
    try:
        from scheduler.scheduler import AsyncScheduler
        scheduler = AsyncScheduler()
        asyncio.run(scheduler.run())
    except Exception as e:
        logger.error(f"💥 Scheduler crashed: {e}", exc_info=True)


def run_channel_monitor():
    """Запуск мониторинга каналов (использует пользовательский аккаунт)"""
    try:
        from telega.channel_monitor import ChannelMonitor

        # Проверяем настройки пользовательского аккаунта
        if not Config.TELEGRAM_SEND_BOOKING_PHONE:
            logger.error("❌ TELEGRAM_SEND_BOOKING_PHONE not configured!")
            logger.error("   Please configure user account for channel monitoring.")
            return

        monitor = ChannelMonitor()

        # Создаем новый цикл событий для этого процесса
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(monitor.run())
        except KeyboardInterrupt:
            logger.info("Channel monitor interrupted")
        finally:
            # Корректно завершаем все задачи
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()
            logger.info("Channel monitor loop closed")

    except Exception as e:
        logger.error(f"💥 Channel monitor crashed: {e}", exc_info=True)


def main():
    """Запуск всех компонентов"""
    logger.info("=" * 60)
    logger.info("🚀 Starting all components...")
    logger.info("=" * 60)

    # Проверяем конфигурацию
    if not Config.TELEGRAM_BOOKING_BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOOKING_BOT_TOKEN not configured!")
        return

    processes = []
    stop_event = multiprocessing.Event()

    # 1. Бот (всегда)
    p1 = multiprocessing.Process(target=run_booking_bot, name="BookingBot")
    processes.append(p1)
    logger.info("✅ BookingBot: enabled")

    # 2. Планировщик (всегда)
    p2 = multiprocessing.Process(target=run_scheduler, name="Scheduler")
    processes.append(p2)
    logger.info("✅ Scheduler: enabled")

    # 3. Мониторинг (только если настроен пользовательский аккаунт)
    if Config.TELEGRAM_SEND_BOOKING_PHONE:
        p3 = multiprocessing.Process(target=run_channel_monitor, name="ChannelMonitor")
        processes.append(p3)
        logger.info("✅ ChannelMonitor: enabled (user account configured)")
    else:
        logger.warning("⚠️ ChannelMonitor: DISABLED (TELEGRAM_SEND_BOOKING_PHONE not set)")

    # Запускаем процессы
    for p in processes:
        logger.info(f"🔄 Starting {p.name}...")
        p.start()

    logger.info("✅ All components started")
    logger.info("=" * 60)

    def signal_handler(signum, frame):
        logger.info(f"⚠️ Received signal {signum}, shutting down...")
        stop_event.set()

        for p in processes:
            if p.is_alive():
                logger.info(f"⏹️ Terminating {p.name} (PID: {p.pid})...")
                p.terminate()

        # Даем время на завершение
        time.sleep(2)

        # Принудительно убиваем, если не завершились
        for p in processes:
            if p.is_alive():
                logger.info(f"💥 Killing {p.name} (PID: {p.pid})...")
                p.kill()
                p.join(timeout=1)

        logger.info("👋 All processes terminated")
        sys.exit(0)

    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Ждем завершения процессов
    for p in processes:
        p.join()

    logger.info("✅ All processes finished")


if __name__ == "__main__":
    if sys.platform == 'win32':
        multiprocessing.set_start_method('spawn')
    main()