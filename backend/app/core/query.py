from __future__ import annotations

from typing import Any, Literal

from fastapi import HTTPException, Query, status
from sqlalchemy.sql.elements import ColumnElement

from app.core.config import settings

SortDirection = Literal["asc", "desc"]


def pagination_params(default_limit: int | None = None, max_limit: int | None = None):
    return {
        "skip": Query(default=0, ge=0),
        "limit": Query(default=default_limit or settings.default_page_limit, ge=1, le=max_limit or settings.max_page_limit),
    }


def validate_search(value: str | None) -> str | None:
    if value is not None and len(value) > settings.max_search_length:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Search query is too long")
    return value


def validate_sort(sort: str, direction: str, allowed: dict[str, ColumnElement[Any]]) -> tuple[ColumnElement[Any], SortDirection]:
    if sort not in allowed:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid sort field")
    if direction not in {"asc", "desc"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid sort direction")
    return allowed[sort], direction  # type: ignore[return-value]
