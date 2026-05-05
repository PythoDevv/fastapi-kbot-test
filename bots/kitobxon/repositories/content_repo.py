from sqlalchemy import select

from bots.kitobxon.models import ActivityBook, ContentText, ScoreChangeLog
from bots.kitobxon.repositories.base import BaseRepository


class ContentRepository(BaseRepository[ContentText]):
    model = ContentText

    async def get_by_key(self, key: str) -> ContentText | None:
        return await self.get_by(key=key)

    async def list_all(self) -> list[ContentText]:
        from sqlalchemy import select
        result = await self.session.execute(select(ContentText).order_by(ContentText.id))
        return list(result.scalars().all())

    async def upsert(
        self,
        key: str,
        *,
        text: str | None = None,
        image_id: str | None = None,
        require_link: bool | None = None,
    ) -> ContentText:
        obj = await self.get_by_key(key)
        if obj is None:
            obj = ContentText(key=key)
            self.session.add(obj)
        if text is not None:
            obj.text = text
        if image_id is not None:
            obj.image_id = image_id
        if require_link is not None:
            obj.require_link = require_link
        await self.session.flush()
        return obj


class BookRepository(BaseRepository[ActivityBook]):
    model = ActivityBook

    async def list_all(self) -> list[ActivityBook]:
        return list(
            (await self.session.execute(select(ActivityBook).order_by(ActivityBook.id)))
            .scalars()
            .all()
        )


class ScoreLogRepository(BaseRepository[ScoreChangeLog]):
    model = ScoreChangeLog

    async def log(
        self,
        *,
        admin_telegram_id: int,
        admin_fio: str | None,
        target_telegram_id: int,
        target_fio: str | None,
        old_score: int,
        new_score: int,
        reason: str | None,
    ) -> ScoreChangeLog:
        entry = ScoreChangeLog(
            admin_telegram_id=admin_telegram_id,
            admin_fio=admin_fio,
            target_telegram_id=target_telegram_id,
            target_fio=target_fio,
            old_score=old_score,
            new_score=new_score,
            reason=reason,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry
