from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from bots.kitobxon.config import QuizType
from bots.kitobxon.models import Channel, Question, User, ZayafkaChannel
from bots.kitobxon.repositories import (
    ChannelRepository,
    QuizRepository,
    ScoreLogRepository,
    UserRepository,
    ZayafkaRepository,
)


@dataclass
class AdminStats:
    total_users: int
    registered_users: int
    solved_users: int
    total_questions: int


class AdminService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.quiz = QuizRepository(session)
        self.channels = ChannelRepository(session)
        self.zayafka = ZayafkaRepository(session)
        self.score_log = ScoreLogRepository(session)

    # --- Stats ---
    async def get_stats(self) -> AdminStats:
        return AdminStats(
            total_users=await self.users.count(),
            registered_users=await self.users.count_registered(),
            solved_users=await self.users.count_solved(),
            total_questions=await self.quiz.count_questions(),
        )

    # --- Users ---
    async def find_user(self, telegram_id: int) -> User | None:
        return await self.users.get_by_telegram_id(telegram_id)

    async def set_score(
        self,
        admin_telegram_id: int,
        admin_fio: str | None,
        target_telegram_id: int,
        new_score: int,
        reason: str | None,
    ) -> User:
        user = await self.users.get_by_telegram_id(target_telegram_id)
        if user is None:
            from bots.kitobxon.exceptions import UserNotFoundError
            raise UserNotFoundError(target_telegram_id)
        old_score = user.score
        await self.users.update_fields(target_telegram_id, score=new_score)
        await self.score_log.log(
            admin_telegram_id=admin_telegram_id,
            admin_fio=admin_fio,
            target_telegram_id=target_telegram_id,
            target_fio=user.fio,
            old_score=old_score,
            new_score=new_score,
            reason=reason,
        )
        user.score = new_score
        return user

    async def toggle_admin(self, target_telegram_id: int, is_admin: bool) -> None:
        await self.users.update_fields(target_telegram_id, is_admin=is_admin)

    async def reset_test(self, target_telegram_id: int) -> None:
        await self.users.update_fields(
            target_telegram_id,
            test_solved=False,
            score=0,
            certificate_received=False,
        )

    # --- Channels ---
    async def add_channel(
        self,
        channel_id: int,
        name: str,
        link: str | None,
        traverse_text: str | None,
    ) -> Channel:
        ch = Channel(
            channel_id=channel_id,
            channel_name=name,
            channel_link=link,
            traverse_text=traverse_text,
            active=True,
        )
        self.session.add(ch)
        await self.session.flush()
        return ch

    async def toggle_channel(self, channel_db_id: int, active: bool) -> None:
        ch = await self.channels.get(channel_db_id)
        if ch:
            ch.active = active
            await self.session.flush()

    async def delete_channel(self, channel_db_id: int) -> None:
        ch = await self.channels.get(channel_db_id)
        if ch:
            await self.channels.delete(ch)

    async def list_channels(self) -> list[Channel]:
        return await self.channels.list_all()

    # --- Zayafka channels ---
    async def add_zayafka_channel(
        self, channel_id: int, name: str, link: str | None, sequence: int = 0
    ) -> ZayafkaChannel:
        zch = ZayafkaChannel(
            channel_id=channel_id,
            name=name,
            link=link,
            sequence=sequence,
        )
        self.session.add(zch)
        await self.session.flush()
        return zch

    async def delete_zayafka_channel(self, db_id: int) -> None:
        zch = await self.zayafka.get(db_id)
        if zch:
            await self.zayafka.delete(zch)

    async def list_zayafka_channels(self) -> list[ZayafkaChannel]:
        return await self.zayafka.list_ordered()

    # --- Questions ---
    async def add_question(
        self,
        text: str,
        correct: str,
        wrong_1: str,
        wrong_2: str,
        wrong_3: str,
    ) -> Question:
        q = Question(
            text=text,
            correct_answer=correct,
            answer_2=wrong_1,
            answer_3=wrong_2,
            answer_4=wrong_3,
        )
        self.session.add(q)
        await self.session.flush()
        return q

    async def delete_question(self, question_id: int) -> None:
        q = await self.quiz.get(question_id)
        if q:
            await self.quiz.delete(q)

    async def list_questions(self) -> list[Question]:
        return await self.quiz.list()

    # --- Quiz settings ---
    async def set_quiz_waiting(self, waiting: bool) -> None:
        s = await self.quiz.ensure_settings()
        s.waiting = waiting

    async def set_quiz_finished(self, finished: bool) -> None:
        s = await self.quiz.ensure_settings()
        s.finished = finished

    async def set_quiz_type(self, quiz_type: QuizType) -> None:
        s = await self.quiz.ensure_settings()
        s.quiz_type = quiz_type

    async def get_settings(self):
        return await self.quiz.ensure_settings()
