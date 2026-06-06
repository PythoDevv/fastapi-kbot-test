# Millatchiroqlaribot — clone of Kitobmillatbot

Date: 2026-06-06

## Goal

Add a third Telegram bot, `Millatchiroqlaribot`, that behaves identically to the
existing `Kitobmillatbot`. It runs in the same FastAPI process via the existing
`BotRegistry`, with its own token, webhook path, admin list, and an isolated set
of database tables.

## Architecture

The project already hosts two bots (`kitobxon`, `kitobmillatbot`) as parallel
self-contained packages under `bots/`. Each package owns its handlers, services,
repositories, models, keyboards, and webapp router. Per-bot table isolation is
achieved through a `TABLE_PREFIX` defined in each bot's `config.py`; SQLAlchemy
models build table names via `t("name")`. Bots are registered in `main.py`'s
lifespan using `BotRegistry.register(...)` and a `BotConfig`.

Cloning a bot is therefore a mechanical operation: duplicate the package and
rename every bot identifier, then add the new bot's config and wiring.

## Changes

1. **Copy package** `bots/Kitobmillatbot/` → `bots/Millatchiroqlaribot/`
   (exclude `__pycache__`).

2. **Rename identifiers inside the new package** (all `.py` files), three cases:
   - `Kitobmillatbot` → `Millatchiroqlaribot` (import paths, relationship class strings)
   - `kitobmillatbot` → `millatchiroqlaribot` (`BOT_NAME`, `TABLE_PREFIX`, enum name
     `kitobmillatbot_quiz_type_enum`, index/constraint names, webapp prefix & tags)
   - `KITOBMILLATBOT` → `MILLATCHIROQLARIBOT` (settings attribute references, e.g.
     `settings.KITOBMILLATBOT_BOT_TOKEN`)

3. **`core/config.py`** — add settings:
   - `MILLATCHIROQLARIBOT_BOT_TOKEN: str = ""`
   - `MILLATCHIROQLARIBOT_ADMIN_IDS: list[int] = Field(default_factory=lambda: [935795577])`
   - `MILLATCHIROQLARIBOT_WEBHOOK_PATH: str = "/millatchiroqlaribot/webhook"`

4. **`main.py`** — import the new package's `build_router`, `User`, `UserRepository`,
   and webapp `router`; register the bot (guarded by token presence, mirroring
   kitobmillatbot); initialize admins; `app.include_router(...)` for its webapp.

5. **`.env` and `.env.example`** — add the three `MILLATCHIROQLARIBOT_*` vars.
   Token value is a placeholder (`<millatchiroqlaribot_token>`); the user fills it
   on the server.

6. **Alembic migration** — new revision creating all `millatchiroqlaribot_*` tables
   and the `millatchiroqlaribot_quiz_type_enum`, cloned from
   `d6f9a8c4b2e1_create_kitobmillatbot_schema.py`. `down_revision = "7af660903cc5"`
   (current head). **The migration file is written only; it is NOT run locally** —
   the bot runs on the server, so the user runs `alembic upgrade head` there after
   deploy.

## Known limitation (faithful clone)

WebApp quiz mode uses a shared static page `static/webapp/index.html`, which
hardcodes the `/webapp` API prefix (line 228), and Kitobmillatbot's quiz button
already points to `BASE_WEBHOOK_URL/webapp/`. So WebApp mode hits the kitobxon
webapp backend regardless of which bot launches it. The new bot replicates this
exactly. The in-bot quiz modes (`web` inline buttons, `quiz` Telegram poll) are
fully isolated per bot. Making WebApp truly per-bot would require parametrizing
the static page — out of scope unless requested.

## Verification

- `python -c "import main"` imports without error.
- `grep -ri kitobmillatbot bots/Millatchiroqlaribot` returns nothing.
- New migration references only `millatchiroqlaribot_*` table/enum/index names and
  chains from the current head.
