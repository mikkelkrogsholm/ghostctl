"""Settings model for Ghost CMS."""

from typing import Optional
from pydantic import BaseModel, HttpUrl


class Settings(BaseModel):
    """Ghost CMS Settings model."""

    # Site settings
    title: str
    description: str
    logo: Optional[HttpUrl] = None
    icon: Optional[HttpUrl] = None
    accent_color: str
    locale: str = "en"
    timezone: str = "UTC"

    # Social accounts
    facebook: Optional[str] = None
    twitter: Optional[str] = None

    # Meta settings
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    og_image: Optional[HttpUrl] = None
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    twitter_image: Optional[HttpUrl] = None
    twitter_title: Optional[str] = None
    twitter_description: Optional[str] = None

    # Code injection
    codeinjection_head: Optional[str] = None
    codeinjection_foot: Optional[str] = None

    class Config:
        """Pydantic configuration."""
        use_enum_values = True