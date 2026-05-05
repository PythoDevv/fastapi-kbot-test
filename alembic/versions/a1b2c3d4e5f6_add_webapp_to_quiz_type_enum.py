"""add webapp to quiz_type_enum

Revision ID: a1b2c3d4e5f6
Revises: 906802f98e1c
Create Date: 2026-05-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '906802f98e1c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE quiz_type_enum ADD VALUE IF NOT EXISTS 'webapp'")


def downgrade() -> None:
    # PostgreSQL doesn't support removing enum values directly.
    # Manual step required if rollback needed.
    pass
