from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.logging import get_logger

logger = get_logger(__name__)


class LoggingMiddleware(BaseMiddleware):
    """Logs incoming updates with user info."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user:
            username = f"@{user.username}" if user.username else f"ID:{user.id}"
            msg_type = event.__class__.__name__

            # Log message text if available
            if hasattr(event, "text"):
                logger.info(f"{username} ({msg_type}): {event.text[:50]}")
            elif hasattr(event, "data"):
                logger.info(f"{username} ({msg_type}): {event.data}")
            else:
                logger.info(f"{username} ({msg_type})")

        return await handler(event, data)


class DbSessionMiddleware(BaseMiddleware):
    """Opens an AsyncSession per update, commits on success, rolls back on error."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        super().__init__()
        self._session_factory = session_factory

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self._session_factory() as session:
            data["session"] = session
            try:
                result = await handler(event, data)
            except Exception:
                await session.rollback()
                raise
            else:
                await session.commit()
                return result
