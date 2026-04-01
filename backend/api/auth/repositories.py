# STL
import uuid

# External
from sqlalchemy.orm import Session
from sqlalchemy import select

# Custom
from database.models import User


def get_user_by_username(session: Session, username: str) -> User | None:
    """get user from the SQL database based on the username"""
    statement = select(User).where(User.username == username)
    return session.execute(statement=statement).scalar_one_or_none()


def is_existing_user(session: Session, username: str, email: str) -> bool:
    """check if the user exist"""
    statement = select(User).where(
        (User.username == username) & (User.email == email)
    )
    existing_user: User | None = session.execute(
        statement=statement
    ).scalar_one_or_none()
    return existing_user is not None


def get_user_by_email(session: Session, email: str) -> User | None:
    """get user from the SQL database based on the email"""
    statement = select(User).where(User.email == email)
    result = session.execute(statement=statement).scalar_one_or_none()
    return result


def get_user_by_id(session: Session, user_id: str) -> User | None:
    """get user from the SQL database based on the user id"""
    try:
        parsed = uuid.UUID(user_id)
    except Exception:
        return None
    statement = select(User).where(User.id == parsed)
    return session.execute(statement=statement).scalar_one_or_none()


def check_user_id(session: Session, user_id: str) -> bool:
    statement = select(User).where(User.id == user_id)
    result = session.execute(statement=statement).scalar_one_or_none()
    if result is None or result.is_verified is False:
        return False
    return True
