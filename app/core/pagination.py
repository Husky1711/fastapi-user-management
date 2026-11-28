"""Pagination shared by every list: bounded inputs and one response shape."""

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
MAX_OFFSET = 10_000  # deep offsets are slow; past this, filter instead of paging


class PaginationParams(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    limit: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)
    offset: int = Field(default=0, ge=0, le=MAX_OFFSET)


class Page[T](BaseModel):
    """`{"items", "total", "limit", "offset"}` (ARCHITECTURE §7)."""

    items: Sequence[T]
    total: int = Field(ge=0)
    limit: int
    offset: int
