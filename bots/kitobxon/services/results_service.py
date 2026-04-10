from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.models import User
from bots.kitobxon.repositories import QuizRepository, UserRepository


@dataclass
class RatingEntry:
    rank: int
    user: User
    is_current: bool


@dataclass
class UserResult:
    user: User
    final_score: int
    total_questions: int
    passed: bool


class ResultsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.quiz = QuizRepository(session)

    async def get_user_result(self, telegram_id: int) -> UserResult | None:
        user = await self.users.get_by_telegram_id(telegram_id)
        if user is None or not user.test_solved:
            return None
        settings = await self.quiz.get_settings()
        total = settings.questions_per_test if settings else 10
        limit = settings.limit_score if settings else 5
        return UserResult(
            user=user,
            final_score=user.score,
            total_questions=total,
            passed=user.score >= limit,
        )

    async def top_by_score(
        self, telegram_id: int, limit: int = 10
    ) -> list[RatingEntry]:
        top = await self.users.top_by_score(limit)
        return [
            RatingEntry(
                rank=i + 1,
                user=u,
                is_current=u.telegram_id == telegram_id,
            )
            for i, u in enumerate(top)
        ]

    async def top_by_referrals(
        self, telegram_id: int, limit: int = 10
    ) -> list[RatingEntry]:
        top = await self.users.top_by_referrals(limit)
        return [
            RatingEntry(
                rank=i + 1,
                user=u,
                is_current=u.telegram_id == telegram_id,
            )
            for i, u in enumerate(top)
        ]
