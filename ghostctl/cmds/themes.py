"""Theme management commands for GhostCtl CLI.

This module provides commands for managing Ghost CMS themes including
listing, uploading, activating, and rolling back themes.
"""

from pathlib import Path
from typing import Optional
import zipfile
import tempfile

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..client import GhostClient
from ..render import OutputFormatter
from ..exceptions import GhostCtlError

app = typer.Typer()
console = Console()


def get_client_and_formatter(ctx: typer.Context) -> tuple[GhostClient, OutputFormatter]:
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


def validate_theme_file(file_path: Path) -> None:
    """Validate that the file is a valid theme package."""
    if not file_path.exists():
        raise GhostCtlError(f"File not found: {file_path}")

    if not file_path.is_file():
        raise GhostCtlError(f"Not a file: {file_path}")

    if file_path.suffix.lower() != '.zip':
        raise GhostCtlError(f"Theme must be a ZIP file, got: {file_path.suffix}")

    # Check if it's a valid ZIP file
    try:
        with zipfile.ZipFile(file_path, 'r') as zip_file:
            # Check for required theme files
            file_list = zip_file.namelist()

            # Look for package.json (required for Ghost themes)
            has_package_json = any(
                name.endswith('package.json') for name in file_list
            )

            # Look for index.hbs (required template)
            has_index_hbs = any(
                name.endswith('index.hbs') for name in file_list
            )

            if not has_package_json:
                raise GhostCtlError("Theme package must contain package.json")

            if not has_index_hbs:
                raise GhostCtlError("Theme package must contain index.hbs template")

    except zipfile.BadZipFile:
        raise GhostCtlError("Invalid ZIP file")

    # Check file size (Ghost usually limits theme uploads)
    max_size = 50 * 1024 * 1024  # 50MB
    if file_path.stat().st_size > max_size:
        size_mb = file_path.stat().st_size / (1024 * 1024)
        raise GhostCtlError(f"Theme file too large: {size_mb:.1f}MB (max 50MB)")


