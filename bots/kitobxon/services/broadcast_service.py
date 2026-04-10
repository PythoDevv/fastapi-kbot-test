import asyncio
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.repositories import UserRepository
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class BroadcastResult:
    total: int
    sent: int
    failed: int


class BroadcastService:
    BATCH_DELAY = 0.05  # 50ms between messages — ~20 msg/sec, safe for Telegram

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def send_to_all(self, bot: Bot, text: str) -> BroadcastResult:
        user_ids = await self.users.all_registered_ids()
        sent = failed = 0
        for tg_id in user_ids:
            try:
                await bot.send_message(chat_id=tg_id, text=text)
                sent += 1
            except TelegramRetryAfter as e:
                logger.warning("Broadcast flood wait %ds", e.retry_after)
                await asyncio.sleep(e.retry_after)
                try:
                    await bot.send_message(chat_id=tg_id, text=text)
                    sent += 1
                except Exception:
                    failed += 1
            except TelegramForbiddenError:
                failed += 1  # user blocked the bot
            except Exception as exc:
                logger.warning("Broadcast error for %d: %s", tg_id, exc)
                failed += 1
            await asyncio.sleep(self.BATCH_DELAY)
        return BroadcastResult(total=len(user_ids), sent=sent, failed=failed)
