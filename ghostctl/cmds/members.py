"""Member management commands for GhostCtl CLI.

This module provides commands for managing Ghost CMS members including
CRUD operations and CSV import functionality.
"""

import csv
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, TaskID

from ..client import GhostClient
from ..render import OutputFormatter
from ..exceptions import GhostCtlError, ValidationError

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
    filter: Optional[str] = typer.Option(None, "--filter", help="Filter members (e.g., 'status:paid')"),
    page: int = typer.Option(1, "--page", help="Page number"),
    limit: int = typer.Option(15, "--limit", help="Number of members per page"),
    include: Optional[str] = typer.Option("labels", "--include", help="Include related data"),
    order: Optional[str] = typer.Option("created_at DESC", "--order", help="Sort order"),
) -> None:
    """List members.

    Examples:
        # List all members
        ghostctl members list

        # List paid members only
        ghostctl members list --filter "status:paid"

        # List members with labels
        ghostctl members list --include "labels"

        # List recent members
        ghostctl members list --order "created_at DESC" --limit 10
    """
    client, formatter = get_client_and_formatter(ctx)

    if ctx.obj["dry_run"]:
        console.print("[yellow]DRY RUN: Would list members with filters:[/yellow]")
        console.print(f"  Filter: {filter or 'none'}")
        console.print(f"  Page: {page}, Limit: {limit}")
        console.print(f"  Include: {include}")
        console.print(f"  Order: {order}")
        return

    try:
        members = client.get_members(
            filter=filter,
            page=page,
            limit=limit,
            include=include,
            order=order,
        )

        if ctx.obj["output_format"] in ["json", "yaml"]:
            formatter.output({"members": members}, format_override=ctx.obj["output_format"])
        else:
            # Table format
            table = Table(title="Members")
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("Email", style="bold")
            table.add_column("Name", style="green")
            table.add_column("Status", style="blue")
            table.add_column("Created", style="dim")
            table.add_column("Labels", style="magenta")

            for member in members:
                created_date = member.created_at.strftime("%Y-%m-%d") if member.created_at else "—"
                labels = ", ".join([label.name for label in member.labels]) if hasattr(member, 'labels') and member.labels else "—"

                table.add_row(
                    member.id[:8],
                    member.email,
                    member.name or "—",
                    member.status or "free",
                    created_date,
                    labels[:30] + "..." if len(labels) > 30 else labels,
                )

            console.print(table)

    except GhostCtlError as e:
        console.print(f"[red]Error listing members: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def get(
    ctx: typer.Context,
    member_id: str = typer.Argument(..., help="Member ID or email"),
    include: Optional[str] = typer.Option("labels", "--include", help="Include related data"),
) -> None:
    """Get a specific member by ID or email.

    Examples:
        # Get member by ID
        ghostctl members get 507f1f77bcf86cd799439011

        # Get member by email
        ghostctl members get user@example.com

        # Get member with subscriptions
        ghostctl members get user@example.com --include "labels,subscriptions"
    """
    client, formatter = get_client_and_formatter(ctx)

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would get member '{member_id}' with includes: {include}[/yellow]")
        return

    try:
        member = client.get_member(member_id, include=include)
        formatter.output({"members": [member]}, format_override=ctx.obj["output_format"])

    except GhostCtlError as e:
        console.print(f"[red]Error getting member: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def create(
    ctx: typer.Context,
    email: str = typer.Option(..., "--email", help="Member email address"),
    name: Optional[str] = typer.Option(None, "--name", help="Member name"),
    note: Optional[str] = typer.Option(None, "--note", help="Internal note about member"),
    subscribed: bool = typer.Option(True, "--subscribed", help="Email subscription status"),
    comped: bool = typer.Option(False, "--comped", help="Give complimentary subscription"),
    labels: Optional[List[str]] = typer.Option(None, "--label", help="Label names (can be repeated)"),
) -> None:
    """Create a new member.

    Examples:
        # Create a basic member
        ghostctl members create --email "user@example.com" --name "John Doe"

        # Create with labels
        ghostctl members create --email "vip@example.com" --name "VIP User" --label "VIP" --label "Priority"

        # Create complimentary member
        ghostctl members create --email "comp@example.com" --comped

        # Create unsubscribed member
        ghostctl members create --email "user@example.com" --unsubscribed
    """
    client, formatter = get_client_and_formatter(ctx)

    if ctx.obj["dry_run"]:
        console.print("[yellow]DRY RUN: Would create member with:[/yellow]")
        console.print(f"  Email: {email}")
        console.print(f"  Name: {name or 'none'}")
        console.print(f"  Subscribed: {subscribed}")
        console.print(f"  Comped: {comped}")
        console.print(f"  Labels: {labels or 'none'}")
        return

    try:
        member_data = {
            "email": email,
            "subscribed": subscribed,
            "comped": comped,
        }

        # Add optional fields
        if name:
            member_data["name"] = name
        if note:
            member_data["note"] = note

        # Handle labels
        if labels:
            member_data["labels"] = [{"name": label} for label in labels]

        member = client.create_member(member_data)
        console.print(f"[green]Member created successfully![/green]")
        formatter.output({"members": [member]}, format_override=ctx.obj["output_format"])

    except GhostCtlError as e:
        console.print(f"[red]Error creating member: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def update(
    ctx: typer.Context,
    member_id: str = typer.Argument(..., help="Member ID or email"),
    name: Optional[str] = typer.Option(None, "--name", help="Member name"),
    note: Optional[str] = typer.Option(None, "--note", help="Internal note about member"),
    subscribed: Optional[bool] = typer.Option(None, "--subscribed", help="Email subscription status"),
    comped: Optional[bool] = typer.Option(None, "--comped", help="Complimentary subscription status"),
    labels: Optional[List[str]] = typer.Option(None, "--label", help="Label names (replaces existing labels)"),
    add_labels: Optional[List[str]] = typer.Option(None, "--add-label", help="Add labels (keeps existing labels)"),
    remove_labels: Optional[List[str]] = typer.Option(None, "--remove-label", help="Remove labels"),
) -> None:
    """Update an existing member.

    Examples:
        # Update name
        ghostctl members update user@example.com --name "Jane Doe"

        # Add labels
        ghostctl members update user@example.com --add-label "Premium" --add-label "Newsletter"

        # Remove labels
        ghostctl members update user@example.com --remove-label "Trial"

        # Update subscription status
        ghostctl members update user@example.com --unsubscribed
    """
    client, formatter = get_client_and_formatter(ctx)

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would update member '{member_id}' with:[/yellow]")
        if name:
            console.print(f"  Name: {name}")
        if subscribed is not None:
            console.print(f"  Subscribed: {subscribed}")
        if labels:
            console.print(f"  Labels (replace): {labels}")
        if add_labels:
            console.print(f"  Labels (add): {add_labels}")
        if remove_labels:
            console.print(f"  Labels (remove): {remove_labels}")
        return

    try:
        # Get current member if we need to handle labels
        current_member = None
        if add_labels or remove_labels:
            current_member = client.get_member(member_id, include="labels")

        # Build update data
        update_data = {}

        if name:
            update_data["name"] = name
        if note:
            update_data["note"] = note
        if subscribed is not None:
            update_data["subscribed"] = subscribed
        if comped is not None:
            update_data["comped"] = comped

        # Handle labels
        if labels:
            update_data["labels"] = [{"name": label} for label in labels]
        elif add_labels or remove_labels:
            if not current_member:
                console.print("[red]Could not fetch current member to modify labels[/red]")
                raise typer.Exit(1)

            current_label_names = {label.name for label in current_member.labels} if hasattr(current_member, 'labels') and current_member.labels else set()

            if add_labels:
                current_label_names.update(add_labels)
            if remove_labels:
                current_label_names -= set(remove_labels)

            update_data["labels"] = [{"name": label} for label in current_label_names]

        if not update_data:
            console.print("[yellow]No updates specified[/yellow]")
            return

        member = client.update_member(member_id, update_data)
        console.print(f"[green]Member updated successfully![/green]")
        formatter.output({"members": [member]}, format_override=ctx.obj["output_format"])

    except GhostCtlError as e:
        console.print(f"[red]Error updating member: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def delete(
    ctx: typer.Context,
    member_id: str = typer.Argument(..., help="Member ID or email"),
    force: bool = typer.Option(False, "--force", help="Delete without confirmation"),
) -> None:
    """Delete a member.

    Examples:
        # Delete with confirmation
        ghostctl members delete user@example.com

        # Force delete without confirmation
        ghostctl members delete member-id --force
    """
    client, formatter = get_client_and_formatter(ctx)

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would delete member '{member_id}'[/yellow]")
        return

    try:
        # Get member details for confirmation
        if not force:
            member = client.get_member(member_id)
            console.print(f"[yellow]About to delete member:[/yellow]")
            console.print(f"  ID: {member.id}")
            console.print(f"  Email: {member.email}")
            console.print(f"  Name: {member.name or 'No name'}")
            console.print(f"  Status: {member.status or 'free'}")

            confirm = typer.confirm("Are you sure you want to delete this member?")
            if not confirm:
                console.print("[yellow]Delete cancelled[/yellow]")
                return

        client.delete_member(member_id)
        console.print(f"[green]Member deleted successfully![/green]")

    except GhostCtlError as e:
        console.print(f"[red]Error deleting member: {e}[/red]")
        raise typer.Exit(1)


