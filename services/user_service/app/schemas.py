from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1, max_length=100, examples=["홍길동"])
    email: EmailStr = Field(max_length=254, examples=["hong@example.com"])


class UserRead(BaseModel):
    id: int
    name: str
    email: EmailStr
    created_at: datetime
