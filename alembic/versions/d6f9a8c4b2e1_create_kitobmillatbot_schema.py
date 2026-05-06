"""create kitobmillatbot schema

Revision ID: d6f9a8c4b2e1
Revises: c7f8a9b0d1e2
Create Date: 2026-05-06 17:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d6f9a8c4b2e1"
down_revision: Union[str, None] = "c7f8a9b0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    quiz_type_enum = postgresql.ENUM(
        "web",
        "quiz",
        "webapp",
        name="kitobmillatbot_quiz_type_enum",
    )
    quiz_type_enum.create(op.get_bind(), checkfirst=True)
    quiz_type_column = postgresql.ENUM(
        "web",
        "quiz",
        "webapp",
        name="kitobmillatbot_quiz_type_enum",
        create_type=False,
    )

    op.create_table(
        "kitobmillatbot_activity_books",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("button_text", sa.String(length=500), nullable=True),
        sa.Column("button_url", sa.String(length=500), nullable=True),
        sa.Column("file_id", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "kitobmillatbot_channels",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_name", sa.String(length=500), nullable=False),
        sa.Column("channel_link", sa.String(length=500), nullable=True),
        sa.Column("traverse_text", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("skip_check", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "kitobmillatbot_content_texts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=50), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("image_id", sa.String(length=500), nullable=True),
        sa.Column("require_link", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_table(
        "kitobmillatbot_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("correct_answer", sa.Text(), nullable=False),
        sa.Column("answer_2", sa.Text(), nullable=False),
        sa.Column("answer_3", sa.Text(), nullable=False),
        sa.Column("answer_4", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "kitobmillatbot_quiz_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quiz_type", quiz_type_column, nullable=False),
        sa.Column("limit_score", sa.Integer(), nullable=False),
        sa.Column("time_limit_seconds", sa.Integer(), nullable=False),
        sa.Column("questions_per_test", sa.Integer(), nullable=False),
        sa.Column("waiting", sa.Boolean(), nullable=False),
        sa.Column("finished", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("waiting_text", sa.Text(), nullable=True),
        sa.Column("finished_text", sa.Text(), nullable=True),
        sa.Column("image_id", sa.String(length=500), nullable=True),
        sa.Column("intro_text", sa.Text(), nullable=True),
        sa.Column("require_link", sa.Boolean(), nullable=False),
        sa.Column("require_phone_number", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "kitobmillatbot_score_change_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("admin_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("admin_fio", sa.String(length=500), nullable=True),
        sa.Column("target_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("target_fio", sa.String(length=500), nullable=True),
        sa.Column("old_score", sa.Integer(), nullable=False),
        sa.Column("new_score", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "kitobmillatbot_users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("fio", sa.String(length=500), nullable=True),
        sa.Column("mobile_number", sa.String(length=50), nullable=True),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("is_registered", sa.Boolean(), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("referrals_count", sa.Integer(), nullable=False),
        sa.Column("referred_by", sa.BigInteger(), nullable=True),
        sa.Column("referral_bonus_awarded", sa.Boolean(), nullable=False),
        sa.Column("test_solved", sa.Boolean(), nullable=False),
        sa.Column("certificate_received", sa.Boolean(), nullable=False),
        sa.Column("how_did_find", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_kitobmillatbot_users_referred_by"),
        "kitobmillatbot_users",
        ["referred_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_kitobmillatbot_users_telegram_id"),
        "kitobmillatbot_users",
        ["telegram_id"],
        unique=True,
    )
    op.create_table(
        "kitobmillatbot_zayafka_channels",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("link", sa.String(length=500), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "kitobmillatbot_test_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_completed", sa.Boolean(), nullable=False),
        sa.Column("quiz_type", quiz_type_column, nullable=False),
        sa.Column("questions_json", sa.Text(), nullable=True),
        sa.Column("current_index", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("total_questions", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["kitobmillatbot_users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_kitobmillatbot_test_sessions_user_id"),
        "kitobmillatbot_test_sessions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_kitobmillatbot_test_sessions_user_completed_id",
        "kitobmillatbot_test_sessions",
        ["user_id", "is_completed", "id"],
        unique=False,
    )
    op.create_table(
        "kitobmillatbot_user_zayafka_channels",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("zayafka_channel_id", sa.Integer(), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["kitobmillatbot_users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["zayafka_channel_id"],
            ["kitobmillatbot_zayafka_channels.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "zayafka_channel_id",
            name="uq_user_zayafka",
        ),
    )
    op.create_table(
        "kitobmillatbot_poll_map",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("poll_id", sa.String(length=128), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("question_index", sa.Integer(), nullable=False),
        sa.Column("correct_option_index", sa.Integer(), nullable=False),
        sa.Column("options_json", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["kitobmillatbot_test_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_kitobmillatbot_poll_map_poll_id"),
        "kitobmillatbot_poll_map",
        ["poll_id"],
        unique=True,
    )
    op.create_index(
        "ix_kitobmillatbot_poll_map_session_id",
        "kitobmillatbot_poll_map",
        ["session_id"],
        unique=False,
    )
    op.create_table(
        "kitobmillatbot_test_answers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=True),
        sa.Column("question_index", sa.Integer(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=True),
        sa.Column("selected_answer", sa.Text(), nullable=True),
        sa.Column("correct_answer", sa.Text(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("is_timeout", sa.Boolean(), nullable=False),
        sa.Column("time_taken_seconds", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["kitobmillatbot_questions.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["kitobmillatbot_test_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_kitobmillatbot_test_answers_session_id"),
        "kitobmillatbot_test_answers",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        "ix_kitobmillatbot_test_answers_session_question",
        "kitobmillatbot_test_answers",
        ["session_id", "question_index"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_kitobmillatbot_test_answers_session_question",
        table_name="kitobmillatbot_test_answers",
    )
    op.drop_index(
        op.f("ix_kitobmillatbot_test_answers_session_id"),
        table_name="kitobmillatbot_test_answers",
    )
    op.drop_table("kitobmillatbot_test_answers")
    op.drop_index(
        "ix_kitobmillatbot_poll_map_session_id",
        table_name="kitobmillatbot_poll_map",
    )
    op.drop_index(
        op.f("ix_kitobmillatbot_poll_map_poll_id"),
        table_name="kitobmillatbot_poll_map",
    )
    op.drop_table("kitobmillatbot_poll_map")
    op.drop_table("kitobmillatbot_user_zayafka_channels")
    op.drop_index(
        "ix_kitobmillatbot_test_sessions_user_completed_id",
        table_name="kitobmillatbot_test_sessions",
    )
    op.drop_index(
        op.f("ix_kitobmillatbot_test_sessions_user_id"),
        table_name="kitobmillatbot_test_sessions",
    )
    op.drop_table("kitobmillatbot_test_sessions")
    op.drop_table("kitobmillatbot_zayafka_channels")
    op.drop_index(
        op.f("ix_kitobmillatbot_users_telegram_id"),
        table_name="kitobmillatbot_users",
    )
    op.drop_index(
        op.f("ix_kitobmillatbot_users_referred_by"),
        table_name="kitobmillatbot_users",
    )
    op.drop_table("kitobmillatbot_users")
    op.drop_table("kitobmillatbot_score_change_log")
    op.drop_table("kitobmillatbot_quiz_settings")
    op.drop_table("kitobmillatbot_questions")
    op.drop_table("kitobmillatbot_content_texts")
    op.drop_table("kitobmillatbot_channels")
    op.drop_table("kitobmillatbot_activity_books")

    quiz_type_enum = postgresql.ENUM(
        "web",
        "quiz",
        "webapp",
        name="kitobmillatbot_quiz_type_enum",
    )
    quiz_type_enum.drop(op.get_bind(), checkfirst=True)