@app.command("import")
def import_members(
    ctx: typer.Context,
    csv_file: Path = typer.Argument(..., help="CSV file containing member data"),
    mapping: Optional[str] = typer.Option(None, "--mapping", help="Column mapping (email:Email,name:Name,labels:Labels)"),
    batch_size: int = typer.Option(100, "--batch-size", help="Number of members to import per batch"),
    skip_duplicates: bool = typer.Option(True, "--skip-duplicates", help="Skip or update existing members"),
    default_subscribed: bool = typer.Option(True, "--default-subscribed", help="Default subscription status"),
) -> None:
    """Import members from a CSV file.

    The CSV file should have columns for email (required), name, and labels.
    Labels should be comma-separated within the cell.

    Examples:
        # Import with default settings
        ghostctl members import members.csv

        # Custom column mapping
        ghostctl members import data.csv --mapping "email:EmailAddress,name:FullName,labels:Tags"

        # Import with smaller batches
        ghostctl members import large-file.csv --batch-size 50

        # Update existing members instead of skipping
        ghostctl members import members.csv --update-duplicates

        # Dry run to test import
        ghostctl members import members.csv --dry-run
    """
    client, formatter = get_client_and_formatter(ctx)

    if not csv_file.exists():
        console.print(f"[red]CSV file not found: {csv_file}[/red]")
        raise typer.Exit(1)

    # Parse column mapping
    column_mapping = {"email": "email", "name": "name", "labels": "labels"}
    if mapping:
        try:
            for pair in mapping.split(","):
                dest, source = pair.split(":")
                column_mapping[dest.strip()] = source.strip()
        except ValueError:
            console.print("[red]Invalid mapping format. Use: email:Email,name:Name,labels:Labels[/red]")
            raise typer.Exit(1)

    try:
        # Read and validate CSV
        members_data = []
        with open(csv_file, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)

            # Check required columns
            if column_mapping["email"] not in reader.fieldnames:
                console.print(f"[red]Required column '{column_mapping['email']}' not found in CSV[/red]")
                console.print(f"Available columns: {', '.join(reader.fieldnames)}")
                raise typer.Exit(1)

            for row_num, row in enumerate(reader, start=2):  # Start at 2 for header
                email = row.get(column_mapping["email"], "").strip()
                if not email:
                    console.print(f"[yellow]Skipping row {row_num}: No email address[/yellow]")
                    continue

                member_data = {
                    "email": email,
                    "subscribed": default_subscribed,
                }

                # Add name if available
                if column_mapping["name"] in row and row[column_mapping["name"]].strip():
                    member_data["name"] = row[column_mapping["name"]].strip()

                # Add labels if available
                if column_mapping["labels"] in row and row[column_mapping["labels"]].strip():
                    labels = [label.strip() for label in row[column_mapping["labels"]].split(",") if label.strip()]
                    if labels:
                        member_data["labels"] = [{"name": label} for label in labels]

                members_data.append(member_data)

        if not members_data:
            console.print("[yellow]No valid member data found in CSV file[/yellow]")
            return

        console.print(f"[blue]Found {len(members_data)} members to import[/blue]")

        if ctx.obj["dry_run"]:
            console.print("[yellow]DRY RUN: Would import the following members:[/yellow]")
            for i, member in enumerate(members_data[:5]):  # Show first 5
                labels = [label["name"] for label in member.get("labels", [])]
                console.print(f"  {member['email']} ({member.get('name', 'No name')}) - Labels: {', '.join(labels) or 'None'}")
            if len(members_data) > 5:
                console.print(f"  ... and {len(members_data) - 5} more")
            return

        # Import members in batches
        imported_count = 0
        skipped_count = 0
        error_count = 0
        errors = []

        with Progress(console=console) as progress:
            import_task = progress.add_task("Importing members...", total=len(members_data))

            for i in range(0, len(members_data), batch_size):
                batch = members_data[i:i + batch_size]

                for member_data in batch:
                    try:
                        # Check if member exists
                        existing_member = None
                        try:
                            existing_member = client.get_member(member_data["email"])
                        except GhostCtlError:
                            pass  # Member doesn't exist

                        if existing_member:
                            if skip_duplicates:
                                skipped_count += 1
                                progress.console.print(f"  → Skipped: {member_data['email']} (already exists)")
                            else:
                                # Update existing member
                                client.update_member(existing_member.id, member_data)
                                imported_count += 1
                                progress.console.print(f"  ✓ Updated: {member_data['email']}")
                        else:
                            # Create new member
                            client.create_member(member_data)
                            imported_count += 1
                            progress.console.print(f"  ✓ Created: {member_data['email']}")

                    except GhostCtlError as e:
                        error_count += 1
                        error_msg = f"{member_data['email']}: {str(e)}"
                        errors.append(error_msg)
                        progress.console.print(f"  ✗ Error: {error_msg}")

                    progress.advance(import_task)

        # Summary
        console.print(f"\n[bold]Import Summary:[/bold]")
        console.print(f"  Total processed: {len(members_data)}")
        console.print(f"  Successfully imported: {imported_count}")
        console.print(f"  Skipped (duplicates): {skipped_count}")
        console.print(f"  Errors: {error_count}")

        if ctx.obj["output_format"] in ["json", "yaml"]:
            formatter.output({
                "summary": {
                    "total": len(members_data),
                    "imported": imported_count,
                    "skipped": skipped_count,
                    "errors": error_count,
                },
                "errors": errors,
            }, format_override=ctx.obj["output_format"])

        if error_count > 0:
            console.print("\n[red]Errors occurred during import:[/red]")
            for error in errors[:10]:  # Show first 10 errors
                console.print(f"  {error}")
            if len(errors) > 10:
                console.print(f"  ... and {len(errors) - 10} more errors")

    except Exception as e:
        console.print(f"[red]Error importing members: {e}[/red]")
        raise typer.Exit(1)


