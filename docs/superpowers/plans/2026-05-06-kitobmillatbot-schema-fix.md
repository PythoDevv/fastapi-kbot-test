# Kitobmillatbot Schema Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a production-safe Alembic migration that creates the missing `kitobmillatbot_*` schema and regression tests that guard the migration chain.

**Architecture:** Keep application startup unchanged and fix the database contract instead. Add one Alembic revision after the current head to create the full `kitobmillatbot` schema defined by the existing SQLAlchemy models, then add small tests that validate metadata and migration coverage.

**Tech Stack:** Python, SQLAlchemy 2.x, Alembic, unittest, PostgreSQL

---

### Task 1: Add regression tests

**Files:**
- Modify: `tests/test_alembic_revisions.py`
- Create: `tests/test_model_metadata.py`

- [ ] Add a test that asserts the new Alembic revision exists and depends on `c7f8a9b0d1e2`.
- [ ] Add a metadata test that imports both model modules and asserts key `kitobmillatbot_*` tables are present in `Base.metadata.tables`.
- [ ] Run the focused unittest commands and confirm they fail before the migration is added.

### Task 2: Add the Kitobmillatbot schema migration

**Files:**
- Create: `alembic/versions/<new_revision>_create_kitobmillatbot_schema.py`

- [ ] Create one Alembic migration after `c7f8a9b0d1e2`.
- [ ] In `upgrade()`, create `kitobmillatbot_quiz_type_enum`, all `kitobmillatbot_*` tables, indexes, and constraints expected by current models.
- [ ] In `downgrade()`, drop those tables, indexes, and enum in reverse order.

### Task 3: Verify end-to-end graph integrity

**Files:**
- No additional code files

- [ ] Run regression tests again and confirm they pass.
- [ ] Run `venv/bin/alembic heads` and `venv/bin/alembic history` to verify the new revision is the sole head and chained correctly.
- [ ] Run `venv/bin/alembic upgrade head --sql` and confirm the new `kitobmillatbot` DDL appears in the generated SQL.
