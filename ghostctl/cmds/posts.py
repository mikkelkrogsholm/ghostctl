"""Post management commands for GhostCtl CLI.

This module provides commands for managing Ghost CMS posts including
listing, creating, updating, deleting, and publishing posts with enhanced
error handling, progress tracking, and bulk operations.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, List

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from ..client import GhostClient
from ..render import OutputFormatter
from ..exceptions import GhostCtlError, ValidationError
from ..models.post import Post
from ..utils.client_factory import get_client_and_formatter
from ..utils.exceptions import format_error_for_user, BulkOperationError
from ..app import handle_exceptions

app = typer.Typer()
console = Console()




@app.command()
@handle_exceptions
def list(
    ctx: typer.Context,
    filter: Optional[str] = typer.Option(None, "--filter", help="Filter posts (e.g., 'status:published')"),
    page: int = typer.Option(1, "--page", help="Page number"),
    limit: int = typer.Option(15, "--limit", help="Number of posts per page"),
    include: Optional[str] = typer.Option("tags,authors", "--include", help="Include related data"),
    order: Optional[str] = typer.Option("updated_at DESC", "--order", help="Sort order"),
    all_pages: bool = typer.Option(False, "--all", help="Fetch all posts (may take time)"),
    show_progress: bool = typer.Option(False, "--progress", help="Show progress bar for long operations"),
) -> None:
    """List posts.

    Examples:
        # List all posts
        ghostctl posts list

        # List published posts only
        ghostctl posts list --filter "status:published"

        # List posts with pagination
        ghostctl posts list --page 2 --limit 10

        # List posts ordered by creation date
        ghostctl posts list --order "created_at ASC"
    """
    client, formatter = get_client_and_formatter(ctx)

    if ctx.obj["dry_run"]:
        console.print("[yellow]DRY RUN: Would list posts with filters:[/yellow]")
        console.print(f"  Filter: {filter or 'none'}")
        console.print(f"  Page: {page}, Limit: {limit}")
        console.print(f"  Include: {include}")
        console.print(f"  Order: {order}")
        return

    if all_pages:
        # Fetch all posts with pagination
        include_list = include.split(",") if include else None
        posts_data = client.get_all_posts(
            filter_query=filter,
            include=include_list,
            show_progress=show_progress,
        )
        posts = {"posts": posts_data}
    else:
        # Fetch single page
        include_list = include.split(",") if include else None
        posts = client.get_posts(
            filter_query=filter,
            page=page,
            limit=limit,
            include=include_list,
            order=order,
        )

    if ctx.obj["output_format"] in ["json", "yaml"]:
        formatter.output(posts, format_override=ctx.obj["output_format"])
    else:
        # Table format
        posts_list = posts.get("posts", [])

        table = Table(title=f"Posts ({len(posts_list)} items)")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Title", style="bold")
        table.add_column("Status", style="green")
        table.add_column("Published", style="dim")
        table.add_column("Authors", style="blue")
        table.add_column("Tags", style="magenta")

        for post_data in posts_list:
            # Handle both model instances and raw dict data
            if hasattr(post_data, 'id'):
                post = post_data
                authors = ", ".join([author.name for author in post.authors])
                tags = ", ".join([tag.name for tag in post.tags])
                published = post.published_at.strftime("%Y-%m-%d") if post.published_at else "—"
                post_id = post.id
                title = post.title
                status = post.status
            else:
                # Raw dict data
                post = post_data
                authors = ", ".join([author.get("name", "") for author in post.get("authors", [])])
                tags = ", ".join([tag.get("name", "") for tag in post.get("tags", [])])
                published_at = post.get("published_at")
                published = datetime.fromisoformat(published_at.replace('Z', '+00:00')).strftime("%Y-%m-%d") if published_at else "—"
                post_id = post.get("id", "")
                title = post.get("title", "")
                status = post.get("status", "")

            table.add_row(
                post_id[:8],
                title[:50] + "..." if len(title) > 50 else title,
                status,
                published,
                authors[:30] + "..." if len(authors) > 30 else authors,
                tags[:30] + "..." if len(tags) > 30 else tags,
            )

        console.print(table)

        # Show pagination info for single page requests
        if not all_pages and "meta" in posts:
            meta = posts["meta"]
            pagination = meta.get("pagination", {})
            if pagination:
                console.print(f"\n[dim]Page {pagination.get('page', 'N/A')} of {pagination.get('pages', 'N/A')} "
                            f"(showing {len(posts_list)} of {pagination.get('total', 'N/A')} total)[/dim]")


@app.command()
@handle_exceptions
def get(
    ctx: typer.Context,
    post_id: str = typer.Argument(..., help="Post ID or slug"),
    include: Optional[str] = typer.Option("tags,authors", "--include", help="Include related data"),
) -> None:
    """Get a specific post by ID or slug.

    Examples:
        # Get post by ID
        ghostctl posts get 507f1f77bcf86cd799439011

        # Get post by slug
        ghostctl posts get my-post-slug

        # Get post with specific includes
        ghostctl posts get my-post --include "tags,authors,email"
    """
    client, formatter = get_client_and_formatter(ctx)

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would get post '{post_id}' with includes: {include}[/yellow]")
        return

    include_list = include.split(",") if include else None
    post = client.get_post(post_id, include=include_list)
    formatter.output({"posts": [post]}, format_override=ctx.obj["output_format"])


@app.command()
@handle_exceptions
def create(
    ctx: typer.Context,
    title: str = typer.Option(..., "--title", help="Post title"),
    content: Optional[str] = typer.Option(None, "--content", help="Post content (HTML or Markdown)"),
    file: Optional[Path] = typer.Option(None, "--file", help="Read content from file"),
    status: str = typer.Option("draft", "--status", help="Post status"),
    slug: Optional[str] = typer.Option(None, "--slug", help="Post slug (auto-generated if not provided)"),
    featured: bool = typer.Option(False, "--featured", help="Mark as featured"),
    tags: Optional[List[str]] = typer.Option(None, "--tag", help="Tag names (can be repeated)"),
    excerpt: Optional[str] = typer.Option(None, "--excerpt", help="Custom excerpt"),
    feature_image: Optional[str] = typer.Option(None, "--feature-image", help="Feature image URL"),
    meta_title: Optional[str] = typer.Option(None, "--meta-title", help="Meta title for SEO"),
    meta_description: Optional[str] = typer.Option(None, "--meta-description", help="Meta description for SEO"),
    visibility: str = typer.Option("public", "--visibility", help="Post visibility"),
    published_at: Optional[str] = typer.Option(None, "--published-at", help="Publish date (ISO 8601 format)"),
) -> None:
    """Create a new post.

    Examples:
        # Create a simple draft post
        ghostctl posts create --title "My Post" --content "Hello World"

        # Create from file and publish
        ghostctl posts create --title "From File" --file content.md --status published

        # Create with tags and metadata
        ghostctl posts create --title "Tagged Post" --content "Content" --tag "tech" --tag "tutorial"

        # Schedule a post
        ghostctl posts create --title "Future Post" --content "Content" --status scheduled --published-at "2025-01-01T10:00:00Z"
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
        console.print("[yellow]DRY RUN: Would create post with:[/yellow]")
        console.print(f"  Title: {title}")
        console.print(f"  Status: {status}")
        console.print(f"  Slug: {slug or 'auto-generated'}")
        console.print(f"  Tags: {tags or 'none'}")
        console.print(f"  Content length: {len(content)} characters")
        return

    post_data = {
        "title": title,
        "html": content,
        "status": status,
        "featured": featured,
        "visibility": visibility,
    }

    # Add optional fields
    if slug:
        post_data["slug"] = slug
    if excerpt:
        post_data["custom_excerpt"] = excerpt
    if feature_image:
        post_data["feature_image"] = feature_image
    if meta_title:
        post_data["meta_title"] = meta_title
    if meta_description:
        post_data["meta_description"] = meta_description
    if published_at_dt:
        post_data["published_at"] = published_at_dt.isoformat()

    # Handle tags
    if tags:
        post_data["tags"] = [{"name": tag} for tag in tags]

    post = client.create_post(post_data)
    console.print(f"[green]Post created successfully![/green]")
    formatter.output({"posts": [post]}, format_override=ctx.obj["output_format"])


