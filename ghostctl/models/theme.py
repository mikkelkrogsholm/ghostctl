"""Theme model for Ghost CMS."""

from typing import List, Dict, Any
from pydantic import BaseModel


class Theme(BaseModel):
    """Ghost CMS Theme model."""

    name: str
    package: Dict[str, Any]  # package.json contents
    active: bool = False
    templates: List[str] = []

    # Version tracking for rollback
    version: str
    previous_versions: List[str] = []

    class Config:
        """Pydantic configuration."""
        use_enum_values = True