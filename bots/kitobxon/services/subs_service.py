from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.cache import (
    ChannelSnapshot,
    ZayafkaChannelSnapshot,
    runtime_cache,
)
from bots.kitobxon.repositories import ChannelRepository, ZayafkaRepository
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SubscriptionStatus:
    all_subscribed: bool
    missing_channels: list[ChannelSnapshot]
    missing_zayafka: list[ZayafkaChannelSnapshot]


class SubsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.channels = ChannelRepository(session)
        self.zayafka = ZayafkaRepository(session)

    async def check_user(
        self, bot: Bot, telegram_id: int, user_db_id: int
    ) -> SubscriptionStatus:
        missing: list[ChannelSnapshot] = []
        for ch in await self.channels.list_active_cached():
            if ch.skip_check:
                continue
            if not await self._is_member(bot, ch.channel_id, telegram_id):
                missing.append(ch)

        requested_or_approved = await self.zayafka.get_user_recorded_ids(user_db_id)
        missing_zayafka: list[ZayafkaChannelSnapshot] = []
        for zch in await self.zayafka.list_ordered_cached():
            if zch.id not in requested_or_approved:
                if not await self._is_member(bot, zch.channel_id, telegram_id):
                    missing_zayafka.append(zch)

        return SubscriptionStatus(
            all_subscribed=not missing and not missing_zayafka,
            missing_channels=missing,
            missing_zayafka=missing_zayafka,
        )

    async def _is_member(
        self, bot: Bot, channel_id: int, telegram_id: int
    ) -> bool:
        if runtime_cache.has_recent_member(channel_id, telegram_id):
            return True

        try:
            member = await bot.get_chat_member(
                chat_id=channel_id, user_id=telegram_id
            )
            is_member = member.status in ("member", "creator", "administrator")
            if is_member:
                runtime_cache.remember_member(channel_id, telegram_id)
            else:
                runtime_cache.forget_member(channel_id, telegram_id)
            return is_member
        except TelegramAPIError as exc:
            logger.warning(
                "Failed to check membership chat=%s user=%s: %s",
                channel_id,
                telegram_id,
                exc,
            )
            return False

    async def mark_zayafka_requested(
        self, user_db_id: int, zayafka_channel_telegram_id: int
    ) -> None:
        zlist = await self.zayafka.list_ordered_cached()
        match = next(
            (z for z in zlist if z.channel_id == zayafka_channel_telegram_id),
            None,
        )
        if match:
            await self.zayafka.mark_requested(user_db_id, match.id)
