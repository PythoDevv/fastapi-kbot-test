"""rename kitobmillatbot uq_user_zayafka to avoid clash with kitobxon

Revision ID: 7af660903cc5
Revises: d6f9a8c4b2e1
Create Date: 2026-05-07
"""
from alembic import op


revision: str = "7af660903cc5"
down_revision: str | None = "d6f9a8c4b2e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Old constraint name "uq_user_zayafka" clashed with kitobxon's identical
    # constraint when both schemas live in the same Postgres database.
    op.execute(
        "ALTER TABLE kitobmillatbot_user_zayafka_channels "
        "RENAME CONSTRAINT uq_user_zayafka TO uq_kitobmillatbot_user_zayafka"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE kitobmillatbot_user_zayafka_channels "
        "RENAME CONSTRAINT uq_kitobmillatbot_user_zayafka TO uq_user_zayafka"
    )
