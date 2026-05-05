from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.config import QuizType
from bots.kitobxon.exceptions import (
    AlreadySolvedError,
    NoQuestionsError,
    QuizAlreadyStartedError,
    QuizFinishedError,
    QuizNotActiveError,
    QuizWaitingError,
    UserNotFoundError,
    UserNotRegisteredError,
)
from bots.kitobxon.models import (
    PollMap,
    Question,
    QuizSettings,
    TestAnswer,
    TestSession,
)
from bots.kitobxon.repositories import QuizRepository, UserRepository


@dataclass
class QuestionPayload:
    question: Question
    index: int
    total: int
    options: list[str]
    correct_option_index: int


@dataclass
class StartResult:
    session: TestSession
    quiz_type: QuizType
    settings: QuizSettings
    first_question: QuestionPayload


@dataclass
class AnswerResult:
    is_last: bool
    score: int
    total_questions: int
    next_question: QuestionPayload | None


class QuizService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.quiz = QuizRepository(session)

    # ---------- Settings ----------
    async def get_settings(self) -> QuizSettings:
        settings = await self.quiz.get_settings()
        if settings is None:
            raise QuizNotActiveError("Quiz sozlamalari topilmadi")
        if not settings.active:
            raise QuizNotActiveError()
        return settings

    # ---------- Start ----------
    async def start_session(self, telegram_id: int) -> StartResult:
        user = await self.users.get_by_telegram_id(telegram_id)
        if user is None:
            raise UserNotFoundError(telegram_id)
        if not user.is_registered:
            raise UserNotRegisteredError()
        if user.test_solved:
            raise AlreadySolvedError()

        await self.quiz.acquire_quiz_lock(user.id)

        if await self.quiz.has_active_session(user.id):
            raise QuizAlreadyStartedError()

        settings = await self.get_settings()
        if settings.waiting:
            raise QuizWaitingError()
        if settings.finished:
            raise QuizFinishedError()

        available_questions = await self.quiz.count_questions()
        question_limit = min(settings.questions_per_test, available_questions)
        questions = await self.quiz.get_random_questions(question_limit)
        if not questions:
            raise NoQuestionsError()

        test_session = await self.quiz.create_session(
            user_id=user.id,
            question_ids=[q.id for q in questions],
            quiz_type=settings.quiz_type,
        )

        first_payload = self._build_payload(
            question=questions[0],
            index=0,
            total=len(questions),
        )
        return StartResult(
            session=test_session,
            quiz_type=settings.quiz_type,
            settings=settings,
            first_question=first_payload,
        )

    async def get_session_quiz_type(self, session_id: int) -> QuizType | None:
        test_session = await self.quiz.get_session(session_id)
        if test_session is None:
            return None
        session_quiz_type = getattr(test_session, "quiz_type", None)
        if session_quiz_type is not None:
            return session_quiz_type
        _, quiz_type = self.quiz.decode_session_questions(test_session.questions_json)
        if quiz_type is not None:
            return quiz_type
        if await self.quiz.has_polls_for_session(session_id):
            return QuizType.QUIZ
        settings = await self.quiz.get_settings()
        return settings.quiz_type if settings else QuizType.WEB

    # ---------- Fetch ----------
    async def get_current_payload(
        self, session_id: int
    ) -> QuestionPayload | None:
        test_session = await self.quiz.get_session(session_id)
        if test_session is None or test_session.is_completed:
            return None
        question_ids, _ = self.quiz.decode_session_questions(test_session.questions_json)
        if test_session.current_index >= len(question_ids):
            return None
        question = await self.quiz.get(question_ids[test_session.current_index])
        if question is None:
            return None
        return self._build_payload(
            question=question,
            index=test_session.current_index,
            total=test_session.total_questions,
        )

    # ---------- Submit ----------
    async def submit_answer(
        self,
        session_id: int,
        question_index: int,
        selected_text: str,
        time_taken: int,
        is_timeout: bool = False,
    ) -> AnswerResult:
        test_session = await self.quiz.get_session_for_update(session_id)
        if test_session is None:
            raise QuizNotActiveError("Session topilmadi")
        if test_session.is_completed:
            raise QuizFinishedError()
        if question_index != test_session.current_index:
            if (
                question_index < test_session.current_index
                and await self.quiz.answer_exists(session_id, question_index)
            ):
                current_payload = await self.get_current_payload(session_id)
                return AnswerResult(
                    is_last=current_payload is None,
                    score=test_session.score,
                    total_questions=test_session.total_questions,
                    next_question=current_payload,
                )
            raise QuizNotActiveError("Noto'g'ri savol tartibi")
        if await self.quiz.answer_exists(session_id, question_index):
            current_payload = await self.get_current_payload(session_id)
            return AnswerResult(
                is_last=current_payload is None,
                score=test_session.score,
                total_questions=test_session.total_questions,
                next_question=current_payload,
            )

        question_ids, _ = self.quiz.decode_session_questions(test_session.questions_json)
        if question_index >= len(question_ids):
            raise QuizNotActiveError("Savol tartibi buzilgan")
        question = await self.quiz.get(question_ids[question_index])
        if question is None:
            raise QuizNotActiveError("Savol topilmadi")

        is_correct = (
            not is_timeout
            and selected_text.strip() == question.correct_answer.strip()
        )

        await self.quiz.save_answer(
            TestAnswer(
                session_id=session_id,
                question_id=question.id,
                question_index=question_index,
                question_text=question.text,
                selected_answer=selected_text if not is_timeout else None,
                correct_answer=question.correct_answer,
                is_correct=is_correct,
                is_timeout=is_timeout,
                time_taken_seconds=time_taken,
            )
        )

        if is_correct:
            await self.quiz.add_score(session_id, 1)

        next_index = question_index + 1
        is_last = next_index >= test_session.total_questions

        if is_last:
            await self.quiz.complete_session(session_id)
            current_score = test_session.score + (1 if is_correct else 0)
            await self._finalize_session(test_session.user_id, current_score)
            return AnswerResult(
                is_last=True,
                score=current_score,
                total_questions=test_session.total_questions,
                next_question=None,
            )

        await self.quiz.advance_session(session_id, next_index)
        next_question = await self.quiz.get(question_ids[next_index])
        assert next_question is not None
        next_payload = self._build_payload(
            question=next_question,
            index=next_index,
            total=test_session.total_questions,
        )
        return AnswerResult(
            is_last=False,
            score=test_session.score + (1 if is_correct else 0),
            total_questions=test_session.total_questions,
            next_question=next_payload,
        )

    async def _finalize_session(self, user_id: int, final_score: int) -> None:
        user = await self.users.get(user_id)
        assert user is not None
        await self.users.update_fields(
            user.telegram_id,
            test_solved=True,
        )
        await self.users.increment_score(user.id, final_score)

    # ---------- Native poll helpers ----------
    async def register_poll(
        self,
        poll_id: str,
        message_id: int,
        sent_at,
        session_id: int,
        payload: QuestionPayload,
    ) -> PollMap:
        return await self.quiz.register_poll(
            poll_id=poll_id,
            message_id=message_id,
            sent_at=sent_at,
            session_id=session_id,
            question_index=payload.index,
            correct_option_index=payload.correct_option_index,
            options=payload.options,
        )

    async def resolve_poll(self, poll_id: str) -> PollMap | None:
        return await self.quiz.resolve_poll(poll_id)

    async def delete_poll(self, poll_id: str) -> None:
        await self.quiz.delete_poll(poll_id)

    async def delete_session_polls(self, session_id: int) -> None:
        await self.quiz.delete_polls_for_session(session_id)

    # ---------- Utilities ----------
    def _build_payload(
        self,
        question: Question,
        index: int,
        total: int,
    ) -> QuestionPayload:
        options, correct_idx = QuizRepository.shuffle_question_options(question)
        return QuestionPayload(
            question=question,
            index=index,
            total=total,
            options=options,
            correct_option_index=correct_idx,
        )
