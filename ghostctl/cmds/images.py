"""Image management commands for GhostCtl CLI.

This module provides commands for uploading and managing images in Ghost CMS,
supporting multipart/form-data uploads.
"""

from pathlib import Path
from typing import Optional, List
import mimetypes

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


def validate_image_file(file_path: Path) -> None:
    """Validate that the file is a supported image format."""
    if not file_path.exists():
        raise GhostCtlError(f"File not found: {file_path}")

    if not file_path.is_file():
        raise GhostCtlError(f"Not a file: {file_path}")

    # Check file extension
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.avif'}
    if file_path.suffix.lower() not in allowed_extensions:
        raise GhostCtlError(
            f"Unsupported file format: {file_path.suffix}. "
            f"Allowed formats: {', '.join(allowed_extensions)}"
        )

    # Check MIME type
    mime_type, _ = mimetypes.guess_type(str(file_path))
    if mime_type and not mime_type.startswith('image/'):
        raise GhostCtlError(f"File is not an image: {mime_type}")

    # Check file size (Ghost usually limits to 5MB for images)
    max_size = 5 * 1024 * 1024  # 5MB
    if file_path.stat().st_size > max_size:
        size_mb = file_path.stat().st_size / (1024 * 1024)
        raise GhostCtlError(f"Image file too large: {size_mb:.1f}MB (max 5MB)")


@app.command()
def upload(
    ctx: typer.Context,
    file_path: Path = typer.Argument(..., help="Path to image file"),
    purpose: str = typer.Option("image", "--purpose", help="Upload purpose (image, profile_image, cover_image)"),
    ref: Optional[str] = typer.Option(None, "--ref", help="Reference identifier for the upload"),
) -> None:
    """Upload an image file to Ghost CMS.

    Examples:
        # Upload a regular image
        ghostctl images upload photo.jpg

        # Upload a profile image
        ghostctl images upload avatar.png --purpose profile_image

        # Upload with reference for tracking
        ghostctl images upload hero.jpg --ref "homepage-hero"

        # Get URL for scripting
        URL=$(ghostctl images upload photo.jpg --output json | jq -r '.images[0].url')
    """
    client, formatter = get_client_and_formatter(ctx)

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would upload image '{file_path}' with:[/yellow]")
        console.print(f"  Purpose: {purpose}")
        console.print(f"  Reference: {ref or 'none'}")
        return

    try:
        # Validate the image file
        validate_image_file(file_path)

        # Show progress during upload
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task(f"Uploading {file_path.name}...", total=None)

            # Upload the image
            result = client.upload_image(
                file_path=file_path,
                purpose=purpose,
                ref=ref,
            )

        console.print(f"[green]Image uploaded successfully![/green]")

        if ctx.obj["output_format"] in ["json", "yaml"]:
            formatter.output({"images": [result]}, format_override=ctx.obj["output_format"])
        else:
            # Table format
            table = Table(title="Uploaded Image")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="bold")

            table.add_row("URL", result.get("url", "N/A"))
            table.add_row("Reference", result.get("ref", "N/A"))
            table.add_row("File Size", f"{file_path.stat().st_size:,} bytes")
            table.add_row("MIME Type", mimetypes.guess_type(str(file_path))[0] or "Unknown")

            console.print(table)

    except GhostCtlError as e:
        console.print(f"[red]Error uploading image: {e}[/red]")
        raise typer.Exit(1)


