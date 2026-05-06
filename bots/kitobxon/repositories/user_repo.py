from sqlalchemy import delete, desc, select, update

from bots.kitobxon.models import User
from bots.kitobxon.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        return await self.get_by(telegram_id=telegram_id)

    async def get_or_create(
        self, telegram_id: int, username: str | None, fio: str | None
    ) -> tuple[User, bool]:
        user = await self.get_by_telegram_id(telegram_id)
        if user:
            return user, False
        user = User(
            telegram_id=telegram_id,
            username=username or "",
            fio=fio or "",
            step=1,
        )
        await self.add(user)
        return user, True

    async def update_fields(self, telegram_id: int, **values) -> None:
        await self.session.execute(
            update(User).where(User.telegram_id == telegram_id).values(**values)
        )

    async def increment_score(self, user_id: int, delta: int) -> None:
        await self.session.execute(
            update(User).where(User.id == user_id).values(score=User.score + delta)
        )

    async def increment_referrals(self, user_id: int, delta: int = 1) -> None:
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(referrals_count=User.referrals_count + delta)
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
