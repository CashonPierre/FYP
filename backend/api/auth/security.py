# External
import bcrypt
from sqlalchemy.orm import Session


# Custom
from configs import settings
from database.models import User
from .repositories import get_user_by_email
from common.exceptions import InvalidCredentialsError


def _verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed one"""
    return bcrypt.checkpw(
        password=plain_password.encode(encoding="utf-8"),
        hashed_password=hashed_password.encode(encoding="utf-8"),
    )


def generate_verify_url(host_prefix: str, token: str) -> str:
    verify_url: str = f"http://{settings.host}:{settings.port}{host_prefix}/verify-email?token={token}"
    return verify_url


def hash_password(password: str) -> str:
    """Hash a password"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(
        password=password.encode(encoding="utf-8"), salt=salt
    )
    return hashed.decode(encoding="utf-8")


def authenticate_user(session: Session, email: str, password: str) -> User:
    """logic for login a user"""
    user = get_user_by_email(session=session, email=email)
    if not user or not _verify_password(
        plain_password=password, hashed_password=user.hashed_password
    ):
        raise InvalidCredentialsError(message="unknown user")
    return user
