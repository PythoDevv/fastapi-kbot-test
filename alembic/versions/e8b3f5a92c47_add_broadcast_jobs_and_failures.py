"""persistent broadcast jobs + per-recipient failures + users.is_blocked

Revision ID: e8b3f5a92c47
Revises: d2c9b4e6a108
Create Date: 2026-08-09

Reklama yuborish endi bazada saqlanadigan "job" sifatida ishlaydi:

* `<prefix>_broadcast_jobs`   — bitta rassilka holati (kursor, hisoblagichlar).
  Server qayta ishga tushsa, rassilka `cursor_id` dan davom etadi, o'chib
  ketmaydi.
* `<prefix>_broadcast_failures` — xabar yetib bormagan har bir foydalanuvchi.
  Shu jadval tufayli "kimga bormadi" ma'lum bo'ladi va faqat o'shalarga qayta
  yuborish mumkin.
* `<prefix>_users.is_blocked` — 403 qaytargan foydalanuvchi belgilanadi.
  Bu **faqat hisobot uchun**: rassilkada hech kim filtrlanmaydi, bloklaganlarga
  ham urinib ko'riladi (blok olib tashlangan bo'lishi mumkin). `/start` bosilsa
  bayroq tozalanadi.

`broadcast_jobs.locked_by/locked_at` — jobni ayni paytda qaysi jarayon
yuborayotgani. Webhook va polling bitta bazada bir vaqtda ishlab qolsa, ikkalasi
ham bir jobni davom ettirib, xabarni ikki marta yuborishining oldini oladi.

Har bir qadam idempotent: ustun/jadval allaqachon bo'lsa tegilmaydi, bot bu
bazada hali yaratilmagan bo'lsa o'tkazib yuboriladi. Shuning uchun migratsiyani
istalgan holatdagi bazaga qo'llash xavfsiz va eski ma'lumotlarga tegmaydi.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "e8b3f5a92c47"
down_revision: Union[str, None] = "d2c9b4e6a108"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


BOT_PREFIXES = (
    "kitobxon",
    "kitobmillatbot",
    "millatchiroqlaribot",
    "barakali_tanlov_bot",
    "manfaadli_konkurs_bot",
)


def _users_table(prefix: str) -> str:
    return f"{prefix}_users"


def upgrade() -> None:
    for prefix in BOT_PREFIXES:
        users = _users_table(prefix)
        jobs = f"{prefix}_broadcast_jobs"
        failures = f"{prefix}_broadcast_failures"

        op.execute(
            f"""
            DO $$
            BEGIN
                -- Bot bu bazada yo'q bo'lsa — hech narsa qilmaymiz.
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = current_schema()
                      AND table_name = '{users}'
                ) THEN
                    RETURN;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = '{users}'
                      AND column_name = 'is_blocked'
                ) THEN
                    ALTER TABLE {users}
                    ADD COLUMN is_blocked BOOLEAN NOT NULL DEFAULT false;
                END IF;

                CREATE TABLE IF NOT EXISTS {jobs} (
                    id                SERIAL PRIMARY KEY,
                    admin_telegram_id BIGINT      NOT NULL,
                    source_chat_id    BIGINT      NOT NULL,
                    source_message_id BIGINT      NOT NULL,
                    status            VARCHAR(20) NOT NULL DEFAULT 'pending',
                    total             INTEGER     NOT NULL DEFAULT 0,
                    sent              INTEGER     NOT NULL DEFAULT 0,
                    failed            INTEGER     NOT NULL DEFAULT 0,
                    blocked           INTEGER     NOT NULL DEFAULT 0,
                    cursor_id         INTEGER     NOT NULL DEFAULT 0,
                    status_chat_id    BIGINT,
                    status_message_id BIGINT,
                    retry_of_job_id   INTEGER,
                    error             TEXT,
                    started_at        TIMESTAMPTZ,
                    finished_at       TIMESTAMPTZ,
                    -- Lease: which process is currently sending this job.
                    locked_by         VARCHAR(64),
                    locked_at         TIMESTAMPTZ,
                    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
                );

                CREATE INDEX IF NOT EXISTS ix_{prefix}_broadcast_jobs_status
                    ON {jobs} (status);

                CREATE TABLE IF NOT EXISTS {failures} (
                    id          SERIAL PRIMARY KEY,
                    job_id      INTEGER     NOT NULL
                                REFERENCES {jobs}(id) ON DELETE CASCADE,
                    telegram_id BIGINT      NOT NULL,
                    reason      VARCHAR(20) NOT NULL,
                    detail      TEXT,
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
                );

                CREATE INDEX IF NOT EXISTS ix_{prefix}_broadcast_failures_job
                    ON {failures} (job_id, id);
            END
            $$;
            """
        )


def downgrade() -> None:
    for prefix in BOT_PREFIXES:
        users = _users_table(prefix)
        op.execute(f"DROP TABLE IF EXISTS {prefix}_broadcast_failures")
        op.execute(f"DROP TABLE IF EXISTS {prefix}_broadcast_jobs")
        op.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = '{users}'
                      AND column_name = 'is_blocked'
                ) THEN
                    ALTER TABLE {users} DROP COLUMN is_blocked;
                END IF;
            END
            $$;
            """
        )
