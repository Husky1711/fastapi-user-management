"""What every repository shares. Repositories build and run queries; they never commit."""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PaginationParams


@dataclass(frozen=True, slots=True)
class Slice[T]:
    """One page of rows plus the total number of rows that match."""

    items: Sequence[T]
    total: int


class Repository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _page[T](self, statement: Select[T], page: PaginationParams) -> Slice[T]:
        """Run `statement` for one page; the statement must already be ordered."""
        total_query = select(func.count()).select_from(statement.order_by(None).subquery())
        total = (await self.session.execute(total_query)).scalar_one()
        rows = await self.session.execute(statement.limit(page.limit).offset(page.offset))
        return Slice(items=rows.unique().scalars().all(), total=int(total))
