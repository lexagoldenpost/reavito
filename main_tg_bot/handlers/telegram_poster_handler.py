# main_tg_bot/handlers/telegram_poster_handler.py

import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import pandas as pd
import aiohttp

from common.config import Config
from common.logging_config import setup_logger
from main_tg_bot.booking_objects import PROJECT_ROOT
from telega.telegram_client import telegram_client
from telega.tg_notifier import send_message
from main_tg_bot.google_sheets.sync_manager import GoogleSheetsCSVSync

TASK_DATA_DIR = PROJECT_ROOT / Config.TASK_DATA_DIR
logger = setup_logger("telegram_poster_handler")


class ChannelCSVManager:
    """Менеджер для работы с CSV файлом каналов"""

    def __init__(self, csv_file_path: str = TASK_DATA_DIR / "channels.csv"):
        self.csv_file_path = Path(csv_file_path)
        self.sync_manager = GoogleSheetsCSVSync()

    async def can_send_to_channel(self, channel_id: str, min_days: int) -> Dict[str, Any]:
        """
        Проверяет, можно ли отправлять сообщение в канал на основе времени последней отправки

        Args:
            channel_id: ID канала
            min_days: Минимальное количество дней между отправками

        Returns:
            Словарь с результатами проверки
        """
        try:
            if not self.csv_file_path.exists():
                logger.warning(f"CSV файл {self.csv_file_path} не найден")
                return {'can_send': True, 'reason': 'CSV файл не найден',
                        'last_post_time': None}

            # Читаем CSV файл
            df = pd.read_csv(self.csv_file_path, dtype=str).fillna('')

            # Ищем канал по ID
            channel_mask = df['Наименование чата'] == channel_id
            if not channel_mask.any():
                logger.warning(f"Канал {channel_id} не найден в CSV файле")
                return {'can_send': True, 'reason': 'Канал не найден в CSV',
                        'last_post_time': None}

            # Получаем время последней отправки
            last_post_time_str = df.loc[channel_mask, 'Время последней отправки'].iloc[0]

            # Если время не указано, можно отправлять
            if not last_post_time_str or last_post_time_str == '':
                return {'can_send': True, 'reason': 'Время отправки не указано',
                        'last_post_time': None}

            # Парсим время последней отправки
            try:
                # Пробуем разные форматы дат
                formats = ['%Y-%m-%d %H:%M:%S', '%d.%m.%Y %H:%M:%S', '%d.%m.%Y']
                last_post_time = None

                for fmt in formats:
                    try:
                        last_post_time = datetime.strptime(last_post_time_str, fmt)
                        break
                    except ValueError:
                        continue

                if not last_post_time:
                    logger.warning(f"Не удалось распарсить время отправки: {last_post_time_str}")
                    return {'can_send': True, 'reason': 'Неверный формат времени',
                            'last_post_time': None}

                # Вычисляем минимальное время до следующей отправки
                min_interval = timedelta(days=min_days)
                # Добавляем 5 минут к интервалу
                min_interval_with_buffer = min_interval + timedelta(minutes=5)

                # Текущее время
                current_time = datetime.now()

                # Время следующей возможной отправки
                next_possible_time = last_post_time + min_interval_with_buffer

                # Проверяем, прошло ли достаточно времени
                if current_time >= next_possible_time:
                    time_until_next = timedelta(0)
                    can_send = True
                    reason = f"Прошло достаточно времени. Следующая отправка возможна с {next_possible_time.strftime('%Y-%m-%d %H:%M:%S')}"
                else:
                    time_until_next = next_possible_time - current_time
                    can_send = False
                    reason = f"Не прошло достаточно времени. Следующая отправка возможна через {self._format_timedelta(time_until_next)}"

                return {
                    'can_send': can_send,
                    'reason': reason,
                    'last_post_time': last_post_time,
                    'next_possible_time': next_possible_time,
                    'time_until_next': time_until_next
                }

            except Exception as e:
                logger.error(f"Ошибка при парсинге времени для канала {channel_id}: {str(e)}")
                return {'can_send': True, 'reason': f'Ошибка парсинга: {str(e)}',
                        'last_post_time': None}

        except Exception as e:
            logger.error(f"❌ Ошибка при проверке канала {channel_id}: {str(e)}")
            return {'can_send': True, 'reason': f'Ошибка проверки: {str(e)}',
                    'last_post_time': None}

    def _format_timedelta(self, td: timedelta) -> str:
        """Форматирует timedelta в читаемый вид"""
        days = td.days
        hours = td.seconds // 3600
        minutes = (td.seconds % 3600) // 60

        parts = []
        if days > 0:
            parts.append(f"{days} д.")
        if hours > 0:
            parts.append(f"{hours} ч.")
        if minutes > 0:
            parts.append(f"{minutes} м.")

        return " ".join(parts) if parts else "менее минуты"

    async def update_channel_after_posting(self, channel_id: str, message_id: Optional[str] = None) -> bool:
        """
        Обновляет данные канала после успешной отправки сообщения:
        - Время последней отправки
        - ИД последнего сообщения
        - Количество сообщение после последней публикации = 0

        Args:
            channel_id: ID канала
            message_id: ID отправленного сообщения

        Returns:
            True если обновление прошло успешно
        """
        try:
            if not self.csv_file_path.exists():
                logger.warning(f"CSV файл {self.csv_file_path} не найден")
                return False

            # Читаем CSV файл
            df = pd.read_csv(self.csv_file_path, dtype=str).fillna('')

            # Ищем канал по ID
            channel_mask = df['Наименование чата'] == channel_id
            if not channel_mask.any():
                logger.warning(f"Канал {channel_id} не найден в CSV файле")
                return False

            # Обновляем все три поля
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            df.loc[channel_mask, 'Время последней отправки'] = current_time
            df.loc[channel_mask, 'Количество сообщение после последней публикации'] = '0'

            if message_id:
                df.loc[channel_mask, 'ИД последнего сообщения'] = message_id
                logger.info(
                    f"✅ Данные канала {channel_id} обновлены: время={current_time}, message_id={message_id}, счетчик=0")
            else:
                logger.info(f"✅ Данные канала {channel_id} обновлены: время={current_time}, счетчик=0")

            # Сохраняем CSV
            df.to_csv(self.csv_file_path, index=False, encoding='utf-8')

            # Синхронизируем с Google Sheets
            try:
                sync_success = self.sync_manager.sync_sheet(
                    sheet_name="Отправка бронирований",
                    direction='csv_to_google'
                )
                if not sync_success:
                    logger.warning("Синхронизация с Google Sheets завершилась со статусом False")
                else:
                    logger.info("✅ CSV синхронизирован с Google Sheets")
            except Exception as sync_error:
                logger.error(f"❌ Ошибка синхронизации с Google Sheets: {sync_error}")

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка при обновлении канала {channel_id}: {str(e)}")
            return False


