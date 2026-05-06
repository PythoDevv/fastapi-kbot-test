from sqlalchemy import delete, or_, select

from bots.Kitobmillatbot.models import ActivityBook, ContentText, ScoreChangeLog
from bots.Kitobmillatbot.repositories.base import BaseRepository


class ContentRepository(BaseRepository[ContentText]):
    model = ContentText

    async def get_by_key(self, key: str) -> ContentText | None:
        return await self.get_by(key=key)

    async def list_all(self) -> list[ContentText]:
        from sqlalchemy import select
        result = await self.session.execute(select(ContentText).order_by(ContentText.id))
        return list(result.scalars().all())

    async def list_by_key_group(self, key: str) -> list[ContentText]:
        stmt = (
            select(ContentText)
            .where(
                or_(
                    ContentText.key == key,
                    ContentText.key.like(f"{key}:%"),
                )
            )
            .order_by(ContentText.id)
        )
        return list((await self.session.execute(stmt)).scalars().all())

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

    async def replace(
        self,
        key: str,
        *,
        text: str | None,
        image_id: str | None,
        require_link: bool,
    ) -> ContentText:
        obj = await self.get_by_key(key)
        if obj is None:
            obj = ContentText(key=key)
            self.session.add(obj)
        obj.text = text
        obj.image_id = image_id
        obj.require_link = require_link
        await self.session.flush()
        return obj

    async def clear(self, key: str) -> ContentText:
        obj = await self.get_by_key(key)
        if obj is None:
            obj = ContentText(key=key)
            self.session.add(obj)
        obj.text = None
        obj.image_id = None
        await self.session.flush()
        return obj

    async def delete_by_key(self, key: str) -> bool:
        obj = await self.get_by_key(key)
        if obj is None:
            return False
        await self.delete(obj)
        return True

    async def create(
        self,
        *,
        key: str,
        text: str | None,
        image_id: str | None,
        require_link: bool,
    ) -> ContentText:
        obj = ContentText(
            key=key,
            text=text,
            image_id=image_id,
            require_link=require_link,
        )
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def delete_latest_by_key_group(self, key: str) -> bool:
        items = await self.list_by_key_group(key)
        if not items:
            return False
        await self.delete(items[-1])
        return True

    async def delete_by_key_group(self, key: str) -> int:
        stmt = delete(ContentText).where(
            or_(
                ContentText.key == key,
                ContentText.key.like(f"{key}:%"),
            )
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return int(result.rowcount or 0)


class BookRepository(BaseRepository[ActivityBook]):
    model = ActivityBook

    async def list_all(self) -> list[ActivityBook]:
        return list(
            (await self.session.execute(select(ActivityBook).order_by(ActivityBook.id)))
            .scalars()
            .all()
        )

    async def create(
        self,
        *,
        title: str | None,
        button_text: str | None,
        button_url: str | None,
        file_id: str | None = None,
    ) -> ActivityBook:
        book = ActivityBook(
            title=title,
            button_text=button_text,
            button_url=button_url,
            file_id=file_id,
        )
        self.session.add(book)
        await self.session.flush()
        return book


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
