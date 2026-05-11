from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from bots.kitobxon.handlers.router import build_router as build_kitobxon_router
from bots.kitobxon.models import User as KitobxonUser
from bots.kitobxon.repositories import UserRepository as KitobxonUserRepo
from bots.kitobxon.webapp.router import router as webapp_router
from bots.Kitobmillatbot.handlers.router import build_router as build_kitobmillatbot_router
from bots.Kitobmillatbot.models import User as KitobmillatbotUser
from bots.Kitobmillatbot.repositories import UserRepository as KitobmillatbotUserRepo
from bots.Kitobmillatbot.webapp.router import router as kitobmillatbot_webapp_router
from core.admin_init import initialize_admins
from core.config import settings
from core.database import AsyncSessionLocal, dispose_engine
from core.http_security import block_scanner_probes
from core.logging import get_logger, setup_logging
from core.registry import BotConfig, BotRegistry

setup_logging()
logger = get_logger(__name__)

registry = BotRegistry()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up kbot_and_test_solve...")

    # Register kitobxon bot
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

    # Register kitobmillatbot
    if settings.KITOBMILLATBOT_BOT_TOKEN:
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

    await registry.set_webhooks()

    # Initialize admin users for each bot
    async with AsyncSessionLocal() as session:
        await initialize_admins(session, settings.KITOBXON_ADMIN_IDS, KitobxonUser, KitobxonUserRepo)
    if settings.KITOBMILLATBOT_BOT_TOKEN:
        async with AsyncSessionLocal() as session:
            await initialize_admins(session, settings.KITOBMILLATBOT_ADMIN_IDS, KitobmillatbotUser, KitobmillatbotUserRepo)

    logger.info("All webhooks set. Ready.")

    yield

    logger.info("Shutting down...")
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
