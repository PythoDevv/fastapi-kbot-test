from sqlalchemy import select

from bots.kitobxon.models import (
    Channel,
    UserZayafkaChannel,
    ZayafkaChannel,
)
from bots.kitobxon.repositories.base import BaseRepository


class ChannelRepository(BaseRepository[Channel]):
    model = Channel

    async def list_active(self) -> list[Channel]:
        stmt = (
            select(Channel)
            .where(Channel.active.is_(True))
            .order_by(Channel.id)
        )
        return list((await self.session.execute(stmt)).scalars().all())

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

    async def get_user_recorded_ids(self, user_id: int) -> set[int]:
        stmt = select(UserZayafkaChannel.zayafka_channel_id).where(
            UserZayafkaChannel.user_id == user_id,
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return set(rows)

    async def mark_requested(self, user_id: int, zayafka_channel_id: int) -> None:
        stmt = select(UserZayafkaChannel).where(
            UserZayafkaChannel.user_id == user_id,
            UserZayafkaChannel.zayafka_channel_id == zayafka_channel_id,
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if not existing:
            self.session.add(
                UserZayafkaChannel(
                    user_id=user_id,
                    zayafka_channel_id=zayafka_channel_id,
                    approved=False,
                )
            )
        await self.session.flush()
