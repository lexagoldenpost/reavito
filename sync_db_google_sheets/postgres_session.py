# postgres_session.py
from typing import Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telethon.crypto import AuthKey
from telethon.sessions import StringSession
from telethon.tl.types import updates
from models import TelethonSession as TelethonSessionModel
from common.database import AsyncSessionLocal
from common.logging_config import setup_logger

# Настройка логгера
logger = setup_logger("postgres_session")


class PostgresSession(StringSession):
  """Асинхронная сессия Telethon с хранением в PostgreSQL"""

  def __init__(self, session_name: str = "default"):
    super().__init__()
    if not isinstance(session_name, str):
      raise ValueError("session_name must be a string")
    self.session_name = session_name.strip()
    if not self.session_name:
      raise ValueError("session_name cannot be empty")

    self._pending_updates: Dict[str, Any] = {}
    self._dc_id: Optional[int] = None
    self._server_address: Optional[str] = None
    self._port: Optional[int] = None

  # Синхронные методы для Telethon
  def set_dc(self, dc_id: int, server_address: str, port: int):
    """Синхронное сохранение данных центра (для Telethon)"""
    self._dc_id = dc_id
    self._server_address = server_address
    self._port = port
    self._pending_updates.update({
      'dc_id': dc_id,
      'server_address': server_address,
      'port': port
    })
    return self

  def set_update_state(self, entity_id: int, state):
    """Синхронное сохранение состояния (для Telethon)"""
    if state:
      self._pending_updates.update({
        'update_state': state.SerializeToString(),
        'pts': state.pts,
        'qts': state.qts,
        'date': state.date,
        'seq': state.seq
      })
    return self

  # Асинхронные методы для работы с БД
  async def save_updates(self):
    """Сохранить все ожидающие обновления в БД"""
    try:
      if self._pending_updates:
        await self._update_or_create_session(**self._pending_updates)
        self._pending_updates.clear()
        logger.debug("Session updates saved to database")
    except Exception as e:
      logger.error(f"Failed to save session updates: {e}")
      raise

  async def _get_db_session(self) -> Optional[TelethonSessionModel]:
    """Получить сессию из БД"""
    async with AsyncSessionLocal() as session:
      result = await session.execute(
          select(TelethonSessionModel)
          .where(TelethonSessionModel.session_id == self.session_name)
      )
      return result.scalar_one_or_none()

  async def _update_or_create_session(self, **kwargs):
    """Обновить или создать сессию в БД"""
    async with AsyncSessionLocal() as session:
      db_session = await self._get_db_session()
      if db_session:
        for key, value in kwargs.items():
          setattr(db_session, key, value)
      else:
        db_session = TelethonSessionModel(
            session_id=self.session_name,
            **kwargs
        )
        session.add(db_session)
      await session.commit()

  async def get_update_state(self, entity_id: int) -> Optional[updates.State]:
    """Получить состояние обновления"""
    db_session = await self._get_db_session()
    if db_session and db_session.update_state:
      return updates.State(
          pts=db_session.pts,
          qts=db_session.qts,
          date=db_session.date,
          seq=db_session.seq,
          unread_count=0
      )
    return None

  async def get_auth_key(self) -> Optional[AuthKey]:
    """Получить ключ авторизации"""
    db_session = await self._get_db_session()
    if db_session and db_session.auth_key:
      return AuthKey(data=db_session.auth_key)
    return None

  async def set_auth_key(self, auth_key: Optional[AuthKey]) -> None:
    """Установить ключ авторизации"""
    await self._update_or_create_session(
        auth_key=auth_key.key if auth_key else None
    )

  async def delete(self) -> None:
    """Удалить сессию из БД"""
    async with AsyncSessionLocal() as session:
      db_session = await self._get_db_session()
      if db_session:
        await session.delete(db_session)
        await session.commit()

  def __str__(self) -> str:
    return f"PostgresSession(session_name='{self.session_name}')"