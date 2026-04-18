# External
from pydantic import BaseModel, EmailStr, Field


class UserProfile(BaseModel):
  username: str
  email: EmailStr
  is_verified: bool


class UpdateUsernameRequest(BaseModel):
  username: str = Field(min_length=3, max_length=64)


class ChangePasswordRequest(BaseModel):
  current_password: str
  new_password: str = Field(min_length=8, max_length=128)
