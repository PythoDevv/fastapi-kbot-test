"""add show_certificate_button to millatchiroqlaribot quiz settings

Revision ID: f5b8d2c47e10
Revises: e4a7c1b93f20
Create Date: 2026-07-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f5b8d2c47e10"
down_revision: Union[str, None] = "e4a7c1b93f20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "millatchiroqlaribot_quiz_settings",
        sa.Column(
            "show_certificate_button",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("millatchiroqlaribot_quiz_settings", "show_certificate_button")