@app.command("bulk-upload")
def bulk_upload(
    ctx: typer.Context,
    directory: Path = typer.Argument(..., help="Directory containing images"),
    pattern: str = typer.Option("*", "--pattern", help="File pattern to match (e.g., '*.jpg')"),
    purpose: str = typer.Option("image", "--purpose", help="Upload purpose for all images"),
    ref_prefix: Optional[str] = typer.Option(None, "--ref-prefix", help="Prefix for reference IDs"),
    max_concurrent: int = typer.Option(3, "--max-concurrent", help="Maximum concurrent uploads"),
) -> None:
    """Bulk upload images from a directory.

    Examples:
        # Upload all images from a directory
        ghostctl images bulk-upload ./photos/

        # Upload only JPG files
        ghostctl images bulk-upload ./photos/ --pattern "*.jpg"

        # Upload with reference prefix
        ghostctl images bulk-upload ./gallery/ --ref-prefix "gallery-"

        # Limit concurrent uploads
        ghostctl images bulk-upload ./images/ --max-concurrent 1
    """
    client, formatter = get_client_and_formatter(ctx)

    if not directory.exists():
        console.print(f"[red]Directory not found: {directory}[/red]")
        raise typer.Exit(1)

    if not directory.is_dir():
        console.print(f"[red]Not a directory: {directory}[/red]")
        raise typer.Exit(1)

    # Find image files
    image_files = []
    for file_path in directory.glob(pattern):
        if file_path.is_file():
            try:
                validate_image_file(file_path)
                image_files.append(file_path)
            except GhostCtlError:
                # Skip invalid image files
                continue

    if not image_files:
        console.print(f"[yellow]No valid image files found in {directory} with pattern '{pattern}'[/yellow]")
        return

    console.print(f"[blue]Found {len(image_files)} image files to upload[/blue]")

    if ctx.obj["dry_run"]:
        console.print("[yellow]DRY RUN: Would upload the following files:[/yellow]")
        for file_path in image_files:
            ref = f"{ref_prefix}{file_path.stem}" if ref_prefix else None
            console.print(f"  {file_path.name} (ref: {ref or 'none'})")
        return

    # Upload files with progress
    uploaded_images = []
    failed_uploads = []

    with Progress(console=console) as progress:
        upload_task = progress.add_task("Uploading images...", total=len(image_files))

        for file_path in image_files:
            try:
                ref = f"{ref_prefix}{file_path.stem}" if ref_prefix else None

                result = client.upload_image(
                    file_path=file_path,
                    purpose=purpose,
                    ref=ref,
                )

                uploaded_images.append({
                    "file": file_path.name,
                    "url": result.get("url"),
                    "ref": result.get("ref"),
                })

                progress.console.print(f"  ✓ {file_path.name}")

            except GhostCtlError as e:
                failed_uploads.append({
                    "file": file_path.name,
                    "error": str(e),
                })
                progress.console.print(f"  ✗ {file_path.name}: {e}")

            progress.advance(upload_task)

    # Summary
    console.print(f"[green]Successfully uploaded {len(uploaded_images)} images[/green]")
    if failed_uploads:
        console.print(f"[red]Failed to upload {len(failed_uploads)} images[/red]")

    # Output results
    if ctx.obj["output_format"] in ["json", "yaml"]:
        formatter.output({
            "uploaded": uploaded_images,
            "failed": failed_uploads,
            "summary": {
                "total": len(image_files),
                "uploaded": len(uploaded_images),
                "failed": len(failed_uploads),
            }
        }, format_override=ctx.obj["output_format"])
    else:
        # Show uploaded images table
        if uploaded_images:
            table = Table(title="Uploaded Images")
            table.add_column("File", style="cyan")
            table.add_column("URL", style="blue")
            table.add_column("Reference", style="dim")

            for img in uploaded_images:
                table.add_row(
                    img["file"],
                    img["url"][:60] + "..." if len(img["url"]) > 60 else img["url"],
                    img["ref"] or "—",
                )

            console.print(table)

        # Show failed uploads
        if failed_uploads:
            console.print("\n[red]Failed Uploads:[/red]")
            for fail in failed_uploads:
                console.print(f"  ✗ {fail['file']}: {fail['error']}")


@app.command("validate")
def validate(
    ctx: typer.Context,
    file_path: Path = typer.Argument(..., help="Path to image file to validate"),
) -> None:
    """Validate an image file for Ghost CMS upload.

    Examples:
        # Validate a single image
        ghostctl images validate photo.jpg

        # Validate before uploading
        ghostctl images validate large-image.png && ghostctl images upload large-image.png
    """
    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would validate image '{file_path}'[/yellow]")
        return

    try:
        validate_image_file(file_path)

        # Get file info
        stat = file_path.stat()
        mime_type, _ = mimetypes.guess_type(str(file_path))
        size_mb = stat.st_size / (1024 * 1024)

        console.print(f"[green]✓ Image is valid for upload[/green]")

        if ctx.obj["output_format"] in ["json", "yaml"]:
            formatter.output({
                "valid": True,
                "file": str(file_path),
                "size_bytes": stat.st_size,
                "size_mb": round(size_mb, 2),
                "mime_type": mime_type,
                "extension": file_path.suffix.lower(),
            }, format_override=ctx.obj["output_format"])
        else:
            # Table format
            table = Table(title="Image Validation")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="bold")

            table.add_row("File", str(file_path))
            table.add_row("Valid", "✓ Yes")
            table.add_row("Size", f"{size_mb:.2f} MB ({stat.st_size:,} bytes)")
            table.add_row("MIME Type", mime_type or "Unknown")
            table.add_row("Extension", file_path.suffix.lower())

            console.print(table)

    except GhostCtlError as e:
        console.print(f"[red]✗ Image validation failed: {e}[/red]")

        if ctx.obj["output_format"] in ["json", "yaml"]:
            formatter.output({
                "valid": False,
                "file": str(file_path),
                "error": str(e),
            }, format_override=ctx.obj["output_format"])

        raise typer.Exit(1)


