from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bots.kitobxon.config import QuizType, TABLE_PREFIX
from core.base_model import Base, TimestampMixin


def t(name: str) -> str:
    return f"{TABLE_PREFIX}{name}"


def quiz_type_db_values(_enum_cls) -> list[str]:
    # Keep the SQLAlchemy enum values aligned with the current QuizType values.
    return ["web", "quiz", "webapp"]


# =====================================================================
# Users
# =====================================================================
class User(Base, TimestampMixin):
    __tablename__ = t("users")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True, nullable=False
    )
    username: Mapped[str | None] = mapped_column(String(255))
    fio: Mapped[str | None] = mapped_column(String(500))
    mobile_number: Mapped[str | None] = mapped_column(String(50))

    step: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_registered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Flipped on when Telegram answers 403 during a broadcast, cleared again
    # on /start — so a user who comes back is not excluded forever.
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    referrals_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    referred_by: Mapped[int | None] = mapped_column(BigInteger, index=True)
    referral_bonus_awarded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    test_solved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    certificate_received: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    how_did_find: Mapped[str | None] = mapped_column(String(255))

    test_sessions: Mapped[list["TestSession"]] = relationship(
        "bots.kitobxon.models.TestSession",
        back_populates="user", cascade="all, delete-orphan"
    )


# =====================================================================
# Channels (mandatory subscription)
# =====================================================================
class Channel(Base, TimestampMixin):
    __tablename__ = t("channels")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel_name: Mapped[str] = mapped_column(String(500), nullable=False)
    channel_link: Mapped[str | None] = mapped_column(String(500))
    traverse_text: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    skip_check: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


