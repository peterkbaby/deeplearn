from uuid import UUID
from pydantic import BaseModel, Field, field_validator, EmailStr
from datetime import datetime
from core.enums import Role


class UserCreate(BaseModel):
    name:str = Field(..., min_length=1, max_length=100, examples=["guru devin"], description="Display name")
    email:EmailStr = Field(..., examples=["guru@example.com"], description="Email address")
    password:str = Field(..., description="Min 6 chars, at least one uppercase, one lowercase, one digit")

    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v    

class UserLogin(BaseModel):
    email:EmailStr
    password:str


class UserResponse(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    created_at: datetime
    provider: str
    role: Role
    onboarding: bool
    username: str | None = None
    profile_pic_url: str | None = None

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class OnboardingRequest(BaseModel):
    username: str | None = None

class ProfilePicResponse(BaseModel):
    profile_pic_url: str
    