@app.command()
@handle_exceptions
def update(
    ctx: typer.Context,
    post_id: str = typer.Argument(..., help="Post ID or slug"),
    title: Optional[str] = typer.Option(None, "--title", help="Post title"),
    content: Optional[str] = typer.Option(None, "--content", help="Post content (HTML or Markdown)"),
    file: Optional[Path] = typer.Option(None, "--file", help="Read content from file"),
    status: Optional[str] = typer.Option(None, "--status", help="Post status"),
    slug: Optional[str] = typer.Option(None, "--slug", help="Post slug"),
    featured: Optional[bool] = typer.Option(None, "--featured", help="Featured status"),
    tags: Optional[List[str]] = typer.Option(None, "--tag", help="Tag names (replaces existing tags)"),
    add_tags: Optional[List[str]] = typer.Option(None, "--add-tag", help="Add tags (keeps existing tags)"),
    remove_tags: Optional[List[str]] = typer.Option(None, "--remove-tag", help="Remove tags"),
    excerpt: Optional[str] = typer.Option(None, "--excerpt", help="Custom excerpt"),
    feature_image: Optional[str] = typer.Option(None, "--feature-image", help="Feature image URL"),
    meta_title: Optional[str] = typer.Option(None, "--meta-title", help="Meta title for SEO"),
    meta_description: Optional[str] = typer.Option(None, "--meta-description", help="Meta description for SEO"),
    visibility: Optional[str] = typer.Option(None, "--visibility", help="Post visibility"),
    published_at: Optional[str] = typer.Option(None, "--published-at", help="Publish date (ISO 8601 format)"),
) -> None:
    """Update an existing post.

    Examples:
        # Update title
        ghostctl posts update post-id --title "New Title"

        # Update content from file
        ghostctl posts update post-id --file updated-content.md

        # Add tags
        ghostctl posts update post-id --add-tag "tutorial" --add-tag "beginner"

        # Remove tags
        ghostctl posts update post-id --remove-tag "draft"

        # Schedule post
        ghostctl posts update post-id --status scheduled --published-at "2025-01-01T10:00:00Z"
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
        console.print(f"[yellow]DRY RUN: Would update post '{post_id}' with:[/yellow]")
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

    # Get current post if we need to handle tags
    current_post = None
    if add_tags or remove_tags:
        current_post = client.get_post(post_id, include=["tags"])

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
        if not current_post:
            raise GhostCtlError("Could not fetch current post to modify tags")

        # Handle both model instances and raw dict data
        if hasattr(current_post, 'tags'):
            current_tag_names = {tag.name for tag in current_post.tags}
        else:
            current_tag_names = {tag.get("name", "") for tag in current_post.get("tags", [])}

        if add_tags:
            current_tag_names.update(add_tags)
        if remove_tags:
            current_tag_names -= set(remove_tags)

        update_data["tags"] = [{"name": tag} for tag in current_tag_names]

    if not update_data:
        console.print("[yellow]No updates specified[/yellow]")
        return

    post = client.update_post(post_id, update_data)
    console.print(f"[green]Post updated successfully![/green]")
    formatter.output({"posts": [post]}, format_override=ctx.obj["output_format"])


@app.command()
@handle_exceptions
def delete(
    ctx: typer.Context,
    post_id: str = typer.Argument(..., help="Post ID or slug"),
    force: bool = typer.Option(False, "--force", help="Delete without confirmation"),
) -> None:
    """Delete a post.

    Examples:
        # Delete with confirmation
        ghostctl posts delete post-id

        # Force delete without confirmation
        ghostctl posts delete post-id --force
    """
    client, formatter = get_client_and_formatter(ctx)

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would delete post '{post_id}'[/yellow]")
        return

    # Get post details for confirmation
    if not force:
        post = client.get_post(post_id)
        console.print(f"[yellow]About to delete post:[/yellow]")

        # Handle both model instances and raw dict data
        if hasattr(post, 'id'):
            console.print(f"  ID: {post.id}")
            console.print(f"  Title: {post.title}")
            console.print(f"  Status: {post.status}")
        else:
            console.print(f"  ID: {post.get('id', 'Unknown')}")
            console.print(f"  Title: {post.get('title', 'Unknown')}")
            console.print(f"  Status: {post.get('status', 'Unknown')}")

        confirm = typer.confirm("Are you sure you want to delete this post?")
        if not confirm:
            console.print("[yellow]Delete cancelled[/yellow]")
            return

    success = client.delete_post(post_id)
    if success:
        console.print(f"[green]Post deleted successfully![/green]")
    else:
        console.print(f"[yellow]Post not found or already deleted[/yellow]")


@app.command()
@handle_exceptions
def publish(
    ctx: typer.Context,
    post_id: str = typer.Argument(..., help="Post ID or slug"),
    published_at: Optional[str] = typer.Option(None, "--published-at", help="Publish date (ISO 8601 format)"),
) -> None:
    """Publish a draft post.

    Examples:
        # Publish immediately
        ghostctl posts publish post-id

        # Schedule for future
        ghostctl posts publish post-id --published-at "2025-01-01T10:00:00Z"
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
        console.print(f"[yellow]DRY RUN: Would publish post '{post_id}' with status '{status}'[/yellow]")
        if published_at:
            console.print(f"  Scheduled for: {published_at}")
        return

    update_data = {
        "status": "scheduled" if published_at else "published"
    }

    if published_at_dt:
        update_data["published_at"] = published_at_dt.isoformat()
    else:
        update_data["published_at"] = datetime.now().isoformat()

    post = client.update_post(post_id, update_data)

    if published_at:
        console.print(f"[green]Post scheduled for publication![/green]")
    else:
        console.print(f"[green]Post published successfully![/green]")

    formatter.output({"posts": [post]}, format_override=ctx.obj["output_format"])


