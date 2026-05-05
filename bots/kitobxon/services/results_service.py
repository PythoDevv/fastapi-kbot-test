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


@dataclass
class DetailedTestResult:
    score: int
    total_questions: int
    total_time_seconds: int
    correct_count: int
    timeout_count: int
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
        self, telegram_id: int, limit: int = 30
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

    async def top_test_takers(
        self, telegram_id: int, limit: int = 30
    ) -> list[RatingEntry]:
        top = await self.users.get_top_by_score_solved(limit)
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

    async def get_detailed_test_result(self, telegram_id: int) -> DetailedTestResult | None:
        user = await self.users.get_by_telegram_id(telegram_id)
        if user is None or not user.test_solved:
            return None

        session = await self.quiz.get_completed_session(user.id)
        if session is None:
            return None

        answers = await self.quiz.get_session_answers(session.id)
        if not answers:
            return DetailedTestResult(
                score=0,
                total_questions=session.total_questions,
                total_time_seconds=0,
                correct_count=0,
                timeout_count=0,
                passed=False,
            )

        total_time = sum(a.time_taken_seconds for a in answers)
        correct_count = sum(1 for a in answers if a.is_correct)
        timeout_count = sum(1 for a in answers if a.is_timeout)

        settings = await self.quiz.get_settings()
        limit_score = settings.limit_score if settings else 5

        return DetailedTestResult(
            score=session.score,
            total_questions=session.total_questions,
            total_time_seconds=total_time,
            correct_count=correct_count,
            timeout_count=timeout_count,
            passed=session.score >= limit_score,
        )
