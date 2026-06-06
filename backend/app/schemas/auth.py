from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterRequest(BaseModel):
    organization_name: str = Field(..., min_length=1, max_length=256)
    email: str = Field(..., max_length=254)
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field("", max_length=100)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("Invalid email address")
        return v


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., max_length=128)

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.strip().lower()


class UserOut(BaseModel):
    id: str
    org_id: str
    email: str
    name: str
    role: str
    capabilities: list[str]

    model_config = ConfigDict(from_attributes=True)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
