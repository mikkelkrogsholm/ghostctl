"""Page management commands for GhostCtl CLI.

This module provides commands for managing Ghost CMS pages. Pages are
essentially the same as posts but stored separately in Ghost CMS.
Most functionality inherits from the posts module.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, List

import typer
from rich.console import Console
from rich.table import Table

from ..client import GhostClient
from ..render import OutputFormatter
from ..exceptions import GhostCtlError
from ..models.post import Page

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


@app.command()
def list(
    ctx: typer.Context,
    filter: Optional[str] = typer.Option(None, "--filter", help="Filter pages (e.g., 'status:published')"),
    page: int = typer.Option(1, "--page", help="Page number"),
    limit: int = typer.Option(15, "--limit", help="Number of pages per page"),
    include: Optional[str] = typer.Option("tags,authors", "--include", help="Include related data"),
    order: Optional[str] = typer.Option("updated_at DESC", "--order", help="Sort order"),
) -> None:
    """List pages.

    Examples:
        # List all pages
        ghostctl pages list

        # List published pages only
        ghostctl pages list --filter "status:published"

        # List pages with pagination
        ghostctl pages list --page 2 --limit 10

        # List pages ordered by creation date
        ghostctl pages list --order "created_at ASC"
    """
    client, formatter = get_client_and_formatter(ctx)

    if ctx.obj["dry_run"]:
        console.print("[yellow]DRY RUN: Would list pages with filters:[/yellow]")
        console.print(f"  Filter: {filter or 'none'}")
        console.print(f"  Page: {page}, Limit: {limit}")
        console.print(f"  Include: {include}")
        console.print(f"  Order: {order}")
        return

    try:
        pages = client.get_pages(
            filter=filter,
            page=page,
            limit=limit,
            include=include,
            order=order,
        )

        if ctx.obj["output_format"] in ["json", "yaml"]:
            formatter.output({"pages": pages}, format_override=ctx.obj["output_format"])
        else:
            # Table format
            table = Table(title="Pages")
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("Title", style="bold")
            table.add_column("Slug", style="dim")
            table.add_column("Status", style="green")
            table.add_column("Published", style="dim")
            table.add_column("Authors", style="blue")

            for page in pages:
                authors = ", ".join([author.name for author in page.authors])
                published = page.published_at.strftime("%Y-%m-%d") if page.published_at else "—"

                table.add_row(
                    page.id[:8],
                    page.title[:40] + "..." if len(page.title) > 40 else page.title,
                    page.slug[:30] + "..." if len(page.slug) > 30 else page.slug,
                    page.status,
                    published,
                    authors[:30] + "..." if len(authors) > 30 else authors,
                )

            console.print(table)

    except GhostCtlError as e:
        console.print(f"[red]Error listing pages: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def get(
    ctx: typer.Context,
    page_id: str = typer.Argument(..., help="Page ID or slug"),
    include: Optional[str] = typer.Option("tags,authors", "--include", help="Include related data"),
) -> None:
    """Get a specific page by ID or slug.

    Examples:
        # Get page by ID
        ghostctl pages get 507f1f77bcf86cd799439011

        # Get page by slug
        ghostctl pages get about-us

        # Get page with specific includes
        ghostctl pages get contact --include "tags,authors"
    """
    client, formatter = get_client_and_formatter(ctx)

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would get page '{page_id}' with includes: {include}[/yellow]")
        return

    try:
        page = client.get_page(page_id, include=include)
        formatter.output({"pages": [page]}, format_override=ctx.obj["output_format"])

    except GhostCtlError as e:
        console.print(f"[red]Error getting page: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def create(
    ctx: typer.Context,
    title: str = typer.Option(..., "--title", help="Page title"),
    content: Optional[str] = typer.Option(None, "--content", help="Page content (HTML or Markdown)"),
    file: Optional[Path] = typer.Option(None, "--file", help="Read content from file"),
    status: str = typer.Option("draft", "--status", help="Page status"),
    slug: Optional[str] = typer.Option(None, "--slug", help="Page slug (auto-generated if not provided)"),
    featured: bool = typer.Option(False, "--featured", help="Mark as featured"),
    tags: Optional[List[str]] = typer.Option(None, "--tag", help="Tag names (can be repeated)"),
    excerpt: Optional[str] = typer.Option(None, "--excerpt", help="Custom excerpt"),
    feature_image: Optional[str] = typer.Option(None, "--feature-image", help="Feature image URL"),
    meta_title: Optional[str] = typer.Option(None, "--meta-title", help="Meta title for SEO"),
    meta_description: Optional[str] = typer.Option(None, "--meta-description", help="Meta description for SEO"),
    visibility: str = typer.Option("public", "--visibility", help="Page visibility"),
    published_at: Optional[str] = typer.Option(None, "--published-at", help="Publish date (ISO 8601 format)"),
) -> None:
    """Create a new page.

    Examples:
        # Create a simple draft page
        ghostctl pages create --title "About Us" --content "Information about our company"

        # Create from file and publish
        ghostctl pages create --title "Privacy Policy" --file privacy.md --status published

        # Create with tags and metadata
        ghostctl pages create --title "Contact" --content "Contact form" --tag "contact" --meta-title "Contact Us"

        # Create static page
        ghostctl pages create --title "Terms" --content "Terms and conditions" --status published
    """
    client, formatter = get_client_and_formatter(ctx)

    # Read content from file if provided
    if file:
        if not file.exists():
            console.print(f"[red]File not found: {file}[/red]")
            raise typer.Exit(1)
        content = file.read_text(encoding="utf-8")

    if not content:
        console.print("[red]Content is required (use --content or --file)[/red]")
        raise typer.Exit(1)

    # Parse published_at if provided
    published_at_dt = None
    if published_at:
        try:
            published_at_dt = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
        except ValueError:
            console.print(f"[red]Invalid date format: {published_at}. Use ISO 8601 format.[/red]")
            raise typer.Exit(1)

    if ctx.obj["dry_run"]:
        console.print("[yellow]DRY RUN: Would create page with:[/yellow]")
        console.print(f"  Title: {title}")
        console.print(f"  Status: {status}")
        console.print(f"  Slug: {slug or 'auto-generated'}")
        console.print(f"  Tags: {tags or 'none'}")
        console.print(f"  Content length: {len(content)} characters")
        return

    try:
        page_data = {
            "title": title,
            "html": content,
            "status": status,
            "featured": featured,
            "visibility": visibility,
        }

        # Add optional fields
        if slug:
            page_data["slug"] = slug
        if excerpt:
            page_data["custom_excerpt"] = excerpt
        if feature_image:
            page_data["feature_image"] = feature_image
        if meta_title:
            page_data["meta_title"] = meta_title
        if meta_description:
            page_data["meta_description"] = meta_description
        if published_at_dt:
            page_data["published_at"] = published_at_dt.isoformat()

        # Handle tags
        if tags:
            page_data["tags"] = [{"name": tag} for tag in tags]

        page = client.create_page(page_data)
        console.print(f"[green]Page created successfully![/green]")
        formatter.output({"pages": [page]}, format_override=ctx.obj["output_format"])

    except GhostCtlError as e:
        console.print(f"[red]Error creating page: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def update(
    ctx: typer.Context,
    page_id: str = typer.Argument(..., help="Page ID or slug"),
    title: Optional[str] = typer.Option(None, "--title", help="Page title"),
    content: Optional[str] = typer.Option(None, "--content", help="Page content (HTML or Markdown)"),
    file: Optional[Path] = typer.Option(None, "--file", help="Read content from file"),
    status: Optional[str] = typer.Option(None, "--status", help="Page status"),
    slug: Optional[str] = typer.Option(None, "--slug", help="Page slug"),
    featured: Optional[bool] = typer.Option(None, "--featured", help="Featured status"),
    tags: Optional[List[str]] = typer.Option(None, "--tag", help="Tag names (replaces existing tags)"),
    add_tags: Optional[List[str]] = typer.Option(None, "--add-tag", help="Add tags (keeps existing tags)"),
    remove_tags: Optional[List[str]] = typer.Option(None, "--remove-tag", help="Remove tags"),
    excerpt: Optional[str] = typer.Option(None, "--excerpt", help="Custom excerpt"),
    feature_image: Optional[str] = typer.Option(None, "--feature-image", help="Feature image URL"),
    meta_title: Optional[str] = typer.Option(None, "--meta-title", help="Meta title for SEO"),
    meta_description: Optional[str] = typer.Option(None, "--meta-description", help="Meta description for SEO"),
    visibility: Optional[str] = typer.Option(None, "--visibility", help="Page visibility"),
    published_at: Optional[str] = typer.Option(None, "--published-at", help="Publish date (ISO 8601 format)"),
) -> None:
    """Update an existing page.

    Examples:
        # Update title
        ghostctl pages update page-id --title "New Title"

        # Update content from file
        ghostctl pages update page-id --file updated-content.md

        # Add tags
        ghostctl pages update page-id --add-tag "important" --add-tag "updated"

        # Publish page
        ghostctl pages update page-id --status published
    """
    client, formatter = get_client_and_formatter(ctx)

    # Read content from file if provided
    if file:
        if not file.exists():
            console.print(f"[red]File not found: {file}[/red]")
            raise typer.Exit(1)
        content = file.read_text(encoding="utf-8")

    # Parse published_at if provided
    published_at_dt = None
    if published_at:
        try:
            published_at_dt = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
        except ValueError:
            console.print(f"[red]Invalid date format: {published_at}. Use ISO 8601 format.[/red]")
            raise typer.Exit(1)

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would update page '{page_id}' with:[/yellow]")
        if title:
            console.print(f"  Title: {title}")
        if status:
            console.print(f"  Status: {status}")
        if tags:
            console.print(f"  Tags (replace): {tags}")
        if add_tags:
            console.print(f"  Tags (add): {add_tags}")
        if remove_tags:
            console.print(f"  Tags (remove): {remove_tags}")
        return

    try:
        # Get current page if we need to handle tags
        current_page = None
        if add_tags or remove_tags:
            current_page = client.get_page(page_id, include="tags")

        # Build update data
        update_data = {}

        if title:
            update_data["title"] = title
        if content:
            update_data["html"] = content
        if status:
            update_data["status"] = status
        if slug:
            update_data["slug"] = slug
        if featured is not None:
            update_data["featured"] = featured
        if excerpt:
            update_data["custom_excerpt"] = excerpt
        if feature_image:
            update_data["feature_image"] = feature_image
        if meta_title:
            update_data["meta_title"] = meta_title
        if meta_description:
            update_data["meta_description"] = meta_description
        if visibility:
            update_data["visibility"] = visibility
        if published_at_dt:
            update_data["published_at"] = published_at_dt.isoformat()

        # Handle tags
        if tags:
            update_data["tags"] = [{"name": tag} for tag in tags]
        elif add_tags or remove_tags:
            if not current_page:
                console.print("[red]Could not fetch current page to modify tags[/red]")
                raise typer.Exit(1)

            current_tag_names = {tag.name for tag in current_page.tags}

            if add_tags:
                current_tag_names.update(add_tags)
            if remove_tags:
                current_tag_names -= set(remove_tags)

            update_data["tags"] = [{"name": tag} for tag in current_tag_names]

        if not update_data:
            console.print("[yellow]No updates specified[/yellow]")
            return

        page = client.update_page(page_id, update_data)
        console.print(f"[green]Page updated successfully![/green]")
        formatter.output({"pages": [page]}, format_override=ctx.obj["output_format"])

    except GhostCtlError as e:
        console.print(f"[red]Error updating page: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def delete(
    ctx: typer.Context,
    page_id: str = typer.Argument(..., help="Page ID or slug"),
    force: bool = typer.Option(False, "--force", help="Delete without confirmation"),
) -> None:
    """Delete a page.

    Examples:
        # Delete with confirmation
        ghostctl pages delete page-id

        # Force delete without confirmation
        ghostctl pages delete page-id --force
    """
    client, formatter = get_client_and_formatter(ctx)

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would delete page '{page_id}'[/yellow]")
        return

    try:
        # Get page details for confirmation
        if not force:
            page = client.get_page(page_id)
            console.print(f"[yellow]About to delete page:[/yellow]")
            console.print(f"  ID: {page.id}")
            console.print(f"  Title: {page.title}")
            console.print(f"  Slug: {page.slug}")
            console.print(f"  Status: {page.status}")

            confirm = typer.confirm("Are you sure you want to delete this page?")
            if not confirm:
                console.print("[yellow]Delete cancelled[/yellow]")
                return

        client.delete_page(page_id)
        console.print(f"[green]Page deleted successfully![/green]")

    except GhostCtlError as e:
        console.print(f"[red]Error deleting page: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def publish(
    ctx: typer.Context,
    page_id: str = typer.Argument(..., help="Page ID or slug"),
    published_at: Optional[str] = typer.Option(None, "--published-at", help="Publish date (ISO 8601 format)"),
) -> None:
    """Publish a draft page.

    Examples:
        # Publish immediately
        ghostctl pages publish page-id

        # Schedule for future
        ghostctl pages publish page-id --published-at "2025-01-01T10:00:00Z"
    """
    client, formatter = get_client_and_formatter(ctx)

    # Parse published_at if provided
    published_at_dt = None
    if published_at:
        try:
            published_at_dt = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
        except ValueError:
            console.print(f"[red]Invalid date format: {published_at}. Use ISO 8601 format.[/red]")
            raise typer.Exit(1)

    if ctx.obj["dry_run"]:
        status = "scheduled" if published_at else "published"
        console.print(f"[yellow]DRY RUN: Would publish page '{page_id}' with status '{status}'[/yellow]")
        if published_at:
            console.print(f"  Scheduled for: {published_at}")
        return

    try:
        update_data = {
            "status": "scheduled" if published_at else "published"
        }

        if published_at_dt:
            update_data["published_at"] = published_at_dt.isoformat()
        else:
            update_data["published_at"] = datetime.now().isoformat()

        page = client.update_page(page_id, update_data)

        if published_at:
            console.print(f"[green]Page scheduled for publication![/green]")
        else:
            console.print(f"[green]Page published successfully![/green]")

        formatter.output({"pages": [page]}, format_override=ctx.obj["output_format"])

    except GhostCtlError as e:
        console.print(f"[red]Error publishing page: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def schedule(
    ctx: typer.Context,
    page_id: str = typer.Argument(..., help="Page ID or slug"),
    date: str = typer.Argument(..., help="Schedule date (ISO 8601 format)"),
) -> None:
    """Schedule a page for future publication.

    Examples:
        # Schedule for specific date and time
        ghostctl pages schedule page-id "2025-01-01T10:00:00Z"

        # Schedule for tomorrow at 9 AM
        ghostctl pages schedule page-id "2025-01-02T09:00:00+01:00"
    """
    # This is a convenience wrapper around publish --published-at
    ctx.invoke(publish, page_id=page_id, published_at=date)


@app.command("convert-to-post")
def convert_to_post(
    ctx: typer.Context,
    page_id: str = typer.Argument(..., help="Page ID or slug to convert"),
    delete_original: bool = typer.Option(False, "--delete-original", help="Delete original page after conversion"),
) -> None:
    """Convert a page to a post.

    Note: This creates a new post with the same content and deletes the original page if requested.

    Examples:
        # Convert page to post
        ghostctl pages convert-to-post page-id

        # Convert and delete original
        ghostctl pages convert-to-post page-id --delete-original
    """
    client, formatter = get_client_and_formatter(ctx)

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would convert page '{page_id}' to post[/yellow]")
        if delete_original:
            console.print("  And delete the original page")
        return

    try:
        # Get the page
        page = client.get_page(page_id, include="tags,authors")

        # Create post data from page
        post_data = {
            "title": page.title,
            "html": page.html,
            "status": page.status,
            "slug": page.slug,
            "featured": page.featured,
            "visibility": page.visibility,
            "custom_excerpt": page.custom_excerpt,
            "feature_image": page.feature_image,
            "meta_title": page.meta_title,
            "meta_description": page.meta_description,
            "published_at": page.published_at.isoformat() if page.published_at else None,
        }

        # Handle tags
        if page.tags:
            post_data["tags"] = [{"name": tag.name} for tag in page.tags]

        # Create the post
        new_post = client.create_post(post_data)
        console.print(f"[green]✓ Created post with ID: {new_post.id}[/green]")

        # Delete original page if requested
        if delete_original:
            client.delete_page(page_id)
            console.print(f"[green]✓ Deleted original page[/green]")

        console.print(f"[green]Page converted to post successfully![/green]")
        formatter.output({"posts": [new_post]}, format_override=ctx.obj["output_format"])

    except GhostCtlError as e:
        console.print(f"[red]Error converting page: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()