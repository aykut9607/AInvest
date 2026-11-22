from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from core.config import get_settings


class Base(DeclarativeBase):
    """Base class of the service's tables; Alembic reads Base.metadata to generate migrations."""


@lru_cache
def get_engine() -> Engine:
    # pool_pre_ping: a connection broken while idle (e.g. Postgres restarted) is replaced instead of failing a request
    return create_engine(get_settings().database_url, pool_pre_ping=True)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed afterwards."""
    session = sessionmaker(bind=get_engine())()
    try:
        yield session
    finally:
        session.close()


def database_reachable(engine: Engine) -> bool:
    """True when the database answers a trivial query; never raises (used by the health check)."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
