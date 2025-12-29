# External
from typing import Literal
from pydantic import BaseModel, EmailStr

# Custom
from common.enums import PayloadEnum


class LoginRequest(BaseModel):
    email: str
    password: str
    rememberMe: bool


class UserCreate(BaseModel):
    username: str
    email: str
    password: str


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
