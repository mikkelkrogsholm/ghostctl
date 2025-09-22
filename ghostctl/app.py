"""Main Typer application for GhostCtl CLI.

This module contains the main Typer app instance and registers all command groups.
It provides the entry point for the CLI and handles global options like profile,
debug mode, output formatting, and environment variable integration.
"""

import os
import sys
from typing import Optional
from pathlib import Path

import typer
from rich.console import Console
from rich.traceback import install

from . import __version__
from .config import ConfigManager, Profile
from .render import OutputFormatter
from .exceptions import GhostCtlError, ConfigError
from .utils.exceptions import format_error_for_user

# Install rich traceback handler for better error display
install(show_locals=True)

# Create main Typer app
app = typer.Typer(
    name="ghostctl",
    help="Command-line tool for managing Ghost CMS instances",
    context_settings={"help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Global state for shared objects
console = Console()
config_manager = ConfigManager()
output_formatter = OutputFormatter(console)


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        typer.echo(f"ghostctl {__version__}")
        raise typer.Exit()


def validate_profile_callback(ctx: typer.Context, param: typer.CallbackParam, value: Optional[str]) -> Optional[str]:
    """Validate profile exists and load it."""
    if value is None:
        return value

    try:
        profile = config_manager.get_profile(value)
        # Store profile in context for commands to use
        ctx.meta = ctx.meta or {}
        ctx.meta["profile"] = profile
        return value
    except ConfigError as e:
        console.print(f"[red]Error loading profile '{value}': {e}[/red]")
        raise typer.Exit(1)


def show_environment_info(debug: bool) -> None:
    """Show environment variable information if debug is enabled."""
    if not debug:
        return

    console.print("[dim]Environment variables:[/dim]")
    env_vars = {
        "GHOST_API_URL": os.getenv("GHOST_API_URL", "[not set]"),
        "GHOST_ADMIN_API_KEY": "[set]" if os.getenv("GHOST_ADMIN_API_KEY") else "[not set]",
        "GHOST_CONTENT_API_KEY": "[set]" if os.getenv("GHOST_CONTENT_API_KEY") else "[not set]",
    }

    for var, value in env_vars.items():
        console.print(f"  {var}: {value}")


# Global options
@app.callback()
def main(
    ctx: typer.Context,
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        "-p",
        help="Configuration profile to use",
        callback=validate_profile_callback,
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable debug output",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be done without making changes",
    ),
    output_format: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output format (table, json, yaml)",
    ),
    timeout: int = typer.Option(
        30,
        "--timeout",
        help="Request timeout in seconds",
    ),
    max_retries: int = typer.Option(
        3,
        "--max-retries",
        help="Maximum number of retry attempts",
    ),
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """GhostCtl - Command-line tool for managing Ghost CMS instances.

    GhostCtl provides a comprehensive command-line interface for managing
    Ghost CMS instances including content management, user administration,
    theme management, and automation capabilities.

    Examples:
        # List all posts
        ghostctl posts list

        # Create a new post
        ghostctl posts create --title "My Post" --content "Hello World"

        # Upload and activate a theme
        ghostctl themes upload theme.zip --activate

        # Export all content
        ghostctl export all --output backup.json
    """
    # Store global options in context
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug
    ctx.obj["dry_run"] = dry_run
    ctx.obj["output_format"] = output_format
    ctx.obj["timeout"] = timeout
    ctx.obj["max_retries"] = max_retries
    ctx.obj["console"] = console
    ctx.obj["config_manager"] = config_manager
    ctx.obj["output_formatter"] = output_formatter

    # Get profile from callback or use default
    profile_obj = ctx.meta.get("profile") if ctx.meta else None
    if profile_obj is None:
        try:
            profile_obj = config_manager.get_default_profile()
        except ConfigError:
            # No default profile - check if environment variables are available
            env_url = os.getenv("GHOST_API_URL")
            env_admin_key = os.getenv("GHOST_ADMIN_API_KEY")
            env_content_key = os.getenv("GHOST_CONTENT_API_KEY")

            if env_url and (env_admin_key or env_content_key):
                # Create a temporary profile from environment variables
                try:
                    profile_obj = Profile(
                        name="env",
                        url=env_url,
                        admin_key=env_admin_key,
                        content_key=env_content_key,
                    )
                    if debug:
                        console.print("[dim]Created temporary profile from environment variables[/dim]")
                except Exception as e:
                    if debug:
                        console.print(f"[dim]Failed to create profile from environment: {e}[/dim]")
                    profile_obj = None
            else:
                profile_obj = None

    ctx.obj["profile"] = profile_obj

    # Configure debug mode
    if debug:
        console.print("[dim]Debug mode enabled[/dim]")
        show_environment_info(debug)

        # Show profile override information
        if profile_obj:
            console.print(f"[dim]Using profile: {profile_obj.name}[/dim]")
            # Check for environment overrides
            env_overrides = []
            if os.getenv("GHOST_API_URL"):
                env_overrides.append("GHOST_API_URL")
            if os.getenv("GHOST_ADMIN_API_KEY"):
                env_overrides.append("GHOST_ADMIN_API_KEY")
            if os.getenv("GHOST_CONTENT_API_KEY"):
                env_overrides.append("GHOST_CONTENT_API_KEY")

            if env_overrides:
                console.print(f"[dim]Environment overrides active: {', '.join(env_overrides)}[/dim]")


def handle_exceptions(func):
    """Decorator to handle common exceptions in commands."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except GhostCtlError as e:
            ctx = typer.get_current_context()
            debug = ctx.obj.get("debug", False) if ctx else False
            error_msg = format_error_for_user(e, debug)
            console.print(f"[red]{error_msg}[/red]")
            if not debug and not isinstance(e, ConfigError):
                console.print("[dim]Use --debug for more details[/dim]")
            raise typer.Exit(1)
        except KeyboardInterrupt:
            console.print("\n[yellow]Operation cancelled by user[/yellow]")
            raise typer.Exit(130)
        except Exception as e:
            ctx = typer.get_current_context()
            debug = ctx.obj.get("debug", False) if ctx else False

            if debug:
                console.print_exception(show_locals=True)
            else:
                console.print(f"[red]Unexpected error: {e}[/red]")
                console.print("[dim]Use --debug for more details[/dim]")
            raise typer.Exit(1)
    return wrapper


# Import and register command groups
def register_commands():
    """Register all command groups with the main app."""
    try:
        from .cmds import (
            posts_app,
            tags_app,
            images_app,
            themes_app,
            config_app,
            pages_app,
            members_app,
            export_app,
            settings_app,
        )

        # Register command groups
        app.add_typer(posts_app, name="posts", help="Manage posts")
        app.add_typer(tags_app, name="tags", help="Manage tags")
        app.add_typer(images_app, name="images", help="Manage images")
        app.add_typer(themes_app, name="themes", help="Manage themes")
        app.add_typer(config_app, name="config", help="Manage configuration")
        app.add_typer(pages_app, name="pages", help="Manage pages")
        app.add_typer(members_app, name="members", help="Manage members")
        app.add_typer(export_app, name="export", help="Export content")
        app.add_typer(settings_app, name="settings", help="Manage settings")

    except ImportError as e:
        console.print(f"[red]Error importing commands: {e}[/red]")
        console.print("[dim]Some commands may not be available[/dim]")


# Don't register commands immediately to avoid circular imports
# register_commands() will be called by cli() when needed


# Convenience function for CLI entry point
def cli():
    """Entry point for the CLI."""
    # Register commands on first run
    register_commands()

    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        # Last resort error handling
        console.print(f"[red]Fatal error: {e}[/red]")
        console.print("[dim]Please report this issue if it persists[/dim]")
        sys.exit(1)


if __name__ == "__main__":
    cli()