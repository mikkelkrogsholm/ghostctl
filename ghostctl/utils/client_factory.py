"""Client factory for dependency injection.

This module provides a centralized factory for creating GhostClient instances
with proper configuration and dependency injection support.
"""

import os
from typing import Optional, Dict, Any
import typer
from rich.console import Console

from ..client import GhostClient
from ..config import ConfigManager, Profile
from ..exceptions import ConfigError, GhostCtlError
from .exceptions import format_error_for_user


class ClientFactory:
    """Factory for creating configured GhostClient instances."""

    def __init__(self, console: Optional[Console] = None):
        """Initialize the client factory.

        Args:
            console: Rich console instance for output
        """
        self.console = console or Console()

    def create_client_from_context(self, ctx: typer.Context) -> GhostClient:
        """Create a GhostClient from Typer context.

        Args:
            ctx: Typer context containing configuration

        Returns:
            Configured GhostClient instance

        Raises:
            ConfigError: If configuration is invalid or missing
            GhostCtlError: If client creation fails
        """
        try:
            # Get configuration from context
            profile = ctx.obj.get("profile")
            debug = ctx.obj.get("debug", False)
            timeout = ctx.obj.get("timeout", 30)
            max_retries = ctx.obj.get("max_retries", 3)

            # Check for environment variable overrides
            env_url = os.getenv("GHOST_API_URL")
            env_admin_key = os.getenv("GHOST_ADMIN_API_KEY")
            env_content_key = os.getenv("GHOST_CONTENT_API_KEY")

            # Create client with environment overrides if available
            if env_url and (env_admin_key or env_content_key):
                if debug:
                    self.console.print("[dim]Using environment variables for Ghost connection[/dim]")

                return GhostClient(
                    url=env_url,
                    admin_key=env_admin_key,
                    content_key=env_content_key,
                    timeout=timeout,
                    retry_attempts=max_retries,
                    debug=debug,
                )

            # Use profile configuration
            if not profile:
                error_msg = (
                    "No Ghost configuration found. Please either:\n"
                    "  1. Run 'ghostctl config init' to set up a profile, or\n"
                    "  2. Set environment variables: GHOST_API_URL and GHOST_ADMIN_API_KEY"
                )
                raise ConfigError(error_msg)

            if debug:
                self.console.print(f"[dim]Using profile: {profile.name}[/dim]")

            return GhostClient(
                profile=profile,
                timeout=timeout,
                retry_attempts=max_retries,
                debug=debug,
            )

        except Exception as e:
            if isinstance(e, (ConfigError, GhostCtlError)):
                raise
            raise GhostCtlError(f"Failed to create Ghost client: {e}")

    def create_client_from_profile(
        self,
        profile: Profile,
        debug: bool = False,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
    ) -> GhostClient:
        """Create a GhostClient from a specific profile.

        Args:
            profile: Configuration profile
            debug: Enable debug mode
            timeout: Request timeout (uses profile default if None)
            max_retries: Max retry attempts (uses profile default if None)

        Returns:
            Configured GhostClient instance
        """
        return GhostClient(
            profile=profile,
            timeout=timeout or profile.timeout,
            retry_attempts=max_retries or profile.retry_attempts,
            debug=debug,
        )

    def create_client_from_env(
        self,
        debug: bool = False,
        timeout: int = 30,
        max_retries: int = 3,
    ) -> GhostClient:
        """Create a GhostClient from environment variables only.

        Args:
            debug: Enable debug mode
            timeout: Request timeout
            max_retries: Max retry attempts

        Returns:
            Configured GhostClient instance

        Raises:
            ConfigError: If required environment variables are missing
        """
        env_url = os.getenv("GHOST_API_URL")
        env_admin_key = os.getenv("GHOST_ADMIN_API_KEY")
        env_content_key = os.getenv("GHOST_CONTENT_API_KEY")

        if not env_url:
            raise ConfigError("GHOST_API_URL environment variable is required")

        if not (env_admin_key or env_content_key):
            raise ConfigError(
                "Either GHOST_ADMIN_API_KEY or GHOST_CONTENT_API_KEY environment variable is required"
            )

        return GhostClient(
            url=env_url,
            admin_key=env_admin_key,
            content_key=env_content_key,
            timeout=timeout,
            retry_attempts=max_retries,
            debug=debug,
        )

    def test_client_connection(
        self,
        client: GhostClient,
        show_details: bool = False,
    ) -> bool:
        """Test client connection and optionally show details.

        Args:
            client: GhostClient to test
            show_details: Whether to show connection details

        Returns:
            True if connection successful, False otherwise
        """
        try:
            if client.test_connection():
                if show_details:
                    try:
                        site_info = client.get_site_info()
                        self.console.print("[green]✓[/green] Connection successful")
                        if "site" in site_info:
                            site = site_info["site"]
                            self.console.print(f"  Site: {site.get('title', 'Unknown')}")
                            self.console.print(f"  URL: {site.get('url', 'Unknown')}")
                            self.console.print(f"  Version: {site.get('version', 'Unknown')}")

                        # Show rate limit info if available
                        rate_limit_info = client.get_rate_limit_info()
                        if rate_limit_info.get("remaining"):
                            self.console.print(f"  Rate limit remaining: {rate_limit_info['remaining']}")

                    except Exception as e:
                        self.console.print("[green]✓[/green] Connection successful (limited info available)")
                        if client.debug:
                            self.console.print(f"[dim]Debug: {e}[/dim]")
                else:
                    self.console.print("[green]✓[/green] Connection successful")
                return True
            else:
                self.console.print("[red]✗[/red] Connection failed")
                return False

        except Exception as e:
            self.console.print(f"[red]✗[/red] Connection failed: {format_error_for_user(e, client.debug)}")
            return False


