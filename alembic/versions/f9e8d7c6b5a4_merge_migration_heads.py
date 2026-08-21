"""Merge the Kitobxonmillattbot and broadcast migration branches.

Revision ID: f9e8d7c6b5a4
Revises: b8d9e0f1a2b3, e8b3f5a92c47
Create Date: 2026-08-21 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = "f9e8d7c6b5a4"
down_revision: Union[str, Sequence[str], None] = (
    "b8d9e0f1a2b3",
    "e8b3f5a92c47",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge both existing heads without changing the database schema."""


def downgrade() -> None:
    """Re-open the two historical branches when downgrading this merge."""
