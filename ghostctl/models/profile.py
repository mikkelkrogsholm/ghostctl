"""Profile configuration model for Ghost CMS CLI."""

from pydantic import BaseModel, HttpUrl, validator
from pydantic.types import SecretStr
from typing_extensions import Literal


class Profile(BaseModel):
    """CLI Profile configuration model."""

    name: str = "default"
    api_url: HttpUrl
    admin_api_key: SecretStr
    api_version: str = "v5"

    # Optional settings
    default_output_format: Literal["table", "json", "yaml"] = "table"
    page_size: int = 15
    max_retries: int = 5
    timeout: int = 30

    @validator('page_size')
    def validate_page_size(cls, v):
        """Validate page size is positive."""
        if v <= 0:
            raise ValueError('Page size must be positive')
        return v

    @validator('max_retries')
    def validate_max_retries(cls, v):
        """Validate max retries is non-negative."""
        if v < 0:
            raise ValueError('Max retries must be non-negative')
        return v

    @validator('timeout')
    def validate_timeout(cls, v):
        """Validate timeout is positive."""
        if v <= 0:
            raise ValueError('Timeout must be positive')
        return v

    class Config:
        """Pydantic configuration."""
        use_enum_values = True