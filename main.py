from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from bots.kitobxon.handlers.router import build_router as build_kitobxon_router
from bots.kitobxon.models import User as KitobxonUser
from bots.kitobxon.repositories import UserRepository as KitobxonUserRepo
from bots.kitobxon.services.broadcast_service import engine as kitobxon_broadcast
from bots.Kitobmillatbot.services.broadcast_service import engine as kitobmillatbot_broadcast
from bots.Millatchiroqlaribot.services.broadcast_service import engine as millatchiroqlaribot_broadcast
from bots.Barakali_tanlov_bot.services.broadcast_service import engine as barakali_tanlov_bot_broadcast
from bots.Manfaadli_konkurs_bot.services.broadcast_service import engine as manfaadli_konkurs_bot_broadcast
from bots.kitobxon.webapp.router import router as webapp_router
from bots.Kitobmillatbot.handlers.router import build_router as build_kitobmillatbot_router
from bots.Kitobmillatbot.models import User as KitobmillatbotUser
from bots.Kitobmillatbot.repositories import UserRepository as KitobmillatbotUserRepo
from bots.Kitobmillatbot.webapp.router import router as kitobmillatbot_webapp_router
from bots.Millatchiroqlaribot.handlers.router import build_router as build_millatchiroqlaribot_router
from bots.Millatchiroqlaribot.models import User as MillatchiroqlaribotUser
from bots.Millatchiroqlaribot.repositories import UserRepository as MillatchiroqlaribotUserRepo
from bots.Millatchiroqlaribot.webapp.router import router as millatchiroqlaribot_webapp_router
from bots.Barakali_tanlov_bot.handlers.router import build_router as build_barakali_tanlov_bot_router
from bots.Barakali_tanlov_bot.models import User as BarakaliTanlovBotUser
from bots.Barakali_tanlov_bot.repositories import UserRepository as BarakaliTanlovBotUserRepo
from bots.Barakali_tanlov_bot.webapp.router import router as barakali_tanlov_bot_webapp_router
from bots.Manfaadli_konkurs_bot.handlers.router import build_router as build_manfaadli_konkurs_bot_router
from bots.Manfaadli_konkurs_bot.models import User as ManfaadliKonkursBotUser
from bots.Manfaadli_konkurs_bot.repositories import UserRepository as ManfaadliKonkursBotUserRepo
from bots.Manfaadli_konkurs_bot.webapp.router import router as manfaadli_konkurs_bot_webapp_router
from bots.Kitobxonmillattbot.handlers.router import build_router as build_kitobxonmillattbot_router
from bots.Kitobxonmillattbot.models import User as KitobxonmillattbotUser
from bots.Kitobxonmillattbot.repositories import UserRepository as KitobxonmillattbotUserRepo
from bots.Kitobxonmillattbot.webapp.router import router as kitobxonmillattbot_webapp_router
from core.admin_init import initialize_admins
from core.config import settings
from core.database import AsyncSessionLocal, dispose_engine
from core.http_security import block_scanner_probes
from core.logging import get_logger, setup_logging
from core.registry import BotConfig, BotRegistry

setup_logging()
logger = get_logger(__name__)

registry = BotRegistry()

# Broadcasts survive restarts: a job cut off mid-run is picked up again here,
# from the cursor it last persisted.
BROADCAST_ENGINES = {
    "kitobxon": kitobxon_broadcast,
    "kitobmillatbot": kitobmillatbot_broadcast,
    "millatchiroqlaribot": millatchiroqlaribot_broadcast,
    "barakali_tanlov_bot": barakali_tanlov_bot_broadcast,
    "manfaadli_konkurs_bot": manfaadli_konkurs_bot_broadcast,
}


def _uses_webhook(mode: str) -> bool:
    return mode == "webhook"


async def _resume_broadcasts() -> None:
    for name, engine in BROADCAST_ENGINES.items():
        bot = registry.get_bot(name)
        if bot is None:
            continue
        try:
            await engine.resume_pending(bot)
        except Exception:
            logger.exception("Failed to resume broadcasts for '%s'", name)


