from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

PASSWORD_MIN_LENGTH = 8


class RegisterRequest(BaseModel):
    email: EmailStr = Field(examples=["analyst@example.com"])
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=128, examples=["correct-horse-battery"])

    @field_validator("email")
    @classmethod
    def _normalise(cls, value: str) -> str:
        return value.strip().lower()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def _normalise(cls, value: str) -> str:
        return value.strip().lower()


class UserResponse(BaseModel):
    id: int
    email: str
    created_at: datetime
    jira_connected: bool = Field(description="Whether a Jira workspace is connected to this account.")

    model_config = {"from_attributes": True}
