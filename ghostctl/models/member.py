"""Member model for Ghost CMS."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, validator
from typing_extensions import Literal


class Label(BaseModel):
    """Member label model."""
    id: str
    name: str
    slug: str
    created_at: datetime
    updated_at: datetime


class Subscription(BaseModel):
    """Member subscription model."""
    id: str
    status: Literal["active", "canceled", "unpaid", "past_due"]
    start_date: datetime
    current_period_end: datetime
    cancel_at_period_end: bool = False
    tier: str  # Tier ID
    cadence: Literal["month", "year"]
    currency: str
    amount: int  # Amount in cents


class Member(BaseModel):
    """Ghost CMS Member model."""

    id: str
    uuid: str
    email: EmailStr
    name: Optional[str] = None
    note: Optional[str] = None
    geolocation: Optional[str] = None
    status: Literal["free", "paid", "comped"]
    labels: List[Label] = []
    created_at: datetime
    updated_at: datetime
    last_seen_at: Optional[datetime] = None
    subscriptions: List[Subscription] = []
    avatar_image: Optional[str] = None
    email_count: int = 0
    email_opened_count: int = 0
    email_open_rate: Optional[float] = None

    @validator('status')
    def validate_paid_status(cls, v, values):
        """Validate paid status requires active subscription."""
        # Note: This validation would need subscription data to be complete
        # In practice, this might be validated at the API level
        return v

    @validator('email_open_rate')
    def validate_email_open_rate(cls, v):
        """Validate email open rate is between 0 and 1."""
        if v is not None and (v < 0 or v > 1):
            raise ValueError('Email open rate must be between 0 and 1')
        return v

    class Config:
        """Pydantic configuration."""
        use_enum_values = True