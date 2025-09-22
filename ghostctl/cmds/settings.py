"""Settings management commands for GhostCtl CLI.

This module provides commands for viewing and updating Ghost CMS site settings.
"""

from typing import Optional, Dict, Any, Tuple
import builtins
from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table

from ..client import GhostClient
from ..render import OutputFormatter
from ..exceptions import GhostCtlError

app = typer.Typer()
console = Console()


def get_client_and_formatter(ctx: typer.Context) -> Tuple[GhostClient, OutputFormatter]:
    """Get client and formatter from context."""
    profile = ctx.obj["profile"]
    if not profile:
        console.print("[red]No profile configured. Run 'ghostctl config init' first.[/red]")
        raise typer.Exit(1)

    client = GhostClient(
        profile=profile,
        timeout=ctx.obj["timeout"],
        retry_attempts=ctx.obj["max_retries"],
    )
    formatter = ctx.obj["output_formatter"]
    return client, formatter


@app.command()
def list(
    ctx: typer.Context,
    filter_pattern: Optional[str] = typer.Option(None, "--filter", help="Filter settings by key pattern"),
    category: Optional[str] = typer.Option(None, "--category", help="Show only specific category (site, social, navigation, etc.)"),
) -> None:
    """List all site settings.

    Examples:
        # List all settings
        ghostctl settings list

        # Filter settings by pattern
        ghostctl settings list --filter "title"

        # Show navigation settings
        ghostctl settings list --category navigation

        # Output in JSON format
        ghostctl settings list --output json
    """
    client, formatter = get_client_and_formatter(ctx)

    if ctx.obj["dry_run"]:
        console.print("[yellow]DRY RUN: Would list site settings with:[/yellow]")
        console.print(f"  Filter: {filter_pattern or 'none'}")
        console.print(f"  Category: {category or 'all'}")
        return

    try:
        settings = client.get_settings()

        # Filter settings if pattern provided
        if filter_pattern:
            filtered_settings = {}
            for key, value in settings.items():
                if filter_pattern.lower() in key.lower():
                    filtered_settings[key] = value
            settings = filtered_settings

        # Category-based filtering
        category_mapping = {
            "site": ["title", "description", "logo", "icon", "accent_color", "cover_image", "timezone", "locale"],
            "social": ["facebook", "twitter", "instagram", "youtube", "linkedin", "github"],
            "navigation": ["navigation", "secondary_navigation"],
            "subscription": ["members_signup_access", "default_content_visibility", "members_support_address"],
            "publication": ["publication_title", "publication_description", "publication_cover", "publication_icon"],
            "branding": ["accent_color", "logo", "icon", "cover_image"],
        }

        if category and category in category_mapping:
            category_keys = category_mapping[category]
            filtered_settings = {}
            for key, value in settings.items():
                if any(cat_key in key for cat_key in category_keys):
                    filtered_settings[key] = value
            settings = filtered_settings

        if ctx.obj["output_format"] in ["json", "yaml"]:
            formatter.render({"settings": settings}, format_override=ctx.obj["output_format"])
        else:
            # Table format
            table = Table(title="Site Settings")
            table.add_column("Setting", style="cyan", no_wrap=True)
            table.add_column("Value", style="bold")
            table.add_column("Type", style="dim")

            for key, value in sorted(settings.items()):
                # Format value for display
                if value is None:
                    display_value = "[dim]null[/dim]"
                    value_type = "null"
                elif isinstance(value, bool):
                    display_value = "✓ True" if value else "✗ False"
                    value_type = "boolean"
                elif isinstance(value, (int, float)):
                    display_value = str(value)
                    value_type = "number"
                elif isinstance(value, str):
                    if len(value) > 100:
                        display_value = value[:97] + "..."
                    else:
                        display_value = value
                    value_type = "string"
                elif isinstance(value, (builtins.list, builtins.dict)):
                    display_value = f"[dim]{type(value).__name__} ({len(value)} items)[/dim]"
                    value_type = type(value).__name__
                else:
                    display_value = str(value)
                    value_type = type(value).__name__

                table.add_row(key, display_value, value_type)

            console.print(table)

    except GhostCtlError as e:
        console.print(f"[red]Error listing settings: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def get(
    ctx: typer.Context,
    setting_key: str = typer.Argument(..., help="Setting key to retrieve"),
) -> None:
    """Get a specific setting value.

    Examples:
        # Get site title
        ghostctl settings get title

        # Get site description
        ghostctl settings get description

        # Get timezone
        ghostctl settings get timezone
    """
    client, formatter = get_client_and_formatter(ctx)

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would get setting '{setting_key}'[/yellow]")
        return

    try:
        settings = client.get_settings()

        if setting_key not in settings:
            console.print(f"[red]Setting '{setting_key}' not found[/red]")
            available_keys = list(settings.keys())[:10]  # Show first 10
            console.print(f"[dim]Available settings: {', '.join(available_keys)}{'...' if len(settings) > 10 else ''}[/dim]")
            raise typer.Exit(1)

        value = settings[setting_key]

        if ctx.obj["output_format"] in ["json", "yaml"]:
            formatter.render({
                "setting": setting_key,
                "value": value
            }, format_override=ctx.obj["output_format"])
        else:
            console.print(f"[cyan]{setting_key}:[/cyan] {value}")

    except GhostCtlError as e:
        console.print(f"[red]Error getting setting: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def update(
    ctx: typer.Context,
    setting_key: str = typer.Argument(..., help="Setting key to update"),
    value: str = typer.Argument(..., help="New value for the setting"),
    value_type: str = typer.Option("auto", "--type", help="Value type (auto, string, number, boolean)"),
) -> None:
    """Update a site setting.

    Examples:
        # Update site title
        ghostctl settings update title "My New Blog Title"

        # Update description
        ghostctl settings update description "A blog about technology"

        # Update boolean setting
        ghostctl settings update members_signup_access "true" --type boolean

        # Update number setting
        ghostctl settings update posts_per_page "10" --type number
    """
    client, formatter = get_client_and_formatter(ctx)

    # Convert value to appropriate type
    converted_value = value
    if value_type == "auto":
        # Auto-detect type
        if value.lower() in ["true", "false"]:
            converted_value = value.lower() == "true"
        elif value.isdigit():
            converted_value = int(value)
        elif value.replace(".", "").isdigit():
            converted_value = float(value)
        # else: keep as string
    elif value_type == "boolean":
        converted_value = value.lower() in ["true", "1", "yes", "on"]
    elif value_type == "number":
        try:
            converted_value = int(value)
        except ValueError:
            try:
                converted_value = float(value)
            except ValueError:
                console.print(f"[red]Invalid number format: {value}[/red]")
                raise typer.Exit(1)
    # else: keep as string

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would update setting '{setting_key}' to '{converted_value}' (type: {type(converted_value).__name__})[/yellow]")
        return

    try:
        # Get current settings to verify key exists
        current_settings = client.get_settings()

        if setting_key not in current_settings:
            console.print(f"[red]Setting '{setting_key}' not found[/red]")
            # Suggest similar keys
            similar_keys = [key for key in current_settings.keys() if setting_key.lower() in key.lower()]
            if similar_keys:
                console.print(f"[dim]Did you mean: {', '.join(similar_keys[:5])}?[/dim]")
            raise typer.Exit(1)

        # Update the setting
        update_data = {setting_key: converted_value}
        updated_settings = client.update_settings(update_data)

        console.print(f"[green]Setting updated successfully![/green]")

        if ctx.obj["output_format"] in ["json", "yaml"]:
            formatter.render({
                "setting": setting_key,
                "old_value": current_settings[setting_key],
                "new_value": converted_value,
                "updated_settings": updated_settings
            }, format_override=ctx.obj["output_format"])
        else:
            console.print(f"[cyan]{setting_key}:[/cyan]")
            console.print(f"  Old value: {current_settings[setting_key]}")
            console.print(f"  New value: {converted_value}")

    except GhostCtlError as e:
        console.print(f"[red]Error updating setting: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def backup(
    ctx: typer.Context,
    output_file: Optional[str] = typer.Option(None, "--output", help="Output file path (default: settings-backup-YYYY-MM-DD.json)"),
) -> None:
    """Backup current site settings to a JSON file.

    Examples:
        # Backup with automatic filename
        ghostctl settings backup

        # Backup to specific file
        ghostctl settings backup --output my-settings.json
    """
    client, formatter = get_client_and_formatter(ctx)

    if not output_file:
        timestamp = datetime.now().strftime("%Y-%m-%d")
        output_file = f"settings-backup-{timestamp}.json"

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would backup settings to '{output_file}'[/yellow]")
        return

    try:
        settings = client.get_settings()

        # Create backup data
        backup_data = {
            "meta": {
                "backup_date": datetime.now().isoformat(),
                "ghost_version": settings.get("version", "unknown"),
                "site_title": settings.get("title", "unknown"),
            },
            "settings": settings
        }

        # Write backup file
        import json
        from pathlib import Path

        output_path = Path(output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2, default=str)

        file_size = output_path.stat().st_size
        console.print(f"[green]Settings backed up successfully![/green]")
        console.print(f"  Output file: {output_file}")
        console.print(f"  File size: {file_size:,} bytes")
        console.print(f"  Settings count: {len(settings)}")

        if ctx.obj["output_format"] in ["json", "yaml"]:
            formatter.render({
                "output_file": output_file,
                "file_size": file_size,
                "settings_count": len(settings),
                "backup_date": backup_data["meta"]["backup_date"],
            }, format_override=ctx.obj["output_format"])

    except GhostCtlError as e:
        console.print(f"[red]Error backing up settings: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def restore(
    ctx: typer.Context,
    backup_file: str = typer.Argument(..., help="Path to settings backup JSON file"),
    exclude_keys: Optional[str] = typer.Option(None, "--exclude", help="Comma-separated list of keys to exclude"),
    include_only: Optional[str] = typer.Option(None, "--include-only", help="Comma-separated list of keys to include (ignores others)"),
    force: bool = typer.Option(False, "--force", help="Restore without confirmation"),
) -> None:
    """Restore site settings from a backup file.

    Examples:
        # Restore all settings
        ghostctl settings restore settings-backup.json

        # Restore excluding sensitive settings
        ghostctl settings restore backup.json --exclude "slack_url,mailgun_api_key"

        # Restore only specific settings
        ghostctl settings restore backup.json --include-only "title,description,timezone"

        # Force restore without confirmation
        ghostctl settings restore backup.json --force
    """
    client, formatter = get_client_and_formatter(ctx)

    from pathlib import Path
    import json

    backup_path = Path(backup_file)
    if not backup_path.exists():
        console.print(f"[red]Backup file not found: {backup_file}[/red]")
        raise typer.Exit(1)

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would restore settings from '{backup_file}' with:[/yellow]")
        console.print(f"  Exclude keys: {exclude_keys or 'none'}")
        console.print(f"  Include only: {include_only or 'all'}")
        return

    try:
        # Load backup file
        with open(backup_path, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)

        if "settings" not in backup_data:
            console.print("[red]Invalid backup file format: missing 'settings' key[/red]")
            raise typer.Exit(1)

        backup_settings = backup_data["settings"]

        # Process include/exclude filters
        settings_to_restore = {}

        if include_only:
            include_keys = [key.strip() for key in include_only.split(",")]
            for key in include_keys:
                if key in backup_settings:
                    settings_to_restore[key] = backup_settings[key]
        else:
            settings_to_restore = backup_settings.copy()

            if exclude_keys:
                exclude_list = [key.strip() for key in exclude_keys.split(",")]
                for key in exclude_list:
                    settings_to_restore.pop(key, None)

        if not settings_to_restore:
            console.print("[yellow]No settings to restore after filtering[/yellow]")
            return

        # Show what will be restored
        console.print(f"[blue]Settings to restore: {len(settings_to_restore)}[/blue]")

        if not force:
            # Get current settings for comparison
            current_settings = client.get_settings()

            console.print("\n[yellow]Settings that will be changed:[/yellow]")
            changes_count = 0
            for key, new_value in settings_to_restore.items():
                if key in current_settings:
                    current_value = current_settings[key]
                    if current_value != new_value:
                        console.print(f"  {key}: {current_value} → {new_value}")
                        changes_count += 1
                else:
                    console.print(f"  {key}: [new] → {new_value}")
                    changes_count += 1

            if changes_count == 0:
                console.print("[green]All settings are already up to date![/green]")
                return

            console.print(f"\n[yellow]Total changes: {changes_count}[/yellow]")

            if "meta" in backup_data:
                meta = backup_data["meta"]
                console.print(f"[dim]Backup from: {meta.get('backup_date', 'unknown')}[/dim]")
                console.print(f"[dim]Original site: {meta.get('site_title', 'unknown')}[/dim]")

            confirm = typer.confirm("Do you want to proceed with the restore?")
            if not confirm:
                console.print("[yellow]Restore cancelled[/yellow]")
                return

        # Restore settings
        updated_settings = client.update_settings(settings_to_restore)

        console.print(f"[green]Settings restored successfully![/green]")
        console.print(f"  Restored {len(settings_to_restore)} settings")

        if ctx.obj["output_format"] in ["json", "yaml"]:
            formatter.render({
                "backup_file": backup_file,
                "restored_count": len(settings_to_restore),
                "updated_settings": updated_settings
            }, format_override=ctx.obj["output_format"])

    except json.JSONDecodeError as e:
        console.print(f"[red]Invalid JSON in backup file: {e}[/red]")
        raise typer.Exit(1)
    except GhostCtlError as e:
        console.print(f"[red]Error restoring settings: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def diff(
    ctx: typer.Context,
    backup_file: str = typer.Argument(..., help="Path to settings backup JSON file"),
    show_unchanged: bool = typer.Option(False, "--show-unchanged", help="Show unchanged settings too"),
) -> None:
    """Compare current settings with a backup file.

    Examples:
        # Show differences with backup
        ghostctl settings diff settings-backup.json

        # Show all settings (changed and unchanged)
        ghostctl settings diff backup.json --show-unchanged
    """
    client, formatter = get_client_and_formatter(ctx)

    from pathlib import Path
    import json

    backup_path = Path(backup_file)
    if not backup_path.exists():
        console.print(f"[red]Backup file not found: {backup_file}[/red]")
        raise typer.Exit(1)

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would compare current settings with '{backup_file}'[/yellow]")
        return

    try:
        # Load backup file and current settings
        with open(backup_path, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)

        if "settings" not in backup_data:
            console.print("[red]Invalid backup file format: missing 'settings' key[/red]")
            raise typer.Exit(1)

        backup_settings = backup_data["settings"]
        current_settings = client.get_settings()

        # Compare settings
        all_keys = set(backup_settings.keys()) | set(current_settings.keys())
        changes = []
        unchanged = []
        new_settings = []
        removed_settings = []

        for key in sorted(all_keys):
            backup_value = backup_settings.get(key)
            current_value = current_settings.get(key)

            if key not in backup_settings:
                new_settings.append((key, current_value))
            elif key not in current_settings:
                removed_settings.append((key, backup_value))
            elif backup_value != current_value:
                changes.append((key, backup_value, current_value))
            else:
                unchanged.append((key, current_value))

        if ctx.obj["output_format"] in ["json", "yaml"]:
            formatter.render({
                "backup_file": backup_file,
                "comparison": {
                    "changed": [{"key": k, "backup_value": bv, "current_value": cv} for k, bv, cv in changes],
                    "new": [{"key": k, "value": v} for k, v in new_settings],
                    "removed": [{"key": k, "value": v} for k, v in removed_settings],
                    "unchanged": [{"key": k, "value": v} for k, v in unchanged] if show_unchanged else [],
                },
                "summary": {
                    "changed": len(changes),
                    "new": len(new_settings),
                    "removed": len(removed_settings),
                    "unchanged": len(unchanged),
                }
            }, format_override=ctx.obj["output_format"])
        else:
            # Show backup metadata
            if "meta" in backup_data:
                meta = backup_data["meta"]
                console.print(f"[dim]Comparing with backup from: {meta.get('backup_date', 'unknown')}[/dim]")
                console.print(f"[dim]Original site: {meta.get('site_title', 'unknown')}[/dim]\n")

            # Show changes
            if changes:
                console.print(f"[red]Changed settings ({len(changes)}):[/red]")
                for key, backup_value, current_value in changes:
                    console.print(f"  [cyan]{key}:[/cyan]")
                    console.print(f"    Backup:  {backup_value}")
                    console.print(f"    Current: {current_value}")
                console.print()

            if new_settings:
                console.print(f"[green]New settings ({len(new_settings)}):[/green]")
                for key, value in new_settings:
                    console.print(f"  [cyan]{key}:[/cyan] {value}")
                console.print()

            if removed_settings:
                console.print(f"[yellow]Removed settings ({len(removed_settings)}):[/yellow]")
                for key, value in removed_settings:
                    console.print(f"  [cyan]{key}:[/cyan] {value}")
                console.print()

            if show_unchanged and unchanged:
                console.print(f"[dim]Unchanged settings ({len(unchanged)}):[/dim]")
                for key, value in unchanged:
                    console.print(f"  [cyan]{key}:[/cyan] {value}")
                console.print()

            # Summary
            console.print(f"[bold]Summary:[/bold]")
            console.print(f"  Changed: {len(changes)}")
            console.print(f"  New: {len(new_settings)}")
            console.print(f"  Removed: {len(removed_settings)}")
            console.print(f"  Unchanged: {len(unchanged)}")

    except json.JSONDecodeError as e:
        console.print(f"[red]Invalid JSON in backup file: {e}[/red]")
        raise typer.Exit(1)
    except GhostCtlError as e:
        console.print(f"[red]Error comparing settings: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()