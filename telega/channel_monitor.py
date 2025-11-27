# channel_monitor.py
import asyncio
import io
import sys
import csv
from pathlib import Path
from typing import Dict, Set, List, Optional, Tuple

from telethon import TelegramClient, events
from telethon.tl.types import Message, User, Channel, PeerChannel, PeerChat

from common.config import Config
from common.logging_config import setup_logger
from telega.telegram_utils import TelegramUtils
from telega.telegram_client import telegram_client

# Fix stdout/stderr encoding issues
if not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if not isinstance(sys.stderr, io.TextIOWrapper):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

logger = setup_logger("channel_monitor")

# CSV file configuration
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
TASK_DATA_DIR = PROJECT_ROOT / Config.TASK_DATA_DIR
CSV_FILE_PATH = TASK_DATA_DIR / "search_channels.csv"


class ChannelMonitor:
    """Monitor Telegram channels for specific keywords and forward matching messages."""

    def __init__(self):
        """Initialize the channel monitor."""
        self.target_group = Config.TARGET_GROUP
        self.group_keywords: Dict[str, Set[str]] = {}
        self.client: TelegramClient = telegram_client.client
        self._is_authenticated = False

    async def initialize(self) -> bool:
        """Initialize Telegram client with shared session."""
        try:
            # Используем единого клиента для аутентификации
            if not await telegram_client.ensure_connection():
                logger.error("Failed to initialize Telegram client")
                return False

            self._is_authenticated = True
            me = await self.client.get_me()
            logger.info(
                f"Authorized as: {me.first_name or 'Unknown'} (ID: {me.id})")
            await self._print_connection_info()

            if not await self._load_keywords_from_csv():
                logger.error("Failed to load keywords from CSV")
                return False

            self._setup_handlers()
            logger.info("Channel monitoring initialized with shared client.")
            return True

        except Exception as e:
            logger.error(f"Initialization error: {e}", exc_info=True)
            return False

    async def _print_connection_info(self):
        """Print information about the current connection and subscribed channels."""
        try:
            me = await self.client.get_me()
            if me:
                name_parts = []
                if me.first_name:
                    name_parts.append(me.first_name)
                if me.last_name:
                    name_parts.append(me.last_name)
                name = " ".join(name_parts) if name_parts else "No name"
                logger.info(f"Authorized as: {name} (id: {me.id})")
            else:
                logger.warning("Could not get user information")

            await self.print_user_subscriptions()

        except Exception as e:
            logger.error(f"Error printing connection info: {e}")

    async def _load_keywords_from_csv(self) -> bool:
        """Load keywords from CSV file."""
        try:
            if not Path(CSV_FILE_PATH).exists():
                logger.error(f"CSV file not found: {CSV_FILE_PATH}")
                return False

            self.group_keywords = {}

            with open(CSV_FILE_PATH, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)

                for row in reader:
                    channel_id = row['Каналы и группы'].strip()
                    keywords_str = row['Ключевые слова'].strip()
                    channel_name = row['Название канала'].strip()

                    keywords = {
                        kw.strip().lower()
                        for kw in keywords_str.split(',')
                        if kw.strip()
                    }

                    if channel_id and keywords:
                        self.group_keywords[channel_id] = keywords
                        logger.debug(
                            f"Loaded keywords for channel {channel_id} ({channel_name}): {keywords}")

                    if channel_name and keywords:
                        self.group_keywords[channel_name] = keywords

            logger.info(f"Loaded {len(self.group_keywords)} keyword groups from CSV")
            logger.debug(f"Available channels: {list(self.group_keywords.keys())}")
            return True

        except Exception as e:
            logger.error(f"CSV keyword loading error: {e}", exc_info=True)
            return False

    def _setup_handlers(self):
        """Setup message handlers for monitoring."""

        @self.client.on(events.NewMessage())
        async def message_handler(event):
            try:
                if not await self._should_process_message(event):
                    return

                chat = await event.get_chat()
                message = event.message
                group_name = getattr(chat, 'title', None)
                group_id = str(chat.id) if hasattr(chat, 'id') else None

                if matched_keywords := self._find_matching_keywords(
                        group_name, group_id, message.text
                ):
                    await self._forward_message(message, group_name or f"ID:{group_id}")
                    logger.info(f"Matched keywords: {matched_keywords}")

            except Exception as e:
                logger.error(f"Message handling error: {e}", exc_info=True)

    async def _should_process_message(self, event) -> bool:
        """Check if a message should be processed."""
        return (
                event.is_group
                and event.message
                and event.message.text
                and await event.get_chat()
        )

    def _find_matching_keywords(self, group_name: str, group_id: str, text: str) -> Set[str]:
        """Find keywords that match the message text."""
        if not text:
            return set()

        text_lower = text.lower()
        matched_keywords = set()

        for identifier, keywords in self.group_keywords.items():
            if (group_name and identifier == group_name) or (group_id and identifier == group_id):
                for phrase in keywords:
                    phrase_words = [w.strip() for w in phrase.split()]
                    words = [w.strip() for w in text_lower.split()]

                    if any(
                            words[i:i + len(phrase_words)] == phrase_words
                            for i in range(len(words) - len(phrase_words) + 1)
                    ):
                        matched_keywords.add(phrase)

        return matched_keywords

    async def _forward_message(self, message: Message, source_name: str):
        """Forward a message to the target group."""
        try:
            target_entity = await TelegramUtils.get_entity_safe(self.client, self.target_group)
            if not target_entity:
                logger.error(f"Target group not found: {self.target_group}")
                return

            chat = await message.get_chat()
            chat_id = chat.id if hasattr(chat, 'id') else 0

            await self.client.send_message(
                entity=target_entity,
                message=(
                    f"🔍 Message from: {source_name}\n\n"
                    f"📄 Text:\n{message.text}\n\n"
                    f"🔗 Link: https://t.me/c/{str(abs(chat_id))[1:] if str(chat_id).startswith('-100') else abs(chat_id)}/{message.id}"
                ),
                link_preview=False
            )
            logger.info(f"Forwarded message from {source_name}")

        except Exception as e:
            logger.error(f"Message forwarding error: {e}", exc_info=True)

    async def send_message_to_chat(self, chat_id: str, message: str,
                                   images: Optional[List[Path]] = None) -> bool:
        """Send a message to a specific chat."""
        try:
            if not self.client or not self.client.is_connected():
                logger.error("Telegram client is not connected")
                return False

            try:
                chat_id_clean = str(chat_id).replace('-100', '')
                chat_id_int = int(chat_id_clean)
            except ValueError:
                logger.error(f"Invalid chat ID: {chat_id}")
                return False

            # Используем утилиту для получения entity
            entity = await TelegramUtils.get_entity_safe(self.client, chat_id_int)
            if not entity:
                return False

            # Используем утилиту для проверки бана
            if await TelegramUtils.is_user_banned(self.client, entity.id):
                logger.info(f"User is banned in chat {chat_id}")
                return False

            # Используем утилиту для проверки ограничений
            if not await TelegramUtils.check_account_restrictions(self.client, entity):
                logger.info(f"User has restrictions in chat {chat_id}")
                return False

            if images:
                await self.client.send_message(entity, message, file=images)
                logger.info(f"Message with {len(images)} images sent to chat {chat_id}")
            else:
                await self.client.send_message(entity, message)
                logger.info(f"Text message sent to chat {chat_id}")

            return True

        except Exception as e:
            logger.error(f"Error sending message to chat {chat_id}: {e}", exc_info=True)
            return False

    async def print_user_subscriptions(self):
        """Print all groups and channels the user is subscribed to."""
        try:
            logger.info("Getting list of all user's groups and channels...")
            dialogs = await self.client.get_dialogs()

            if not dialogs:
                logger.warning("No dialogs found or list is empty")
                return

            logger.info("=== User's groups and channels ===")
            for dialog in dialogs:
                if not hasattr(dialog, "entity"):
                    continue

                entity = dialog.entity
                name = self._get_entity_name(dialog, entity)
                entity_type, status = self._get_entity_type_and_status(dialog, entity)
                entity_id = getattr(entity, 'id', 'N/A')

                name = name.encode('utf-8', 'ignore').decode('utf-8').strip()

                logger.info(f"Name: {name}")
                logger.info(f"Type: {entity_type}{status}")
                logger.info(f"ID: {entity_id}")
                logger.info("------------------------")

            logger.info(f"=== Total groups/channels: {len(dialogs)} ===")

        except Exception as e:
            logger.error(f"Error getting subscriptions list: {e}", exc_info=True)

    def _get_entity_name(self, dialog, entity) -> str:
        """Get the name of a Telegram entity."""
        try:
            if hasattr(dialog, 'name') and dialog.name:
                return dialog.name
            elif hasattr(entity, 'title') and entity.title:
                return entity.title
            elif hasattr(entity, 'username') and entity.username:
                return f"@{entity.username}"
            elif hasattr(entity, 'first_name') and entity.first_name:
                name = entity.first_name
                if hasattr(entity, 'last_name') and entity.last_name:
                    name += f" {entity.last_name}"
                return name
            return "Unknown name"
        except Exception as e:
            logger.error(f"Error getting name: {e}")
            return "Error getting name"

    def _get_entity_type_and_status(self, dialog, entity) -> Tuple[str, str]:
        """Get the type and status of a Telegram entity."""
        entity_type = "Unknown type"
        status = ""

        if isinstance(entity, User):
            entity_type = "Private chat"
        elif dialog.is_group:
            entity_type = "Group"
        elif isinstance(entity, (Channel, PeerChannel)):
            if getattr(entity, 'megagroup', False):
                entity_type = "Supergroup"
            elif getattr(entity, 'broadcast', False):
                entity_type = "Channel"
            else:
                entity_type = "Group/Channel"
        elif isinstance(entity, PeerChat):
            entity_type = "Group"

        if getattr(entity, 'left', False):
            status = " (Left)"
        elif getattr(entity, 'kicked', False):
            status = " (Banned)"
        else:
            status = " (Active)"

        return entity_type, status

    async def check_channel_accessibility(self, channel_identifier: str) -> Dict[str, bool]:
        """Проверить доступность канала по всем параметрам."""
        result = {
            'exists': False,
            'accessible': False,
            'not_banned': False,
            'can_send_messages': False
        }

        try:
            # Получаем entity
            entity = await TelegramUtils.get_entity_safe(self.client, channel_identifier)
            if not entity:
                return result

            result['exists'] = True

            # Проверяем бан
            result['not_banned'] = not await TelegramUtils.is_user_banned(self.client, entity.id)

            # Проверяем ограничения
            result['can_send_messages'] = await TelegramUtils.check_account_restrictions(self.client, entity)

            result['accessible'] = result['not_banned'] and result['can_send_messages']

            return result

        except Exception as e:
            logger.error(f"Error checking channel accessibility {channel_identifier}: {e}")
            return result

    async def run(self):
        """Run the channel monitoring."""
        try:
            if not await self.initialize():
                raise RuntimeError("Initialization failed")

            logger.info("Starting channel monitoring")
            await self.client.run_until_disconnected()

        except Exception as e:
            logger.error(f"Monitoring error: {e}", exc_info=True)
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Shut down the monitor gracefully."""
        try:
            if self.client and self.client.is_connected():
                # Не отключаем клиент, так как он используется другими модулями
                logger.info("Channel monitor stopped (client remains connected for other modules)")
        except Exception as e:
            logger.error(f"Shutdown error: {e}", exc_info=True)


async def main():
    """Main async entry point."""
    monitor = ChannelMonitor()
    try:
        await monitor.run()
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        await monitor.shutdown()


if __name__ == "__main__":
    asyncio.run(main())