#!/usr/bin/env python3
# run_channel_monitor.py - запуск channel_monitor отдельно

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common.logging_config import setup_logger
from telega.channel_monitor import ChannelMonitor
import asyncio

logger = setup_logger("channel_monitor_runner")

# run_channel_monitor.py - исправьте:
if __name__ == "__main__":
    try:
        logger.info("🚀 Starting channel monitor...")
        monitor = ChannelMonitor()
        asyncio.run(monitor.run())
    except KeyboardInterrupt:
        logger.info("Channel monitor stopped by user")
    except Exception as e:
        logger.error(f"Channel monitor error: {e}", exc_info=True)
        sys.exit(1)