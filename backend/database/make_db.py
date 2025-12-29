# STL
from typing import Generator

# External
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, Session

# Custom
from configs import settings

"""
For testing, use sqlite as it is easier to test and create,
For production system where we need to use store TimeSeries Data,
use postgresSQL as we can use TimeScaleDB for that
"""

postgres_sql = False
sqlite_url = "sqlite:///./app.db"

if postgres_sql:
    url_object = URL.create(
        drivername=settings.database_driver,
        username=settings.database_username,
        password=settings.database_password,
        host=settings.database_host,
        database=settings.database,
        port=settings.database_port,
    )
    engine = create_engine(
        url=url_object,
        echo=settings.debug,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )
else:
    engine = create_engine(
        url=sqlite_url,
        echo=settings.debug,
        connect_args={"check_same_thread": False},
    )

sql_session = Session(bind=engine)


class Base(DeclarativeBase):
    pass


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency for auto-commit/rollback"""
    with sql_session as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
