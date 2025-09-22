"""Tag model for Ghost CMS."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, validator
from typing_extensions import Literal


class Tag(BaseModel):
    """Ghost CMS Tag model."""

    id: str
    name: str
    slug: str
    description: Optional[str] = None
    feature_image: Optional[str] = None
    visibility: Literal["public", "internal"] = "public"
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    og_image: Optional[str] = None
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    twitter_image: Optional[str] = None
    twitter_title: Optional[str] = None
    twitter_description: Optional[str] = None
    codeinjection_head: Optional[str] = None
    codeinjection_foot: Optional[str] = None
    canonical_url: Optional[str] = None
    accent_color: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @validator('slug')
    def validate_slug(cls, v):
        """Validate slug is unique and URL-safe."""
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError('Slug must be URL-safe (lowercase, alphanumeric, hyphens)')
        return v.lower()

    @validator('visibility')
    def validate_internal_tags(cls, v, values):
        """Validate internal tags start with #."""
        name = values.get('name', '')
        if v == 'internal' and not name.startswith('#'):
            raise ValueError('Internal tags must start with #')
        return v

    @validator('accent_color')
    def validate_accent_color(cls, v):
        """Validate accent color is valid hex color."""
        if v is not None:
            if not v.startswith('#') or len(v) not in [4, 7]:
                raise ValueError('Accent color must be a valid hex color (e.g., #FF0000 or #F00)')
            try:
                int(v[1:], 16)
            except ValueError:
                raise ValueError('Accent color must be a valid hex color')
        return v

    class Config:
        """Pydantic configuration."""
        use_enum_values = True