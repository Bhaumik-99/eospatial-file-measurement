from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def build_engine(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    db_engine = create_engine(database_url, connect_args=connect_args, future=True)

    if database_url.startswith("sqlite"):
        @event.listens_for(db_engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return db_engine


engine = build_engine(get_settings().database_url)


@lru_cache
def get_session_factory(database_url: str):
    return sessionmaker(
        bind=build_engine(database_url),
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )


SessionLocal = get_session_factory(get_settings().database_url)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
