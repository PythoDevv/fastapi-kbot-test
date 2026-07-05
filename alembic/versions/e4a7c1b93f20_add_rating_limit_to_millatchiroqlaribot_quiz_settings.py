"""add rating_limit to millatchiroqlaribot quiz settings

Revision ID: e4a7c1b93f20
Revises: a1f2e3d4c5b6
Create Date: 2026-07-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e4a7c1b93f20"
down_revision: Union[str, None] = "a1f2e3d4c5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "millatchiroqlaribot_quiz_settings",
        sa.Column("rating_limit", sa.Integer(), nullable=False, server_default="30"),
    )


def downgrade() -> None:
    op.drop_column("millatchiroqlaribot_quiz_settings", "rating_limit")
