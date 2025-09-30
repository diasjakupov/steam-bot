from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, Callable

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .config import get_settings

_engine: AsyncEngine | None = None
_SessionLocal: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(str(settings.database_url), future=True)
        _SessionLocal = async_sessionmaker(_engine, expire_on_commit=False)
    assert _engine is not None
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _SessionLocal is None:
        get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    session = get_sessionmaker()()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


def session_dependency() -> Callable[[], AsyncIterator[AsyncSession]]:
    @asynccontextmanager
    async def _dependency() -> AsyncIterator[AsyncSession]:
        async with session_scope() as session:
            yield session

    return _dependency

