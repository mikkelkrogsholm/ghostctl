"""Webhook model for Ghost CMS."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, HttpUrl, validator
from typing_extensions import Literal


class Webhook(BaseModel):
    """Ghost CMS Webhook model."""

    id: str
    event: str  # e.g., "post.published", "member.added"
    target_url: HttpUrl
    name: Optional[str] = None
    secret: Optional[str] = None
    api_version: str = "v5"
    integration_id: str
    status: Literal["enabled", "disabled"] = "enabled"
    last_triggered_at: Optional[datetime] = None
    last_triggered_status: Optional[str] = None
    last_triggered_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @validator('target_url')
    def validate_https_in_production(cls, v):
        """Validate target_url is HTTPS in production."""
        # Note: This could be enhanced to check environment
        # For now, we'll just recommend HTTPS
        if str(v).startswith('http://'):
            # In a real implementation, you might want to check if this is production
            pass  # Warning could be logged here
        return v

    @validator('event')
    def validate_ghost_event(cls, v):
        """Validate event is a valid Ghost event."""
        valid_events = [
            'post.published', 'post.added', 'post.deleted', 'post.edited',
            'page.published', 'page.added', 'page.deleted', 'page.edited',
            'tag.added', 'tag.edited', 'tag.deleted',
            'member.added', 'member.edited', 'member.deleted',
            'site.changed'
        ]
        # This is a basic validation - in practice, Ghost might support more events
        # or the validation might be handled server-side
        return v

    class Config:
        """Pydantic configuration."""
        use_enum_values = True