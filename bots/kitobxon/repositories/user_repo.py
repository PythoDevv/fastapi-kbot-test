from sqlalchemy import delete, desc, func, select, update
from sqlalchemy.dialects.postgresql import insert

from bots.kitobxon.models import User
from bots.kitobxon.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User
    BULK_LOOKUP_CHUNK_SIZE = 5000

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        return await self.get_by(telegram_id=telegram_id)

    async def get_or_create(
        self, telegram_id: int, username: str | None, fio: str | None
    ) -> tuple[User, bool]:
        stmt = (
            insert(User)
            .values(
                telegram_id=telegram_id,
                username=username or "",
                fio=fio or "",
                step=1,
            )
            .on_conflict_do_nothing(index_elements=[User.telegram_id])
        )
        result = await self.session.execute(stmt)
        user = await self.get_by_telegram_id(telegram_id)
        assert user is not None
        return user, result.rowcount > 0

    async def update_fields(self, telegram_id: int, **values) -> None:
        await self.session.execute(
            update(User).where(User.telegram_id == telegram_id).values(**values)
        )

    async def increment_score(self, user_id: int, delta: int) -> None:
        await self.session.execute(
            update(User).where(User.id == user_id).values(score=User.score + delta)
        )

    async def top_by_score(self, limit: int = 10) -> list[User]:
        stmt = (
            select(User)
            .where(User.is_registered.is_(True))
            .order_by(desc(User.score), User.id)
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def top_by_referrals(self, limit: int = 10) -> list[User]:
        stmt = (
            select(User)
            .where(User.is_registered.is_(True))
            .order_by(desc(User.referrals_count), User.id)
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def all_registered_ids(self) -> list[int]:
        stmt = select(User.telegram_id).where(User.is_registered.is_(True))
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_referred_users(self, referrer_telegram_id: int) -> list[User]:
        stmt = (
            select(User)
            .where(User.referred_by == referrer_telegram_id)
            .order_by(User.id)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_by_telegram_ids(self, telegram_ids: list[int]) -> dict[int, User]:
        if not telegram_ids:
            return {}

        users_by_tid: dict[int, User] = {}
        for start in range(0, len(telegram_ids), self.BULK_LOOKUP_CHUNK_SIZE):
            chunk = telegram_ids[start:start + self.BULK_LOOKUP_CHUNK_SIZE]
            stmt = select(User).where(User.telegram_id.in_(chunk))
            users = (await self.session.execute(stmt)).scalars().all()
            for user in users:
                users_by_tid[user.telegram_id] = user
        return users_by_tid

    async def count_awarded_referrals(self, referrer_telegram_id: int) -> int:
        stmt = select(func.count()).select_from(User).where(
            User.referred_by == referrer_telegram_id,
            User.referral_bonus_awarded.is_(True),
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def count_registered(self) -> int:
        return await self.count(is_registered=True)

    async def count_solved(self) -> int:
        return await self.count(test_solved=True)

    async def get_top_by_score_solved(self, limit: int = 30) -> list[User]:
        """Get top users by score who have solved the test"""
        stmt = (
            select(User)
            .where(User.test_solved.is_(True))
            .order_by(desc(User.score), User.id)
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def delete_by_telegram_id(self, telegram_id: int) -> None:
        """Delete a user by telegram_id"""
        await self.session.execute(
            delete(User).where(User.telegram_id == telegram_id)
        )

    async def delete_all(self) -> None:
        """Delete all users"""
        await self.session.execute(delete(User))

    async def update_all(self, **values) -> None:
        """Update all users with given values"""
        await self.session.execute(update(User).values(**values))
