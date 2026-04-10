from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
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
        SAEnum(QuizType, name="quiz_type_enum"),
        default=QuizType.WEB,
        nullable=False,
    )
    limit_score: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    time_limit_seconds: Mapped[int] = mapped_column(
        Integer, default=30, nullable=False
    )
    questions_per_test: Mapped[int] = mapped_column(
        Integer, default=10, nullable=False
    )
    waiting: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    finished: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    waiting_text: Mapped[str | None] = mapped_column(Text)
    finished_text: Mapped[str | None] = mapped_column(Text)
    image_id: Mapped[str | None] = mapped_column(String(500))
    intro_text: Mapped[str | None] = mapped_column(Text)
    require_link: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


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
    questions_json: Mapped[str | None] = mapped_column(Text)  # list[int] JSON
    current_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_questions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user: Mapped["User"] = relationship(back_populates="test_sessions")
    answers: Mapped[list["TestAnswer"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class TestAnswer(Base, TimestampMixin):
    __tablename__ = t("test_answers")

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

    session: Mapped["TestSession"] = relationship(back_populates="answers")


class PollMap(Base, TimestampMixin):
    """Maps Telegram poll_id → active test session question (quiz mode only)."""

    __tablename__ = t("poll_map")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    poll_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
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
