"""Output rendering and formatting utilities.

This module provides various output formatters for displaying data
in different formats including tables, JSON, and YAML.
"""

import sys
import json
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable, TextIO
from io import StringIO
import os

from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.style import Style
from rich import box

from .exceptions import ValidationError


class OutputFormatter:
    """Main output formatter that handles multiple output formats."""

    def __init__(self, console: Optional[Console] = None) -> None:
        """Initialize output formatter.

        Args:
            console: Rich console instance. If None, creates a new one.
        """
        self.console = console or Console()
        self._custom_formatters: Dict[str, Callable] = {}

    def determine_format(self, format_override: Optional[str] = None) -> str:
        """Determine the output format to use.

        Args:
            format_override: Explicit format override

        Returns:
            Format name (table, json, yaml)
        """
        # Check explicit override first
        if format_override:
            return format_override.lower()

        # Check command line arguments
        if "--format" in sys.argv:
            try:
                idx = sys.argv.index("--format")
                if idx + 1 < len(sys.argv):
                    return sys.argv[idx + 1].lower()
            except (IndexError, ValueError):
                pass

        # Check environment variable
        env_format = os.environ.get("GHOSTCTL_OUTPUT_FORMAT")
        if env_format:
            return env_format.lower()

        # Auto-detect based on terminal
        if sys.stdout.isatty():
            return "table"  # Interactive terminal
        else:
            return "json"  # Non-interactive (piped output)

    def render(
        self,
        data: Any,
        format: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Render data in the specified format.

        Args:
            data: Data to render
            format: Output format (table, json, yaml)
            **kwargs: Additional formatting options
        """
        format_name = self.determine_format(format)

        if format_name == "table":
            self.render_table(data, **kwargs)
        elif format_name == "json":
            self.render_json(data, **kwargs)
        elif format_name == "yaml":
            self.render_yaml(data, **kwargs)
        elif format_name in self._custom_formatters:
            self._custom_formatters[format_name](data, **kwargs)
        else:
            raise ValidationError(f"Unknown output format: {format_name}")

    def render_table(
        self,
        data: Union[List[Dict[str, Any]], Dict[str, Any]],
        columns: Optional[List[str]] = None,
        title: Optional[str] = None,
        show_header: bool = True,
        show_lines: bool = False,
        max_width: Optional[int] = None,
        theme: str = "default",
        colors: bool = True,
        sort_by: Optional[List[tuple[str, str]]] = None,
        group_by: Optional[str] = None,
        show_group_headers: bool = False,
        page_size: Optional[int] = None,
        interactive: bool = False,
        field_config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Render data as a table using Rich.

        Args:
            data: Data to render
            columns: Column names to display
            title: Table title
            show_header: Whether to show column headers
            show_lines: Whether to show row separators
            max_width: Maximum table width
            theme: Color theme
            colors: Whether to use colors
            sort_by: List of (field, direction) tuples for sorting
            group_by: Field to group by
            show_group_headers: Whether to show group headers
            page_size: Number of rows per page for pagination
            interactive: Whether to enable interactive pagination
            field_config: Field configuration for filtering/aliasing
            **kwargs: Additional arguments
        """
        if not data:
            self.console.print("[dim]No data to display[/dim]")
            return

        # Ensure data is a list
        if isinstance(data, dict):
            if "posts" in data:
                data = data["posts"]
            elif "tags" in data:
                data = data["tags"]
            elif "users" in data:
                data = data["users"]
            else:
                data = [data]

        # Apply field configuration
        if field_config:
            data = self._apply_field_config(data, field_config)

        # Apply sorting
        if sort_by:
            data = self._sort_data(data, sort_by)

        # Apply grouping
        if group_by:
            grouped_data = self._group_data(data, group_by)
            for group_value, group_items in grouped_data.items():
                if show_group_headers:
                    self.console.print(f"\n[bold]{group_by.upper()}: {group_value}[/bold]")
                self._render_table_data(
                    group_items,
                    columns=columns,
                    title=None,
                    show_header=show_header,
                    show_lines=show_lines,
                    max_width=max_width,
                    theme=theme,
                    colors=colors,
                )
        else:
            # Handle pagination
            if page_size and len(data) > page_size:
                self._render_paginated_table(
                    data,
                    page_size=page_size,
                    interactive=interactive,
                    columns=columns,
                    title=title,
                    show_header=show_header,
                    show_lines=show_lines,
                    max_width=max_width,
                    theme=theme,
                    colors=colors,
                )
            else:
                self._render_table_data(
                    data,
                    columns=columns,
                    title=title,
                    show_header=show_header,
                    show_lines=show_lines,
                    max_width=max_width,
                    theme=theme,
                    colors=colors,
                )

    def render_json(
        self,
        data: Any,
        fields: Optional[List[str]] = None,
        pretty: bool = True,
        indent: int = 2,
        streaming: bool = False,
        skip_invalid: bool = False,
        field_config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Render data as JSON.

        Args:
            data: Data to render
            fields: Fields to include
            pretty: Whether to format JSON nicely
            indent: Indentation level for pretty printing
            streaming: Whether to use streaming output for large datasets
            skip_invalid: Whether to skip invalid entries
            field_config: Field configuration for filtering/aliasing
            **kwargs: Additional arguments
        """
        if not data:
            print("[]")
            return

        # Apply field filtering
        if fields or field_config:
            data = self._filter_fields(data, fields, field_config)

        # Handle invalid data
        if skip_invalid and isinstance(data, list):
            data = [item for item in data if item is not None]

        try:
            if streaming and isinstance(data, list) and len(data) > 100:
                # Stream large datasets
                print("[")
                for i, item in enumerate(data):
                    if i > 0:
                        print(",")
                    print(json.dumps(item, indent=indent if pretty else None, default=str), end="")
                print("\n]")
            else:
                # Standard JSON output
                output = json.dumps(
                    data,
                    indent=indent if pretty else None,
                    ensure_ascii=False,
                    default=str,
                )
                print(output)

        except (TypeError, ValueError) as e:
            if "circular reference" in str(e).lower():
                raise ValidationError("Circular reference detected in data structure")
            raise ValidationError(f"Failed to serialize data to JSON: {e}")

    def render_yaml(
        self,
        data: Any,
        include_metadata: bool = False,
        document_separator: bool = False,
        field_config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Render data as YAML.

        Args:
            data: Data to render
            include_metadata: Whether to include metadata comments
            document_separator: Whether to use document separators
            field_config: Field configuration for filtering/aliasing
            **kwargs: Additional arguments
        """
        if not data:
            print("[]")
            return

        # Apply field configuration
        if field_config:
            data = self._apply_field_config(data, field_config)

        try:
            if include_metadata:
                print("# Generated by Ghost CMS CLI")
                print(f"# Timestamp: {self._get_timestamp()}")
                print("---")

            if document_separator and isinstance(data, list):
                for i, item in enumerate(data):
                    if i > 0:
                        print("---")
                    print(yaml.dump(item, default_flow_style=False, allow_unicode=True))
            else:
                print(yaml.dump(data, default_flow_style=False, allow_unicode=True))

        except yaml.YAMLError as e:
            raise ValidationError(f"Failed to serialize data to YAML: {e}")

    def render_to_file(
        self,
        data: Any,
        file_path: Union[str, Path],
        format: Optional[str] = None,
        append: bool = False,
        **kwargs: Any,
    ) -> None:
        """Render data to a file.

        Args:
            data: Data to render
            file_path: Path to output file
            format: Output format (auto-detected from file extension if not provided)
            append: Whether to append to existing file
            **kwargs: Additional formatting options
        """
        file_path = Path(file_path)

        # Auto-detect format from file extension
        if not format:
            ext = file_path.suffix.lower()
            if ext == ".json":
                format = "json"
            elif ext in [".yaml", ".yml"]:
                format = "yaml"
            else:
                format = "json"  # Default

        # Capture output
        original_stdout = sys.stdout
        try:
            output_buffer = StringIO()
            sys.stdout = output_buffer

            # Render to buffer
            self.render(data, format=format, **kwargs)

            # Write to file
            mode = "a" if append else "w"
            with open(file_path, mode, encoding="utf-8") as f:
                f.write(output_buffer.getvalue())

        finally:
            sys.stdout = original_stdout

    def register_format(self, name: str, formatter: Callable) -> None:
        """Register a custom output format.

        Args:
            name: Format name
            formatter: Formatter function
        """
        self._custom_formatters[name] = formatter

    def _render_table_data(
        self,
        data: List[Dict[str, Any]],
        columns: Optional[List[str]] = None,
        title: Optional[str] = None,
        show_header: bool = True,
        show_lines: bool = False,
        max_width: Optional[int] = None,
        theme: str = "default",
        colors: bool = True,
    ) -> None:
        """Render table data using Rich."""
        if not data:
            return

        # Determine columns
        if not columns:
            # Get all unique keys from all items
            all_keys = set()
            for item in data:
                all_keys.update(item.keys())
            columns = sorted(all_keys)

        # Create table
        table = Table(
            title=title,
            show_header=show_header,
            show_lines=show_lines,
            box=box.SIMPLE if theme == "simple" else box.ROUNDED,
            width=max_width,
        )

        # Add columns
        for col in columns:
            table.add_column(col.replace("_", " ").title(), overflow="fold")

        # Add rows
        for item in data:
            row = []
            for col in columns:
                value = item.get(col, "")
                if value is None:
                    value = ""
                elif isinstance(value, (list, dict)):
                    value = str(value)
                elif isinstance(value, bool):
                    value = "✓" if value else "✗"
                row.append(str(value))
            table.add_row(*row)

        # Render table
        if colors:
            self.console.print(table)
        else:
            with self.console.capture() as capture:
                self.console.print(table)
            # Strip ANSI codes for non-color output
            plain_output = self._strip_ansi(capture.get())
            print(plain_output)

    def _render_paginated_table(
        self,
        data: List[Dict[str, Any]],
        page_size: int,
        interactive: bool,
        **table_kwargs: Any,
    ) -> None:
        """Render paginated table."""
        total_pages = (len(data) + page_size - 1) // page_size
        current_page = 1

        while current_page <= total_pages:
            start_idx = (current_page - 1) * page_size
            end_idx = start_idx + page_size
            page_data = data[start_idx:end_idx]

            # Update title to include page info
            original_title = table_kwargs.get("title", "")
            table_kwargs["title"] = f"{original_title} (Page {current_page} of {total_pages})"

            self._render_table_data(page_data, **table_kwargs)

            if interactive and current_page < total_pages:
                user_input = input("\nPress Enter for next page, 'q' to quit: ").strip().lower()
                if user_input == "q":
                    break

            current_page += 1

    def _apply_field_config(self, data: Any, config: Dict[str, Any]) -> Any:
        """Apply field configuration (filtering, aliasing, computed fields)."""
        if not isinstance(data, list):
            data = [data]

        result = []
        for item in data:
            if not isinstance(item, dict):
                continue

            new_item = {}

            # Apply include/exclude filters
            include_fields = config.get("include")
            exclude_fields = config.get("exclude", [])

            if include_fields:
                for field in include_fields:
                    if "." in field:  # Nested field access
                        value = self._get_nested_value(item, field)
                    else:
                        value = item.get(field)
                    new_item[field] = value
            else:
                new_item = item.copy()

            # Remove excluded fields
            for field in exclude_fields:
                new_item.pop(field, None)

            # Apply aliases
            aliases = config.get("aliases", {})
            for old_name, new_name in aliases.items():
                if old_name in new_item:
                    new_item[new_name] = new_item.pop(old_name)

            # Add computed fields
            computed_fields = config.get("computed", {})
            for field_name, computation in computed_fields.items():
                try:
                    new_item[field_name] = computation(item)
                except Exception:
                    new_item[field_name] = None

            result.append(new_item)

        return result

    def _filter_fields(
        self,
        data: Any,
        fields: Optional[List[str]],
        field_config: Optional[Dict[str, Any]],
    ) -> Any:
        """Filter fields from data."""
        if field_config:
            return self._apply_field_config(data, field_config)

        if not fields:
            return data

        if not isinstance(data, list):
            data = [data]

        result = []
        for item in data:
            if isinstance(item, dict):
                filtered_item = {field: item.get(field) for field in fields if field in item}
                result.append(filtered_item)
            else:
                result.append(item)

        return result

    def _sort_data(self, data: List[Dict[str, Any]], sort_by: List[tuple[str, str]]) -> List[Dict[str, Any]]:
        """Sort data by specified fields."""
        def sort_key(item: Dict[str, Any]) -> tuple:
            key_values = []
            for field, direction in sort_by:
                value = item.get(field, "")
                if direction.lower() == "desc":
                    # For descending, negate numeric values or reverse strings
                    if isinstance(value, (int, float)):
                        value = -value
                    elif isinstance(value, str):
                        value = value[::-1]  # Reverse string for sorting
                key_values.append(value)
            return tuple(key_values)

        return sorted(data, key=sort_key)

    def _group_data(self, data: List[Dict[str, Any]], group_by: str) -> Dict[str, List[Dict[str, Any]]]:
        """Group data by a field."""
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for item in data:
            group_value = str(item.get(group_by, "Unknown"))
            if group_value not in groups:
                groups[group_value] = []
            groups[group_value].append(item)
        return groups

    def _get_nested_value(self, obj: Dict[str, Any], path: str) -> Any:
        """Get nested value from object using dot notation."""
        parts = path.split(".")
        current = obj
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()

    def _strip_ansi(self, text: str) -> str:
        """Strip ANSI escape sequences from text."""
        import re
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_escape.sub("", text)


# Convenience functions
def render_table(data: Any, **kwargs: Any) -> None:
    """Render data as a table."""
    formatter = OutputFormatter()
    formatter.render_table(data, **kwargs)


def render_json(data: Any, **kwargs: Any) -> None:
    """Render data as JSON."""
    formatter = OutputFormatter()
    formatter.render_json(data, **kwargs)


def render_yaml(data: Any, **kwargs: Any) -> None:
    """Render data as YAML."""
    formatter = OutputFormatter()
    formatter.render_yaml(data, **kwargs)


# Aliases for compatibility with test files
TableRenderer = OutputFormatter
JSONRenderer = OutputFormatter
YAMLRenderer = OutputFormatter