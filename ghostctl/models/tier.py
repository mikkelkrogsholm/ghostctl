"""Tier model for Ghost CMS."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, validator
from typing_extensions import Literal


class Tier(BaseModel):
    """Ghost CMS Tier model."""

    id: str
    name: str
    description: Optional[str] = None
    slug: str
    active: bool = True
    type: Literal["free", "paid"]
    welcome_page_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    visibility: Literal["public", "none"] = "public"
    trial_days: int = 0

    # Paid tier specific
    currency: Optional[str] = None
    monthly_price: Optional[int] = None
    yearly_price: Optional[int] = None

    # Benefits
    benefits: List[str] = []

    @validator('slug')
    def validate_slug(cls, v):
        """Validate slug is URL-safe."""
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError('Slug must be URL-safe (lowercase, alphanumeric, hyphens)')
        return v.lower()

    @validator('monthly_price')
    def validate_monthly_price(cls, v, values):
        """Validate monthly price for paid tiers."""
        if v is not None and v < 0:
            raise ValueError('Price must be non-negative (in cents)')
        return v

    @validator('yearly_price')
    def validate_yearly_price(cls, v, values):
        """Validate yearly price and ensure at least one price for paid tiers."""
        if v is not None and v < 0:
            raise ValueError('Price must be non-negative (in cents)')

        tier_type = values.get('type')
        if tier_type == 'paid':
            monthly_price = values.get('monthly_price')
            if monthly_price is None and v is None:
                raise ValueError('Paid tiers require at least one of monthly_price or yearly_price')
        return v

    @validator('currency')
    def validate_currency_for_paid_tier(cls, v, values):
        """Validate currency is provided for paid tiers."""
        tier_type = values.get('type')
        if tier_type == 'paid' and not v:
            raise ValueError('Currency is required for paid tiers')
        return v

    class Config:
        """Pydantic configuration."""
        use_enum_values = True