"""Database engine and session management (SQLAlchemy 2.x)."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from . import config


def _make_engine(url: str):
    kwargs: dict = {}
    if url.startswith("sqlite"):
        # FastAPI serves sync routes on a threadpool. SQLite needs this flag to
        # allow a connection to be used from a different thread.
        kwargs["connect_args"] = {"check_same_thread": False}
        if url in ("sqlite://", "sqlite:///:memory:"):
            # In-memory SQLite is per-connection. StaticPool pins one shared
            # connection so the background worker sees the same database as the
            # request that created the job. Used by the test suite only.
            kwargs["poolclass"] = StaticPool
    return create_engine(url, **kwargs)


engine = _make_engine(config.DATABASE_URL)

# expire_on_commit=False: we build the HTTP response from ORM objects after
# commit, and do not want that to trigger a lazy reload.
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: one session per request, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables if missing. Called on application startup."""
    from . import models  # noqa: F401  -- registers models on Base.metadata

    Base.metadata.create_all(bind=engine)