async def handle_telegram_poster(data: dict, filename: str) -> None:
    """
    Обработчик данных рассылки (аналогично contract_handler)

    Args:
        data: Данные JSON из файла
        filename: Имя файла
    """
    logger.info(f"📢 [handle_telegram_poster] Начало обработки рассылки из файла: {filename}")

    try:
        # Валидация обязательных полей
        required_fields = ['form_type', 'message_text', 'channels', 'init_chat_id']
        for field in required_fields:
            if field not in data:
                error_msg = f"❌ Отсутствует обязательное поле: {field}"
                logger.error(error_msg)
                await _send_notification(data['init_chat_id'], error_msg)
                return

        if data['form_type'] != 'telegram_poster':
            error_msg = f"❌ Неверный тип формы: {data['form_type']}"
            logger.error(error_msg)
            await _send_notification(data['init_chat_id'], error_msg)
            return

        # Инициализируем менеджер CSV
        csv_manager = ChannelCSVManager()

        # Извлекаем данные
        init_chat_id = data['init_chat_id']
        message_text = data['message_text']
        object_name = data.get('object', '')
        channels = data['channels']
        include_images = data.get('include_images', False)

        logger.info(f"📢 [handle_telegram_poster] Обработка рассылки для {len(channels)} каналов")
        logger.info(f"📢 [handle_telegram_poster] Объект: {object_name}")
        logger.info(f"📢 [handle_telegram_poster] Включить изображения: {include_images}")

        # Отправляем начальное уведомление
        await _send_notification(
            init_chat_id,
            f"📢 Запущена рассылка в {len(channels)} каналов. Обработка..."
        )

        # Обрабатываем каждый канал
        results = []
        skipped_channels = []

        for channel in channels:
            channel_result = await _process_channel(
                channel=channel,
                message_text=message_text,
                object_name=object_name,
                include_images=include_images,
                csv_manager=csv_manager
            )

            if channel_result.get('skipped', False):
                skipped_channels.append(channel_result)
            else:
                results.append(channel_result)

        # Формируем итоговый отчет
        await _send_final_report(init_chat_id, results, skipped_channels)

        logger.info(f"📢 [handle_telegram_poster] Рассылка завершена")

    except Exception as e:
        error_msg = f"❌ Критическая ошибка при обработке рассылки: {str(e)}"
        logger.error(error_msg)
        if 'init_chat_id' in locals():
            await _send_notification(init_chat_id, error_msg)


