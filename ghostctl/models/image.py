"""Image model for Ghost CMS."""

from typing import Optional
from pydantic import BaseModel, HttpUrl


class Image(BaseModel):
    """Ghost CMS Image model."""

    url: HttpUrl
    ref: Optional[str] = None  # Storage reference

    class Config:
        """Pydantic configuration."""
        use_enum_values = True