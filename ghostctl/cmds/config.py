"""Configuration management commands for GhostCtl CLI.

This module provides commands for managing Ghost CMS configuration profiles
including initialization, validation, and profile management.
"""

from pathlib import Path
from typing import Optional
import os

import typer
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm

from ..config import ConfigManager, Profile
from ..render import OutputFormatter
from ..exceptions import GhostCtlError, ConfigError
from ..client import GhostClient

app = typer.Typer()
console = Console()


@app.command()
def init(
    ctx: typer.Context,
    profile_name: str = typer.Option("default", "--profile", help="Profile name"),
    url: Optional[str] = typer.Option(None, "--url", help="Ghost CMS URL"),
    admin_key: Optional[str] = typer.Option(None, "--admin-key", help="Admin API key"),
    content_key: Optional[str] = typer.Option(None, "--content-key", help="Content API key"),
    api_version: str = typer.Option("v5", "--api-version", help="Ghost API version"),
    interactive: bool = typer.Option(True, "--interactive", help="Interactive setup"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing profile"),
) -> None:
    """Initialize a new configuration profile.

    Examples:
        # Interactive setup
        ghostctl config init

        # Non-interactive setup
        ghostctl config init --no-interactive --url "https://blog.example.com" --admin-key "key"

        # Create a named profile
        ghostctl config init --profile production --url "https://blog.com"

        # Force overwrite existing profile
        ghostctl config init --profile staging --force
    """
    config_manager = ctx.obj["config_manager"]
    formatter = ctx.obj["output_formatter"]

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would initialize profile '{profile_name}' with:[/yellow]")
        console.print(f"  URL: {url or 'interactive'}")
        console.print(f"  Admin Key: {'provided' if admin_key else 'interactive'}")
        console.print(f"  Content Key: {'provided' if content_key else 'interactive'}")
        console.print(f"  API Version: {api_version}")
        console.print(f"  Interactive: {interactive}")
        return

    try:
        # Check if profile already exists
        existing_profiles = config_manager.list_profiles()
        if profile_name in existing_profiles and not force:
            console.print(f"[red]Profile '{profile_name}' already exists. Use --force to overwrite.[/red]")
            raise typer.Exit(1)

        # Interactive mode
        if interactive:
            console.print(f"[bold blue]Setting up profile: {profile_name}[/bold blue]")
            console.print()

            # Get URL
            if not url:
                url = Prompt.ask(
                    "Ghost CMS URL",
                    default="https://your-blog.ghost.io"
                )

            # Get Admin API key
            if not admin_key:
                admin_key = Prompt.ask(
                    "Admin API Key",
                    password=True,
                    show_default=False
                )

            # Get Content API key (optional)
            if not content_key:
                has_content_key = Confirm.ask("Do you have a Content API key?", default=False)
                if has_content_key:
                    content_key = Prompt.ask(
                        "Content API Key",
                        password=True,
                        show_default=False
                    )

            # Confirm API version
            api_version = Prompt.ask(
                "API Version",
                default=api_version,
                choices=["v3", "v4", "v5"]
            )

        # Validate required fields
        if not url:
            console.print("[red]URL is required[/red]")
            raise typer.Exit(1)

        if not admin_key:
            console.print("[red]Admin API key is required[/red]")
            raise typer.Exit(1)

        # Create profile
        profile = Profile(
            name=profile_name,
            api_url=url.rstrip('/'),
            admin_api_key=admin_key,
            content_api_key=content_key,
            api_version=api_version,
        )

        # Test connection
        console.print("\n[blue]Testing connection...[/blue]")
        try:
            client = GhostClient(profile=profile, timeout=10)
            # Try to fetch site settings to validate connection
            client.get_settings()
            console.print("[green]✓ Connection successful![/green]")
        except Exception as e:
            console.print(f"[yellow]⚠ Connection test failed: {e}[/yellow]")
            if interactive:
                continue_anyway = Confirm.ask("Save profile anyway?", default=True)
                if not continue_anyway:
                    console.print("[yellow]Profile creation cancelled[/yellow]")
                    raise typer.Exit(1)

        # Save profile
        config_manager.save_profile(profile)

        # Set as default if it's the first profile
        profiles = config_manager.list_profiles()
        if len(profiles) == 1:
            config_manager.set_default_profile(profile_name)
            console.print(f"[green]Profile '{profile_name}' saved and set as default![/green]")
        else:
            console.print(f"[green]Profile '{profile_name}' saved![/green]")

        if ctx.obj["output_format"] in ["json", "yaml"]:
            # Don't expose sensitive keys in output
            safe_profile = {
                "name": profile.name,
                "api_url": profile.api_url,
                "api_version": profile.api_version,
                "has_admin_key": bool(profile.admin_api_key),
                "has_content_key": bool(profile.content_api_key),
            }
            formatter.render({"profile": safe_profile}, format_override=ctx.obj["output_format"])

    except ConfigError as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Setup cancelled[/yellow]")
        raise typer.Exit(1)


@app.command()
def validate(
    ctx: typer.Context,
    profile_name: Optional[str] = typer.Option(None, "--profile", help="Profile to validate (default: all)"),
) -> None:
    """Validate configuration profiles.

    Examples:
        # Validate all profiles
        ghostctl config validate

        # Validate specific profile
        ghostctl config validate --profile production

        # Validate in CI/CD
        ghostctl config validate --output json
    """
    config_manager = ctx.obj["config_manager"]
    formatter = ctx.obj["output_formatter"]

    if ctx.obj["dry_run"]:
        if profile_name:
            console.print(f"[yellow]DRY RUN: Would validate profile '{profile_name}'[/yellow]")
        else:
            console.print("[yellow]DRY RUN: Would validate all profiles[/yellow]")
        return

    try:
        profiles_to_validate = []

        if profile_name:
            # Validate specific profile
            profile = config_manager.get_profile(profile_name)
            profiles_to_validate = [profile]
        else:
            # Validate all profiles
            profile_names = config_manager.list_profiles()
            for name in profile_names:
                try:
                    profile = config_manager.get_profile(name)
                    profiles_to_validate.append(profile)
                except ConfigError as e:
                    console.print(f"[red]Error loading profile '{name}': {e}[/red]")

        if not profiles_to_validate:
            console.print("[yellow]No profiles found to validate[/yellow]")
            return

        validation_results = []

        for profile in profiles_to_validate:
            console.print(f"\n[blue]Validating profile: {profile.name}[/blue]")

            result = {
                "profile": profile.name,
                "valid": True,
                "errors": [],
                "warnings": [],
            }

            # Basic validation
            if not profile.api_url:
                result["errors"].append("API URL is missing")
                result["valid"] = False

            if not profile.admin_api_key:
                result["errors"].append("Admin API key is missing")
                result["valid"] = False

            if profile.api_url and not profile.api_url.startswith(('http://', 'https://')):
                result["errors"].append("API URL must start with http:// or https://")
                result["valid"] = False

            # Connection test
            if result["valid"]:
                try:
                    client = GhostClient(profile=profile, timeout=10)
                    settings = client.get_settings()
                    console.print("  ✓ Connection successful")
                    console.print(f"  ✓ Site: {settings.get('title', 'Unknown')}")

                    # Check API key permissions
                    try:
                        # Try to get posts (requires admin permissions)
                        client.get_posts(limit=1)
                        console.print("  ✓ Admin API key has required permissions")
                    except Exception:
                        result["warnings"].append("Admin API key may have limited permissions")
                        console.print("  ⚠ Admin API key may have limited permissions")

                except Exception as e:
                    result["errors"].append(f"Connection failed: {str(e)}")
                    result["valid"] = False
                    console.print(f"  ✗ Connection failed: {e}")
            else:
                console.print("  ✗ Skipping connection test due to configuration errors")

            validation_results.append(result)

            # Summary for this profile
            if result["valid"] and not result["warnings"]:
                console.print(f"  [green]✓ Profile '{profile.name}' is valid[/green]")
            elif result["valid"] and result["warnings"]:
                console.print(f"  [yellow]⚠ Profile '{profile.name}' is valid with warnings[/yellow]")
            else:
                console.print(f"  [red]✗ Profile '{profile.name}' has errors[/red]")

        # Overall summary
        valid_count = sum(1 for r in validation_results if r["valid"])
        total_count = len(validation_results)

        console.print(f"\n[bold]Validation Summary:[/bold]")
        console.print(f"  Valid profiles: {valid_count}/{total_count}")

        if ctx.obj["output_format"] in ["json", "yaml"]:
            formatter.render({
                "validation_results": validation_results,
                "summary": {
                    "total": total_count,
                    "valid": valid_count,
                    "invalid": total_count - valid_count,
                }
            }, format_override=ctx.obj["output_format"])

        # Exit with error if any profile is invalid
        if valid_count < total_count:
            raise typer.Exit(1)

    except ConfigError as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        raise typer.Exit(1)


@app.command("list-profiles")
def list_profiles(
    ctx: typer.Context,
) -> None:
    """List all configuration profiles.

    Examples:
        # List all profiles
        ghostctl config list-profiles

        # List profiles in JSON format
        ghostctl config list-profiles --output json
    """
    config_manager = ctx.obj["config_manager"]
    formatter = ctx.obj["output_formatter"]

    if ctx.obj["dry_run"]:
        console.print("[yellow]DRY RUN: Would list all configuration profiles[/yellow]")
        return

    try:
        profile_names = config_manager.list_profiles()

        if not profile_names:
            console.print("[yellow]No profiles configured. Run 'ghostctl config init' to create one.[/yellow]")
            return

        # Get default profile
        try:
            default_profile = config_manager.get_default_profile()
            default_name = default_profile.name if default_profile else None
        except ConfigError:
            default_name = None

        profiles_info = []
        for name in profile_names:
            try:
                profile = config_manager.get_profile(name)
                profiles_info.append({
                    "name": profile.name,
                    "api_url": profile.api_url,
                    "api_version": profile.api_version,
                    "has_admin_key": bool(profile.admin_api_key),
                    "has_content_key": bool(profile.content_api_key),
                    "is_default": name == default_name,
                })
            except ConfigError as e:
                profiles_info.append({
                    "name": name,
                    "error": str(e),
                    "is_default": name == default_name,
                })

        if ctx.obj["output_format"] in ["json", "yaml"]:
            formatter.render({
                "profiles": profiles_info,
                "default_profile": default_name,
            }, format_override=ctx.obj["output_format"])
        else:
            # Table format
            table = Table(title="Configuration Profiles")
            table.add_column("Name", style="bold")
            table.add_column("URL", style="cyan")
            table.add_column("Version", style="dim")
            table.add_column("Admin Key", style="green")
            table.add_column("Content Key", style="blue")
            table.add_column("Default", style="yellow")

            for profile_info in profiles_info:
                if "error" in profile_info:
                    table.add_row(
                        profile_info["name"],
                        f"[red]Error: {profile_info['error']}[/red]",
                        "—",
                        "—",
                        "—",
                        "✓" if profile_info["is_default"] else "—",
                    )
                else:
                    table.add_row(
                        profile_info["name"],
                        profile_info["api_url"],
                        profile_info["api_version"],
                        "✓" if profile_info["has_admin_key"] else "—",
                        "✓" if profile_info["has_content_key"] else "—",
                        "✓" if profile_info["is_default"] else "—",
                    )

            console.print(table)

    except ConfigError as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        raise typer.Exit(1)


@app.command("set-default")
def set_default(
    ctx: typer.Context,
    profile_name: str = typer.Argument(..., help="Profile name to set as default"),
) -> None:
    """Set the default profile.

    Examples:
        # Set production as default
        ghostctl config set-default production

        # Set staging as default
        ghostctl config set-default staging
    """
    config_manager = ctx.obj["config_manager"]

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would set '{profile_name}' as default profile[/yellow]")
        return

    try:
        # Verify profile exists
        config_manager.get_profile(profile_name)

        # Set as default
        config_manager.set_default_profile(profile_name)
        console.print(f"[green]Profile '{profile_name}' set as default![/green]")

    except ConfigError as e:
        console.print(f"[red]Error setting default profile: {e}[/red]")
        raise typer.Exit(1)


@app.command("delete")
def delete_profile(
    ctx: typer.Context,
    profile_name: str = typer.Argument(..., help="Profile name to delete"),
    force: bool = typer.Option(False, "--force", help="Delete without confirmation"),
) -> None:
    """Delete a configuration profile.

    Examples:
        # Delete with confirmation
        ghostctl config delete old-profile

        # Force delete without confirmation
        ghostctl config delete old-profile --force
    """
    config_manager = ctx.obj["config_manager"]

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would delete profile '{profile_name}'[/yellow]")
        return

    try:
        # Verify profile exists
        profile = config_manager.get_profile(profile_name)

        # Check if it's the default profile
        try:
            default_profile = config_manager.get_default_profile()
            is_default = default_profile and default_profile.name == profile_name
        except ConfigError:
            is_default = False

        if not force:
            console.print(f"[yellow]About to delete profile:[/yellow]")
            console.print(f"  Name: {profile.name}")
            console.print(f"  URL: {profile.api_url}")
            console.print(f"  Default: {'Yes' if is_default else 'No'}")

            if is_default:
                console.print("[yellow]Warning: This is the default profile[/yellow]")

            confirm = typer.confirm(f"Are you sure you want to delete profile '{profile_name}'?")
            if not confirm:
                console.print("[yellow]Delete cancelled[/yellow]")
                return

        # Delete profile
        config_manager.delete_profile(profile_name)
        console.print(f"[green]Profile '{profile_name}' deleted successfully![/green]")

        if is_default:
            console.print("[yellow]Note: You may want to set a new default profile[/yellow]")

    except ConfigError as e:
        console.print(f"[red]Error deleting profile: {e}[/red]")
        raise typer.Exit(1)


@app.command("show")
def show_config(
    ctx: typer.Context,
) -> None:
    """Show configuration file location and status.

    Examples:
        # Show config file info
        ghostctl config show

        # Show in JSON format
        ghostctl config show --output json
    """
    config_manager = ctx.obj["config_manager"]
    formatter = ctx.obj["output_formatter"]

    config_file = config_manager.config_file
    config_exists = config_file.exists()

    # Get environment variables
    env_vars = {
        "GHOST_API_URL": os.getenv("GHOST_API_URL"),
        "GHOST_ADMIN_API_KEY": "set" if os.getenv("GHOST_ADMIN_API_KEY") else None,
        "GHOST_CONTENT_API_KEY": "set" if os.getenv("GHOST_CONTENT_API_KEY") else None,
        "GHOST_API_VERSION": os.getenv("GHOST_API_VERSION"),
    }

    if ctx.obj["output_format"] in ["json", "yaml"]:
        formatter.render({
            "config_file": str(config_file),
            "config_exists": config_exists,
            "config_size": config_file.stat().st_size if config_exists else 0,
            "environment_variables": env_vars,
        }, format_override=ctx.obj["output_format"])
    else:
        # Table format
        table = Table(title="Configuration Status")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="bold")

        table.add_row("Config File", str(config_file))
        table.add_row("Exists", "✓ Yes" if config_exists else "✗ No")

        if config_exists:
            table.add_row("Size", f"{config_file.stat().st_size} bytes")

        table.add_row("", "")  # Spacer
        table.add_row("[bold]Environment Variables[/bold]", "")

        for var, value in env_vars.items():
            if value:
                table.add_row(var, value)
            else:
                table.add_row(var, "[dim]not set[/dim]")

        console.print(table)


if __name__ == "__main__":
    app()