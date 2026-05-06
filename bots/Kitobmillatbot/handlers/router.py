from aiogram import Router
from aiogram.types import ErrorEvent

from bots.Kitobmillatbot.handlers import (
    auth,
    broadcast,
    menu,
    quiz,
    results,
    start,
    subs,
)
from bots.Kitobmillatbot.handlers.admin import (
    admins,
    channels,
    content,
    export,
    panel,
    questions,
    settings,
    users,
)
from core.logging import get_logger

logger = get_logger(__name__)


def build_router() -> Router:
    root = Router(name="kitobmillatbot_root")

    # Error handler — catches all unhandled exceptions in handlers
    @root.errors()
    async def global_error_handler(event: ErrorEvent) -> None:
        logger.exception(
            "Unhandled error in update %s: %s",
            event.update.update_id,
            event.exception,
        )
        msg = getattr(event.update, "message", None) or getattr(
            event.update, "callback_query", None
        )
        if msg:
            try:
                answer = getattr(msg, "answer", None) or getattr(msg.message, "answer", None)
                if answer:
                    await answer("Xatolik yuz berdi. Iltimos qayta urinib ko'ring.")
            except Exception:
                pass

    # Order matters: more specific routers first
    root.include_router(start.router)
    root.include_router(auth.router)
    root.include_router(subs.router)
    root.include_router(quiz.router)

    # Admin sub-routers
    root.include_router(panel.router)
    root.include_router(users.router)
    root.include_router(admins.router)
    root.include_router(channels.router)
    root.include_router(questions.router)
    root.include_router(settings.router)
    root.include_router(content.router)
    root.include_router(export.router)
    root.include_router(broadcast.router)

    # Menu last — catches general text commands
    root.include_router(menu.router)
    root.include_router(results.router)

    return root
