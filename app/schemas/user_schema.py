from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from app.enums.auth_provider import AuthProvider


class UserRegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: str = Field(min_length=8)


class UserResponse(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    profile_url: Optional[str] = None
    auth_provider: AuthProvider


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    profile_url: Optional[str] = None
