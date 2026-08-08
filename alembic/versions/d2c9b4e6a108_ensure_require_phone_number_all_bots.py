"""ensure require_phone_number exists on every bot's quiz_settings

Revision ID: d2c9b4e6a108
Revises: c4d8e1f70a92
Create Date: 2026-08-08

Har bir botning `<prefix>_quiz_settings` jadvalida `require_phone_number`
ustuni borligini kafolatlaydi (admin panelidagi "📱 Telefon ✅/❌" tugmasi shu
ustunni boshqaradi).

Ustun allaqachon mavjud bo'lsa hech narsa o'zgartirilmaydi, jadval hali
yaratilmagan bo'lsa o'tkazib yuboriladi — shuning uchun migratsiya har qanday
holatdagi bazaga xavfsiz qo'llanadi va eski logikaga tegmaydi.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "d2c9b4e6a108"
down_revision: Union[str, None] = "c4d8e1f70a92"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COLUMN_NAME = "require_phone_number"

QUIZ_SETTINGS_TABLES = (
    "kitobxon_quiz_settings",
    "kitobmillatbot_quiz_settings",
    "millatchiroqlaribot_quiz_settings",
    "barakali_tanlov_bot_quiz_settings",
    "manfaadli_konkurs_bot_quiz_settings",
)


def upgrade() -> None:
    for table in QUIZ_SETTINGS_TABLES:
        op.execute(
            f"""
            DO $$
            BEGIN
                -- Bot bu bazada hali yaratilmagan bo'lsa — hech narsa qilmaymiz.
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = current_schema()
                      AND table_name = '{table}'
                ) THEN
                    RETURN;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = '{table}'
                      AND column_name = '{COLUMN_NAME}'
                ) THEN
                    ALTER TABLE {table}
                    ADD COLUMN {COLUMN_NAME} BOOLEAN NOT NULL DEFAULT false;
                    RETURN;
                END IF;

                -- Ustun bor, lekin ba'zi create-schema migratsiyalarida
                -- server default'siz yaratilgan. ORM'dan tashqari INSERT'lar
                -- uzilmasligi uchun default'ni qo'yib qo'yamiz.
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = '{table}'
                      AND column_name = '{COLUMN_NAME}'
                      AND column_default IS NULL
                ) THEN
                    ALTER TABLE {table}
                    ALTER COLUMN {COLUMN_NAME} SET DEFAULT false;
                END IF;
            END;
            $$;
            """
        )


def downgrade() -> None:
    # Ustunni bu yerda o'chirib bo'lmaydi: u eskiroq migratsiyalarga
    # (5b45e79f6c88 va create-schema revizyalariga) tegishli. O'chirilsa
    # downgrade ma'lumotni yo'qotgan bo'lardi, shuning uchun no-op.
    pass
