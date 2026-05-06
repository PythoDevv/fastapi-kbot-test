import json
import random
from datetime import datetime

from sqlalchemy import case, delete, func, select, update

from bots.Kitobmillatbot.cache import runtime_cache
from bots.Kitobmillatbot.config import QuizType
from bots.Kitobmillatbot.models import (
    PollMap,
    Question,
    QuizSettings,
    TestAnswer,
    TestSession,
    User,
)
from bots.Kitobmillatbot.repositories.base import BaseRepository


class QuizRepository(BaseRepository[Question]):
    model = Question
    _QUIZ_LOCK_NAMESPACE = 41001
    _system_random = random.SystemRandom()

    @staticmethod
    def encode_session_questions(
        question_ids: list[int],
        quiz_type: QuizType,
    ) -> str:
        return json.dumps(
            {
                "question_ids": question_ids,
                "quiz_type": quiz_type.value,
            },
            ensure_ascii=False,
        )

    @staticmethod
    def decode_session_questions(
        raw_payload: str | None,
    ) -> tuple[list[int], QuizType | None]:
        if not raw_payload:
            return [], None

        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            return [], None

        if isinstance(payload, list):
            return [int(item) for item in payload], None

        if not isinstance(payload, dict):
            return [], None

        raw_question_ids = payload.get("question_ids")
        question_ids = (
            [int(item) for item in raw_question_ids]
            if isinstance(raw_question_ids, list)
            else []
        )

        raw_quiz_type = payload.get("quiz_type")
        quiz_type = None
        if isinstance(raw_quiz_type, str):
            try:
                quiz_type = QuizType(raw_quiz_type.lower())
            except ValueError:
                quiz_type = None

        return question_ids, quiz_type

    # --- Settings ---
    async def get_settings(self) -> QuizSettings | None:
        stmt = select(QuizSettings).order_by(QuizSettings.id).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def ensure_settings(self) -> QuizSettings:
        existing = await self.get_settings()
        if existing:
            return existing
        settings = QuizSettings()
        self.session.add(settings)
        await self.session.flush()
        return settings

    # --- Questions ---
    async def get_random_questions(self, count: int) -> list[Question]:
        if count <= 0:
            return []

        question_ids = await self.get_all_question_ids()
        if not question_ids:
            return []

        selected_ids = self._system_random.sample(
            question_ids,
            k=min(count, len(question_ids)),
        )
        return await self.get_questions_by_ids(selected_ids)

    async def get_questions_by_ids(self, ids: list[int]) -> list[Question]:
        if not ids:
            return []
        stmt = select(Question).where(Question.id.in_(ids))
        rows = list((await self.session.execute(stmt)).scalars().all())
        order = {qid: i for i, qid in enumerate(ids)}
        rows.sort(key=lambda q: order.get(q.id, 1_000_000))
        return rows

    async def count_questions(self) -> int:
        question_ids = await self.get_all_question_ids()
        return len(question_ids)

    async def get_all_question_ids(self) -> list[int]:
        cached = runtime_cache.get_question_ids()
        if cached is not None:
            return cached

        question_ids = list(
            (
                await self.session.execute(
                    select(Question.id).order_by(Question.id)
                )
            ).scalars().all()
        )
        runtime_cache.set_question_ids(question_ids)
        return question_ids

    # --- Test sessions ---
    async def get_active_session(self, user_id: int) -> TestSession | None:
        stmt = (
            select(TestSession)
            .where(TestSession.user_id == user_id, TestSession.is_completed.is_(False))
            .order_by(TestSession.id.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def acquire_quiz_lock(self, user_id: int) -> None:
        await self.session.execute(
            select(func.pg_advisory_xact_lock(self._QUIZ_LOCK_NAMESPACE, user_id))
        )

    async def has_active_session(self, user_id: int) -> bool:
        return (await self.get_active_session(user_id)) is not None

    async def has_completed_session(self, user_id: int) -> bool:
        stmt = (
            select(TestSession.id)
            .where(TestSession.user_id == user_id, TestSession.is_completed.is_(True))
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None

    async def sum_session_scores(self, user_id: int) -> int:
        stmt = select(func.coalesce(func.sum(TestSession.score), 0)).where(
            TestSession.user_id == user_id
        )
        return int((await self.session.execute(stmt)).scalar_one() or 0)

    async def create_session(
        self, user_id: int, question_ids: list[int], quiz_type: QuizType
    ) -> TestSession:
        session = TestSession(
            user_id=user_id,
            quiz_type=quiz_type,
            questions_json=self.encode_session_questions(question_ids, quiz_type),
            total_questions=len(question_ids),
            current_index=0,
            started_at=datetime.utcnow(),
        )
        self.session.add(session)
        await self.session.flush()
        return session

    async def get_session(self, session_id: int) -> TestSession | None:
        return await self.session.get(TestSession, session_id)

    async def refresh_session(self, test_session: TestSession) -> TestSession:
        await self.session.refresh(test_session)
        return test_session

    async def get_session_for_update(self, session_id: int) -> TestSession | None:
        stmt = (
            select(TestSession)
            .where(TestSession.id == session_id)
            .with_for_update()
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def advance_session(self, session_id: int, new_index: int) -> None:
        await self.session.execute(
            update(TestSession)
            .where(TestSession.id == session_id)
            .values(current_index=new_index)
        )

    async def add_score(self, session_id: int, delta: int) -> None:
        await self.session.execute(
            update(TestSession)
            .where(TestSession.id == session_id)
            .values(score=TestSession.score + delta)
        )

    async def complete_session(self, session_id: int) -> None:
        await self.session.execute(
            update(TestSession)
            .where(TestSession.id == session_id)
            .values(is_completed=True, completed_at=datetime.utcnow())
        )

    async def abandon_active_session(self, user_id: int) -> None:
        """Mark any active session as completed (abandoned)"""
        active = await self.get_active_session(user_id)
        if active:
            await self.complete_session(active.id)

    async def delete_sessions_for_user(self, user_id: int) -> None:
        await self.session.execute(
            delete(TestSession).where(TestSession.user_id == user_id)
        )
        await self.session.flush()

    # --- Answers ---
    async def save_answer(self, answer: TestAnswer) -> TestAnswer:
        self.session.add(answer)
        await self.session.flush()
        return answer

    async def answer_exists(self, session_id: int, question_index: int) -> bool:
        stmt = (
            select(TestAnswer.id)
            .where(
                TestAnswer.session_id == session_id,
                TestAnswer.question_index == question_index,
            )
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None

    async def get_completed_session(self, user_id: int) -> TestSession | None:
        stmt = (
            select(TestSession)
            .where(TestSession.user_id == user_id, TestSession.is_completed.is_(True))
            .order_by(TestSession.id.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_latest_completed_sessions_summary(self) -> list[dict]:
        latest_sessions = (
            select(
                TestSession.user_id.label("user_id"),
                func.max(TestSession.id).label("session_id"),
            )
            .where(TestSession.is_completed.is_(True))
            .group_by(TestSession.user_id)
            .subquery()
        )

        stmt = (
            select(
                User.telegram_id.label("telegram_id"),
                User.fio.label("fio"),
                User.username.label("username"),
                TestSession.id.label("session_id"),
                TestSession.score.label("score"),
                TestSession.total_questions.label("total_questions"),
                TestSession.completed_at.label("completed_at"),
                func.coalesce(func.sum(TestAnswer.time_taken_seconds), 0).label(
                    "total_time_seconds"
                ),
                func.coalesce(
                    func.sum(case((TestAnswer.is_correct.is_(True), 1), else_=0)),
                    0,
                ).label("correct_count"),
                func.coalesce(
                    func.sum(case((TestAnswer.is_correct.is_(False), 1), else_=0)),
                    0,
                ).label("incorrect_count"),
                func.coalesce(
                    func.sum(case((TestAnswer.is_timeout.is_(True), 1), else_=0)),
                    0,
                ).label("timeout_count"),
            )
            .join(latest_sessions, latest_sessions.c.session_id == TestSession.id)
            .join(User, User.id == TestSession.user_id)
            .outerjoin(TestAnswer, TestAnswer.session_id == TestSession.id)
            .group_by(
                User.telegram_id,
                User.fio,
                User.username,
                TestSession.id,
                TestSession.score,
                TestSession.total_questions,
                TestSession.completed_at,
            )
            .order_by(TestSession.completed_at.desc(), TestSession.id.desc())
        )

        rows = (await self.session.execute(stmt)).mappings().all()
        return [dict(row) for row in rows]

    async def get_top_latest_completed_sessions(self, limit: int = 30) -> list[dict]:
        latest_sessions = (
            select(
                TestSession.user_id.label("user_id"),
                func.max(TestSession.id).label("session_id"),
            )
            .where(TestSession.is_completed.is_(True))
            .group_by(TestSession.user_id)
            .subquery()
        )

        stmt = (
            select(
                User.telegram_id.label("telegram_id"),
                User.fio.label("fio"),
                User.username.label("username"),
                TestSession.id.label("session_id"),
                TestSession.score.label("score"),
                TestSession.total_questions.label("total_questions"),
                TestSession.completed_at.label("completed_at"),
            )
            .join(latest_sessions, latest_sessions.c.session_id == TestSession.id)
            .join(User, User.id == TestSession.user_id)
            .order_by(TestSession.score.desc(), TestSession.completed_at.desc(), TestSession.id.desc())
            .limit(limit)
        )

        rows = (await self.session.execute(stmt)).mappings().all()
        return [dict(row) for row in rows]

    async def get_session_answers(self, session_id: int) -> list[TestAnswer]:
        stmt = (
            select(TestAnswer)
            .where(TestAnswer.session_id == session_id)
            .order_by(TestAnswer.question_index)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def sum_answer_time(self, session_id: int) -> int:
        stmt = select(func.coalesce(func.sum(TestAnswer.time_taken_seconds), 0)).where(
            TestAnswer.session_id == session_id
        )
        return int((await self.session.execute(stmt)).scalar_one() or 0)

    # --- Poll map (native quiz mode only) ---
    async def register_poll(
        self,
        poll_id: str,
        message_id: int,
        sent_at: datetime,
        session_id: int,
        question_index: int,
        correct_option_index: int,
        options: list[str],
    ) -> PollMap:
        entry = PollMap(
            poll_id=poll_id,
            message_id=message_id,
            sent_at=sent_at,
            session_id=session_id,
            question_index=question_index,
            correct_option_index=correct_option_index,
            options_json=json.dumps(options, ensure_ascii=False),
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def resolve_poll(self, poll_id: str) -> PollMap | None:
        stmt = select(PollMap).where(PollMap.poll_id == poll_id).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def delete_poll(self, poll_id: str) -> None:
        entry = await self.resolve_poll(poll_id)
        if entry:
            await self.session.delete(entry)
            await self.session.flush()

    async def delete_polls_for_session(self, session_id: int) -> None:
        await self.session.execute(
            delete(PollMap).where(PollMap.session_id == session_id)
        )
        await self.session.flush()

    async def has_polls_for_session(self, session_id: int) -> bool:
        stmt = (
            select(PollMap.id)
            .where(PollMap.session_id == session_id)
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None

    # --- Test questions shuffle helper ---
    @staticmethod
    def shuffle_question_options(
        question: Question,
    ) -> tuple[list[str], int]:
        options = [
            question.correct_answer,
            question.answer_2,
            question.answer_3,
            question.answer_4,
        ]
        random.shuffle(options)
        return options, options.index(question.correct_answer)
