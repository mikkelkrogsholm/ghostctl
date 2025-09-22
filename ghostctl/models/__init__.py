"""Data models for Ghost CMS CLI.

This package contains Pydantic models for Ghost CMS entities
like posts, tags, members, and API responses following the
Ghost CMS v5 API specifications.
"""

# Import all models from their respective modules
from .post import Post, Page, Author
from .tag import Tag
from .member import Member, Label, Subscription
from .image import Image
from .theme import Theme
from .profile import Profile
from .newsletter import Newsletter
from .tier import Tier
from .offer import Offer
from .webhook import Webhook
from .settings import Settings

# Base model for backward compatibility
from pydantic import BaseModel


class BaseGhostModel(BaseModel):
    """Base model for Ghost CMS entities."""

    class Config:
        """Pydantic configuration."""
        validate_by_name = True
        use_enum_values = True


# Legacy aliases for backward compatibility
User = Author  # User is now Author in the new model
Site = Settings  # Site is now Settings in the new model


__all__ = [
    # Base models
    "BaseGhostModel",

    # Core entities
    "Post",
    "Page",
    "Tag",
    "Member",
    "Image",
    "Theme",
    "Profile",
    "Newsletter",
    "Tier",
    "Offer",
    "Webhook",
    "Settings",

    # Supporting models
    "Author",
    "Label",
    "Subscription",

    # Legacy aliases
    "User",
    "Site",
]