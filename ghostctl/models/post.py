"""Post and Page models for Ghost CMS."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, validator
from pydantic.types import SecretStr
from typing_extensions import Literal


class Author(BaseModel):
    """Author model for posts."""
    id: str
    name: str
    slug: str
    email: Optional[str] = None
    profile_image: Optional[str] = None


class Tag(BaseModel):
    """Simplified Tag model for post relationships."""
    id: str
    name: str
    slug: str
    visibility: Literal["public", "internal"] = "public"


class Post(BaseModel):
    """Ghost CMS Post model."""

    id: str
    uuid: str
    title: str
    slug: str
    mobiledoc: Optional[str] = None
    lexical: Optional[str] = None
    html: Optional[str] = None
    feature_image: Optional[str] = None
    featured: bool = False
    status: Literal["draft", "published", "scheduled"]
    visibility: Literal["public", "members", "paid", "tiers"]
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None
    custom_excerpt: Optional[str] = None
    codeinjection_head: Optional[str] = None
    codeinjection_foot: Optional[str] = None
    custom_template: Optional[str] = None
    canonical_url: Optional[str] = None
    tags: List[Tag] = []
    authors: List[Author] = []
    primary_author: Author
    primary_tag: Optional[Tag] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    og_image: Optional[str] = None
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    twitter_image: Optional[str] = None
    twitter_title: Optional[str] = None
    twitter_description: Optional[str] = None

    @validator('slug')
    def validate_slug(cls, v):
        """Validate slug is URL-safe."""
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError('Slug must be URL-safe (lowercase, alphanumeric, hyphens)')
        return v.lower()

    @validator('published_at')
    def validate_published_at(cls, v, values):
        """Validate published_at is required for published/scheduled posts."""
        status = values.get('status')
        if status in ['published', 'scheduled'] and v is None:
            raise ValueError('published_at is required when status is published or scheduled')
        return v

    @validator('lexical')
    def validate_content(cls, v, values):
        """Validate at least one content field is provided."""
        html = values.get('html')
        mobiledoc = values.get('mobiledoc')
        if not any([html, mobiledoc, v]):
            raise ValueError('At least one of html, mobiledoc, or lexical must be provided')
        return v

    class Config:
        """Pydantic configuration."""
        use_enum_values = True


class Page(Post):
    """Ghost CMS Page model - identical to Post but stored separately."""
    pass