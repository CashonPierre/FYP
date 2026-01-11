# STL
from typing import Generator

# External
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

# Custom
from configs import settings


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite:")


db_url = settings.database_url
is_sqlite = _is_sqlite(db_url)

engine_kwargs: dict = {
    "url": db_url if not is_sqlite else "sqlite:///./app.db",
    "echo": settings.debug,
    "pool_pre_ping": False if is_sqlite else True,
}

if is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_engine(**engine_kwargs)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency for auto-commit/rollback"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