@app.command("export")
def export_members(
    ctx: typer.Context,
    output_file: Path = typer.Argument(..., help="Output CSV file path"),
    filter: Optional[str] = typer.Option(None, "--filter", help="Filter members to export"),
    include_labels: bool = typer.Option(True, "--include-labels", help="Include member labels"),
    limit: Optional[int] = typer.Option(None, "--limit", help="Maximum number of members to export"),
) -> None:
    """Export members to a CSV file.

    Examples:
        # Export all members
        ghostctl members export members.csv

        # Export only paid members
        ghostctl members export paid-members.csv --filter "status:paid"

        # Export without labels
        ghostctl members export simple-members.csv --no-labels

        # Export first 1000 members
        ghostctl members export recent-members.csv --limit 1000
    """
    client, formatter = get_client_and_formatter(ctx)

    if ctx.obj["dry_run"]:
        console.print(f"[yellow]DRY RUN: Would export members to '{output_file}' with:[/yellow]")
        console.print(f"  Filter: {filter or 'none'}")
        console.print(f"  Include labels: {include_labels}")
        console.print(f"  Limit: {limit or 'no limit'}")
        return

    try:
        # Fetch all members
        all_members = []
        page = 1
        members_per_page = 100

        with Progress(console=console) as progress:
            fetch_task = progress.add_task("Fetching members...", total=None)

            while True:
                members = client.get_members(
                    filter=filter,
                    page=page,
                    limit=members_per_page,
                    include="labels" if include_labels else None,
                    order="created_at ASC",
                )

                if not members:
                    break

                all_members.extend(members)
                progress.console.print(f"  Fetched page {page} ({len(members)} members)")

                if limit and len(all_members) >= limit:
                    all_members = all_members[:limit]
                    break

                if len(members) < members_per_page:
                    break

                page += 1

        if not all_members:
            console.print("[yellow]No members found to export[/yellow]")
            return

        console.print(f"[blue]Exporting {len(all_members)} members to CSV...[/blue]")

        # Write CSV file
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['email', 'name', 'status', 'subscribed', 'created_at']
            if include_labels:
                fieldnames.append('labels')

            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for member in all_members:
                row = {
                    'email': member.email,
                    'name': member.name or '',
                    'status': member.status or 'free',
                    'subscribed': str(member.subscribed).lower(),
                    'created_at': member.created_at.isoformat() if member.created_at else '',
                }

                if include_labels:
                    labels = []
                    if hasattr(member, 'labels') and member.labels:
                        labels = [label.name for label in member.labels]
                    row['labels'] = ', '.join(labels)

                writer.writerow(row)

        console.print(f"[green]Successfully exported {len(all_members)} members to '{output_file}'![/green]")

        if ctx.obj["output_format"] in ["json", "yaml"]:
            formatter.output({
                "output_file": str(output_file),
                "exported_count": len(all_members),
                "file_size": output_file.stat().st_size,
            }, format_override=ctx.obj["output_format"])

    except GhostCtlError as e:
        console.print(f"[red]Error exporting members: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()