async def _process_channel(
        channel: Dict[str, Any],
        message_text: str,
        object_name: str,
        include_images: bool,
        csv_manager: ChannelCSVManager
) -> Dict[str, Any]:
    """
    Обработка отправки сообщения в один канал

    Returns:
        Словарь с результатами отправки
    """
    channel_id = channel.get('channel_id', '')
    display_name = channel.get('display_name', '')
    accepts_images = channel.get('accepts_images', True)
    min_days = int(channel.get('min_days', 7))  # По умолчанию 7 дней

    logger.info(f"📢 Обработка канала: {display_name} ({channel_id})")
    logger.info(f"📢 Канал принимает фото: {accepts_images}, include_images: {include_images}")

    try:
        # Проверяем временной интервал
        time_check = await csv_manager.can_send_to_channel(channel_id, min_days)

        if not time_check['can_send']:
            logger.warning(f"⏰ Пропуск канала {display_name}: {time_check['reason']}")
            return {
                'channel_id': channel_id,
                'display_name': display_name,
                'success': False,
                'skipped': True,
                'reason': time_check['reason'],
                'message_link': '',
                'message_id': None,
                'images_sent': 0,
                'error': 'Временное ограничение',
                'time_check': time_check
            }

        logger.info(f"✅ Временная проверка пройдена для {display_name}: {time_check['reason']}")

        # Подготовка медиафайлов
        media_files = []
        if accepts_images and object_name:
            media_files = await _get_image_files(object_name)
            if media_files:
                logger.info(f"📸 Найдено {len(media_files)} изображений для объекта {object_name}")
                for i, file_path in enumerate(media_files, 1):
                    logger.info(f"   Фото {i}: {Path(file_path).name}")
            else:
                logger.warning(f"⚠️ Изображения для объекта {object_name} не найдены")
        else:
            logger.info(
                f"📝 Отправка без изображений (include_images={include_images}, accepts_images={accepts_images})")

        # Отправка через Telethon
        logger.info(f"📤 Отправка сообщения в канал {display_name}...")

        # Если есть медиафайлы, отправляем с ними, иначе только текст
        if media_files:
            success, message_link = await telegram_client.send_message(
                channel_identifier=channel_id,
                message=message_text,
                media_files=media_files,
                return_message_link=True
            )
        else:
            success, message_link = await telegram_client.send_message(
                channel_identifier=channel_id,
                message=message_text,
                media_files=None,
                return_message_link=True
            )

        # Извлекаем ID сообщения из ссылки
        message_id = _extract_message_id_from_link(message_link) if success and message_link else None

        # Обновляем данные в CSV если отправка успешна
        if success:
            await csv_manager.update_channel_after_posting(channel_id, message_id)
            logger.info(f"✅ Сообщение успешно отправлено в {display_name}")
            if media_files:
                logger.info(f"   Отправлено фото: {len(media_files)} шт.")
            if message_link:
                logger.info(f"   Ссылка: {message_link}")
        else:
            logger.error(f"❌ Ошибка отправки в {display_name}")

        result = {
            'channel_id': channel_id,
            'display_name': display_name,
            'success': success,
            'skipped': False,
            'message_link': message_link or '',
            'message_id': message_id,
            'images_sent': len(media_files) if media_files else 0,
            'error': None if success else "Не удалось отправить сообщение",
            'time_check': time_check
        }

    except Exception as e:
        error_msg = f"Ошибка при обработке канала {display_name}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        result = {
            'channel_id': channel_id,
            'display_name': display_name,
            'success': False,
            'skipped': False,
            'message_link': '',
            'message_id': None,
            'images_sent': 0,
            'error': error_msg,
            'time_check': {}
        }

    return result


