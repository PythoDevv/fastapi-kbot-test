"""add show_certificate_button to barakali_tanlov_bot quiz settings

Revision ID: a7c3e9f21b48
Revises: f5b8d2c47e10
Create Date: 2026-07-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7c3e9f21b48"
down_revision: Union[str, None] = "f5b8d2c47e10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "barakali_tanlov_bot_quiz_settings",
        sa.Column(
            "show_certificate_button",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("barakali_tanlov_bot_quiz_settings", "show_certificate_button")
