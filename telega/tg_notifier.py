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
        timeout_sec: int = 30,
        max_retries: int = 3
) -> bool:
    """
    Отправка сообщения или файлов в Telegram через Bot API
    """
    if not message and not media_files:
        logger.error("Не указаны ни message, ни media_files")
        raise ValueError("Нужно указать либо message, либо media_files")

    bot_token = Config.TELEGRAM_BOOKING_BOT_TOKEN
    if not bot_token:
        logger.error("TELEGRAM_BOOKING_BOT_TOKEN не задан")
        return False

    base_url = f"https://api.telegram.org/bot{bot_token}"
    files_list = [media_files] if isinstance(media_files, str) else (media_files or [])

    for attempt in range(max_retries):
        try:
            # Задержка между повторными попытками
            if attempt > 0:
                wait_time = min(2 ** attempt, 10)  # Максимальная задержка 10 секунд
                logger.info(f"🔄 Повтор {attempt + 1}/{max_retries} через {wait_time} сек.")
                await asyncio.sleep(wait_time)

            if not files_list:
                # Отправка текста
                payload = {
                    'chat_id': str(chat_id),
                    'text': message,
                    'parse_mode': 'HTML'
                }

                timeout = aiohttp.ClientTimeout(total=timeout_sec)
                async with session.post(f"{base_url}/sendMessage", data=payload, timeout=timeout) as resp:
                    if resp.status == 200:
                        logger.info(f"✅ Текст отправлен в чат {chat_id}")
                        return True
                    else:
                        err = await resp.text()
                        logger.error(f"❌ Ошибка текста в {chat_id}: {resp.status} — {err}")
                        if attempt == max_retries - 1:
                            return False
                        continue

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
                    # Увеличиваем таймаут для файлов
                    file_timeout = aiohttp.ClientTimeout(total=60)
                    async with session.post(
                            f"{base_url}/sendDocument",
                            data=form,
                            timeout=file_timeout
                    ) as resp:
                        if resp.status == 200:
                            logger.info(f"✅ Файл {file_path} отправлен в чат {chat_id}")
                        else:
                            err = await resp.text()
                            logger.error(f"❌ Ошибка отправки {file_path} в {chat_id}: {resp.status} — {err}")
                            # Если это не последняя попытка, продолжаем цикл
                            if attempt < max_retries - 1:
                                break
                            return False

                    # Пауза между отправкой нескольких файлов
                    if i < len(files_list) - 1:
                        await asyncio.sleep(0.5)

            return True

        except (aiohttp.ClientOSError, ConnectionResetError, ConnectionError) as e:
            logger.warning(f"⚠️ Сетевая ошибка при отправке в {chat_id}: {e}")

            if attempt == max_retries - 1:
                logger.error(f"❌ Не удалось отправить в {chat_id} после {max_retries} попыток")
                return False

        except asyncio.TimeoutError:  # Используем встроенное исключение asyncio
            logger.warning(f"⏰ Таймаут при отправке в чат {chat_id}")

            if attempt == max_retries - 1:
                logger.error(f"❌ Таймаут при отправке в {chat_id} после {max_retries} попыток")
                return False

        except Exception as e:
            logger.exception(f"💥 Неожиданная ошибка в send_message для чата {chat_id}: {e}")

            # Для непредвиденных ошибок не повторяем
            return False

    return False

if __name__ == "__main__":
    # Пример использования
    test_chat_id = 651627886
    if send_message(test_chat_id, "TEST"):
        print("✅ Сообщение отправлено успешно")
    else:
        print("❌ Ошибка при отправке сообщения")