@app.command()
def list(
    ctx: typer.Context,
) -> None:
    """List all available themes.

    Examples:
        # List all themes
        ghostctl themes list

        # List themes in JSON format
        ghostctl themes list --output json
    """
    client, formatter = get_client_and_formatter(ctx)

    if ctx.obj["dry_run"]:
        console.print("[yellow]DRY RUN: Would list all themes[/yellow]")
        return

    try:
        themes = client.get_themes()

        if ctx.obj["output_format"] in ["json", "yaml"]:
            formatter.output({"themes": themes}, format_override=ctx.obj["output_format"])
        else:
            # Table format
            table = Table(title="Themes")
            table.add_column("Name", style="bold")
            table.add_column("Version", style="cyan")
            table.add_column("Active", style="green")
            table.add_column("Templates", style="blue", justify="right")
            table.add_column("Package", style="dim")

            for theme in themes:
                is_active = "✓" if theme.get("active", False) else "—"
                templates = len(theme.get("templates", []))
                package_version = theme.get("package", {}).get("version", "—")

                table.add_row(
                    theme.get("name", "Unknown"),
                    package_version,
                    is_active,
                    str(templates) if templates > 0 else "—",
                    theme.get("package", {}).get("name", "—"),
                )

            console.print(table)

    except GhostCtlError as e:
        console.print(f"[red]Error listing themes: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def upload(
    ctx: typer.Context,
    theme_file: Path = typer.Argument(..., help="Path to theme ZIP file"),
    activate: bool = typer.Option(False, "--activate", help="Activate theme after upload"),
) -> None:
    """Upload a theme package to Ghost CMS.

    Examples:
        # Upload a theme
        ghostctl themes upload my-theme.zip

        # Upload and activate immediately
        ghostctl themes upload my-theme.zip --activate

        # Upload with validation
        ghostctl themes validate my-theme.zip && ghostctl themes upload my-theme.zip
    """
    client, formatter = get_client_and_formatter(ctx)

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would upload theme '{theme_file}'[/yellow]")
        if activate:
            console.print("  And activate it immediately")
        return

    try:
        # Validate the theme file
        validate_theme_file(theme_file)

        # Show progress during upload
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task(f"Uploading {theme_file.name}...", total=None)

            # Upload the theme
            result = client.upload_theme(theme_file, activate=activate)

        if activate:
            console.print(f"[green]Theme uploaded and activated successfully![/green]")
        else:
            console.print(f"[green]Theme uploaded successfully![/green]")

        if ctx.obj["output_format"] in ["json", "yaml"]:
            formatter.output({"themes": [result]}, format_override=ctx.obj["output_format"])
        else:
            # Table format
            table = Table(title="Uploaded Theme")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="bold")

            theme_data = result.get("themes", [{}])[0] if result.get("themes") else result

            table.add_row("Name", theme_data.get("name", "Unknown"))
            table.add_row("Version", theme_data.get("package", {}).get("version", "Unknown"))
            table.add_row("Active", "✓ Yes" if theme_data.get("active", False) else "No")
            table.add_row("Templates", str(len(theme_data.get("templates", []))))
            table.add_row("File Size", f"{theme_file.stat().st_size:,} bytes")

            console.print(table)

    except GhostCtlError as e:
        console.print(f"[red]Error uploading theme: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def activate(
    ctx: typer.Context,
    theme_name: str = typer.Argument(..., help="Name of theme to activate"),
) -> None:
    """Activate an uploaded theme.

    Examples:
        # Activate a theme by name
        ghostctl themes activate casper

        # Activate a custom theme
        ghostctl themes activate my-custom-theme
    """
    client, formatter = get_client_and_formatter(ctx)

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would activate theme '{theme_name}'[/yellow]")
        return

    try:
        result = client.activate_theme(theme_name)
        console.print(f"[green]Theme '{theme_name}' activated successfully![/green]")

        if ctx.obj["output_format"] in ["json", "yaml"]:
            formatter.output({"themes": [result]}, format_override=ctx.obj["output_format"])
        else:
            # Show activated theme info
            theme_data = result.get("themes", [{}])[0] if result.get("themes") else result

            table = Table(title="Activated Theme")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="bold")

            table.add_row("Name", theme_data.get("name", "Unknown"))
            table.add_row("Version", theme_data.get("package", {}).get("version", "Unknown"))
            table.add_row("Active", "✓ Yes")
            table.add_row("Templates", str(len(theme_data.get("templates", []))))

            console.print(table)

    except GhostCtlError as e:
        console.print(f"[red]Error activating theme: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def delete(
    ctx: typer.Context,
    theme_name: str = typer.Argument(..., help="Name of theme to delete"),
    force: bool = typer.Option(False, "--force", help="Delete without confirmation"),
) -> None:
    """Delete an uploaded theme.

    Note: You cannot delete the currently active theme.

    Examples:
        # Delete with confirmation
        ghostctl themes delete old-theme

        # Force delete without confirmation
        ghostctl themes delete old-theme --force
    """
    client, formatter = get_client_and_formatter(ctx)

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would delete theme '{theme_name}'[/yellow]")
        return

    try:
        # Check if theme exists and is not active
        themes = client.get_themes()
        theme_to_delete = None
        active_theme = None

        for theme in themes:
            if theme.get("name") == theme_name:
                theme_to_delete = theme
            if theme.get("active", False):
                active_theme = theme.get("name")

        if not theme_to_delete:
            console.print(f"[red]Theme '{theme_name}' not found[/red]")
            raise typer.Exit(1)

        if theme_to_delete.get("active", False):
            console.print(f"[red]Cannot delete active theme '{theme_name}'. Activate another theme first.[/red]")
            raise typer.Exit(1)

        # Confirmation
        if not force:
            console.print(f"[yellow]About to delete theme:[/yellow]")
            console.print(f"  Name: {theme_name}")
            console.print(f"  Version: {theme_to_delete.get('package', {}).get('version', 'Unknown')}")
            console.print(f"  Currently active: {active_theme}")

            confirm = typer.confirm(f"Are you sure you want to delete theme '{theme_name}'?")
            if not confirm:
                console.print("[yellow]Delete cancelled[/yellow]")
                return

        client.delete_theme(theme_name)
        console.print(f"[green]Theme '{theme_name}' deleted successfully![/green]")

    except GhostCtlError as e:
        console.print(f"[red]Error deleting theme: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def download(
    ctx: typer.Context,
    theme_name: str = typer.Argument(..., help="Name of theme to download"),
    output_file: Optional[Path] = typer.Option(None, "--output", help="Output file path (default: theme-name.zip)"),
) -> None:
    """Download an active theme as a ZIP file.

    Examples:
        # Download current active theme
        ghostctl themes download casper

        # Download to specific location
        ghostctl themes download my-theme --output ./backups/my-theme-backup.zip
    """
    client, formatter = get_client_and_formatter(ctx)

    # Set default output file name
    if output_file is None:
        output_file = Path(f"{theme_name}.zip")

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would download theme '{theme_name}' to '{output_file}'[/yellow]")
        return

    try:
        # Show progress during download
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task(f"Downloading {theme_name}...", total=None)

            # Download the theme
            client.download_theme(theme_name, output_file)

        console.print(f"[green]Theme downloaded successfully to '{output_file}'![/green]")

        if ctx.obj["output_format"] in ["json", "yaml"]:
            formatter.output({
                "theme": theme_name,
                "output_file": str(output_file),
                "file_size": output_file.stat().st_size,
            }, format_override=ctx.obj["output_format"])
        else:
            # Table format
            table = Table(title="Downloaded Theme")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="bold")

            table.add_row("Theme", theme_name)
            table.add_row("Output File", str(output_file))
            table.add_row("File Size", f"{output_file.stat().st_size:,} bytes")

            console.print(table)

    except GhostCtlError as e:
        console.print(f"[red]Error downloading theme: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def validate(
    ctx: typer.Context,
    theme_file: Path = typer.Argument(..., help="Path to theme ZIP file to validate"),
) -> None:
    """Validate a theme package before uploading.

    Examples:
        # Validate a theme file
        ghostctl themes validate my-theme.zip

        # Validate before uploading
        ghostctl themes validate theme.zip && ghostctl themes upload theme.zip
    """
    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would validate theme '{theme_file}'[/yellow]")
        return

    try:
        validate_theme_file(theme_file)

        # Extract additional information from the theme
        theme_info = {}
        with zipfile.ZipFile(theme_file, 'r') as zip_file:
            file_list = zip_file.namelist()

            # Try to read package.json
            package_json_files = [f for f in file_list if f.endswith('package.json')]
            if package_json_files:
                try:
                    import json
                    with zip_file.open(package_json_files[0]) as package_file:
                        package_data = json.load(package_file)
                        theme_info.update({
                            "name": package_data.get("name", "Unknown"),
                            "version": package_data.get("version", "Unknown"),
                            "description": package_data.get("description", ""),
                            "author": package_data.get("author", {}).get("name") if isinstance(package_data.get("author"), dict) else package_data.get("author", "Unknown"),
                        })
                except (json.JSONDecodeError, KeyError):
                    pass

            # Count templates
            hbs_files = [f for f in file_list if f.endswith('.hbs')]
            theme_info["templates"] = len(hbs_files)
            theme_info["files"] = len(file_list)

        console.print(f"[green]✓ Theme is valid for upload[/green]")

        if ctx.obj["output_format"] in ["json", "yaml"]:
            formatter.output({
                "valid": True,
                "file": str(theme_file),
                "size_bytes": theme_file.stat().st_size,
                "theme_info": theme_info,
            }, format_override=ctx.obj["output_format"])
        else:
            # Table format
            table = Table(title="Theme Validation")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="bold")

            table.add_row("File", str(theme_file))
            table.add_row("Valid", "✓ Yes")
            table.add_row("Size", f"{theme_file.stat().st_size / (1024*1024):.2f} MB")

            if theme_info:
                table.add_row("Name", theme_info.get("name", "Unknown"))
                table.add_row("Version", theme_info.get("version", "Unknown"))
                table.add_row("Author", theme_info.get("author", "Unknown"))
                table.add_row("Templates", str(theme_info.get("templates", 0)))
                table.add_row("Total Files", str(theme_info.get("files", 0)))
                if theme_info.get("description"):
                    description = theme_info["description"]
                    if len(description) > 50:
                        description = description[:47] + "..."
                    table.add_row("Description", description)

            console.print(table)

    except GhostCtlError as e:
        console.print(f"[red]✗ Theme validation failed: {e}[/red]")

        if ctx.obj["output_format"] in ["json", "yaml"]:
            formatter.output({
                "valid": False,
                "file": str(theme_file),
                "error": str(e),
            }, format_override=ctx.obj["output_format"])

        raise typer.Exit(1)


