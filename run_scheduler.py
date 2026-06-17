#!/usr/bin/env python3
# run_scheduler.py - запуск scheduler отдельно

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common.logging_config import setup_logger
from scheduler.scheduler import AsyncScheduler
import asyncio

logger = setup_logger("scheduler_runner")

if __name__ == "__main__":
    try:
        logger.info("🚀 Starting scheduler...")
        scheduler = AsyncScheduler()
        asyncio.run(scheduler.run())
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.error(f"Scheduler error: {e}", exc_info=True)
        sys.exit(1)