import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator

USERNAME_PATTERN = r"^[A-Za-z0-9_.-]{3,50}$"


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(pattern=USERNAME_PATTERN, examples=["jane_doe"])
    # Max length bounds hashing cost (Argon2 on a huge input is a DoS vector)
    password: SecretStr = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: SecretStr) -> SecretStr:
        raw = v.get_secret_value()
        if not any(c.isalpha() for c in raw) or not any(c.isdigit() for c in raw):
            raise ValueError("Password must contain at least one letter and one digit")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    username: str
    is_active: bool
    created_at: datetime


class AuthResponse(BaseModel):
    """Returned by login and refresh. Tokens themselves travel only in HttpOnly cookies."""

    user: UserOut
    csrf_token: str = Field(description="Send as X-CSRF-Token header on POST/PUT/PATCH/DELETE")
    access_token_expires_at: datetime


class TokenResponse(BaseModel):
    """OAuth2 password-flow response for API clients and Swagger UI."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105
    expires_in: int
