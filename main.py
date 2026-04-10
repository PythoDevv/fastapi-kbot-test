from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from bots.kitobxon.handlers.router import build_router as build_kitobxon_router
from core.config import settings
from core.database import dispose_engine
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

    # === To add a new bot in the future ===
    # from bots.yangi_bot.handlers.router import build_router as build_yangi_router
    # registry.register(app, BotConfig(
    #     name="yangi_bot",
    #     token=settings.YANGI_BOT_TOKEN,
    #     webhook_path="/yangi_bot/webhook",
    #     router=build_yangi_router(),
    #     admin_ids=settings.YANGI_BOT_ADMIN_IDS,
    # ))

    await registry.set_webhooks()
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