# Global factory instance
_client_factory = ClientFactory()


def get_client_from_context(ctx: typer.Context) -> GhostClient:
    """Convenience function to get client from context.

    Args:
        ctx: Typer context

    Returns:
        Configured GhostClient instance
    """
    return _client_factory.create_client_from_context(ctx)


def get_client_and_formatter(ctx: typer.Context) -> tuple[GhostClient, Any]:
    """Get both client and formatter from context.

    Args:
        ctx: Typer context

    Returns:
        Tuple of (GhostClient, OutputFormatter)
    """
    client = get_client_from_context(ctx)
    formatter = ctx.obj["output_formatter"]
    return client, formatter


def validate_client_connection(client: GhostClient, exit_on_failure: bool = True) -> bool:
    """Validate client connection and optionally exit on failure.

    Args:
        client: GhostClient to validate
        exit_on_failure: Whether to exit on connection failure

    Returns:
        True if connection is valid
    """
    if client.test_connection():
        return True

    if exit_on_failure:
        Console().print("[red]Failed to connect to Ghost CMS. Please check your configuration.[/red]")
        raise typer.Exit(1)

    return False


def create_client_with_error_handling(
    profile: Optional[Profile] = None,
    url: Optional[str] = None,
    admin_key: Optional[str] = None,
    content_key: Optional[str] = None,
    debug: bool = False,
    console: Optional[Console] = None,
) -> Optional[GhostClient]:
    """Create a client with comprehensive error handling.

    Args:
        profile: Configuration profile
        url: Ghost URL
        admin_key: Admin API key
        content_key: Content API key
        debug: Enable debug mode
        console: Console for output

    Returns:
        GhostClient instance or None if creation failed
    """
    console = console or Console()

    try:
        if profile:
            return GhostClient(profile=profile, debug=debug)
        elif url:
            return GhostClient(
                url=url,
                admin_key=admin_key,
                content_key=content_key,
                debug=debug,
            )
        else:
            # Try environment variables
            return _client_factory.create_client_from_env(debug=debug)

    except Exception as e:
        error_msg = format_error_for_user(e, debug)
        console.print(f"[red]Failed to create Ghost client: {error_msg}[/red]")
        return None