# =====================================================================
# Zayafka channels (join request channels)
# =====================================================================
class ZayafkaChannel(Base, TimestampMixin):
    __tablename__ = t("zayafka_channels")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    link: Mapped[str | None] = mapped_column(String(500))
    sequence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class UserZayafkaChannel(Base):
    __tablename__ = t("user_zayafka_channels")
    __table_args__ = (
        UniqueConstraint("user_id", "zayafka_channel_id", name="uq_user_zayafka"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey(f"{t('users')}.id", ondelete="CASCADE"), nullable=False
    )
    zayafka_channel_id: Mapped[int] = mapped_column(
        ForeignKey(f"{t('zayafka_channels')}.id", ondelete="CASCADE"),
        nullable=False,
    )
    approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


# =====================================================================
# Quiz settings, questions, sessions, answers
# =====================================================================
class QuizSettings(Base, TimestampMixin):
    __tablename__ = t("quiz_settings")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quiz_type: Mapped[QuizType] = mapped_column(
        SAEnum(
            QuizType,
            name="quiz_type_enum",
            values_callable=quiz_type_db_values,
        ),
        default=QuizType.WEB,
        nullable=False,
    )
    limit_score: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    time_limit_seconds: Mapped[int] = mapped_column(
        Integer, default=40, nullable=False
    )
    questions_per_test: Mapped[int] = mapped_column(
        Integer, default=40, nullable=False
    )
    waiting: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    finished: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    waiting_text: Mapped[str | None] = mapped_column(Text)
    finished_text: Mapped[str | None] = mapped_column(Text)
    image_id: Mapped[str | None] = mapped_column(String(500))
    intro_text: Mapped[str | None] = mapped_column(Text)
    require_link: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    require_phone_number: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Question(Base, TimestampMixin):
    __tablename__ = t("questions")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    answer_2: Mapped[str] = mapped_column(Text, nullable=False)
    answer_3: Mapped[str] = mapped_column(Text, nullable=False)
    answer_4: Mapped[str] = mapped_column(Text, nullable=False)


class TestSession(Base, TimestampMixin):
    __tablename__ = t("test_sessions")
    __table_args__ = (
        Index("ix_kitobxon_test_sessions_user_completed_id", "user_id", "is_completed", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey(f"{t('users')}.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    quiz_type: Mapped[QuizType] = mapped_column(
        SAEnum(
            QuizType,
            name="quiz_type_enum",
            values_callable=quiz_type_db_values,
        ),
        default=QuizType.WEB,
        nullable=False,
    )
    questions_json: Mapped[str | None] = mapped_column(Text)
    current_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_questions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user: Mapped["User"] = relationship(
        "bots.kitobxon.models.User",
        back_populates="test_sessions",
    )
    answers: Mapped[list["TestAnswer"]] = relationship(
        "bots.kitobxon.models.TestAnswer",
        back_populates="session", cascade="all, delete-orphan"
    )


class TestAnswer(Base, TimestampMixin):
    __tablename__ = t("test_answers")
    __table_args__ = (
        Index("ix_kitobxon_test_answers_session_question", "session_id", "question_index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey(f"{t('test_sessions')}.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey(f"{t('questions')}.id", ondelete="SET NULL"),
        nullable=True,
    )
    question_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    question_text: Mapped[str | None] = mapped_column(Text)
    selected_answer: Mapped[str | None] = mapped_column(Text)
    correct_answer: Mapped[str | None] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_timeout: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    time_taken_seconds: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )

    session: Mapped["TestSession"] = relationship(
        "bots.kitobxon.models.TestSession",
        back_populates="answers",
    )


class PollMap(Base, TimestampMixin):
    """Maps Telegram poll_id → active test session question (quiz mode only)."""

    __tablename__ = t("poll_map")
    __table_args__ = (
        Index("ix_kitobxon_poll_map_session_id", "session_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    poll_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey(f"{t('test_sessions')}.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_index: Mapped[int] = mapped_column(Integer, nullable=False)
    correct_option_index: Mapped[int] = mapped_column(Integer, nullable=False)
    options_json: Mapped[str] = mapped_column(Text, nullable=False)  # list[str] JSON


# =====================================================================
# Content (static texts, images, books)
# =====================================================================
class ContentText(Base, TimestampMixin):
    __tablename__ = t("content_texts")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    image_id: Mapped[str | None] = mapped_column(String(500))
    require_link: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ActivityBook(Base, TimestampMixin):
    __tablename__ = t("activity_books")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str | None] = mapped_column(String(500))
    button_text: Mapped[str | None] = mapped_column(String(500))
    button_url: Mapped[str | None] = mapped_column(String(500))
    file_id: Mapped[str | None] = mapped_column(String(500))


class ScoreChangeLog(Base, TimestampMixin):
    __tablename__ = t("score_change_log")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    admin_fio: Mapped[str | None] = mapped_column(String(500))
    target_telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    target_fio: Mapped[str | None] = mapped_column(String(500))
    old_score: Mapped[int] = mapped_column(Integer, nullable=False)
    new_score: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)


# =====================================================================
# Broadcast jobs (persistent + resumable — engine lives in core/broadcast.py)
# =====================================================================
class BroadcastJob(Base, TimestampMixin):
    """One "Reklama jo'natish" run.

    The row is the source of truth: if the process dies mid-run, the next boot
    picks the job up from ``cursor_id`` instead of silently dropping everyone
    who had not been reached yet.
    """

    __tablename__ = t("broadcast_jobs")
    __table_args__ = (
        Index("ix_kitobxon_broadcast_jobs_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # pending | running | done | failed | cancelled
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Recipients that answered 403. Recorded for reporting only — they are
    # still attempted on every broadcast, because a block can be undone.
    blocked: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Last processed users.id — or broadcast_failures.id when this is a retry job.
    cursor_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Where the live progress / final report message lives.
    status_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    status_message_id: Mapped[int | None] = mapped_column(BigInteger)

    # Set when this job only re-sends the failures of an earlier job.
    retry_of_job_id: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Lease held by the process currently sending this job. Webhook and polling
    # can share one database; without it both would resume the same job and
    # every user would receive the message twice.
    locked_by: Mapped[str | None] = mapped_column(String(64))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BroadcastFailure(Base, TimestampMixin):
    """One row per recipient a broadcast could not reach.

    Replaces the old bare ``failed`` counter: without this there is no way to
    tell who missed the message, nor to re-send only to them.
    """

    __tablename__ = t("broadcast_failures")
    __table_args__ = (
        Index("ix_kitobxon_broadcast_failures_job", "job_id", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey(f"{t('broadcast_jobs')}.id", ondelete="CASCADE"), nullable=False
    )
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # blocked | not_found | flood | error
    reason: Mapped[str] = mapped_column(String(20), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