def _extract_message_id_from_link(message_link: str) -> Optional[str]:
    """
    Извлекает ID сообщения из ссылки на сообщение в Telegram

    Args:
        message_link: Ссылка на сообщение

    Returns:
        ID сообщения или None если не удалось извлечь
    """
    if not message_link:
        return None

    try:
        # Разные форматы ссылок:
        # https://t.me/username/123
        # https://t.me/c/1234567890/123
        # https://t.me/c/123/456

        parts = message_link.split('/')
        if len(parts) >= 2:
            # Берем последнюю часть URL как ID сообщения
            message_id = parts[-1]

            # Проверяем что это число
            if message_id.isdigit():
                return message_id
            else:
                logger.warning(f"Не удалось извлечь ID сообщения из ссылки: {message_link}")
                return None
        else:
            logger.warning(f"Некорректный формат ссылки: {message_link}")
            return None

    except Exception as e:
        logger.error(f"Ошибка при извлечении ID сообщения из {message_link}: {str(e)}")
        return None


async def _get_image_files(object_name: str) -> List[str]:
    """
    Поиск изображений для объекта в папке images

    Args:
        object_name: Название объекта

    Returns:
        Список путей к файлам изображений
    """
    try:
        # Определяем путь к папке с изображениями
        images_dir = PROJECT_ROOT / "images" / object_name

        logger.info(f"🔍 Поиск изображений в: {images_dir}")

        if not images_dir.exists():
            logger.warning(f"📁 Папка с изображениями не найдена: {images_dir}")
            return []

        # Поддерживаемые форматы изображений
        image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.webp', '*.gif']
        image_files = []

        for extension in image_extensions:
            found_files = list(images_dir.glob(extension))
            if found_files:
                logger.info(f"   Найдено {len(found_files)} файлов с расширением {extension}")
                image_files.extend(found_files)

        # Сортируем для consistency
        image_files.sort()

        # Логируем найденные файлы
        if image_files:
            logger.info(f"📸 Всего найдено изображений: {len(image_files)}")
            for i, file_path in enumerate(image_files, 1):
                logger.info(f"   {i}. {file_path.name}")
        else:
            logger.warning(f"⚠️ Изображения не найдены в папке {images_dir}")
            # Проверяем содержимое папки
            try:
                all_files = list(images_dir.glob('*'))
                if all_files:
                    logger.info(f"   Содержимое папки: {[f.name for f in all_files]}")
            except:
                pass

        return [str(path) for path in image_files]

    except Exception as e:
        logger.error(f"❌ Ошибка при поиске изображений для {object_name}: {str(e)}", exc_info=True)
        return []


