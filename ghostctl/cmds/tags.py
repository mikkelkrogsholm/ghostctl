"""Tag management commands for GhostCtl CLI.

This module provides commands for managing Ghost CMS tags including
listing, creating, updating, and deleting tags with enhanced error handling.
"""

from typing import Optional, List

import typer
from rich.console import Console
from rich.table import Table

from ..client import GhostClient
from ..render import OutputFormatter
from ..exceptions import GhostCtlError
from ..utils.client_factory import get_client_and_formatter
from ..app import handle_exceptions

app = typer.Typer()
console = Console()




@app.command()
@handle_exceptions
def list(
    ctx: typer.Context,
    filter: Optional[str] = typer.Option(None, "--filter", help="Filter tags (e.g., 'visibility:public')"),
    page: int = typer.Option(1, "--page", help="Page number"),
    limit: int = typer.Option(15, "--limit", help="Number of tags per page"),
    include: Optional[str] = typer.Option("count.posts", "--include", help="Include related data"),
    order: Optional[str] = typer.Option("name ASC", "--order", help="Sort order"),
    all_pages: bool = typer.Option(False, "--all", help="Fetch all tags (may take time)"),
    show_progress: bool = typer.Option(False, "--progress", help="Show progress bar for long operations"),
) -> None:
    """List tags.

    Examples:
        # List all tags
        ghostctl tags list

        # List public tags only
        ghostctl tags list --filter "visibility:public"

        # List tags with post counts
        ghostctl tags list --include "count.posts"

        # List tags ordered by creation date
        ghostctl tags list --order "created_at DESC"
    """
    client, formatter = get_client_and_formatter(ctx)

    if ctx.obj["dry_run"]:
        console.print("[yellow]DRY RUN: Would list tags with filters:[/yellow]")
        console.print(f"  Filter: {filter or 'none'}")
        console.print(f"  Page: {page}, Limit: {limit}")
        console.print(f"  Include: {include}")
        console.print(f"  Order: {order}")
        return

    try:
        tags = client.get_tags(
            filter=filter,
            page=page,
            limit=limit,
            include=include,
            order=order,
        )

        if ctx.obj["output_format"] in ["json", "yaml"]:
            formatter.output({"tags": tags}, format_override=ctx.obj["output_format"])
        else:
            # Table format
            table = Table(title="Tags")
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("Name", style="bold")
            table.add_column("Slug", style="dim")
            table.add_column("Visibility", style="green")
            table.add_column("Posts", style="blue", justify="right")
            table.add_column("Description", style="dim")

            for tag in tags:
                # Handle post count if included
                post_count = "—"
                if hasattr(tag, 'count') and hasattr(tag.count, 'posts'):
                    post_count = str(tag.count.posts)

                description = tag.description or "—"
                if len(description) > 40:
                    description = description[:37] + "..."

                table.add_row(
                    tag.id[:8],
                    tag.name,
                    tag.slug,
                    tag.visibility,
                    post_count,
                    description,
                )

            console.print(table)

    except GhostCtlError as e:
        console.print(f"[red]Error listing tags: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def get(
    ctx: typer.Context,
    tag_id: str = typer.Argument(..., help="Tag ID or slug"),
    include: Optional[str] = typer.Option("count.posts", "--include", help="Include related data"),
) -> None:
    """Get a specific tag by ID or slug.

    Examples:
        # Get tag by ID
        ghostctl tags get 507f1f77bcf86cd799439011

        # Get tag by slug
        ghostctl tags get technology

        # Get tag with post count
        ghostctl tags get technology --include "count.posts"
    """
    client, formatter = get_client_and_formatter(ctx)

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would get tag '{tag_id}' with includes: {include}[/yellow]")
        return

    try:
        tag = client.get_tag(tag_id, include=include)
        formatter.output({"tags": [tag]}, format_override=ctx.obj["output_format"])

    except GhostCtlError as e:
        console.print(f"[red]Error getting tag: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def create(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name", help="Tag name"),
    slug: Optional[str] = typer.Option(None, "--slug", help="Tag slug (auto-generated if not provided)"),
    description: Optional[str] = typer.Option(None, "--description", help="Tag description"),
    feature_image: Optional[str] = typer.Option(None, "--feature-image", help="Feature image URL"),
    visibility: str = typer.Option("public", "--visibility", help="Tag visibility (public, internal)"),
    meta_title: Optional[str] = typer.Option(None, "--meta-title", help="Meta title for SEO"),
    meta_description: Optional[str] = typer.Option(None, "--meta-description", help="Meta description for SEO"),
    og_image: Optional[str] = typer.Option(None, "--og-image", help="Open Graph image URL"),
    og_title: Optional[str] = typer.Option(None, "--og-title", help="Open Graph title"),
    og_description: Optional[str] = typer.Option(None, "--og-description", help="Open Graph description"),
    twitter_image: Optional[str] = typer.Option(None, "--twitter-image", help="Twitter card image URL"),
    twitter_title: Optional[str] = typer.Option(None, "--twitter-title", help="Twitter card title"),
    twitter_description: Optional[str] = typer.Option(None, "--twitter-description", help="Twitter card description"),
    accent_color: Optional[str] = typer.Option(None, "--accent-color", help="Accent color (hex format)"),
    canonical_url: Optional[str] = typer.Option(None, "--canonical-url", help="Canonical URL"),
) -> None:
    """Create a new tag.

    Examples:
        # Create a simple tag
        ghostctl tags create --name "Technology"

        # Create with description and custom slug
        ghostctl tags create --name "Web Development" --slug "webdev" --description "Articles about web development"

        # Create internal tag
        ghostctl tags create --name "#Internal Notes" --visibility internal

        # Create with full SEO metadata
        ghostctl tags create --name "JavaScript" --description "JS tutorials" --meta-title "JavaScript Tutorials" --accent-color "#f7df1e"
    """
    client, formatter = get_client_and_formatter(ctx)

    if ctx.obj["dry_run"]:
        console.print("[yellow]DRY RUN: Would create tag with:[/yellow]")
        console.print(f"  Name: {name}")
        console.print(f"  Slug: {slug or 'auto-generated'}")
        console.print(f"  Visibility: {visibility}")
        console.print(f"  Description: {description or 'none'}")
        return

    try:
        tag_data = {
            "name": name,
            "visibility": visibility,
        }

        # Add optional fields
        if slug:
            tag_data["slug"] = slug
        if description:
            tag_data["description"] = description
        if feature_image:
            tag_data["feature_image"] = feature_image
        if meta_title:
            tag_data["meta_title"] = meta_title
        if meta_description:
            tag_data["meta_description"] = meta_description
        if og_image:
            tag_data["og_image"] = og_image
        if og_title:
            tag_data["og_title"] = og_title
        if og_description:
            tag_data["og_description"] = og_description
        if twitter_image:
            tag_data["twitter_image"] = twitter_image
        if twitter_title:
            tag_data["twitter_title"] = twitter_title
        if twitter_description:
            tag_data["twitter_description"] = twitter_description
        if accent_color:
            tag_data["accent_color"] = accent_color
        if canonical_url:
            tag_data["canonical_url"] = canonical_url

        tag = client.create_tag(tag_data)
        console.print(f"[green]Tag created successfully![/green]")
        formatter.output({"tags": [tag]}, format_override=ctx.obj["output_format"])

    except GhostCtlError as e:
        console.print(f"[red]Error creating tag: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def update(
    ctx: typer.Context,
    tag_id: str = typer.Argument(..., help="Tag ID or slug"),
    name: Optional[str] = typer.Option(None, "--name", help="Tag name"),
    slug: Optional[str] = typer.Option(None, "--slug", help="Tag slug"),
    description: Optional[str] = typer.Option(None, "--description", help="Tag description"),
    feature_image: Optional[str] = typer.Option(None, "--feature-image", help="Feature image URL"),
    visibility: Optional[str] = typer.Option(None, "--visibility", help="Tag visibility (public, internal)"),
    meta_title: Optional[str] = typer.Option(None, "--meta-title", help="Meta title for SEO"),
    meta_description: Optional[str] = typer.Option(None, "--meta-description", help="Meta description for SEO"),
    og_image: Optional[str] = typer.Option(None, "--og-image", help="Open Graph image URL"),
    og_title: Optional[str] = typer.Option(None, "--og-title", help="Open Graph title"),
    og_description: Optional[str] = typer.Option(None, "--og-description", help="Open Graph description"),
    twitter_image: Optional[str] = typer.Option(None, "--twitter-image", help="Twitter card image URL"),
    twitter_title: Optional[str] = typer.Option(None, "--twitter-title", help="Twitter card title"),
    twitter_description: Optional[str] = typer.Option(None, "--twitter-description", help="Twitter card description"),
    accent_color: Optional[str] = typer.Option(None, "--accent-color", help="Accent color (hex format)"),
    canonical_url: Optional[str] = typer.Option(None, "--canonical-url", help="Canonical URL"),
) -> None:
    """Update an existing tag.

    Examples:
        # Update description
        ghostctl tags update technology --description "Updated description"

        # Update visibility
        ghostctl tags update internal-tag --visibility public

        # Update SEO metadata
        ghostctl tags update javascript --meta-title "JavaScript Tutorials" --accent-color "#f7df1e"
    """
    client, formatter = get_client_and_formatter(ctx)

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would update tag '{tag_id}' with:[/yellow]")
        if name:
            console.print(f"  Name: {name}")
        if slug:
            console.print(f"  Slug: {slug}")
        if description:
            console.print(f"  Description: {description}")
        if visibility:
            console.print(f"  Visibility: {visibility}")
        return

    try:
        # Build update data
        update_data = {}

        if name:
            update_data["name"] = name
        if slug:
            update_data["slug"] = slug
        if description:
            update_data["description"] = description
        if feature_image:
            update_data["feature_image"] = feature_image
        if visibility:
            update_data["visibility"] = visibility
        if meta_title:
            update_data["meta_title"] = meta_title
        if meta_description:
            update_data["meta_description"] = meta_description
        if og_image:
            update_data["og_image"] = og_image
        if og_title:
            update_data["og_title"] = og_title
        if og_description:
            update_data["og_description"] = og_description
        if twitter_image:
            update_data["twitter_image"] = twitter_image
        if twitter_title:
            update_data["twitter_title"] = twitter_title
        if twitter_description:
            update_data["twitter_description"] = twitter_description
        if accent_color:
            update_data["accent_color"] = accent_color
        if canonical_url:
            update_data["canonical_url"] = canonical_url

        if not update_data:
            console.print("[yellow]No updates specified[/yellow]")
            return

        tag = client.update_tag(tag_id, update_data)
        console.print(f"[green]Tag updated successfully![/green]")
        formatter.output({"tags": [tag]}, format_override=ctx.obj["output_format"])

    except GhostCtlError as e:
        console.print(f"[red]Error updating tag: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def delete(
    ctx: typer.Context,
    tag_id: str = typer.Argument(..., help="Tag ID or slug"),
    force: bool = typer.Option(False, "--force", help="Delete without confirmation"),
) -> None:
    """Delete a tag.

    Examples:
        # Delete with confirmation
        ghostctl tags delete tag-id

        # Force delete without confirmation
        ghostctl tags delete tag-id --force
    """
    client, formatter = get_client_and_formatter(ctx)

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would delete tag '{tag_id}'[/yellow]")
        return

    try:
        # Get tag details for confirmation
        if not force:
            tag = client.get_tag(tag_id, include="count.posts")
            console.print(f"[yellow]About to delete tag:[/yellow]")
            console.print(f"  ID: {tag.id}")
            console.print(f"  Name: {tag.name}")
            console.print(f"  Visibility: {tag.visibility}")

            # Show post count if available
            if hasattr(tag, 'count') and hasattr(tag.count, 'posts'):
                post_count = tag.count.posts
                console.print(f"  Posts using this tag: {post_count}")
                if post_count > 0:
                    console.print(f"  [yellow]Warning: This tag is used by {post_count} post(s)[/yellow]")

            confirm = typer.confirm("Are you sure you want to delete this tag?")
            if not confirm:
                console.print("[yellow]Delete cancelled[/yellow]")
                return

        client.delete_tag(tag_id)
        console.print(f"[green]Tag deleted successfully![/green]")

    except GhostCtlError as e:
        console.print(f"[red]Error deleting tag: {e}[/red]")
        raise typer.Exit(1)


