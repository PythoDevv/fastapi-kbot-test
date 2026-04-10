from dataclasses import dataclass, field
from typing import Any

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update
from fastapi import FastAPI, HTTPException, Request

from core.config import settings
from core.database import AsyncSessionLocal
from core.logging import get_logger
from core.middleware import DbSessionMiddleware, LoggingMiddleware

logger = get_logger(__name__)


@dataclass
class BotConfig:
    name: str
    token: str
    webhook_path: str
    router: Router
    admin_ids: list[int] = field(default_factory=list)
    extra_data: dict[str, Any] = field(default_factory=dict)


class BotRegistry:
    def __init__(self) -> None:
        self._bots: dict[str, tuple[Bot, Dispatcher, BotConfig]] = {}

    def register(self, app: FastAPI, config: BotConfig) -> None:
        if config.name in self._bots:
            raise ValueError(f"Bot '{config.name}' already registered")

        bot = Bot(
            token=config.token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        dp = Dispatcher(storage=MemoryStorage())
        dp["admin_ids"] = config.admin_ids
        dp["bot_name"] = config.name
        for key, value in config.extra_data.items():
            dp[key] = value

        dp.update.middleware(DbSessionMiddleware(AsyncSessionLocal))
        dp.update.middleware(LoggingMiddleware())
        dp.include_router(config.router)

        self._bots[config.name] = (bot, dp, config)
        self._attach_webhook_route(app, bot, dp, config)
        logger.info("Registered bot '%s' at %s", config.name, config.webhook_path)

    def _attach_webhook_route(
        self,
        app: FastAPI,
        bot: Bot,
        dp: Dispatcher,
        config: BotConfig,
    ) -> None:
        path = config.webhook_path

        async def webhook_endpoint(request: Request) -> dict[str, bool]:
            secret_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if secret_header != settings.WEBHOOK_SECRET:
                logger.warning("Invalid webhook secret for bot %s", config.name)
                raise HTTPException(status_code=403, detail="forbidden")
            try:
                payload = await request.json()
            except ValueError:
                raise HTTPException(status_code=400, detail="invalid json")
            try:
                update = Update.model_validate(payload)
            except Exception:
                logger.exception("Invalid update payload for bot %s", config.name)
                raise HTTPException(status_code=400, detail="invalid update")
            await dp.feed_update(bot, update)
            return {"ok": True}

        webhook_endpoint.__name__ = f"webhook_{config.name}"
        app.post(path, name=f"webhook_{config.name}", include_in_schema=False)(
            webhook_endpoint
        )

    async def set_webhooks(self) -> None:
        import asyncio
        for name, (bot, _dp, config) in self._bots.items():
            url = f"{settings.BASE_WEBHOOK_URL.rstrip('/')}{config.webhook_path}"
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    await bot.set_webhook(
                        url=url,
                        secret_token=settings.WEBHOOK_SECRET,
                        drop_pending_updates=False,
                        allowed_updates=[
                            "message",
                            "callback_query",
                            "poll_answer",
                            "chat_join_request",
                            "my_chat_member",
                        ],
                    )
                    logger.info("Webhook set for '%s': %s", name, url)
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                        logger.warning(
                            "Failed to set webhook for '%s' (attempt %d/%d), retrying in %ds...",
                            name, attempt + 1, max_retries, wait_time
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.exception("Failed to set webhook for '%s' after %d attempts", name, max_retries)

    async def close_all(self) -> None:
        for name, (bot, _dp, _cfg) in self._bots.items():
            try:
                await bot.session.close()
                logger.info("Closed bot '%s'", name)
            except Exception:
                logger.exception("Error closing bot '%s'", name)
