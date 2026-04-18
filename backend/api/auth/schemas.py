# External
from typing import Literal
from pydantic import BaseModel, EmailStr, Field

# Custom
from app_common.enums import PayloadEnum


class LoginRequest(BaseModel):
    email: str
    password: str
    rememberMe: bool


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: str
    password: str = Field(min_length=8, max_length=128)


class UserPublic(BaseModel):
    username: str
    email: str


class AccessToken(BaseModel):
    token_type: Literal["bearer"]
    access_token: str


class CurrentUser(BaseModel):
    username: str
    email: EmailStr


class JwtToken(BaseModel):
    sub: str
    exp: int | None = None
    iat: int
    what: PayloadEnum


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)
