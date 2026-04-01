# external
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session


# Custom
from configs import settings
from common.exceptions import InvalidCredentialsError
from .repositories import get_user_by_id
from .schemas import CurrentUser
from database.make_db import get_session


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(
        dependency=HTTPBearer()
    ),
    session: Session = Depends(dependency=get_session),
):
    try:
        payload = jwt.decode(
            jwt=credentials.credentials,
            key=settings.jwt_secret_key,
            algorithms=[settings.algorithm],
            options={"require": ["sub", "exp"]},
        )
    except jwt.PyJWTError:
        raise InvalidCredentialsError(message="Could not validate credentials")

    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise InvalidCredentialsError(message="Could not validate credentials")

    user = get_user_by_id(session=session, user_id=user_id)
    if not user or user.is_verified is False:
        raise InvalidCredentialsError(message="Could not validate credentials")

    return CurrentUser(username=user.username, email=user.email)
