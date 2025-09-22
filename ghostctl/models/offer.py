"""Offer model for Ghost CMS."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, validator
from typing_extensions import Literal
from .tier import Tier


class Offer(BaseModel):
    """Ghost CMS Offer model."""

    id: str
    name: str
    code: str
    display_title: str
    display_description: Optional[str] = None
    type: Literal["percent", "fixed", "trial"]
    amount: int  # Percentage or cents
    duration: Literal["once", "forever", "repeating", "trial"]
    duration_in_months: Optional[int] = None
    currency: Optional[str] = None
    status: Literal["active", "archived"] = "active"
    redemption_count: int = 0
    tier: Tier
    created_at: datetime
    updated_at: datetime

    @validator('code')
    def validate_code(cls, v):
        """Validate code is uppercase."""
        return v.upper()

    @validator('amount')
    def validate_amount_by_type(cls, v, values):
        """Validate amount based on offer type."""
        offer_type = values.get('type')
        if offer_type == 'percent' and (v < 0 or v > 100):
            raise ValueError('Percent offers must have amount between 0-100')
        elif offer_type == 'fixed' and v < 0:
            raise ValueError('Fixed offers must have non-negative amount in cents')
        return v

    @validator('currency')
    def validate_currency_for_fixed(cls, v, values):
        """Validate currency is required for fixed offers."""
        offer_type = values.get('type')
        if offer_type == 'fixed' and not v:
            raise ValueError('Currency is required for fixed offers')
        return v

    @validator('duration_in_months')
    def validate_repeating_duration(cls, v, values):
        """Validate duration_in_months is required for repeating offers."""
        duration = values.get('duration')
        if duration == 'repeating' and v is None:
            raise ValueError('duration_in_months is required for repeating offers')
        return v

    @validator('tier')
    def validate_paid_tier(cls, v):
        """Validate offer is associated with a paid tier."""
        if v.type != 'paid':
            raise ValueError('Offers must be associated with paid tiers')
        return v

    class Config:
        """Pydantic configuration."""
        use_enum_values = True