async def _pause_broadcasts() -> None:
    """Checkpoint running broadcasts before the bots and the DB engine close."""
    for name, engine in BROADCAST_ENGINES.items():
        if registry.get_bot(name) is None:
            continue
        try:
            await engine.pause()
        except Exception:
            logger.exception("Failed to pause broadcasts for '%s'", name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up kbot_and_test_solve...")

    # Register kitobxon bot
    if _uses_webhook(settings.KITOBXON_MODE):
        registry.register(
            app,
            BotConfig(
                name="kitobxon",
                token=settings.KITOBXON_BOT_TOKEN,
                webhook_path=settings.KITOBXON_WEBHOOK_PATH,
                router=build_kitobxon_router(),
                admin_ids=settings.KITOBXON_ADMIN_IDS,
            ),
        )
    else:
        logger.info("Skipping webhook for 'kitobxon' because mode=%s", settings.KITOBXON_MODE)

    # Register kitobmillatbot
    if settings.KITOBMILLATBOT_BOT_TOKEN and _uses_webhook(settings.KITOBMILLATBOT_MODE):
        registry.register(
            app,
            BotConfig(
                name="kitobmillatbot",
                token=settings.KITOBMILLATBOT_BOT_TOKEN,
                webhook_path=settings.KITOBMILLATBOT_WEBHOOK_PATH,
                router=build_kitobmillatbot_router(),
                admin_ids=settings.KITOBMILLATBOT_ADMIN_IDS,
            ),
        )
    elif settings.KITOBMILLATBOT_BOT_TOKEN:
        logger.info(
            "Skipping webhook for 'kitobmillatbot' because mode=%s",
            settings.KITOBMILLATBOT_MODE,
        )

    # Register millatchiroqlaribot
    if settings.MILLATCHIROQLARIBOT_BOT_TOKEN and _uses_webhook(settings.MILLATCHIROQLARIBOT_MODE):
        registry.register(
            app,
            BotConfig(
                name="millatchiroqlaribot",
                token=settings.MILLATCHIROQLARIBOT_BOT_TOKEN,
                webhook_path=settings.MILLATCHIROQLARIBOT_WEBHOOK_PATH,
                router=build_millatchiroqlaribot_router(),
                admin_ids=settings.MILLATCHIROQLARIBOT_ADMIN_IDS,
            ),
        )
    elif settings.MILLATCHIROQLARIBOT_BOT_TOKEN:
        logger.info(
            "Skipping webhook for 'millatchiroqlaribot' because mode=%s",
            settings.MILLATCHIROQLARIBOT_MODE,
        )

    # Register barakali_tanlov_bot
    if settings.BARAKALI_TANLOV_BOT_BOT_TOKEN and _uses_webhook(settings.BARAKALI_TANLOV_BOT_MODE):
        registry.register(
            app,
            BotConfig(
                name="barakali_tanlov_bot",
                token=settings.BARAKALI_TANLOV_BOT_BOT_TOKEN,
                webhook_path=settings.BARAKALI_TANLOV_BOT_WEBHOOK_PATH,
                router=build_barakali_tanlov_bot_router(),
                admin_ids=settings.BARAKALI_TANLOV_BOT_ADMIN_IDS,
            ),
        )
    elif settings.BARAKALI_TANLOV_BOT_BOT_TOKEN:
        logger.info(
            "Skipping webhook for 'barakali_tanlov_bot' because mode=%s",
            settings.BARAKALI_TANLOV_BOT_MODE,
        )

    # Register manfaadli_konkurs_bot
    if settings.MANFAADLI_KONKURS_BOT_BOT_TOKEN and _uses_webhook(settings.MANFAADLI_KONKURS_BOT_MODE):
        registry.register(
            app,
            BotConfig(
                name="manfaadli_konkurs_bot",
                token=settings.MANFAADLI_KONKURS_BOT_BOT_TOKEN,
                webhook_path=settings.MANFAADLI_KONKURS_BOT_WEBHOOK_PATH,
                router=build_manfaadli_konkurs_bot_router(),
                admin_ids=settings.MANFAADLI_KONKURS_BOT_ADMIN_IDS,
            ),
        )
    elif settings.MANFAADLI_KONKURS_BOT_BOT_TOKEN:
        logger.info(
            "Skipping webhook for 'manfaadli_konkurs_bot' because mode=%s",
            settings.MANFAADLI_KONKURS_BOT_MODE,
        )

    # Register kitobxonmillattbot
    if settings.KITOBXONMILLATTBOT_BOT_TOKEN and _uses_webhook(settings.KITOBXONMILLATTBOT_MODE):
        registry.register(
            app,
            BotConfig(
                name="kitobxonmillattbot",
                token=settings.KITOBXONMILLATTBOT_BOT_TOKEN,
                webhook_path=settings.KITOBXONMILLATTBOT_WEBHOOK_PATH,
                router=build_kitobxonmillattbot_router(),
                admin_ids=settings.KITOBXONMILLATTBOT_ADMIN_IDS,
            ),
        )
    elif settings.KITOBXONMILLATTBOT_BOT_TOKEN:
        logger.info(
            "Skipping webhook for 'kitobxonmillattbot' because mode=%s",
            settings.KITOBXONMILLATTBOT_MODE,
        )

    await registry.set_webhooks()

    # Initialize admin users for each bot
    async with AsyncSessionLocal() as session:
        await initialize_admins(session, settings.KITOBXON_ADMIN_IDS, KitobxonUser, KitobxonUserRepo)
    if settings.KITOBMILLATBOT_BOT_TOKEN:
        async with AsyncSessionLocal() as session:
            await initialize_admins(session, settings.KITOBMILLATBOT_ADMIN_IDS, KitobmillatbotUser, KitobmillatbotUserRepo)
    if settings.MILLATCHIROQLARIBOT_BOT_TOKEN:
        async with AsyncSessionLocal() as session:
            await initialize_admins(session, settings.MILLATCHIROQLARIBOT_ADMIN_IDS, MillatchiroqlaribotUser, MillatchiroqlaribotUserRepo)
    if settings.BARAKALI_TANLOV_BOT_BOT_TOKEN:
        async with AsyncSessionLocal() as session:
            await initialize_admins(session, settings.BARAKALI_TANLOV_BOT_ADMIN_IDS, BarakaliTanlovBotUser, BarakaliTanlovBotUserRepo)
    if settings.MANFAADLI_KONKURS_BOT_BOT_TOKEN:
        async with AsyncSessionLocal() as session:
            await initialize_admins(session, settings.MANFAADLI_KONKURS_BOT_ADMIN_IDS, ManfaadliKonkursBotUser, ManfaadliKonkursBotUserRepo)
    if settings.KITOBXONMILLATTBOT_BOT_TOKEN:
        async with AsyncSessionLocal() as session:
            await initialize_admins(session, settings.KITOBXONMILLATTBOT_ADMIN_IDS, KitobxonmillattbotUser, KitobxonmillattbotUserRepo)

    await _resume_broadcasts()

    logger.info("All webhooks set. Ready.")

    yield

    logger.info("Shutting down...")
    await _pause_broadcasts()
    await registry.close_all()
    await dispose_engine()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="kbot_and_test_solve",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)

app.middleware("http")(block_scanner_probes)
app.include_router(webapp_router)
app.include_router(kitobmillatbot_webapp_router)
app.include_router(millatchiroqlaribot_webapp_router)
app.include_router(barakali_tanlov_bot_webapp_router)
app.include_router(manfaadli_konkurs_bot_webapp_router)
app.include_router(kitobxonmillattbot_webapp_router)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health", tags=["system"])
async def health() -> dict:
    return {"status": "ok", "version": "1.0.0"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        workers=1,
        reload=False,
    )
