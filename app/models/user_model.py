from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from app.enums.auth_provider import AuthProvider


class UserModel(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    profile_url: Optional[str] = None
    auth_provider: AuthProvider = AuthProvider.EMAIL
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