async def _send_notification(chat_id: str, message: str) -> None:
    """
    Отправка уведомления в Telegram чат

    Args:
        chat_id: ID чата для уведомлений
        message: Текст сообщения
    """
    try:
        async with aiohttp.ClientSession() as session:
            await send_message(session, chat_id, message, timeout_sec=30)
    except Exception as e:
        logger.error(f"❌ Не удалось отправить уведомление в {chat_id}: {str(e)}")


async def _send_detailed_report(chat_id: str, results: List[Dict[str, Any]],
                                skipped_channels: List[Dict[str, Any]]) -> None:
    """
    Отправка развернутого отчета о рассылке с названиями каналов и ссылками на сообщения

    Args:
        chat_id: ID чата для отчета
        results: Список результатов отправки
        skipped_channels: Список пропущенных каналов
    """
    try:
        # Формируем подробный отчет
        detailed_report_lines = [
            "📋 **ПОДРОБНЫЙ ОТЧЕТ О РАССЫЛКЕ**",
            "━━━━━━━━━━━━━━━━━━━━━━",
            ""
        ]

        # Добавляем информацию об успешных отправках
        successful_sends = [r for r in results if r['success']]
        if successful_sends:
            detailed_report_lines.append("✅ **УСПЕШНЫЕ ОТПРАВКИ:**")
            detailed_report_lines.append("")

            for idx, result in enumerate(successful_sends, 1):
                channel_name = result['display_name']
                message_link = result.get('message_link', '')
                message_id = result.get('message_id', '')
                images_sent = result.get('images_sent', 0)

                detailed_report_lines.append(f"**{idx}. Канал:** {channel_name}")
                detailed_report_lines.append(f"   📎 **Ссылка:** {message_link if message_link else 'Недоступна'}")
                detailed_report_lines.append(f"   🆔 **ID сообщения:** {message_id if message_id else 'Неизвестен'}")
                if images_sent > 0:
                    detailed_report_lines.append(f"   🖼️ **Фото:** {images_sent} шт. ✅")
                else:
                    detailed_report_lines.append(f"   🖼️ **Фото:** не отправлялись")
                detailed_report_lines.append("")

        # Добавляем информацию об ошибках
        failed_sends = [r for r in results if not r['success'] and not r.get('skipped', False)]
        if failed_sends:
            detailed_report_lines.append("❌ **ОШИБКИ ОТПРАВКИ:**")
            detailed_report_lines.append("")

            for idx, result in enumerate(failed_sends, 1):
                channel_name = result['display_name']
                error_msg = result.get('error', 'Неизвестная ошибка')

                detailed_report_lines.append(f"**{idx}. Канал:** {channel_name}")
                detailed_report_lines.append(f"   ⚠️ **Ошибка:** {error_msg}")
                detailed_report_lines.append("")

        # Добавляем информацию о пропущенных каналах
        if skipped_channels:
            detailed_report_lines.append("⏰ **ПРОПУЩЕННЫЕ КАНАЛЫ (временной лимит):**")
            detailed_report_lines.append("")

            for idx, skipped in enumerate(skipped_channels, 1):
                channel_name = skipped['display_name']
                reason = skipped.get('reason', 'Не указана причина')
                time_check = skipped.get('time_check', {})

                detailed_report_lines.append(f"**{idx}. Канал:** {channel_name}")
                detailed_report_lines.append(f"   📋 **Причина:** {reason}")

                # Добавляем информацию о времени
                if 'last_post_time' in time_check and time_check['last_post_time']:
                    last_time = time_check['last_post_time']
                    if hasattr(last_time, 'strftime'):
                        last_time_str = last_time.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        last_time_str = str(last_time)
                    detailed_report_lines.append(f"   🕐 **Последняя отправка:** {last_time_str}")

                if 'next_possible_time' in time_check and time_check['next_possible_time']:
                    next_time = time_check['next_possible_time']
                    if hasattr(next_time, 'strftime'):
                        next_time_str = next_time.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        next_time_str = str(next_time)
                    detailed_report_lines.append(f"   ⏳ **Следующая возможна:** {next_time_str}")

                if 'time_until_next' in time_check and time_check['time_until_next']:
                    time_until = time_check['time_until_next']
                    if hasattr(time_until, 'days'):
                        # Создаем временный экземпляр менеджера для форматирования
                        temp_manager = ChannelCSVManager()
                        formatted_time = temp_manager._format_timedelta(time_until)
                        detailed_report_lines.append(f"   ⏱️ **Осталось ждать:** {formatted_time}")

                detailed_report_lines.append("")

        # Добавляем итоговую статистику
        total_processed = len(results) + len(skipped_channels)
        total_successful = len(successful_sends)
        total_failed = len(failed_sends)
        total_skipped = len(skipped_channels)

        detailed_report_lines.extend([
            "━━━━━━━━━━━━━━━━━━━━━━",
            "📊 **ОБЩАЯ СТАТИСТИКА:**",
            f"   📨 Всего каналов: {total_processed}",
            f"   ✅ Успешно: {total_successful}",
            f"   ❌ Ошибки: {total_failed}",
            f"   ⏰ Пропущено: {total_skipped}",
            "━━━━━━━━━━━━━━━━━━━━━━"
        ])

        # Отправляем подробный отчет как отдельный пост
        detailed_report = "\n".join(detailed_report_lines)

        async with aiohttp.ClientSession() as session:
            await send_message(session, chat_id, detailed_report)
            logger.info(f"📋 Подробный отчет о рассылке отправлен в {chat_id}")

            # Небольшая задержка между сообщениями
            await asyncio.sleep(1)

        # Также отправляем краткий отчет для быстрого ознакомления
        # await _send_quick_summary(chat_id, total_successful, total_failed, total_skipped)

    except Exception as e:
        logger.error(f"❌ Ошибка при отправке подробного отчета: {str(e)}")


