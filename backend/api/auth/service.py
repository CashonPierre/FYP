from datetime import datetime, timedelta

# external
import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
from pydantic import BaseModel
from sqlalchemy.orm import Session

# custom
from common.exceptions import TokenError, TokenExpiredError
from database.models import User
from configs import get_logger, settings
from .security import hash_password

logger = get_logger()


def register_user(
    session: Session, username: str, email: str, password: str
) -> User:
    db_user = User(
        username=username,
        email=email,
        hashed_password=hash_password(password=password),
    )
    session.add(instance=db_user)
    session.flush()
    return db_user


def get_time_tuple(rememberMe: bool) -> tuple[int, int]:
    now = datetime.now()
    if rememberMe:
        exp = now + timedelta(days=settings.remember_me_expire_day)
        return int(now.timestamp()), int(exp.timestamp())

    exp = now + timedelta(hours=settings.access_token_expire_hour)
    return int(now.timestamp()), int(exp.timestamp())


def create_jwt_token(data: BaseModel) -> str:
    return jwt.encode(
        payload=data.model_dump(),
        key=settings.jwt_secret_key,
        algorithm=settings.algorithm,
    )


def verify_jwt_token(token: str) -> str:
    try:
        payload = jwt.decode(
            jwt=token,
            key=settings.jwt_secret_key,
            algorithms=[settings.algorithm],
        )
    except ExpiredSignatureError as e:
        raise TokenExpiredError(message="Verification token expired") from e
    except InvalidTokenError as e:
        raise TokenError(message="Invalid verification token") from e

    email = payload.get("email")

    if not isinstance(email, str) or not email:
        raise TokenError(message="Invalid verification token")

    return email
