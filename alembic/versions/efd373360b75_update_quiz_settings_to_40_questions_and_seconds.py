"""update quiz settings to 40 questions and 40 seconds

Revision ID: efd373360b75
Revises: efd373360b74
Create Date: 2026-04-11 09:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'efd373360b75'
down_revision: Union[str, None] = 'efd373360b74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update existing quiz_settings to 40 questions per test and 40 seconds time limit
    op.execute(
        sa.text(
            "UPDATE kitobxon_quiz_settings SET questions_per_test = 40, time_limit_seconds = 40 WHERE id = 1"
        )
    )


def downgrade() -> None:
    # Revert to original values
    op.execute(
        sa.text(
            "UPDATE kitobxon_quiz_settings SET questions_per_test = 10, time_limit_seconds = 30 WHERE id = 1"
        )
    )
