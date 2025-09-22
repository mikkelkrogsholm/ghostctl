"""Newsletter model for Ghost CMS."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, validator
from typing_extensions import Literal


class Newsletter(BaseModel):
    """Ghost CMS Newsletter model."""

    id: str
    uuid: str
    name: str
    description: Optional[str] = None
    slug: str
    sender_name: Optional[str] = None
    sender_email: Optional[EmailStr] = None
    sender_reply_to: Literal["newsletter", "support"] = "newsletter"
    status: Literal["active", "archived"] = "active"
    visibility: Literal["members", "paid"] = "members"
    subscribe_on_signup: bool = True
    sort_order: int = 0
    header_image: Optional[str] = None
    show_header_icon: bool = True
    show_header_title: bool = True
    title_font_category: Literal["serif", "sans_serif"] = "sans_serif"
    title_alignment: Literal["center", "left"] = "center"
    show_feature_image: bool = True
    body_font_category: Literal["serif", "sans_serif"] = "sans_serif"
    footer_content: Optional[str] = None
    show_badge: bool = True
    created_at: datetime
    updated_at: datetime

    @validator('slug')
    def validate_slug(cls, v):
        """Validate slug is URL-safe."""
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError('Slug must be URL-safe (lowercase, alphanumeric, hyphens)')
        return v.lower()

    @validator('sender_email')
    def validate_sender_email(cls, v, values):
        """Validate sender_email is required if sender_name is set."""
        sender_name = values.get('sender_name')
        if sender_name and not v:
            raise ValueError('sender_email is required when sender_name is set')
        return v

    class Config:
        """Pydantic configuration."""
        use_enum_values = True