@app.command()
@handle_exceptions
def schedule(
    ctx: typer.Context,
    post_id: str = typer.Argument(..., help="Post ID or slug"),
    date: str = typer.Argument(..., help="Schedule date (ISO 8601 format)"),
) -> None:
    """Schedule a post for future publication.

    Examples:
        # Schedule for specific date and time
        ghostctl posts schedule post-id "2025-01-01T10:00:00Z"

        # Schedule for tomorrow at 9 AM
        ghostctl posts schedule post-id "2025-01-02T09:00:00+01:00"
    """
    # This is a convenience wrapper around publish --published-at
    ctx.invoke(publish, post_id=post_id, published_at=date)


# Bulk operations
@app.command()
@handle_exceptions
def bulk_update(
    ctx: typer.Context,
    file: Path = typer.Argument(..., help="JSON file with post updates (format: [{\"id\": \"...\", \"data\": {...}}])"),
    show_progress: bool = typer.Option(True, "--progress", help="Show progress bar"),
) -> None:
    """Bulk update posts from a JSON file.

    Example file format:
    [
        {"id": "post-id-1", "data": {"status": "published"}},
        {"id": "post-id-2", "data": {"title": "New Title"}}
    ]
    """
    import json

    if not file.exists():
        raise GhostCtlError(f"File not found: {file}")

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would bulk update posts from {file}[/yellow]")
        return

    client, formatter = get_client_and_formatter(ctx)

    try:
        with open(file, "r") as f:
            updates = json.load(f)
    except json.JSONDecodeError as e:
        raise GhostCtlError(f"Invalid JSON in file {file}: {e}")

    if not isinstance(updates, list):
        raise GhostCtlError("File must contain a JSON array of update objects")

    # Convert to the format expected by bulk_update_posts
    update_tuples = []
    for update in updates:
        if not isinstance(update, dict) or "id" not in update or "data" not in update:
            raise GhostCtlError("Each update must have 'id' and 'data' fields")
        update_tuples.append((update["id"], update["data"]))

    results = client.bulk_update_posts(update_tuples, show_progress=show_progress)

    # Count successes and failures
    successes = sum(1 for r in results if "error" not in r)
    failures = len(results) - successes

    if failures > 0:
        console.print(f"[yellow]Bulk update completed with {failures} failures out of {len(results)} operations[/yellow]")

        # Show first few failures
        error_results = [r for r in results if "error" in r]
        for i, error_result in enumerate(error_results[:3]):
            console.print(f"  Failed: {error_result.get('post_id', 'unknown')} - {error_result.get('error', 'unknown error')}")

        if len(error_results) > 3:
            console.print(f"  ... and {len(error_results) - 3} more failures")
    else:
        console.print(f"[green]All {len(results)} posts updated successfully![/green]")

    if ctx.obj["output_format"] in ["json", "yaml"]:
        formatter.output({"results": results}, format_override=ctx.obj["output_format"])


