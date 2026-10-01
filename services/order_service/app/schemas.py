from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrderCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    user_id: int = Field(ge=1, strict=True, examples=[1])
    product_name: str = Field(min_length=1, max_length=200, examples=["파이썬 교재"])
    quantity: int = Field(ge=1, le=1000, strict=True, examples=[2])
    unit_price: int = Field(ge=1, le=1_000_000_000, strict=True, examples=[15000])


class OrderRead(BaseModel):
    id: int
    user_id: int
    product_name: str
    quantity: int
    unit_price: int
    total_price: int
    created_at: datetime
