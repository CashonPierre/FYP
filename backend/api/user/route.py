# External
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

# Custom
from database.make_db import get_session
from database.models import User
from api.auth.dependencies import get_current_user
from api.auth.schemas import CurrentUser
from api.auth.repositories import get_user_by_email, get_user_by_username
from api.auth.security import _verify_password, hash_password
from app_common.exceptions import (
  NotFoundError,
  ConflictError,
  InvalidCredentialsError,
)
from .schemas import UserProfile, UpdateUsernameRequest, ChangePasswordRequest

user_router = APIRouter(prefix="/user", tags=["User endpoints"])


@user_router.get(
  path="/me",
  response_model=UserProfile,
  status_code=status.HTTP_200_OK,
)
def get_profile(
  current_user: CurrentUser = Depends(get_current_user),
  session: Session = Depends(get_session),
) -> UserProfile:
  user: User | None = get_user_by_email(session=session, email=current_user.email)
  if not user:
    raise NotFoundError(message="User not found")
  return UserProfile(
    username=user.username,
    email=user.email,
    is_verified=user.is_verified,
  )


@user_router.patch(
  path="/me",
  response_model=UserProfile,
  status_code=status.HTTP_200_OK,
)
def update_profile(
  payload: UpdateUsernameRequest,
  current_user: CurrentUser = Depends(get_current_user),
  session: Session = Depends(get_session),
) -> UserProfile:
  user: User | None = get_user_by_email(session=session, email=current_user.email)
  if not user:
    raise NotFoundError(message="User not found")

  new_username = payload.username.strip()
  if new_username != user.username:
    existing = get_user_by_username(session=session, username=new_username)
    if existing and existing.id != user.id:
      raise ConflictError(message="Username already taken")
    user.username = new_username
    session.add(user)

  return UserProfile(
    username=user.username,
    email=user.email,
    is_verified=user.is_verified,
  )


@user_router.post(
  path="/change-password",
  status_code=status.HTTP_200_OK,
)
def change_password(
  payload: ChangePasswordRequest,
  current_user: CurrentUser = Depends(get_current_user),
  session: Session = Depends(get_session),
) -> Response:
  user: User | None = get_user_by_email(session=session, email=current_user.email)
  if not user:
    raise NotFoundError(message="User not found")

  if not _verify_password(
    plain_password=payload.current_password,
    hashed_password=user.hashed_password,
  ):
    raise InvalidCredentialsError(message="Current password is incorrect")

  user.hashed_password = hash_password(payload.new_password)
  session.add(user)
  return Response(status_code=status.HTTP_200_OK, content="Password changed")