@app.command()
@handle_exceptions
def bulk_delete(
    ctx: typer.Context,
    post_ids: List[str] = typer.Argument(..., help="List of post IDs to delete"),
    force: bool = typer.Option(False, "--force", help="Delete without confirmation"),
    show_progress: bool = typer.Option(True, "--progress", help="Show progress bar"),
) -> None:
    """Bulk delete posts by ID.

    Examples:
        # Delete multiple posts
        ghostctl posts bulk-delete post-id-1 post-id-2 post-id-3

        # Force delete without confirmation
        ghostctl posts bulk-delete post-id-1 post-id-2 --force
    """
    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would delete {len(post_ids)} posts[/yellow]")
        for post_id in post_ids:
            console.print(f"  - {post_id}")
        return

    client, formatter = get_client_and_formatter(ctx)

    if not force:
        console.print(f"[yellow]About to delete {len(post_ids)} posts:[/yellow]")
        for post_id in post_ids[:5]:  # Show first 5
            console.print(f"  - {post_id}")
        if len(post_ids) > 5:
            console.print(f"  ... and {len(post_ids) - 5} more")

        confirm = typer.confirm("Are you sure you want to delete these posts?")
        if not confirm:
            console.print("[yellow]Bulk delete cancelled[/yellow]")
            return

    results = client.bulk_delete_posts(post_ids, show_progress=show_progress)

    # Count successes and failures
    successes = sum(1 for r in results if r.get("deleted", False))
    failures = len(results) - successes

    if failures > 0:
        console.print(f"[yellow]Bulk delete completed with {failures} failures out of {len(results)} operations[/yellow]")

        # Show failures
        error_results = [r for r in results if not r.get("deleted", False)]
        for error_result in error_results[:3]:
            error_msg = error_result.get("error", "unknown error")
            console.print(f"  Failed: {error_result.get('post_id', 'unknown')} - {error_msg}")

        if len(error_results) > 3:
            console.print(f"  ... and {len(error_results) - 3} more failures")
    else:
        console.print(f"[green]All {len(results)} posts deleted successfully![/green]")

    if ctx.obj["output_format"] in ["json", "yaml"]:
        formatter.output({"results": results}, format_override=ctx.obj["output_format"])


if __name__ == "__main__":
    app()