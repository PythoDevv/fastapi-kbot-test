from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select

from bots.Kitobmillatbot.cache import (
    ChannelSnapshot,
    ZayafkaChannelSnapshot,
    runtime_cache,
)
from bots.Kitobmillatbot.models import (
    Channel,
    UserZayafkaChannel,
    ZayafkaChannel,
)
from bots.Kitobmillatbot.repositories.base import BaseRepository


class ChannelRepository(BaseRepository[Channel]):
    model = Channel

    async def list_active(self) -> list[Channel]:
        stmt = (
            select(Channel)
            .where(Channel.active.is_(True))
            .order_by(Channel.id)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_active_cached(self) -> list[ChannelSnapshot]:
        cached = runtime_cache.get_active_channels()
        if cached is not None:
            return cached

        rows = await self.list_active()
        snapshots = [
            ChannelSnapshot(
                id=channel.id,
                channel_id=channel.channel_id,
                channel_name=channel.channel_name,
                channel_link=channel.channel_link,
                skip_check=channel.skip_check,
            )
            for channel in rows
        ]
        runtime_cache.set_active_channels(snapshots)
        return snapshots

    async def list_all(self) -> list[Channel]:
        return list(
            (await self.session.execute(select(Channel).order_by(Channel.id)))
            .scalars()
            .all()
        )


class ZayafkaRepository(BaseRepository[ZayafkaChannel]):
    model = ZayafkaChannel

    async def list_ordered(self) -> list[ZayafkaChannel]:
        stmt = select(ZayafkaChannel).order_by(
            ZayafkaChannel.sequence, ZayafkaChannel.id
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_ordered_cached(self) -> list[ZayafkaChannelSnapshot]:
        cached = runtime_cache.get_zayafka_channels()
        if cached is not None:
            return cached

        rows = await self.list_ordered()
        snapshots = [
            ZayafkaChannelSnapshot(
                id=channel.id,
                channel_id=channel.channel_id,
                name=channel.name,
                link=channel.link,
                sequence=channel.sequence,
            )
            for channel in rows
        ]
        runtime_cache.set_zayafka_channels(snapshots)
        return snapshots

    async def get_user_recorded_ids(self, user_id: int) -> set[int]:
        stmt = select(UserZayafkaChannel.zayafka_channel_id).where(
            UserZayafkaChannel.user_id == user_id,
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return set(rows)

    async def mark_requested(self, user_id: int, zayafka_channel_id: int) -> None:
        stmt = (
            insert(UserZayafkaChannel)
            .values(
                user_id=user_id,
                zayafka_channel_id=zayafka_channel_id,
                approved=False,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    UserZayafkaChannel.user_id,
                    UserZayafkaChannel.zayafka_channel_id,
                ]
            )
        )
        await self.session.execute(stmt)
        await self.session.flush()
