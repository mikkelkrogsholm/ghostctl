"""Command modules for GhostCtl CLI.

This module exports all command groups (Typer apps) that can be registered
with the main application.
"""

# Import all command apps
from .posts import app as posts_app
from .tags import app as tags_app
from .images import app as images_app
from .themes import app as themes_app
from .config import app as config_app
from .pages import app as pages_app
from .members import app as members_app
from .export import app as export_app
from .settings import app as settings_app

__all__ = [
    "posts_app",
    "tags_app",
    "images_app",
    "themes_app",
    "config_app",
    "pages_app",
    "members_app",
    "export_app",
    "settings_app",
]