# tg_notifier.py (финальная, рабочая версия)

import asyncio
import os
from typing import Optional, Union, List

import aiohttp
from aiohttp import FormData

from common.config import Config
from common.logging_config import setup_logger

logger = setup_logger("tg_notifier")


async def send_message(
    session: aiohttp.ClientSession,
    chat_id: Union[str, int],
    message: Optional[str] = None,
    media_files: Optional[Union[str, List[str]]] = None,
    timeout_sec: int = 15
) -> bool:
    if not message and not media_files:
        logger.error("Не указаны ни message, ни media_files")
        raise ValueError("Нужно указать либо message, либо media_files")

    bot_token = Config.TELEGRAM_BOOKING_BOT_TOKEN
    if not bot_token:
        logger.error("TELEGRAM_BOOKING_BOT_TOKEN не задан")
        return False

    base_url = f"https://api.telegram.org/bot{bot_token}"
    timeout = aiohttp.ClientTimeout(total=timeout_sec)

    try:
        files_list = [media_files] if isinstance(media_files, str) else (media_files or [])

        if not files_list:
            # Только текст
            payload = {
                'chat_id': str(chat_id),
                'text': message,
                'parse_mode': 'HTML'
            }
            async with session.post(f"{base_url}/sendMessage", data=payload, timeout=timeout) as resp:
                if resp.status == 200:
                    logger.info(f"✅ Текст отправлен в чат {chat_id}")
                    return True
                else:
                    err = await resp.text()
                    logger.error(f"❌ Ошибка текста в {chat_id}: {resp.status} — {err}")
                    return False

        # Отправка файлов
        for i, file_path in enumerate(files_list):
            if not os.path.isfile(file_path):
                logger.error(f"Файл не найден: {file_path}")
                return False

            form = FormData()
            form.add_field('chat_id', str(chat_id))
            if i == 0 and message:
                form.add_field('caption', message)
                form.add_field('parse_mode', 'HTML')

            with open(file_path, 'rb') as f:
                form.add_field(
                    'document',
                    f,
                    filename=os.path.basename(file_path),
                    content_type='application/octet-stream'
                )

                logger.debug(f"📤 Отправка {file_path} в чат {chat_id}")
                async with session.post(
                    f"{base_url}/sendDocument",
                    data=form,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 200:
                        logger.info(f"✅ Файл {file_path} отправлен в чат {chat_id}")
                    else:
                        err = await resp.text()
                        logger.error(f"❌ Ошибка отправки {file_path} в {chat_id}: {resp.status} — {err}")
                        return False

        return True

    except asyncio.TimeoutError:
        logger.error(f"⏰ Таймаут при отправке в чат {chat_id}")
        return False
    except Exception as e:
        logger.exception(f"💥 Ошибка в send_message для чата {chat_id}: {e}")
        return False

if __name__ == "__main__":
    # Пример использования
    test_chat_id = 651627886
    if send_message(test_chat_id, "TEST"):
        print("✅ Сообщение отправлено успешно")
    else:
        print("❌ Ошибка при отправке сообщения")