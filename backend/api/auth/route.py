# STL

# External
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

# Custom
from configs.config_loader import settings
from .security import (
    authenticate_user,
    generate_verify_url,
    generate_reset_url,
    hash_password,
)
from .dependencies import get_current_user
from .schemas import (
    CurrentUser,
    JwtToken,
    UserPublic,
    UserCreate,
    LoginRequest,
    AccessToken,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from background.tasks import send_email_task
from background.tasks.email import send_email
from database.make_db import get_session
from database.models import User
from .repositories import is_existing_user, get_user_by_email
from .repositories import get_user_by_id
from app_common.exceptions import (
    InvalidCredentialsError,
    NotFoundError,
    ConflictError,
)
from .service import (
    create_jwt_token,
    verify_jwt_token,
    get_time_tuple,
    register_user,
)
from app_common.enums import PayloadEnum


auth_router = APIRouter(prefix="/auth", tags=["Authentication endpoints"])


@auth_router.post(
    path="/send-again",
    status_code=status.HTTP_200_OK,
)
def reverify_email(
    user: UserPublic,
    session: Session = Depends(dependency=get_session),
) -> Response:
    """reverify your email if the token expired"""
    db_user: User | None = get_user_by_email(session=session, email=user.email)
    if not db_user:
        raise NotFoundError(message="User not found")

    if db_user.is_verified:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    now, exp = get_time_tuple(rememberMe=False)
    data = JwtToken(
        sub=str(db_user.id),
        what=PayloadEnum.VERIFICATION,
        exp=exp,
        iat=now,
    )
    token: str = create_jwt_token(data=data)

    verify_url: str = generate_verify_url(
        host_prefix=auth_router.prefix, token=token
    )

    if settings.debug:
        send_email(
            subject="Reverify you email", to_email=db_user.email, body=verify_url
        )
    else:
        send_email_task.delay(
            subject="Reverify you email",
            to_email=db_user.email,
            body=verify_url,
        )

    return Response(
        content="Please check your email", status_code=status.HTTP_200_OK
    )


@auth_router.post(path="/register", status_code=status.HTTP_201_CREATED)
def register(
    user: UserCreate,
    session: Session = Depends(dependency=get_session),
):
    """register a new user, it will also send a verification token through email"""

    if is_existing_user(
        session=session, username=user.username, email=user.email
    ):
        raise ConflictError(message="user already exist")

    now, exp = get_time_tuple(rememberMe=False)

    db_user: User = register_user(
        session=session,
        username=user.username,
        email=user.email,
        password=user.password,
    )
    data = JwtToken(
        sub=str(db_user.id),
        what=PayloadEnum.VERIFICATION,
        exp=exp,
        iat=now,
    )
    token: str = create_jwt_token(data=data)

    verify_url: str = generate_verify_url(
        host_prefix=auth_router.prefix, token=token
    )

    if settings.debug:
        send_email(
            subject="Verify your email", to_email=db_user.email, body=verify_url
        )
    else:
        send_email_task.delay(
            subject="Verify your email",
            to_email=db_user.email,
            body=verify_url,
        )

    return Response(
        status_code=status.HTTP_200_OK,
        content="register sucessfully! Please verify your account",
    )


@auth_router.post(
    path="/login", response_model=AccessToken, status_code=status.HTTP_200_OK
)
def login(
    form_data: LoginRequest, session: Session = Depends(dependency=get_session)
) -> AccessToken:
    """login the user (only verified user can login)"""
    user: User = authenticate_user(
        session=session, email=form_data.email, password=form_data.password
    )
    if not user or not user.is_verified:
        raise InvalidCredentialsError(message="Invalid Credentials")

    now, exp = get_time_tuple(rememberMe=form_data.rememberMe)

    token_data = JwtToken(
        exp=exp, iat=now, sub=str(user.id), what=PayloadEnum.LOGIN
    )

    access_token: str = create_jwt_token(data=token_data)

    return AccessToken(token_type="bearer", access_token=access_token)


@auth_router.get(
    path="/me", response_model=CurrentUser, status_code=status.HTTP_200_OK
)
def get_yourself(
    payload: CurrentUser = Depends(dependency=get_current_user),
) -> CurrentUser:
    return payload


@auth_router.get(path="/verify-email", status_code=status.HTTP_200_OK)
def verify_email(
    token: str, session: Session = Depends(dependency=get_session)
) -> Response:
    """verify email using the token link"""
    user_id: str = verify_jwt_token(token=token, expected_what=PayloadEnum.VERIFICATION)

    user: User | None = get_user_by_id(session=session, user_id=user_id)
    if not user:
        raise NotFoundError(message="User not found")

    if user.is_verified:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    user.is_verified = True
    session.add(instance=user)
    return Response(
        status_code=status.HTTP_200_OK, content="Email verified successfully"
    )


@auth_router.post(path="/forgot-password", status_code=status.HTTP_200_OK)
def forgot_password(
    payload: ForgotPasswordRequest,
    session: Session = Depends(dependency=get_session),
) -> Response:
    """Request a password reset link. Always returns 200 to avoid leaking which emails exist."""
    user: User | None = get_user_by_email(session=session, email=payload.email)
    if user:
        now, exp = get_time_tuple(rememberMe=False)
        token_data = JwtToken(
            sub=str(user.id),
            what=PayloadEnum.PASSWORD_RESET,
            exp=exp,
            iat=now,
        )
        token: str = create_jwt_token(data=token_data)
        reset_url: str = generate_reset_url(token=token)

        if settings.debug or not settings.resend_api_key:
            send_email(
                subject="Reset your password",
                to_email=user.email,
                body=f"Click here to reset your password:\n\n{reset_url}\n\nThis link expires in {settings.access_token_expire_hour} hours.",
            )
        else:
            send_email_task.delay(
                subject="Reset your password",
                to_email=user.email,
                body=f"Click here to reset your password:\n\n{reset_url}\n\nThis link expires in {settings.access_token_expire_hour} hours.",
            )

    return Response(
        status_code=status.HTTP_200_OK,
        content="If that email is registered you will receive a reset link shortly.",
    )


@auth_router.post(path="/reset-password", status_code=status.HTTP_200_OK)
def reset_password(
    payload: ResetPasswordRequest,
    session: Session = Depends(dependency=get_session),
) -> Response:
    """Reset the user's password using the token from the reset email."""
    user_id: str = verify_jwt_token(token=payload.token, expected_what=PayloadEnum.PASSWORD_RESET)

    user: User | None = get_user_by_id(session=session, user_id=user_id)
    if not user:
        raise NotFoundError(message="User not found")

    user.hashed_password = hash_password(payload.new_password)
    session.add(user)
    return Response(status_code=status.HTTP_200_OK, content="Password reset successfully")
