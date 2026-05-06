from dataclasses import dataclass

from sqlalchemy import delete, desc, func, select, update
from sqlalchemy.dialects.postgresql import insert

from bots.kitobxon.models import User
from bots.kitobxon.repositories.base import BaseRepository


@dataclass
class ReferralScoreRepairCandidate:
    user_id: int
    telegram_id: int
    fio: str | None
    old_score: int
    new_score: int
    referral_count: int


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
                fio=fio or None,
                step=0,
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

    async def get_referral_score_repair_candidates(
        self,
        *,
        score_threshold: int = 10,
        referral_cap: int = 5,
    ) -> list[ReferralScoreRepairCandidate]:
        referred = (
            select(
                User.referred_by.label("referrer_telegram_id"),
                func.count(User.id).label("referral_count"),
            )
            .where(
                User.referred_by.is_not(None),
                User.is_registered.is_(True),
            )
            .group_by(User.referred_by)
            .subquery()
        )

        target_score = func.least(referred.c.referral_count, referral_cap)
        stmt = (
            select(
                User.id,
                User.telegram_id,
                User.fio,
                User.score,
                target_score.label("new_score"),
                referred.c.referral_count,
            )
            .join(referred, referred.c.referrer_telegram_id == User.telegram_id)
            .where(
                User.is_registered.is_(True),
                User.score < score_threshold,
                User.score < target_score,
            )
            .order_by(User.id)
        )

        rows = (await self.session.execute(stmt)).all()
        return [
            ReferralScoreRepairCandidate(
                user_id=row.id,
                telegram_id=row.telegram_id,
                fio=row.fio,
                old_score=row.score,
                new_score=int(row.new_score),
                referral_count=int(row.referral_count),
            )
            for row in rows
        ]
