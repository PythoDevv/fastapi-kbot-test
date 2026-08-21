from typing import Any, ClassVar, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.base_model import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    model: ClassVar[type[Base]]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, id: int) -> T | None:
        return await self.session.get(self.model, id)  # type: ignore[return-value]

    async def get_by(self, **filters: Any) -> T | None:
        stmt = select(self.model).filter_by(**filters)
        return (await self.session.execute(stmt)).scalar_one_or_none()  # type: ignore[return-value]

    async def list(self, **filters: Any) -> list[T]:
        stmt = select(self.model).filter_by(**filters)
        return list((await self.session.execute(stmt)).scalars().all())  # type: ignore[arg-type]

    async def add(self, obj: T) -> T:
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def delete(self, obj: T) -> None:
        await self.session.delete(obj)
        await self.session.flush()

    async def count(self, **filters: Any) -> int:
        stmt = select(func.count()).select_from(self.model).filter_by(**filters)
        return int((await self.session.execute(stmt)).scalar_one())
