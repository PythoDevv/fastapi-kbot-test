"""add quiz_type to test sessions

Revision ID: b7c9d1e2f3a4
Revises: a1b2c3d4e5f6
Create Date: 2026-05-05 21:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7c9d1e2f3a4"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE quiz_type_enum ADD VALUE IF NOT EXISTS 'web'")
    op.execute("ALTER TYPE quiz_type_enum ADD VALUE IF NOT EXISTS 'quiz'")

    op.add_column(
        "kitobxon_test_sessions",
        sa.Column(
            "quiz_type",
            sa.Enum("web", "quiz", "webapp", name="quiz_type_enum", create_type=False),
            nullable=False,
            server_default="web",
        ),
    )
    op.alter_column(
        "kitobxon_test_sessions",
        "quiz_type",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("kitobxon_test_sessions", "quiz_type")