@app.command("bulk-update")
def bulk_update(
    ctx: typer.Context,
    filter: str = typer.Option(..., "--filter", help="Filter to select tags for update"),
    visibility: Optional[str] = typer.Option(None, "--visibility", help="Update visibility for all matching tags"),
    accent_color: Optional[str] = typer.Option(None, "--accent-color", help="Update accent color for all matching tags"),
    meta_title_template: Optional[str] = typer.Option(None, "--meta-title-template", help="Template for meta title (use {name} for tag name)"),
    meta_description_template: Optional[str] = typer.Option(None, "--meta-description-template", help="Template for meta description"),
) -> None:
    """Bulk update tags matching a filter.

    Examples:
        # Make all internal tags public
        ghostctl tags bulk-update --filter "visibility:internal" --visibility public

        # Set accent color for all tags
        ghostctl tags bulk-update --filter "name:-[Tech,Dev]" --accent-color "#0066cc"

        # Update meta titles using template
        ghostctl tags bulk-update --filter "meta_title:null" --meta-title-template "{name} - My Blog"
    """
    client, formatter = get_client_and_formatter(ctx)

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would bulk update tags matching '{filter}' with:[/yellow]")
        if visibility:
            console.print(f"  Visibility: {visibility}")
        if accent_color:
            console.print(f"  Accent color: {accent_color}")
        if meta_title_template:
            console.print(f"  Meta title template: {meta_title_template}")
        if meta_description_template:
            console.print(f"  Meta description template: {meta_description_template}")
        return

    try:
        # First, get all tags matching the filter
        tags = client.get_tags(filter=filter, limit="all")

        if not tags:
            console.print("[yellow]No tags match the specified filter[/yellow]")
            return

        console.print(f"[blue]Found {len(tags)} tags matching filter[/blue]")

        # Build update data
        updated_count = 0
        for tag in tags:
            update_data = {}

            if visibility:
                update_data["visibility"] = visibility
            if accent_color:
                update_data["accent_color"] = accent_color
            if meta_title_template:
                update_data["meta_title"] = meta_title_template.format(name=tag.name)
            if meta_description_template:
                update_data["meta_description"] = meta_description_template.format(name=tag.name)

            if update_data:
                try:
                    client.update_tag(tag.id, update_data)
                    updated_count += 1
                    console.print(f"  ✓ Updated: {tag.name}")
                except GhostCtlError as e:
                    console.print(f"  ✗ Failed to update {tag.name}: {e}")

        console.print(f"[green]Successfully updated {updated_count}/{len(tags)} tags[/green]")

    except GhostCtlError as e:
        console.print(f"[red]Error in bulk update: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()