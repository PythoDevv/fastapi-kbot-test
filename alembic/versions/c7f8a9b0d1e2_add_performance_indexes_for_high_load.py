"""add performance indexes for high load

Revision ID: c7f8a9b0d1e2
Revises: b7c9d1e2f3a4
Create Date: 2026-05-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "c7f8a9b0d1e2"
down_revision: Union[str, None] = "b7c9d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_kitobxon_test_sessions_user_completed_id",
        "kitobxon_test_sessions",
        ["user_id", "is_completed", "id"],
        unique=False,
    )
    op.create_index(
        "ix_kitobxon_test_answers_session_question",
        "kitobxon_test_answers",
        ["session_id", "question_index"],
        unique=False,
    )
    op.create_index(
        "ix_kitobxon_poll_map_session_id",
        "kitobxon_poll_map",
        ["session_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_kitobxon_poll_map_session_id",
        table_name="kitobxon_poll_map",
    )
    op.drop_index(
        "ix_kitobxon_test_answers_session_question",
        table_name="kitobxon_test_answers",
    )
    op.drop_index(
        "ix_kitobxon_test_sessions_user_completed_id",
        table_name="kitobxon_test_sessions",
    )
