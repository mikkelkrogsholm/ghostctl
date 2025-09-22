"""Export commands for GhostCtl CLI.

This module provides commands for exporting content from Ghost CMS
including posts, members, and complete site exports.
"""

from pathlib import Path
from typing import Optional
import json
import csv
from datetime import datetime

import typer
from rich.console import Console
from rich.progress import Progress

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


@app.command()
def all(
    ctx: typer.Context,
    output_file: Path = typer.Argument(..., help="Output file path (.json)"),
    include_members: bool = typer.Option(True, "--include-members/--no-members", help="Include member data"),
    include_content: bool = typer.Option(True, "--include-content/--no-content", help="Include posts and pages"),
    include_settings: bool = typer.Option(True, "--include-settings/--no-settings", help="Include site settings"),
    include_themes: bool = typer.Option(False, "--include-themes/--no-themes", help="Include theme information"),
    compress: bool = typer.Option(False, "--compress", help="Compress output file"),
) -> None:
    """Export all site data to a JSON file.

    This creates a comprehensive backup of your Ghost site including
    posts, pages, members, tags, and settings.

    Examples:
        # Export everything
        ghostctl export all backup.json

        # Export without members (GDPR compliance)
        ghostctl export all content-only.json --no-members

        # Export content only
        ghostctl export all posts-pages.json --no-members --no-settings

        # Export with compression
        ghostctl export all backup.json --compress
    """
    client, formatter = get_client_and_formatter(ctx)

    if output_file.suffix.lower() not in ['.json']:
        console.print("[red]Output file must have .json extension[/red]")
        raise typer.Exit(1)

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would export all data to '{output_file}' with:[/yellow]")
        console.print(f"  Include members: {include_members}")
        console.print(f"  Include content: {include_content}")
        console.print(f"  Include settings: {include_settings}")
        console.print(f"  Include themes: {include_themes}")
        console.print(f"  Compress: {compress}")
        return

    try:
        export_data = {
            "meta": {
                "exported_on": datetime.now().isoformat(),
                "version": "1.0",
                "ghost_version": "5.x",  # Will be updated from site info
            },
            "data": {}
        }

        with Progress(console=console) as progress:
            # Count tasks
            task_count = 0
            if include_content:
                task_count += 4  # posts, pages, tags, authors
            if include_members:
                task_count += 1
            if include_settings:
                task_count += 1
            if include_themes:
                task_count += 1

            main_task = progress.add_task("Exporting data...", total=task_count)

            # Export site settings first to get version info
            if include_settings:
                progress.console.print("  Exporting settings...")
                settings = client.get_settings()
                export_data["data"]["settings"] = settings

                # Update meta with actual Ghost version if available
                if isinstance(settings, dict) and "version" in settings:
                    export_data["meta"]["ghost_version"] = settings["version"]

                progress.advance(main_task)

            # Export content
            if include_content:
                # Export posts
                progress.console.print("  Exporting posts...")
                all_posts = []
                page = 1
                while True:
                    posts = client.get_posts(
                        page=page,
                        limit=100,
                        include="tags,authors",
                        order="created_at ASC"
                    )
                    if not posts:
                        break
                    all_posts.extend(posts)
                    if len(posts) < 100:
                        break
                    page += 1

                export_data["data"]["posts"] = all_posts
                progress.console.print(f"    Exported {len(all_posts)} posts")
                progress.advance(main_task)

                # Export pages
                progress.console.print("  Exporting pages...")
                all_pages = []
                page = 1
                while True:
                    pages = client.get_pages(
                        page=page,
                        limit=100,
                        include="tags,authors",
                        order="created_at ASC"
                    )
                    if not pages:
                        break
                    all_pages.extend(pages)
                    if len(pages) < 100:
                        break
                    page += 1

                export_data["data"]["pages"] = all_pages
                progress.console.print(f"    Exported {len(all_pages)} pages")
                progress.advance(main_task)

                # Export tags
                progress.console.print("  Exporting tags...")
                all_tags = []
                page = 1
                while True:
                    tags = client.get_tags(
                        page=page,
                        limit=100,
                        include="count.posts",
                        order="created_at ASC"
                    )
                    if not tags:
                        break
                    all_tags.extend(tags)
                    if len(tags) < 100:
                        break
                    page += 1

                export_data["data"]["tags"] = all_tags
                progress.console.print(f"    Exported {len(all_tags)} tags")
                progress.advance(main_task)

                # Export authors (users)
                progress.console.print("  Exporting authors...")
                try:
                    authors = client.get_users(include="count.posts")
                    export_data["data"]["users"] = authors
                    progress.console.print(f"    Exported {len(authors)} authors")
                except GhostCtlError:
                    progress.console.print("    Could not export authors (insufficient permissions)")
                    export_data["data"]["users"] = []
                progress.advance(main_task)

            # Export members
            if include_members:
                progress.console.print("  Exporting members...")
                all_members = []
                page = 1
                while True:
                    try:
                        members = client.get_members(
                            page=page,
                            limit=100,
                            include="labels",
                            order="created_at ASC"
                        )
                        if not members:
                            break
                        all_members.extend(members)
                        if len(members) < 100:
                            break
                        page += 1
                    except GhostCtlError as e:
                        progress.console.print(f"    Warning: Could not export members: {e}")
                        break

                export_data["data"]["members"] = all_members
                progress.console.print(f"    Exported {len(all_members)} members")
                progress.advance(main_task)

            # Export themes
            if include_themes:
                progress.console.print("  Exporting theme information...")
                try:
                    themes = client.get_themes()
                    export_data["data"]["themes"] = themes
                    progress.console.print(f"    Exported {len(themes)} themes")
                except GhostCtlError as e:
                    progress.console.print(f"    Warning: Could not export themes: {e}")
                    export_data["data"]["themes"] = []
                progress.advance(main_task)

        # Write export file
        console.print(f"\n[blue]Writing export data to {output_file}...[/blue]")

        if compress:
            import gzip
            with gzip.open(str(output_file) + '.gz', 'wt', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, default=str)
            output_file = Path(str(output_file) + '.gz')
        else:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, default=str)

        file_size = output_file.stat().st_size
        console.print(f"[green]Export completed successfully![/green]")
        console.print(f"  Output file: {output_file}")
        console.print(f"  File size: {file_size:,} bytes ({file_size / 1024 / 1024:.1f} MB)")

        # Summary statistics
        data = export_data["data"]
        console.print(f"\n[bold]Export Summary:[/bold]")
        if "posts" in data:
            console.print(f"  Posts: {len(data['posts'])}")
        if "pages" in data:
            console.print(f"  Pages: {len(data['pages'])}")
        if "tags" in data:
            console.print(f"  Tags: {len(data['tags'])}")
        if "users" in data:
            console.print(f"  Authors: {len(data['users'])}")
        if "members" in data:
            console.print(f"  Members: {len(data['members'])}")
        if "themes" in data:
            console.print(f"  Themes: {len(data['themes'])}")

        if ctx.obj["output_format"] in ["json", "yaml"]:
            formatter.output({
                "output_file": str(output_file),
                "file_size": file_size,
                "compressed": compress,
                "summary": {k: len(v) if isinstance(v, list) else 1 for k, v in data.items()}
            }, format_override=ctx.obj["output_format"])

    except GhostCtlError as e:
        console.print(f"[red]Error during export: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def posts(
    ctx: typer.Context,
    output_file: Path = typer.Argument(..., help="Output file path (.json or .csv)"),
    filter: Optional[str] = typer.Option(None, "--filter", help="Filter posts to export"),
    include_content: bool = typer.Option(True, "--include-content/--no-content", help="Include post content"),
    format: Optional[str] = typer.Option(None, "--format", help="Output format (json, csv)"),
) -> None:
    """Export posts to JSON or CSV file.

    Examples:
        # Export all posts to JSON
        ghostctl export posts posts.json

        # Export published posts only
        ghostctl export posts published.json --filter "status:published"

        # Export to CSV without content
        ghostctl export posts posts.csv --no-content

        # Export drafts only
        ghostctl export posts drafts.json --filter "status:draft"
    """
    client, formatter = get_client_and_formatter(ctx)

    # Determine format from file extension or explicit format
    if format:
        export_format = format.lower()
    else:
        export_format = output_file.suffix.lower().lstrip('.')

    if export_format not in ['json', 'csv']:
        console.print("[red]Output format must be 'json' or 'csv'[/red]")
        raise typer.Exit(1)

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would export posts to '{output_file}' with:[/yellow]")
        console.print(f"  Format: {export_format}")
        console.print(f"  Filter: {filter or 'none'}")
        console.print(f"  Include content: {include_content}")
        return

    try:
        # Fetch all posts
        all_posts = []
        page = 1

        with Progress(console=console) as progress:
            fetch_task = progress.add_task("Fetching posts...", total=None)

            while True:
                posts = client.get_posts(
                    filter=filter,
                    page=page,
                    limit=100,
                    include="tags,authors",
                    order="created_at ASC"
                )

                if not posts:
                    break

                all_posts.extend(posts)
                progress.console.print(f"  Fetched page {page} ({len(posts)} posts)")

                if len(posts) < 100:
                    break

                page += 1

        if not all_posts:
            console.print("[yellow]No posts found to export[/yellow]")
            return

        console.print(f"[blue]Exporting {len(all_posts)} posts to {export_format.upper()}...[/blue]")

        if export_format == 'json':
            # JSON export
            export_data = {
                "meta": {
                    "exported_on": datetime.now().isoformat(),
                    "filter": filter,
                    "include_content": include_content,
                },
                "posts": all_posts
            }

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, default=str)

        elif export_format == 'csv':
            # CSV export
            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'id', 'title', 'slug', 'status', 'visibility', 'featured',
                    'published_at', 'created_at', 'updated_at', 'authors', 'tags'
                ]

                if include_content:
                    fieldnames.extend(['excerpt', 'html', 'feature_image'])

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for post in all_posts:
                    row = {
                        'id': post.id,
                        'title': post.title,
                        'slug': post.slug,
                        'status': post.status,
                        'visibility': post.visibility,
                        'featured': post.featured,
                        'published_at': post.published_at.isoformat() if post.published_at else '',
                        'created_at': post.created_at.isoformat() if post.created_at else '',
                        'updated_at': post.updated_at.isoformat() if post.updated_at else '',
                        'authors': ', '.join([author.name for author in post.authors]),
                        'tags': ', '.join([tag.name for tag in post.tags]),
                    }

                    if include_content:
                        row.update({
                            'excerpt': post.custom_excerpt or '',
                            'html': post.html or '',
                            'feature_image': post.feature_image or '',
                        })

                    writer.writerow(row)

        file_size = output_file.stat().st_size
        console.print(f"[green]Successfully exported {len(all_posts)} posts to '{output_file}'![/green]")
        console.print(f"  File size: {file_size:,} bytes ({file_size / 1024 / 1024:.1f} MB)")

        if ctx.obj["output_format"] in ["json", "yaml"]:
            formatter.output({
                "output_file": str(output_file),
                "format": export_format,
                "exported_count": len(all_posts),
                "file_size": file_size,
            }, format_override=ctx.obj["output_format"])

    except GhostCtlError as e:
        console.print(f"[red]Error exporting posts: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def members(
    ctx: typer.Context,
    output_file: Path = typer.Argument(..., help="Output file path (.csv or .json)"),
    filter: Optional[str] = typer.Option(None, "--filter", help="Filter members to export"),
    include_labels: bool = typer.Option(True, "--include-labels/--no-labels", help="Include member labels"),
    format: Optional[str] = typer.Option(None, "--format", help="Output format (csv, json)"),
) -> None:
    """Export members to CSV or JSON file.

    Examples:
        # Export all members to CSV
        ghostctl export members members.csv

        # Export paid members only
        ghostctl export members paid-members.csv --filter "status:paid"

        # Export to JSON with labels
        ghostctl export members members.json --include-labels

        # Export free members without labels
        ghostctl export members free-members.csv --filter "status:free" --no-labels
    """
    client, formatter = get_client_and_formatter(ctx)

    # Determine format from file extension or explicit format
    if format:
        export_format = format.lower()
    else:
        export_format = output_file.suffix.lower().lstrip('.')

    if export_format not in ['csv', 'json']:
        console.print("[red]Output format must be 'csv' or 'json'[/red]")
        raise typer.Exit(1)

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would export members to '{output_file}' with:[/yellow]")
        console.print(f"  Format: {export_format}")
        console.print(f"  Filter: {filter or 'none'}")
        console.print(f"  Include labels: {include_labels}")
        return

    try:
        # Fetch all members
        all_members = []
        page = 1

        with Progress(console=console) as progress:
            fetch_task = progress.add_task("Fetching members...", total=None)

            while True:
                members = client.get_members(
                    filter=filter,
                    page=page,
                    limit=100,
                    include="labels" if include_labels else None,
                    order="created_at ASC"
                )

                if not members:
                    break

                all_members.extend(members)
                progress.console.print(f"  Fetched page {page} ({len(members)} members)")

                if len(members) < 100:
                    break

                page += 1

        if not all_members:
            console.print("[yellow]No members found to export[/yellow]")
            return

        console.print(f"[blue]Exporting {len(all_members)} members to {export_format.upper()}...[/blue]")

        if export_format == 'json':
            # JSON export
            export_data = {
                "meta": {
                    "exported_on": datetime.now().isoformat(),
                    "filter": filter,
                    "include_labels": include_labels,
                },
                "members": all_members
            }

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, default=str)

        elif export_format == 'csv':
            # CSV export
            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'email', 'name', 'status', 'subscribed', 'comped',
                    'created_at', 'updated_at', 'note'
                ]

                if include_labels:
                    fieldnames.append('labels')

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for member in all_members:
                    row = {
                        'email': member.email,
                        'name': member.name or '',
                        'status': member.status or 'free',
                        'subscribed': str(member.subscribed).lower() if hasattr(member, 'subscribed') else 'true',
                        'comped': str(getattr(member, 'comped', False)).lower(),
                        'created_at': member.created_at.isoformat() if member.created_at else '',
                        'updated_at': member.updated_at.isoformat() if member.updated_at else '',
                        'note': getattr(member, 'note', '') or '',
                    }

                    if include_labels:
                        labels = []
                        if hasattr(member, 'labels') and member.labels:
                            labels = [label.name for label in member.labels]
                        row['labels'] = ', '.join(labels)

                    writer.writerow(row)

        file_size = output_file.stat().st_size
        console.print(f"[green]Successfully exported {len(all_members)} members to '{output_file}'![/green]")
        console.print(f"  File size: {file_size:,} bytes ({file_size / 1024:.1f} KB)")

        if ctx.obj["output_format"] in ["json", "yaml"]:
            formatter.output({
                "output_file": str(output_file),
                "format": export_format,
                "exported_count": len(all_members),
                "file_size": file_size,
            }, format_override=ctx.obj["output_format"])

    except GhostCtlError as e:
        console.print(f"[red]Error exporting members: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def content(
    ctx: typer.Context,
    output_file: Path = typer.Argument(..., help="Output file path (.json)"),
    include_posts: bool = typer.Option(True, "--include-posts/--no-posts", help="Include posts"),
    include_pages: bool = typer.Option(True, "--include-pages/--no-pages", help="Include pages"),
    include_tags: bool = typer.Option(True, "--include-tags/--no-tags", help="Include tags"),
    published_only: bool = typer.Option(False, "--published-only", help="Export only published content"),
) -> None:
    """Export content (posts, pages, tags) to JSON file.

    Examples:
        # Export all content
        ghostctl export content content.json

        # Export only published content
        ghostctl export content published-content.json --published-only

        # Export posts and pages only
        ghostctl export content posts-pages.json --no-tags

        # Export tags only
        ghostctl export content tags-only.json --no-posts --no-pages
    """
    client, formatter = get_client_and_formatter(ctx)

    if output_file.suffix.lower() != '.json':
        console.print("[red]Output file must have .json extension[/red]")
        raise typer.Exit(1)

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would export content to '{output_file}' with:[/yellow]")
        console.print(f"  Include posts: {include_posts}")
        console.print(f"  Include pages: {include_pages}")
        console.print(f"  Include tags: {include_tags}")
        console.print(f"  Published only: {published_only}")
        return

    try:
        export_data = {
            "meta": {
                "exported_on": datetime.now().isoformat(),
                "published_only": published_only,
            },
            "data": {}
        }

        with Progress(console=console) as progress:
            task_count = sum([include_posts, include_pages, include_tags])
            main_task = progress.add_task("Exporting content...", total=task_count)

            # Export posts
            if include_posts:
                progress.console.print("  Exporting posts...")
                all_posts = []
                page = 1
                filter_posts = "status:published" if published_only else None

                while True:
                    posts = client.get_posts(
                        filter=filter_posts,
                        page=page,
                        limit=100,
                        include="tags,authors",
                        order="created_at ASC"
                    )
                    if not posts:
                        break
                    all_posts.extend(posts)
                    if len(posts) < 100:
                        break
                    page += 1

                export_data["data"]["posts"] = all_posts
                progress.console.print(f"    Exported {len(all_posts)} posts")
                progress.advance(main_task)

            # Export pages
            if include_pages:
                progress.console.print("  Exporting pages...")
                all_pages = []
                page = 1
                filter_pages = "status:published" if published_only else None

                while True:
                    pages = client.get_pages(
                        filter=filter_pages,
                        page=page,
                        limit=100,
                        include="tags,authors",
                        order="created_at ASC"
                    )
                    if not pages:
                        break
                    all_pages.extend(pages)
                    if len(pages) < 100:
                        break
                    page += 1

                export_data["data"]["pages"] = all_pages
                progress.console.print(f"    Exported {len(all_pages)} pages")
                progress.advance(main_task)

            # Export tags
            if include_tags:
                progress.console.print("  Exporting tags...")
                all_tags = []
                page = 1

                while True:
                    tags = client.get_tags(
                        page=page,
                        limit=100,
                        include="count.posts",
                        order="created_at ASC"
                    )
                    if not tags:
                        break
                    all_tags.extend(tags)
                    if len(tags) < 100:
                        break
                    page += 1

                export_data["data"]["tags"] = all_tags
                progress.console.print(f"    Exported {len(all_tags)} tags")
                progress.advance(main_task)

        # Write export file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, default=str)

        file_size = output_file.stat().st_size
        console.print(f"[green]Content export completed successfully![/green]")
        console.print(f"  Output file: {output_file}")
        console.print(f"  File size: {file_size:,} bytes ({file_size / 1024 / 1024:.1f} MB)")

        # Summary statistics
        data = export_data["data"]
        console.print(f"\n[bold]Export Summary:[/bold]")
        if "posts" in data:
            console.print(f"  Posts: {len(data['posts'])}")
        if "pages" in data:
            console.print(f"  Pages: {len(data['pages'])}")
        if "tags" in data:
            console.print(f"  Tags: {len(data['tags'])}")

        if ctx.obj["output_format"] in ["json", "yaml"]:
            formatter.output({
                "output_file": str(output_file),
                "file_size": file_size,
                "summary": {k: len(v) if isinstance(v, list) else 1 for k, v in data.items()}
            }, format_override=ctx.obj["output_format"])

    except GhostCtlError as e:
        console.print(f"[red]Error exporting content: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()