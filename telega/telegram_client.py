# telegram_client.py
from pathlib import Path
from typing import Optional, Union, List, Tuple, Dict
import asyncio
import json
import time

from telethon import TelegramClient
from telethon.tl.types import InputMediaUploadedPhoto, \
  InputMediaUploadedDocument
from telethon import errors

from common.config import Config
from common.logging_config import setup_logger
from main_tg_bot.booking_objects import PROJECT_ROOT
from telega.telegram_utils import TelegramUtils

logger = setup_logger("telegram_client")


class EntityFileManager:
  """Менеджер для хранения entity в файле"""

  def __init__(self, cache_file: Path):
    self.cache_file = cache_file
    self._cache_loaded = False
    self._cache_loading = False

  def load_entities(self) -> Dict[str, Dict]:
    """Загрузка entity из файла"""
    try:
      if not self.cache_file.exists():
        logger.debug("Файл entity не существует, создаем новый")
        return {}

      with open(self.cache_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

      # Преобразуем обратно в нормальный формат
      entities = {}
      for identifier, entity_data in data.items():
        entities[identifier] = entity_data

      self._cache_loaded = True
      logger.info(f"✅ Entity загружены из файла: {len(entities)} записей")
      return entities

    except Exception as e:
      logger.warning(f"⚠️ Не удалось загрузить entity из файла: {e}")
      return {}

  def save_entities(self, entities: Dict[str, Dict]):
    """Сохранение entity в файл"""
    try:
      # Создаем директорию если нужно
      self.cache_file.parent.mkdir(parents=True, exist_ok=True)

      with open(self.cache_file, 'w', encoding='utf-8') as f:
        json.dump(entities, f, indent=2, ensure_ascii=False)

      logger.debug(f"💾 Entity сохранены в файл: {len(entities)} записей")

    except Exception as e:
      logger.error(f"❌ Ошибка сохранения entity в файл: {e}")

  def get_entity(self, identifier: str, entities: Dict[str, Dict]) -> Optional[
    Dict]:
    """Получение entity по идентификатору"""
    return entities.get(str(identifier))

  def add_entity(self, identifier: str, entity_data: Dict,
      entities: Dict[str, Dict]):
    """Добавление entity в файл"""
    entities[str(identifier)] = entity_data
    self.save_entities(entities)
    logger.debug(f"✅ Entity для {identifier} добавлено в файл")

  def clear_entities(self):
    """Очистка файла entity"""
    try:
      if self.cache_file.exists():
        cache_size = len(self.load_entities())
        self.cache_file.unlink()
        self._cache_loaded = False
        logger.info(f"🧹 Файл entity очищен (было {cache_size} записей)")
      else:
        logger.info("Файл entity не существует, нечего очищать")
    except Exception as e:
      logger.error(f"❌ Ошибка очистки файла entity: {e}")


class TelegramClientManager:
  """Единый менеджер для работы с Telegram API"""

  _instance = None
  _client = None

  def __new__(cls):
    if cls._instance is None:
      cls._instance = super().__new__(cls)
      cls._instance._initialize()
    return cls._instance

  def _initialize(self):
    """Инициализация клиента"""
    self.api_id = Config.TELEGRAM_API_SEND_BOOKING_ID
    self.api_hash = Config.TELEGRAM_API_SEND_BOOKING_HASH
    self.phone = Config.TELEGRAM_SEND_BOOKING_PHONE

    # Создаем папку sessions если её нет
    sessions_dir = PROJECT_ROOT / "sessions"
    sessions_dir.mkdir(exist_ok=True)

    # Определяем путь к файлу сессии
    session_filename = f"{self.api_id}_{Config.TELEGRAM_SESSION_NAME}"
    self.session_file_path = sessions_dir / f"{session_filename}.session"

    # Файл для хранения entity
    self.entity_file_path = sessions_dir / f"{session_filename}_entities.json"

    # Создаем менеджер файлов entity
    self.entity_manager = EntityFileManager(self.entity_file_path)

    # Загружаем entity при инициализации
    self.entities = self.entity_manager.load_entities()

    # Создаем клиент
    self._client = TelegramClient(
        str(self.session_file_path),
        self.api_id,
        self.api_hash,
        system_version='4.16.30-vxCUSTOM',
        connection_retries=5,
        request_retries=3,
        auto_reconnect=True
    )

    self._connection_open = False

  @property
  def client(self) -> TelegramClient:
    """Получить экземпляр клиента"""
    return self._client

  async def ensure_connection(self) -> bool:
    """Убедиться, что подключение установлено и клиент аутентифицирован"""
    try:
      if not self._connection_open:
        await self.client.connect()
        self._connection_open = True

      if not await self.client.is_user_authorized():
        logger.info("No valid session found. Starting new authorization...")
        await self.client.start(
            phone=self.phone,
            password=getattr(Config, 'TELEGRAM_PASSWORD', None),
            code_callback=self._get_verification_code
        )
        # После успешной авторизации выводим новую строку сессии
        new_session_str = self.client.session.save()
        logger.critical("✅ NEW STRING SESSION (SAVE THIS IMMEDIATELY):")
        logger.critical(new_session_str)

      return True
    except Exception as e:
      logger.error(f"Ошибка подключения/аутентификации: {str(e)}")
      return False

  def _get_verification_code(self):
    """Получить код верификации от пользователя"""
    return input("Enter SMS/Telegram verification code: ")

  async def preload_entity_cache(self) -> bool:
    """Предварительная загрузка entity из всех доступных каналов в файл"""
    try:
      if self.entity_manager._cache_loaded:
        logger.debug("✅ Entity уже загружены")
        return True

      if self.entity_manager._cache_loading:
        logger.debug("⏳ Entity уже загружаются...")
        return False

      self.entity_manager._cache_loading = True

      if not await self.ensure_connection():
        return False

      logger.info("🔄 Начинаем предварительную загрузку entity...")
      channels = await TelegramUtils.get_all_available_channels(self.client)

      if not channels:
        logger.warning("❌ Не найдено каналов для загрузки")
        return False

      # Загружаем все entity в файл
      loaded_count = 0
      for channel in channels:
        entity = channel['entity']
        # Создаем упрощенное представление entity для хранения
        entity_data = {
          'id': entity.id,
          'title': getattr(entity, 'title', ''),
          'username': getattr(entity, 'username', ''),
          'type': type(entity).__name__,
          'access_hash': getattr(entity, 'access_hash', ''),
          'full_id': channel.get('full_id', '')
        }

        # Добавляем по разным идентификаторам, но только если их еще нет
        identifiers = [
          str(channel['id']),
          channel['full_id'],
          f"@{channel['username']}" if channel.get('username') else None,
          channel['title']
        ]

        for identifier in identifiers:
          if identifier and identifier not in self.entities:
            self.entity_manager.add_entity(identifier, entity_data,
                                           self.entities)
            loaded_count += 1
          elif identifier and identifier in self.entities:
            # Обновляем существующую запись если нужно
            self.entity_manager.add_entity(identifier, entity_data,
                                           self.entities)

      self.entity_manager._cache_loaded = True
      logger.info(
          f"✅ Entity загружены: {loaded_count} записей, {len(channels)} каналов")
      return True

    except Exception as e:
      logger.error(f"❌ Ошибка загрузки entity: {str(e)}")
      return False
    finally:
      self.entity_manager._cache_loading = False

  async def get_entity_cached(self, channel_identifier: Union[str, int]):
    """Получение entity с использованием файлового хранилища"""
    cache_key = str(channel_identifier)

    # Шаг 1: Проверяем в файле
    entity_data = self.entity_manager.get_entity(cache_key, self.entities)
    if entity_data:
        logger.debug(f"📦 Найдено entity в файле для {channel_identifier}")
        # Пробуем получить entity по сохраненным данным
        try:
            # Используем оригинальный идентификатор для поиска
            entity = await TelegramUtils.get_entity_safe(self.client, channel_identifier)
            if entity:
                logger.debug(f"✅ Entity получено по сохраненным данным для {channel_identifier}")
                return entity
            else:
                logger.debug(f"⚠️ Не удалось получить entity по сохраненным данным для {channel_identifier}")
        except Exception as e:
            logger.debug(f"⚠️ Ошибка при получении entity по сохраненным данным: {e}")

    # Шаг 2: Если нет в файле или не удалось получить - пробуем получить напрямую
    logger.debug(f"🔄 Прямой поиск entity для {channel_identifier}")
    try:
        if not await self.ensure_connection():
            return None

        entity = await TelegramUtils.get_entity_safe(self.client, channel_identifier)
        if entity:
            # Сохраняем в файл
            entity_data = {
                'id': entity.id,
                'title': getattr(entity, 'title', ''),
                'username': getattr(entity, 'username', ''),
                'type': type(entity).__name__,
                'access_hash': getattr(entity, 'access_hash', '')
            }
            self.entity_manager.add_entity(cache_key, entity_data, self.entities)
            logger.debug(f"✅ Entity для {channel_identifier} найдено и сохранено в файл")
            return entity
    except Exception as e:
        logger.debug(
            f"⚠️ Не удалось получить entity напрямую для {channel_identifier}: {e}")

    # Шаг 3: Если не получилось напрямую - перезагружаем все entity
    logger.info(f"🔍 Entity для {channel_identifier} не найдено, перезагружаем...")
    await self.force_reload_cache()

    # Шаг 4: После перезагрузки пробуем снова найти в файле и получить
    entity_data = self.entity_manager.get_entity(cache_key, self.entities)
    if entity_data:
        logger.info(f"✅ Entity для {channel_identifier} найдено в файле после перезагрузки")
        # Пробуем получить entity разными способами
        try:
            # Способ 1: По оригинальному идентификатору
            entity = await TelegramUtils.get_entity_safe(self.client, channel_identifier)
            if entity:
                logger.info(f"✅ Entity получено после перезагрузки для {channel_identifier}")
                return entity
        except Exception as e:
            logger.debug(f"⚠️ Не удалось получить entity после перезагрузки: {e}")

        # Способ 2: По ID из сохраненных данных
        try:
            if 'id' in entity_data:
                entity = await TelegramUtils.get_entity_safe(self.client, entity_data['id'])
                if entity:
                    logger.info(f"✅ Entity получено по ID {entity_data['id']} после перезагрузки")
                    return entity
        except Exception as e:
            logger.debug(f"⚠️ Не удалось получить entity по ID: {e}")

        # Способ 3: По username если есть
        try:
            if entity_data.get('username'):
                entity = await TelegramUtils.get_entity_safe(self.client, f"@{entity_data['username']}")
                if entity:
                    logger.info(f"✅ Entity получено по username @{entity_data['username']} после перезагрузки")
                    return entity
        except Exception as e:
            logger.debug(f"⚠️ Не удалось получить entity по username: {e}")

    logger.error(f"❌ Entity для {channel_identifier} не найдено после всех попыток")
    return None

  async def close(self):
    """Корректное закрытие клиента"""
    await self.close_connection()

  async def check_existing_session(self) -> bool:
    """Проверяет и использует существующую сессию без полной аутентификации"""
    try:
      if not self._connection_open:
        await self.client.connect()
        self._connection_open = True

      # Быстрая проверка авторизации без полного цикла ensure_connection
      if await self.client.is_user_authorized():
        logger.info("✅ Using existing authorized session")
        return True
      else:
        logger.warning("❌ No valid session found")
        return False

    except Exception as e:
      logger.error(f"Error checking existing session: {str(e)}")
      return False

  async def force_reload_cache(self) -> bool:
    """Принудительная перезагрузка entity"""
    logger.info("🔄 Принудительная перезагрузка entity...")
    self.entity_manager._cache_loaded = False
    self.clear_entity_cache()
    return await self.preload_entity_cache()

  async def _find_entity_partial_match(self, identifier: str) -> Optional:
    """Поиск entity по частичному совпадению в уже загруженных entity"""
    try:
      if not self.entity_manager._cache_loaded:
        await self.preload_entity_cache()

      # Ищем по разным критериям в уже загруженных entity
      identifier_lower = identifier.lower()

      for cached_identifier, entity_data in self.entities.items():
        # Проверяем различные варианты совпадения
        if (identifier_lower == cached_identifier.lower() or
            identifier_lower in cached_identifier.lower() or
            cached_identifier.lower() in identifier_lower):

          logger.debug(
              f"🔍 Найдено частичное совпадение: {identifier} -> {cached_identifier}")

          # Пробуем получить entity по сохраненным данным
          try:
            # Используем ID для поиска, если он есть
            if 'id' in entity_data:
              entity = await TelegramUtils.get_entity_safe(self.client,
                                                           entity_data['id'])
              if entity:
                return entity
          except:
            pass

      return None
    except Exception as e:
      logger.error(f"❌ Ошибка при поиске частичного совпадения: {str(e)}")
      return None

  async def send_message(
      self,
      channel_identifier: Union[str, int],
      message: Optional[str] = None,
      media_files: Optional[List[str]] = None,
      return_message_link: bool = False
  ) -> Union[bool, Tuple[bool, str]]:
    """Упрощенная отправка сообщения в канал/группу с использованием файлового хранилища"""
    try:
      # Убеждаемся, что подключение установлено
      if not await self.ensure_connection():
        return (False, "") if return_message_link else False

      # Логируем информацию об аккаунте
      try:
        me = await self.client.get_me()
        if me:
          username = f"@{me.username}" if me.username else "без username"
          logger.info(
              f"🆔 Отправка под аккаунтом: {me.first_name} {me.last_name or ''} "
              f"(ID: {me.id}, {username})")
      except Exception as e:
        logger.warning(f"Не удалось получить информацию об аккаунте: {e}")

      # ✅ ФАЙЛОВОЕ ХРАНИЛИЩЕ: автоматически догружает entity при необходимости
      entity = await self.get_entity_cached(channel_identifier)
      if not entity:
        logger.error(f"❌ Не удалось получить entity для {channel_identifier}")
        return (False, "") if return_message_link else False

      # Отправка сообщения
      sent_message = None

      if media_files:
        if len(media_files) == 1:
          sent_message = await self.client.send_message(
              entity, message=message, file=media_files[0]
          )
        else:
          sent_message = await self.client.send_message(
              entity, message=message, file=media_files
          )
      elif message:
        sent_message = await self.client.send_message(entity, message)
      else:
        logger.error("Не указано ни сообщение, ни медиафайлы")
        return (False, "") if return_message_link else False

      # Генерация ссылки на сообщение
      if return_message_link and sent_message:
        if isinstance(sent_message, list) and sent_message:
          message_link = await TelegramUtils.get_message_link(
              self.client, entity, sent_message[0].id
          )
        else:
          message_link = await TelegramUtils.get_message_link(
              self.client, entity, sent_message.id
          )
        return True, message_link

      return True

    except errors.FloodWaitError as e:
      logger.error(f"Flood wait: нужно подождать {e.seconds} секунд")
      return (False, "") if return_message_link else False
    except Exception as e:
      logger.error(f"Ошибка при отправке сообщения: {str(e)}")
      return (False, "") if return_message_link else False

  async def close_connection(self):
    """Закрыть подключение"""
    if self._connection_open:
      await self.client.disconnect()
      self._connection_open = False
      logger.debug("🔌 Подключение закрыто")

  async def _upload_media(self, file_path: str):
    """Загружает медиафайл на сервер Telegram"""
    try:
      file = Path(file_path)
      if not file.exists():
        logger.error(f"Файл не найден: {file_path}")
        return None

      if file.suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp'):
        media = await self.client.upload_file(file)
        return InputMediaUploadedPhoto(media)
      else:
        media = await self.client.upload_file(file)
        return InputMediaUploadedDocument(
            media, mime_type=None, attributes=[]
        )
    except Exception as e:
      logger.error(f"Ошибка загрузки медиа: {str(e)}")
      return None

  async def get_channel_info(self, channel_identifier: Union[str, int]) -> \
      Optional[Dict]:
    """Получить информацию о канале"""
    try:
      if not await self.ensure_connection():
        return None

      result = await TelegramUtils.resolve_channel_identifier(self.client,
                                                              channel_identifier)
      if result:
        entity, channel_id, channel_name = result
        info = {
          'entity': entity,
          'id': channel_id,
          'name': channel_name,
          'username': getattr(entity, 'username', None),
          'title': getattr(entity, 'title', None),
          'participants_count': getattr(entity, 'participants_count', None),
          'accessible': await TelegramUtils.check_account_restrictions(
              self.client, entity),
          'not_banned': not await TelegramUtils.is_user_banned(self.client,
                                                               entity.id)
        }
        return info
      return None
    except Exception as e:
      logger.error(f"Ошибка получения информации о канале: {str(e)}")
      return None

  async def update_channels_csv_async(self) -> bool:
    """Асинхронное обновление CSV файлов информацией о каналах"""
    try:
      if not await self.ensure_connection():
        return False

      await TelegramUtils.update_channels_csv_files_standalone(self.client)
      return True

    except Exception as e:
      logger.error(f"Ошибка при обновлении CSV файлов: {str(e)}")
      return False

  def update_channels_csv(self) -> bool:
    """Синхронное обновление CSV файлов информацией о каналах"""
    try:
      loop = asyncio.get_event_loop()
    except RuntimeError:
      loop = asyncio.new_event_loop()
      asyncio.set_event_loop(loop)

    return loop.run_until_complete(self.update_channels_csv_async())

  def clear_entity_cache(self):
    """Очистка файла entity"""
    self.entity_manager.clear_entities()
    # Перезагружаем пустой словарь
    self.entities = self.entity_manager.load_entities()

  def get_cache_stats(self) -> Dict:
    """Получить статистику entity"""
    return {
      'entities_count': len(self.entities),
      'cache_loaded': self.entity_manager._cache_loaded,
      'connection_open': self._connection_open,
      'cached_entities': list(self.entities.keys())
    }


# Синглтон экземпляр
telegram_client = TelegramClientManager()