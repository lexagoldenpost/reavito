# channel_monitor.py
import asyncio
import io
import sys
from pathlib import Path
from typing import Dict, Set, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from telethon import TelegramClient, events
from telethon.tl.functions.messages import ExportChatInviteRequest
from telethon.tl.types import ChatBannedRights
from telethon.tl.types import Message, PeerChat, User, Channel, PeerChannel

from common.config import Config
from common.logging_config import setup_logger
from models import ChannelKeyword
from postgres_session import PostgresSession

# Fix stdout/stderr encoding issues
if not isinstance(sys.stdout, io.TextIOWrapper):
  sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if not isinstance(sys.stderr, io.TextIOWrapper):
  sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

logger = setup_logger("channel_monitor")

# Telegram session configuration
TELEGRAM_SESSION_NAME = f"{Config.TELEGRAM_API_SEND_BOOKING_ID}_{Config.TELEGRAM_SESSION_NAME}"

# Database configuration
async_engine = create_async_engine(
    f"postgresql+asyncpg://{Config.POSTGRES_USER}:{Config.POSTGRES_PASSWORD}@"
    f"{Config.POSTGRES_HOST}:{Config.POSTGRES_PORT}/{Config.POSTGRES_DB}",
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True
)

AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


class ChannelMonitor:
  """Monitor Telegram channels for specific keywords and forward matching messages."""

  def __init__(self):
    """Initialize the channel monitor."""
    self.api_id = Config.TELEGRAM_API_SEND_BOOKING_ID
    self.api_hash = Config.TELEGRAM_API_SEND_BOOKING_HASH
    self.phone = Config.TELEGRAM_SEND_BOOKING_PHONE
    self.target_group = Config.TARGET_GROUP
    self.group_keywords: Dict[str, Set[str]] = {}
    self.client: Optional[TelegramClient] = None
    self.telethon_session: Optional[PostgresSession] = None

  async def initialize(self) -> bool:
    """Initialize the monitor and Telegram client.

        Returns:
            bool: True if initialization was successful, False otherwise.
        """
    try:
      # Initialize Telegram session and client
      self.telethon_session = PostgresSession(
        session_name=TELEGRAM_SESSION_NAME)
      await self.telethon_session.load_session()

      if await self.telethon_session.get_auth_key():
        logger.info("Found existing session in database")
      else:
        logger.info("No session found, new authorization required")

      self.client = TelegramClient(
          self.telethon_session,
          self.api_id,
          self.api_hash,
          system_version='4.16.30-vxCUSTOM',
          connection_retries=5,
          request_retries=3,
          auto_reconnect=True
      )

      # Connect to Telegram
      try:
        if await self.telethon_session.get_auth_key():
          await self.client.connect()
        else:
          await self.client.start(
              phone=self.phone,
              password=lambda: input("Enter Telegram password (if set): "),
              code_callback=lambda: input("Enter SMS/Telegram code: "),
              max_attempts=3
          )
      except Exception as e:
        logger.error(f"Telegram connection error: {e}")
        return False

      logger.info("Telegram client started successfully")
      await self.telethon_session.save_updates()
      logger.debug("Telegram session saved to database")

      # Print connection info
      await self._print_connection_info()

      # Load keywords and setup handlers
      if not await self._load_keywords():
        logger.error("Failed to load keywords")
        return False

      self._setup_handlers()
      logger.info("Channel monitoring initialized")
      return True

    except Exception as e:
      logger.error(f"Initialization error: {e}", exc_info=True)
      return False

  def get_client(self) -> Optional[TelegramClient]:
    """Возвращает текущий клиент Telegram."""
    return self.client if self.client and self.client.is_connected() else None

  async def _print_connection_info(self):
    """Print information about the current connection and subscribed channels."""
    try:
      me = await self.client.get_me()
      logger.info(f"Authorized as: {me.first_name} (id: {me.id})")

      # Print subscribed channels/groups
      await self.print_user_subscriptions()
      await self.print_active_dialogs()
      await self.print_active_groups()
    except Exception as e:
      logger.error(f"Error printing connection info: {e}")

  async def _load_keywords(self) -> bool:
    """Load keywords from the database.

        Returns:
            bool: True if keywords were loaded successfully, False otherwise.
        """
    try:
      async with AsyncSessionLocal() as session:
        result = await session.execute(select(ChannelKeyword))
        self.group_keywords = {
          record.channel.strip(): {
            kw.strip().lower()
            for kw in record.keywords.split(',')
            if kw.strip()
          }
          for record in result.scalars()
          if record.channel
        }
        logger.debug(f"Loaded {len(self.group_keywords)} keyword groups")
        return True
    except Exception as e:
      logger.error(f"Keyword loading error: {e}", exc_info=True)
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
    """Check if a message should be processed.

        Args:
            event: The message event to check.

        Returns:
            bool: True if the message should be processed, False otherwise.
        """
    return (
        event.is_group
        and event.message
        and event.message.text
        and await event.get_chat()
    )

  def _find_matching_keywords(self, group_name: str, group_id: str,
      text: str) -> Set[str]:
    """Find keywords that match the message text.

        Args:
            group_name: Name of the group/channel
            group_id: ID of the group/channel
            text: Message text to check

        Returns:
            Set[str]: Set of matched keywords
        """
    if not text:
      return set()

    text_lower = text.lower()
    matched_keywords = set()

    for identifier, keywords in self.group_keywords.items():
      if (group_name and identifier == group_name) or (
          group_id and identifier == group_id):
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
    """Forward a message to the target group.

        Args:
            message: The message to forward
            source_name: Name of the source channel/group
        """
    try:
      target_entity = await self.client.get_entity(self.target_group)
      chat = await message.get_chat()
      chat_id = chat.id if hasattr(chat, 'id') else 0

      await self.client.send_message(
          entity=target_entity,
          message=(
            f"🔍 Message from: {source_name}\n\n"
            f"📄 Text:\n{message.text}\n\n"
            f"🔗 Link: https://t.me/c/{chat_id}/{message.id}" if chat_id else ""
          ),
          link_preview=False
      )
      logger.info(f"Forwarded message from {source_name}")

    except Exception as e:
      logger.error(f"Message forwarding error: {e}", exc_info=True)

  async def send_message_to_chat(self, chat_id: str, message: str,
      images: Optional[List[Path]] = None) -> bool:
    """Send a message to a specific chat.

        Args:
            chat_id: ID of the chat (can be with or without -100 prefix)
            message: Text of the message to send
            images: Optional list of image paths to attach

        Returns:
            bool: True if message was sent successfully, False otherwise
        """
    try:
      if not self.client or not self.client.is_connected():
        logger.error("Telegram client is not connected")
        return False

      # Convert chat_id to int (remove -100 if present)
      try:
        chat_id_int = int(str(chat_id).replace('-100', ''))
      except ValueError:
        logger.error(f"Invalid chat ID: {chat_id}")
        return False

      # Get chat entity
      try:
        entity = await self.client.get_entity(chat_id_int)
      except ValueError:
        try:
          entity = await self.client.get_entity(int(f"-100{chat_id_int}"))
        except Exception as e:
          logger.error(f"Failed to find chat with ID {chat_id}: {e}")
          return False

      # Check if user is banned
      if await self._is_user_banned(entity.id):
        logger.info(f"User is banned in chat {chat_id}")
        return False

      # Send message
      if images:
        await self.client.send_message(entity, message, file=images)
        logger.info(f"Message with {len(images)} images sent to chat {chat_id}")
      else:
        await self.client.send_message(entity, message)
        logger.info(f"Text message sent to chat {chat_id}")

      return True

    except Exception as e:
      logger.error(f"Error sending message to chat {chat_id}: {e}",
                   exc_info=True)
      return False

  async def _is_user_banned(self, chat_id: int) -> bool:
    """Check if the user is banned in a chat.

        Args:
            chat_id: ID of the chat to check

        Returns:
            bool: True if user is banned, False otherwise
        """
    try:
      chat = await self.client.get_entity(chat_id)
      if isinstance(chat, Channel):
        participant = await self.client.get_permissions(chat, 'me')
        if hasattr(participant, 'banned_rights') and participant.banned_rights:
          if isinstance(participant.banned_rights, ChatBannedRights):
            return participant.banned_rights.view_messages
        elif hasattr(participant, 'kicked'):
          return participant.kicked
      return False
    except Exception as e:
      logger.error(f"Error checking ban status in chat {chat_id}: {e}")
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

        # Clean non-printable characters
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

  async def print_active_dialogs(self):
    """Print information about all available dialogs."""
    try:
      dialogs = await self.client.get_dialogs()
      if not dialogs:
        logger.error("No dialogs found")
        return

      logger.info("List of all available dialogs:")
      for dialog in dialogs:
        if not hasattr(dialog, "entity"):
          continue

        entity = dialog.entity
        name = getattr(entity, 'title', None) or getattr(entity, 'username',
                                                         None) or "No name"
        entity_type = self._get_simple_entity_type(entity)
        status = self._get_simple_status(entity)

        logger.info("- %s: '%s' (ID: %d, Type: %s, Status: %s)",
                    "Dialog", name, entity.id, entity_type, status)

    except Exception as e:
      logger.error(f"Error getting dialogs list: {e}", exc_info=True)

  def _get_simple_entity_type(self, entity) -> str:
    """Get simplified entity type for logging."""
    if isinstance(entity, User):
      return "User"
    elif isinstance(entity, PeerChat):
      return "Group"
    elif isinstance(entity, (Channel, PeerChannel)):
      return "Channel"
    return "Unknown type"

  def _get_simple_status(self, entity) -> str:
    """Get simplified status for logging."""
    if getattr(entity, 'left', False):
      return "Left"
    elif getattr(entity, 'kicked', False):
      return "Banned"
    return "Active"

  async def print_active_groups(self):
    """Print detailed information about available groups."""
    try:
      dialogs = await self.client.get_dialogs()
      logger.info(f"Total dialogs: {len(dialogs)}")
      if not dialogs:
        logger.error("No dialogs found")
        return

      logger.info("List of available groups:")
      for dialog in dialogs:
        if not hasattr(dialog, "entity"):
          continue

        entity = dialog.entity
        if not self._is_group(dialog, entity):
          continue

        status = self._get_group_status(entity)
        name = getattr(entity, 'title', "No name")
        participants, description, invite_link = await self._get_group_details(
          entity)

        logger.info("- Group: '%s'%s", name, status)
        logger.info(f"  ID: {entity.id}")
        logger.info(f"  Type: {type(entity)}")
        logger.info(f"  Participants: {participants}")
        logger.info(f"  Description: {description}")
        logger.info(f"  Invite link: {invite_link}")
        logger.info("------------------------")

    except Exception as e:
      logger.error(f"Error getting groups list: {e}", exc_info=True)

  def _is_group(self, dialog, entity) -> bool:
    """Check if an entity is a group."""
    return (
        dialog.is_group
        or isinstance(entity, PeerChat)
        or (hasattr(entity, 'megagroup') and entity.megagroup)
        or (hasattr(entity, 'broadcast') and not entity.broadcast
            ))

  def _get_group_status(self, entity) -> str:
    """Get group status for logging."""
    status = ""
    if getattr(entity, 'left', False):
      status = " (Left)"
    elif getattr(entity, 'kicked', False):
      status = " (Banned)"
    return status

  async def _get_group_details(self, entity) -> Tuple[str, str, str]:
    """Get detailed group information."""
    participants = "N/A"
    try:
      if hasattr(entity, 'participants_count'):
        participants = entity.participants_count
      else:
        full_chat = await self.client.get_entity(entity)
        if hasattr(full_chat, 'participants_count'):
          participants = full_chat.participants_count
    except Exception as e:
      logger.debug(f"Failed to get participants count: {e}")

    description = "No description"
    try:
      if hasattr(entity, 'about'):
        description = entity.about if entity.about else "No description"
    except Exception as e:
      logger.debug(f"Failed to get description: {e}")

    invite_link = "N/A"
    try:
      if hasattr(entity, 'username') and entity.username:
        invite_link = f"https://t.me/{entity.username}"
      elif hasattr(entity, 'admin_rights') and entity.admin_rights:
        export_result = await self.client(ExportChatInviteRequest(entity))
        if export_result and hasattr(export_result, 'link'):
          invite_link = export_result.link
      else:
        invite_link = "No admin rights to export invite"
    except Exception as e:
      logger.debug(f"Failed to get invite link: {e}")
      invite_link = f"Error: {e}"

    return participants, description, invite_link

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
        if self.telethon_session:
          await self.telethon_session.save_updates()
        await self.client.disconnect()
        logger.info("Telegram client disconnected and session saved")
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