# Kitobmillatbot Schema Design

## Goal

Make `Kitobmillatbot` start safely with its token enabled by ensuring the PostgreSQL schema contains the `kitobmillatbot_*` tables and enum types expected by the existing SQLAlchemy models.

## Current Problem

- The application imports and starts both bots from the same process.
- `main.py` initializes `Kitobmillatbot` admin users whenever `KITOBMILLATBOT_BOT_TOKEN` is set.
- The database currently contains only the `kitobxon_*` schema created by Alembic.
- As a result, startup fails with `UndefinedTableError: relation "kitobmillatbot_users" does not exist`.

## Constraints

- Keep the existing startup flow intact.
- Avoid broad refactors or behavior changes.
- Use Alembic to create the missing schema rather than ad-hoc SQL on the server.
- Preserve the existing model/table naming conventions.

## Recommended Approach

Add one new Alembic revision after the current head that creates the full `kitobmillatbot_*` schema:

- Create `kitobmillatbot_quiz_type_enum`
- Create all `kitobmillatbot_*` tables mirrored from the current models
- Create required indexes and constraints

Also add regression tests that:

- verify SQLAlchemy metadata contains the `kitobmillatbot_*` tables
- verify the Alembic revision chain includes the new schema migration

## Why This Approach

- It matches the architecture already used for `kitobxon`.
- It is production-safe and repeatable across environments.
- It avoids hiding real schema problems behind conditional startup logic.

## Risks

- Fresh-database bootstrap may still have unrelated enum-value inconsistencies in older migrations; this fix focuses only on the missing `kitobmillatbot` schema.
- Existing production databases must run the new Alembic revision before re-enabling `KITOBMILLATBOT_BOT_TOKEN`.