@app.command("optimize")
def optimize(
    ctx: typer.Context,
    file_path: Path = typer.Argument(..., help="Path to image file to optimize"),
    output_path: Optional[Path] = typer.Option(None, "--output", help="Output path (default: overwrite original)"),
    quality: int = typer.Option(85, "--quality", help="JPEG quality (1-100)"),
    max_width: Optional[int] = typer.Option(None, "--max-width", help="Maximum width in pixels"),
    max_height: Optional[int] = typer.Option(None, "--max-height", help="Maximum height in pixels"),
    format: Optional[str] = typer.Option(None, "--format", help="Output format (jpg, png, webp)"),
) -> None:
    """Optimize an image for web use before uploading.

    Note: This command requires the Pillow library to be installed.

    Examples:
        # Basic optimization (reduce quality to 85%)
        ghostctl images optimize large-photo.jpg

        # Resize and optimize
        ghostctl images optimize photo.jpg --max-width 1200 --max-height 800

        # Convert to WebP format
        ghostctl images optimize photo.jpg --format webp --output photo.webp

        # Save to different location
        ghostctl images optimize original.jpg --output optimized.jpg --quality 75
    """
    try:
        from PIL import Image
    except ImportError:
        console.print("[red]Error: Pillow library is required for image optimization.[/red]")
        console.print("[dim]Install with: pip install Pillow[/dim]")
        raise typer.Exit(1)

    if not file_path.exists():
        console.print(f"[red]File not found: {file_path}[/red]")
        raise typer.Exit(1)

    output_path = output_path or file_path

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would optimize '{file_path}' with:[/yellow]")
        console.print(f"  Output: {output_path}")
        console.print(f"  Quality: {quality}%")
        if max_width:
            console.print(f"  Max width: {max_width}px")
        if max_height:
            console.print(f"  Max height: {max_height}px")
        if format:
            console.print(f"  Format: {format}")
        return

    try:
        # Open and process image
        with Image.open(file_path) as img:
            original_size = img.size
            original_format = img.format
            original_file_size = file_path.stat().st_size

            # Convert RGBA to RGB for JPEG
            if format == 'jpg' and img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background

            # Resize if dimensions specified
            if max_width or max_height:
                # Calculate new size maintaining aspect ratio
                width, height = img.size
                if max_width and width > max_width:
                    height = int(height * max_width / width)
                    width = max_width
                if max_height and height > max_height:
                    width = int(width * max_height / height)
                    height = max_height

                if (width, height) != img.size:
                    img = img.resize((width, height), Image.Resampling.LANCZOS)

            # Determine output format
            save_format = format.upper() if format else original_format
            if save_format == 'JPG':
                save_format = 'JPEG'

            # Save optimized image
            save_kwargs = {}
            if save_format == 'JPEG':
                save_kwargs.update({
                    'quality': quality,
                    'optimize': True,
                    'progressive': True,
                })
            elif save_format == 'PNG':
                save_kwargs.update({
                    'optimize': True,
                })
            elif save_format == 'WEBP':
                save_kwargs.update({
                    'quality': quality,
                    'optimize': True,
                })

            img.save(output_path, format=save_format, **save_kwargs)

        # Get results
        new_file_size = output_path.stat().st_size
        compression_ratio = (1 - new_file_size / original_file_size) * 100

        console.print(f"[green]✓ Image optimized successfully![/green]")

        if ctx.obj["output_format"] in ["json", "yaml"]:
            formatter.output({
                "original": {
                    "file": str(file_path),
                    "size": original_size,
                    "format": original_format,
                    "file_size": original_file_size,
                },
                "optimized": {
                    "file": str(output_path),
                    "size": img.size,
                    "format": save_format,
                    "file_size": new_file_size,
                },
                "compression_ratio": round(compression_ratio, 1),
            }, format_override=ctx.obj["output_format"])
        else:
            # Table format
            table = Table(title="Image Optimization Results")
            table.add_column("Property", style="cyan")
            table.add_column("Original", style="dim")
            table.add_column("Optimized", style="bold green")

            table.add_row("File", str(file_path), str(output_path))
            table.add_row("Dimensions", f"{original_size[0]} × {original_size[1]}", f"{img.size[0]} × {img.size[1]}")
            table.add_row("Format", original_format, save_format)
            table.add_row("File Size", f"{original_file_size:,} bytes", f"{new_file_size:,} bytes")
            table.add_row("Compression", "—", f"{compression_ratio:.1f}% smaller")

            console.print(table)

    except Exception as e:
        console.print(f"[red]Error optimizing image: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()