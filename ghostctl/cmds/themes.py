"""Theme management commands for GhostCtl CLI.

This module provides commands for managing Ghost CMS themes including
uploading and activating themes.

Note: Ghost API v5 does not support listing themes via API (returns 501).
Theme management must be done through upload and activation endpoints only.
"""

from pathlib import Path
import zipfile

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

    # Use a longer timeout for theme operations (60 seconds instead of default)
    # and disable retries since theme operations are not idempotent
    timeout = max(ctx.obj["timeout"], 60)

    client = GhostClient(
        profile=profile,
        timeout=timeout,
        retry_attempts=0,  # Disable retries for theme operations
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
                name.endswith('package.json') and '/' not in name[:-12]
                for name in file_list
            )

            # Look for index.hbs (required template)
            has_index_hbs = any(
                name.endswith('index.hbs') and '/' not in name[:-9]
                for name in file_list
            )

            if not has_package_json:
                raise GhostCtlError(
                    "Theme package must contain package.json in root directory. "
                    "If downloaded from GitHub, extract and rezip without the top-level folder."
                )

            if not has_index_hbs:
                raise GhostCtlError(
                    "Theme package must contain index.hbs template in root directory. "
                    "If downloaded from GitHub, extract and rezip without the top-level folder."
                )

    except zipfile.BadZipFile:
        raise GhostCtlError("Invalid ZIP file")

    # Check file size (Ghost usually limits theme uploads)
    max_size = 50 * 1024 * 1024  # 50MB
    if file_path.stat().st_size > max_size:
        size_mb = file_path.stat().st_size / (1024 * 1024)
        raise GhostCtlError(f"Theme file too large: {size_mb:.1f}MB (max 50MB)")


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

        # Validate before uploading
        ghostctl themes validate my-theme.zip && ghostctl themes upload my-theme.zip

    Note: Theme files must have package.json and index.hbs in the root of the ZIP.
    If downloading from GitHub, extract and rezip without the top-level folder.
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
            result = client.upload_theme(str(theme_file))

            # If activate flag is set, activate the theme
            if activate and result:
                theme_data = result.get("themes", [{}])[0] if result.get("themes") else result
                theme_name = theme_data.get("name")
                if theme_name:
                    client.activate_theme(theme_name)

        if activate:
            console.print(f"[green]Theme uploaded and activated successfully![/green]")
        else:
            console.print(f"[green]Theme uploaded successfully![/green]")

        if ctx.obj["output_format"] in ["json", "yaml"]:
            formatter.render({"themes": [result]}, format_override=ctx.obj["output_format"])
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
    theme_name: str = typer.Argument(..., help="Name of the theme to activate"),
) -> None:
    """Activate an installed theme.

    Examples:
        # Activate a theme
        ghostctl themes activate casper

        # Activate with confirmation
        ghostctl themes activate my-custom-theme
    """
    client, formatter = get_client_and_formatter(ctx)

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would activate theme '{theme_name}'[/yellow]")
        return

    try:
        # Show progress during activation
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task(f"Activating theme '{theme_name}'...", total=None)

            result = client.activate_theme(theme_name)

        console.print(f"[green]Theme '{theme_name}' activated successfully![/green]")

        if ctx.obj["output_format"] in ["json", "yaml"]:
            formatter.render({"themes": [result]}, format_override=ctx.obj["output_format"])
        else:
            # Table format
            table = Table(title="Activated Theme")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="bold")

            theme_data = result.get("themes", [{}])[0] if result.get("themes") else result

            table.add_row("Name", theme_data.get("name", theme_name))
            table.add_row("Version", theme_data.get("package", {}).get("version", "Unknown"))
            table.add_row("Active", "✓ Yes")
            table.add_row("Templates", str(len(theme_data.get("templates", []))))

            console.print(table)

    except GhostCtlError as e:
        console.print(f"[red]Error activating theme: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def validate(
    ctx: typer.Context,
    theme_file: Path = typer.Argument(..., help="Path to theme ZIP file to validate"),
) -> None:
    """Validate a theme package before uploading.

    Checks that the ZIP file contains required Ghost theme files:
    - package.json in root directory
    - index.hbs template in root directory
    - Valid ZIP structure
    - File size under 50MB

    Examples:
        # Validate a theme
        ghostctl themes validate my-theme.zip

        # Validate and upload if successful
        ghostctl themes validate theme.zip && ghostctl themes upload theme.zip
    """
    try:
        validate_theme_file(theme_file)

        # Additional validation info
        with zipfile.ZipFile(theme_file, 'r') as zip_file:
            file_list = zip_file.namelist()

            # Count templates
            templates = [f for f in file_list if f.endswith('.hbs')]

            # Check for package.json
            package_files = [f for f in file_list if f.endswith('package.json')]

        console.print(f"[green]✓ Theme package is valid![/green]")

        # Show theme info
        table = Table(title="Theme Package Info")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="bold")

        table.add_row("File", str(theme_file))
        table.add_row("Size", f"{theme_file.stat().st_size:,} bytes")
        table.add_row("Templates", str(len(templates)))
        table.add_row("Total Files", str(len(file_list)))

        console.print(table)

    except GhostCtlError as e:
        console.print(f"[red]✗ Validation failed: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]✗ Validation error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def current(
    ctx: typer.Context,
) -> None:
    """Show the currently active theme.

    Examples:
        # Show current theme
        ghostctl themes current

        # Get as JSON
        ghostctl themes current -o json
    """
    client, formatter = get_client_and_formatter(ctx)

    try:
        # Get settings to find active theme
        settings = client.get_settings()

        # Find active_theme in settings
        active_theme = None
        if isinstance(settings, dict):
            active_theme = settings.get('active_theme', 'Unknown')

        if ctx.obj["output_format"] in ["json", "yaml"]:
            formatter.render({"active_theme": active_theme}, format_override=ctx.obj["output_format"])
        else:
            console.print(f"Active theme: [bold cyan]{active_theme}[/bold cyan]")

    except GhostCtlError as e:
        console.print(f"[red]Error getting current theme: {e}[/red]")
        raise typer.Exit(1)