async def _send_quick_summary(chat_id: str, successful: int, failed: int, skipped: int) -> None:
    """
    Отправка краткой сводки о рассылке

    Args:
        chat_id: ID чата
        successful: Количество успешных отправок
        failed: Количество ошибок
        skipped: Количество пропущенных
    """
    try:
        summary_lines = [
            "📈 **КРАТКАЯ СВОДКА**",
            f"✅ Успешно: {successful}",
            f"❌ Ошибки: {failed}",
            f"⏰ Пропущено: {skipped}",
            "",
            "📄 Подробный отчет смотрите выше ⬆️"
        ]

        summary_message = "\n".join(summary_lines)

        async with aiohttp.ClientSession() as session:
            await send_message(session, chat_id, summary_message)

    except Exception as e:
        logger.error(f"❌ Ошибка при отправке краткой сводки: {str(e)}")


async def _send_final_report(chat_id: str, results: List[Dict[str, Any]],
                             skipped_channels: List[Dict[str, Any]]) -> None:
    """
    Отправка итогового отчета о рассылке

    Args:
        chat_id: ID чата для отчета
        results: Список результатов отправки
        skipped_channels: Список пропущенных каналов
    """
    try:
        # Отправляем подробный отчет
        await _send_detailed_report(chat_id, results, skipped_channels)

        logger.info(f"📊 Отчеты о рассылке отправлены в {chat_id}")

    except Exception as e:
        logger.error(f"❌ Ошибка при отправке итогового отчета: {str(e)}")


# Функция для запуска извне
async def process_telegram_poster(json_file_path: str) -> None:
    """
    Основная функция для запуска обработчика рассылки

    Args:
        json_file_path: Путь к JSON файлу с данными рассылки
    """
    await handle_telegram_poster(json_file_path)


# Обновляем функцию process_telegram_poster_sync для совместимости
def process_telegram_poster_sync(data: dict, filename: str) -> None:
    """
    Синхронная версия обработчика рассылки для совместимости с booking_bot
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(handle_telegram_poster(data, filename))