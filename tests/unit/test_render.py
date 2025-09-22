"""Unit tests for render.py module.

Tests the OutputFormatter class for output rendering
including table, JSON, YAML formatting, field configuration, and file output.
"""

import sys
import json
import yaml
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from io import StringIO

from rich.console import Console
from rich.table import Table

from ghostctl.render import OutputFormatter, render_table, render_json, render_yaml
from ghostctl.exceptions import ValidationError


class TestOutputFormatter:
    """Test cases for the OutputFormatter class."""

    @pytest.fixture
    def formatter(self):
        """Create an OutputFormatter instance."""
        return OutputFormatter()

    @pytest.fixture
    def sample_data(self):
        """Sample data for testing."""
        return [
            {
                "id": "1",
                "title": "First Post",
                "status": "published",
                "author": "John Doe",
                "created_at": "2023-01-01T00:00:00Z",
                "featured": True,
            },
            {
                "id": "2",
                "title": "Second Post",
                "status": "draft",
                "author": "Jane Smith",
                "created_at": "2023-01-02T00:00:00Z",
                "featured": False,
            },
        ]

    def test_formatter_initialization_default(self):
        """Test OutputFormatter initialization with default console."""
        formatter = OutputFormatter()
        assert formatter.console is not None
        assert isinstance(formatter.console, Console)

    def test_formatter_initialization_custom_console(self):
        """Test OutputFormatter initialization with custom console."""
        custom_console = Console()
        formatter = OutputFormatter(console=custom_console)
        assert formatter.console is custom_console

    def test_determine_format_explicit_override(self, formatter):
        """Test format determination with explicit override."""
        assert formatter.determine_format("json") == "json"
        assert formatter.determine_format("YAML") == "yaml"
        assert formatter.determine_format("Table") == "table"

    @patch("sys.argv", ["ghostctl", "posts", "list", "--format", "yaml"])
    def test_determine_format_command_line(self, formatter):
        """Test format determination from command line arguments."""
        assert formatter.determine_format() == "yaml"

    @patch("sys.argv", ["ghostctl", "posts", "list"])
    @patch.dict("os.environ", {"GHOSTCTL_OUTPUT_FORMAT": "json"})
    def test_determine_format_environment(self, formatter):
        """Test format determination from environment variable."""
        assert formatter.determine_format() == "json"

    @patch("sys.argv", ["ghostctl", "posts", "list"])
    @patch.dict("os.environ", {}, clear=True)
    def test_determine_format_auto_detect_tty(self, formatter):
        """Test format auto-detection for TTY."""
        with patch("sys.stdout.isatty", return_value=True):
            assert formatter.determine_format() == "table"

    @patch("sys.argv", ["ghostctl", "posts", "list"])
    @patch.dict("os.environ", {}, clear=True)
    def test_determine_format_auto_detect_non_tty(self, formatter):
        """Test format auto-detection for non-TTY."""
        with patch("sys.stdout.isatty", return_value=False):
            assert formatter.determine_format() == "json"

    def test_render_table_format(self, formatter, sample_data):
        """Test rendering with table format."""
        with patch.object(formatter, "render_table") as mock_render:
            formatter.render(sample_data, format="table")
            mock_render.assert_called_once_with(sample_data)

    def test_render_json_format(self, formatter, sample_data):
        """Test rendering with JSON format."""
        with patch.object(formatter, "render_json") as mock_render:
            formatter.render(sample_data, format="json")
            mock_render.assert_called_once_with(sample_data)

    def test_render_yaml_format(self, formatter, sample_data):
        """Test rendering with YAML format."""
        with patch.object(formatter, "render_yaml") as mock_render:
            formatter.render(sample_data, format="yaml")
            mock_render.assert_called_once_with(sample_data)

    def test_render_unknown_format(self, formatter, sample_data):
        """Test rendering with unknown format."""
        with pytest.raises(ValidationError, match="Unknown output format: unknown"):
            formatter.render(sample_data, format="unknown")

    def test_render_custom_format(self, formatter, sample_data):
        """Test rendering with custom format."""
        custom_formatter = Mock()
        formatter.register_format("custom", custom_formatter)

        formatter.render(sample_data, format="custom", extra_arg="test")
        custom_formatter.assert_called_once_with(sample_data, extra_arg="test")

    def test_render_table_empty_data(self, formatter, capsys):
        """Test rendering table with empty data."""
        formatter.render_table([])

        captured = capsys.readouterr()
        assert "No data to display" in captured.out

    def test_render_table_dict_data(self, formatter):
        """Test rendering table with dictionary data."""
        data = {"posts": [{"id": "1", "title": "Test"}]}

        with patch.object(formatter, "_render_table_data") as mock_render:
            formatter.render_table(data)
            mock_render.assert_called_once()
            # Should extract posts from dictionary
            call_args = mock_render.call_args[0][0]
            assert len(call_args) == 1
            assert call_args[0]["id"] == "1"

    def test_render_table_single_dict(self, formatter):
        """Test rendering table with single dictionary."""
        data = {"id": "1", "title": "Single Post"}

        with patch.object(formatter, "_render_table_data") as mock_render:
            formatter.render_table(data)
            mock_render.assert_called_once()
            # Should wrap single dict in list
            call_args = mock_render.call_args[0][0]
            assert len(call_args) == 1
            assert call_args[0]["id"] == "1"

    def test_render_table_with_sorting(self, formatter, sample_data):
        """Test rendering table with sorting."""
        with patch.object(formatter, "_sort_data", return_value=sample_data) as mock_sort:
            with patch.object(formatter, "_render_table_data"):
                formatter.render_table(
                    sample_data,
                    sort_by=[("title", "asc"), ("created_at", "desc")]
                )

        mock_sort.assert_called_once_with(sample_data, [("title", "asc"), ("created_at", "desc")])

    def test_render_table_with_grouping(self, formatter, sample_data, capsys):
        """Test rendering table with grouping."""
        with patch.object(formatter, "_group_data", return_value={"published": [sample_data[0]], "draft": [sample_data[1]]}):
            with patch.object(formatter, "_render_table_data"):
                formatter.render_table(
                    sample_data,
                    group_by="status",
                    show_group_headers=True
                )

        captured = capsys.readouterr()
        assert "STATUS: published" in captured.out
        assert "STATUS: draft" in captured.out

    def test_render_table_with_pagination(self, formatter, sample_data):
        """Test rendering table with pagination."""
        with patch.object(formatter, "_render_paginated_table") as mock_paginated:
            formatter.render_table(sample_data, page_size=1)
            mock_paginated.assert_called_once()

    def test_render_json_empty_data(self, formatter, capsys):
        """Test rendering JSON with empty data."""
        formatter.render_json([])

        captured = capsys.readouterr()
        assert captured.out.strip() == "[]"

    def test_render_json_simple_data(self, formatter, sample_data, capsys):
        """Test rendering JSON with simple data."""
        formatter.render_json(sample_data)

        captured = capsys.readouterr()
        output_data = json.loads(captured.out)
        assert len(output_data) == 2
        assert output_data[0]["title"] == "First Post"

    def test_render_json_not_pretty(self, formatter, sample_data, capsys):
        """Test rendering JSON without pretty formatting."""
        formatter.render_json(sample_data, pretty=False)

        captured = capsys.readouterr()
        # Should not have indentation
        assert "  " not in captured.out

    def test_render_json_with_field_filtering(self, formatter, sample_data, capsys):
        """Test rendering JSON with field filtering."""
        formatter.render_json(sample_data, fields=["id", "title"])

        captured = capsys.readouterr()
        output_data = json.loads(captured.out)
        assert list(output_data[0].keys()) == ["id", "title"]

    def test_render_json_streaming_large_dataset(self, formatter, capsys):
        """Test rendering JSON with streaming for large dataset."""
        large_data = [{"id": str(i), "value": f"item_{i}"} for i in range(150)]

        formatter.render_json(large_data, streaming=True)

        captured = capsys.readouterr()
        # Should contain streaming format indicators
        assert captured.out.startswith("[")
        assert captured.out.endswith("\n]")

    def test_render_json_skip_invalid(self, formatter, capsys):
        """Test rendering JSON with skip_invalid option."""
        data_with_none = [{"id": "1"}, None, {"id": "2"}]

        formatter.render_json(data_with_none, skip_invalid=True)

        captured = capsys.readouterr()
        output_data = json.loads(captured.out)
        assert len(output_data) == 2
        assert all(item is not None for item in output_data)

    def test_render_json_circular_reference_error(self, formatter):
        """Test rendering JSON with circular reference."""
        with patch("json.dumps", side_effect=ValueError("circular reference detected")):
            with pytest.raises(ValidationError, match="Circular reference detected"):
                formatter.render_json({"data": "test"})

    def test_render_yaml_empty_data(self, formatter, capsys):
        """Test rendering YAML with empty data."""
        formatter.render_yaml([])

        captured = capsys.readouterr()
        assert captured.out.strip() == "[]"

    def test_render_yaml_simple_data(self, formatter, sample_data, capsys):
        """Test rendering YAML with simple data."""
        formatter.render_yaml(sample_data)

        captured = capsys.readouterr()
        output_data = yaml.safe_load(captured.out)
        assert len(output_data) == 2
        assert output_data[0]["title"] == "First Post"

    def test_render_yaml_with_metadata(self, formatter, sample_data, capsys):
        """Test rendering YAML with metadata."""
        with patch.object(formatter, "_get_timestamp", return_value="2023-01-01T00:00:00"):
            formatter.render_yaml(sample_data, include_metadata=True)

        captured = capsys.readouterr()
        assert "# Generated by Ghost CMS CLI" in captured.out
        assert "# Timestamp: 2023-01-01T00:00:00" in captured.out
        assert "---" in captured.out

    def test_render_yaml_with_document_separator(self, formatter, sample_data, capsys):
        """Test rendering YAML with document separators."""
        formatter.render_yaml(sample_data, document_separator=True)

        captured = capsys.readouterr()
        # Should have document separators between items
        assert captured.out.count("---") >= 1

    def test_render_yaml_error(self, formatter):
        """Test rendering YAML with serialization error."""
        with patch("yaml.dump", side_effect=yaml.YAMLError("YAML error")):
            with pytest.raises(ValidationError, match="Failed to serialize data to YAML"):
                formatter.render_yaml({"data": "test"})

    def test_render_to_file_json(self, formatter, sample_data):
        """Test rendering to JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp_file:
            temp_path = tmp_file.name

        try:
            formatter.render_to_file(sample_data, temp_path)

            with open(temp_path, "r") as f:
                file_data = json.load(f)
                assert len(file_data) == 2
                assert file_data[0]["title"] == "First Post"
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_render_to_file_yaml(self, formatter, sample_data):
        """Test rendering to YAML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp_file:
            temp_path = tmp_file.name

        try:
            formatter.render_to_file(sample_data, temp_path)

            with open(temp_path, "r") as f:
                file_data = yaml.safe_load(f)
                assert len(file_data) == 2
                assert file_data[0]["title"] == "First Post"
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_render_to_file_explicit_format(self, formatter, sample_data):
        """Test rendering to file with explicit format."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp_file:
            temp_path = tmp_file.name

        try:
            formatter.render_to_file(sample_data, temp_path, format="json")

            with open(temp_path, "r") as f:
                file_data = json.load(f)
                assert len(file_data) == 2
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_render_to_file_append_mode(self, formatter, sample_data):
        """Test rendering to file in append mode."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp_file:
            temp_path = tmp_file.name
            # Write initial data
            json.dump({"existing": "data"}, tmp_file)

        try:
            formatter.render_to_file(sample_data, temp_path, append=True)

            with open(temp_path, "r") as f:
                content = f.read()
                # Should contain both original and new data
                assert '{"existing": "data"}' in content
                assert '"First Post"' in content
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_register_format(self, formatter):
        """Test registering custom format."""
        custom_formatter = Mock()
        formatter.register_format("custom", custom_formatter)

        assert "custom" in formatter._custom_formatters
        assert formatter._custom_formatters["custom"] is custom_formatter

    def test_render_table_data_empty(self, formatter, capsys):
        """Test _render_table_data with empty data."""
        formatter._render_table_data([])

        # Should not output anything for empty data
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_render_table_data_with_columns(self, formatter, sample_data):
        """Test _render_table_data with specific columns."""
        with patch.object(formatter.console, "print") as mock_print:
            formatter._render_table_data(sample_data, columns=["id", "title"])

        mock_print.assert_called_once()
        table = mock_print.call_args[0][0]
        assert isinstance(table, Table)

    def test_render_table_data_boolean_formatting(self, formatter):
        """Test _render_table_data with boolean values."""
        data = [{"featured": True, "draft": False}]

        with patch.object(formatter.console, "print") as mock_print:
            formatter._render_table_data(data)

        # Check that booleans are converted to checkmarks
        table = mock_print.call_args[0][0]
        assert isinstance(table, Table)

    def test_render_table_data_without_colors(self, formatter, sample_data):
        """Test _render_table_data without colors."""
        with patch.object(formatter, "_strip_ansi", return_value="plain text") as mock_strip:
            with patch("builtins.print") as mock_print:
                formatter._render_table_data(sample_data, colors=False)

        mock_strip.assert_called_once()
        mock_print.assert_called_once_with("plain text")

    def test_render_paginated_table_interactive(self, formatter, sample_data):
        """Test _render_paginated_table in interactive mode."""
        with patch.object(formatter, "_render_table_data"):
            with patch("builtins.input", side_effect=["", "q"]):  # Continue, then quit
                formatter._render_paginated_table(
                    sample_data * 3,  # 6 items
                    page_size=2,
                    interactive=True,
                )

    def test_apply_field_config_include_fields(self, formatter, sample_data):
        """Test _apply_field_config with include fields."""
        config = {"include": ["id", "title"]}
        result = formatter._apply_field_config(sample_data, config)

        assert len(result) == 2
        assert list(result[0].keys()) == ["id", "title"]
        assert result[0]["id"] == "1"
        assert result[0]["title"] == "First Post"

    def test_apply_field_config_exclude_fields(self, formatter, sample_data):
        """Test _apply_field_config with exclude fields."""
        config = {"exclude": ["created_at", "featured"]}
        result = formatter._apply_field_config(sample_data, config)

        assert len(result) == 2
        assert "created_at" not in result[0]
        assert "featured" not in result[0]
        assert "id" in result[0]

    def test_apply_field_config_aliases(self, formatter, sample_data):
        """Test _apply_field_config with field aliases."""
        config = {"aliases": {"id": "post_id", "title": "post_title"}}
        result = formatter._apply_field_config(sample_data, config)

        assert "post_id" in result[0]
        assert "post_title" in result[0]
        assert "id" not in result[0]
        assert "title" not in result[0]

    def test_apply_field_config_computed_fields(self, formatter, sample_data):
        """Test _apply_field_config with computed fields."""
        config = {
            "computed": {
                "display_name": lambda item: f"{item['title']} ({item['status']})",
                "author_caps": lambda item: item['author'].upper(),
            }
        }
        result = formatter._apply_field_config(sample_data, config)

        assert result[0]["display_name"] == "First Post (published)"
        assert result[0]["author_caps"] == "JOHN DOE"

    def test_apply_field_config_computed_fields_error(self, formatter, sample_data):
        """Test _apply_field_config with computed fields that error."""
        config = {
            "computed": {
                "error_field": lambda item: item["nonexistent_key"],
            }
        }
        result = formatter._apply_field_config(sample_data, config)

        assert result[0]["error_field"] is None

    def test_apply_field_config_nested_fields(self, formatter):
        """Test _apply_field_config with nested field access."""
        data = [{"user": {"profile": {"name": "John"}}, "id": "1"}]
        config = {"include": ["id", "user.profile.name"]}

        result = formatter._apply_field_config(data, config)

        assert result[0]["id"] == "1"
        assert result[0]["user.profile.name"] == "John"

    def test_filter_fields_simple(self, formatter, sample_data):
        """Test _filter_fields with simple field list."""
        result = formatter._filter_fields(sample_data, ["id", "title"], None)

        assert len(result) == 2
        assert list(result[0].keys()) == ["id", "title"]

    def test_sort_data(self, formatter, sample_data):
        """Test _sort_data functionality."""
        # Sort by title ascending
        result = formatter._sort_data(sample_data, [("title", "asc")])
        assert result[0]["title"] == "First Post"
        assert result[1]["title"] == "Second Post"

        # Sort by title descending
        result = formatter._sort_data(sample_data, [("title", "desc")])
        assert result[0]["title"] == "Second Post"
        assert result[1]["title"] == "First Post"

    def test_group_data(self, formatter, sample_data):
        """Test _group_data functionality."""
        result = formatter._group_data(sample_data, "status")

        assert "published" in result
        assert "draft" in result
        assert len(result["published"]) == 1
        assert len(result["draft"]) == 1
        assert result["published"][0]["title"] == "First Post"

    def test_get_nested_value(self, formatter):
        """Test _get_nested_value functionality."""
        data = {
            "user": {
                "profile": {
                    "name": "John",
                    "settings": {"theme": "dark"}
                }
            }
        }

        assert formatter._get_nested_value(data, "user.profile.name") == "John"
        assert formatter._get_nested_value(data, "user.profile.settings.theme") == "dark"
        assert formatter._get_nested_value(data, "user.nonexistent") is None
        assert formatter._get_nested_value(data, "nonexistent.path") is None

    def test_get_timestamp(self, formatter):
        """Test _get_timestamp functionality."""
        with patch("datetime.datetime") as mock_datetime:
            mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T00:00:00"

            timestamp = formatter._get_timestamp()
            assert timestamp == "2023-01-01T00:00:00"

    def test_strip_ansi(self, formatter):
        """Test _strip_ansi functionality."""
        text_with_ansi = "\x1b[31mRed text\x1b[0m normal text"
        result = formatter._strip_ansi(text_with_ansi)
        assert result == "Red text normal text"


class TestConvenienceFunctions:
    """Test cases for convenience functions."""

    def test_render_table_function(self, sample_data):
        """Test render_table convenience function."""
        with patch.object(OutputFormatter, "render_table") as mock_render:
            render_table(sample_data, title="Test Table")
            mock_render.assert_called_once_with(sample_data, title="Test Table")

    def test_render_json_function(self, sample_data):
        """Test render_json convenience function."""
        with patch.object(OutputFormatter, "render_json") as mock_render:
            render_json(sample_data, pretty=False)
            mock_render.assert_called_once_with(sample_data, pretty=False)

    def test_render_yaml_function(self, sample_data):
        """Test render_yaml convenience function."""
        with patch.object(OutputFormatter, "render_yaml") as mock_render:
            render_yaml(sample_data, include_metadata=True)
            mock_render.assert_called_once_with(sample_data, include_metadata=True)

    @pytest.fixture
    def sample_data(self):
        """Sample data for testing convenience functions."""
        return [
            {"id": "1", "title": "Test Post", "status": "published"},
            {"id": "2", "title": "Draft Post", "status": "draft"},
        ]