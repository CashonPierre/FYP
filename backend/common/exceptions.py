# External
from typing import Literal
from fastapi import status

# Custom
from .enums import ExceptionEnum


class AppError(Exception):
    status_code: int = status.HTTP_400_BAD_REQUEST
    error_code: ExceptionEnum = ExceptionEnum.APP_ERROR

    def __init__(self, message: str | None = None):
        self.message = message or "Application error"
        super().__init__(self.message)


class InvalidCredentialsError(AppError):
    status_code: Literal[401] = status.HTTP_401_UNAUTHORIZED
    error_code: ExceptionEnum = ExceptionEnum.INVALID_CREDENTIALS


class NotFoundError(AppError):
    status_code: Literal[404] = status.HTTP_404_NOT_FOUND
    error_code: ExceptionEnum = ExceptionEnum.NOT_FOUND


class ConflictError(AppError):
    status_code: Literal[409] = status.HTTP_409_CONFLICT
    error_code: ExceptionEnum = ExceptionEnum.CONFLICT


class TokenError(AppError):
    status_code: Literal[400] = status.HTTP_400_BAD_REQUEST
    error_code: ExceptionEnum = ExceptionEnum.INVALID_TOKEN


class TokenExpiredError(TokenError):
    error_code: ExceptionEnum = ExceptionEnum.TOKEN_EXPIRED