@app.command()
def backup(
    ctx: typer.Context,
    output_dir: Path = typer.Option(Path("./theme-backups"), "--output-dir", help="Directory to save theme backups"),
) -> None:
    """Backup all themes.

    Examples:
        # Backup all themes to default directory
        ghostctl themes backup

        # Backup to specific directory
        ghostctl themes backup --output-dir ./my-backups/
    """
    client, formatter = get_client_and_formatter(ctx)

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would backup all themes to '{output_dir}'[/yellow]")
        return

    try:
        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get all themes
        themes = client.get_themes()
        if not themes:
            console.print("[yellow]No themes found to backup[/yellow]")
            return

        console.print(f"[blue]Found {len(themes)} themes to backup[/blue]")

        backed_up = []
        failed = []

        with Progress(console=console) as progress:
            backup_task = progress.add_task("Backing up themes...", total=len(themes))

            for theme in themes:
                theme_name = theme.get("name", "unknown")
                try:
                    output_file = output_dir / f"{theme_name}.zip"
                    client.download_theme(theme_name, output_file)

                    backed_up.append({
                        "name": theme_name,
                        "file": str(output_file),
                        "size": output_file.stat().st_size,
                    })

                    progress.console.print(f"  ✓ {theme_name}")

                except GhostCtlError as e:
                    failed.append({
                        "name": theme_name,
                        "error": str(e),
                    })
                    progress.console.print(f"  ✗ {theme_name}: {e}")

                progress.advance(backup_task)

        # Summary
        console.print(f"[green]Successfully backed up {len(backed_up)} themes[/green]")
        if failed:
            console.print(f"[red]Failed to backup {len(failed)} themes[/red]")

        if ctx.obj["output_format"] in ["json", "yaml"]:
            formatter.output({
                "backed_up": backed_up,
                "failed": failed,
                "output_directory": str(output_dir),
                "summary": {
                    "total": len(themes),
                    "success": len(backed_up),
                    "failed": len(failed),
                }
            }, format_override=ctx.obj["output_format"])

    except GhostCtlError as e:
        console.print(f"[red]Error backing up themes: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()