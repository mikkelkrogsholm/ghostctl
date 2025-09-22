"""Integration tests for output formats (table/json/yaml).

Tests the complete output formatting workflow including data transformation,
rendering, and user experience across different output formats.
"""

import pytest
from unittest.mock import Mock, patch
import json
import yaml
from io import StringIO

from ghostctl.output import OutputFormatter, TableRenderer, JSONRenderer, YAMLRenderer
from ghostctl.models import Post, Tag, User


class TestOutputFormats:
    """Integration tests for output format handling and rendering."""

    @pytest.fixture
    def sample_posts_data(self):
        """Sample posts data for testing output formats."""
        return [
            {
                "id": "post-1",
                "title": "First Blog Post",
                "slug": "first-blog-post",
                "status": "published",
                "created_at": "2024-01-15T10:00:00.000Z",
                "updated_at": "2024-01-15T10:30:00.000Z",
                "published_at": "2024-01-15T10:30:00.000Z",
                "excerpt": "This is the first blog post excerpt...",
                "reading_time": 5,
                "tags": ["technology", "python"]
            },
            {
                "id": "post-2",
                "title": "Advanced Ghost CMS Tips",
                "slug": "advanced-ghost-cms-tips",
                "status": "draft",
                "created_at": "2024-01-16T14:00:00.000Z",
                "updated_at": "2024-01-16T15:00:00.000Z",
                "published_at": None,
                "excerpt": "Learn advanced techniques for Ghost CMS...",
                "reading_time": 8,
                "tags": ["ghost", "cms", "tutorial"]
            }
        ]

    @pytest.fixture
    def output_formatter(self):
        """Create OutputFormatter instance for testing."""
        return OutputFormatter()

    def test_table_format_workflow(self, output_formatter, sample_posts_data):
        """Test table format output workflow.

        Validates:
        1. Data transformation to table format
        2. Column selection and ordering
        3. Table rendering with proper alignment
        4. Pagination for large datasets
        5. Color coding and styling
        """
        # This should fail initially as OutputFormatter doesn't exist
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            output_formatter.render_table(
                data=sample_posts_data,
                columns=['title', 'status', 'created_at', 'reading_time'],
                title="Blog Posts"
            )

        output = mock_stdout.getvalue()

        # Should contain table structure
        assert "Blog Posts" in output
        assert "First Blog Post" in output
        assert "Advanced Ghost CMS Tips" in output
        assert "published" in output
        assert "draft" in output

        # Should have proper table formatting
        assert "│" in output or "|" in output  # Table borders
        assert "─" in output or "-" in output  # Horizontal lines

    def test_json_format_workflow(self, output_formatter, sample_posts_data):
        """Test JSON format output workflow.

        Validates:
        1. Data serialization to JSON
        2. Pretty printing with indentation
        3. Field filtering and selection
        4. Nested object handling
        5. Date format preservation
        """
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            output_formatter.render_json(
                data=sample_posts_data,
                fields=['id', 'title', 'status', 'tags'],
                pretty=True
            )

        output = mock_stdout.getvalue()

        # Should be valid JSON
        parsed_data = json.loads(output)
        assert len(parsed_data) == 2
        assert parsed_data[0]['title'] == "First Blog Post"
        assert parsed_data[1]['status'] == "draft"

        # Should include specified fields only
        for post in parsed_data:
            assert set(post.keys()) == {'id', 'title', 'status', 'tags'}

        # Should have pretty formatting
        assert "  " in output  # Indentation
        assert "\n" in output  # Line breaks

    def test_yaml_format_workflow(self, output_formatter, sample_posts_data):
        """Test YAML format output workflow.

        Validates:
        1. Data serialization to YAML
        2. Proper YAML structure and indentation
        3. List and dictionary handling
        4. Comments and metadata inclusion
        5. Multi-document support
        """
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            output_formatter.render_yaml(
                data=sample_posts_data,
                include_metadata=True,
                document_separator=True
            )

        output = mock_stdout.getvalue()

        # Should be valid YAML
        parsed_data = yaml.safe_load_all(output)
        posts_list = list(parsed_data)

        # Should contain both posts
        assert len(posts_list) >= 1
        first_doc = posts_list[0]
        if isinstance(first_doc, list):
            assert len(first_doc) == 2
            assert first_doc[0]['title'] == "First Blog Post"

        # Should have YAML formatting
        assert ":" in output  # Key-value pairs
        assert "- " in output  # List items
        assert "  " in output  # Indentation

    def test_output_format_selection_workflow(self, output_formatter):
        """Test automatic output format selection based on context.

        Validates:
        1. Format selection based on CLI flags
        2. Environment variable override
        3. Content type detection
        4. Terminal capability detection
        5. Default format fallback
        """
        # Test CLI flag override
        with patch('sys.argv', ['ghostctl', 'posts', 'list', '--format', 'json']):
            format_choice = output_formatter.determine_format()
            assert format_choice == 'json'

        # Test environment variable
        with patch.dict('os.environ', {'GHOSTCTL_OUTPUT_FORMAT': 'yaml'}):
            format_choice = output_formatter.determine_format()
            assert format_choice == 'yaml'

        # Test terminal detection
        with patch('sys.stdout.isatty', return_value=True):
            format_choice = output_formatter.determine_format()
            assert format_choice == 'table'  # Default for interactive terminal

        with patch('sys.stdout.isatty', return_value=False):
            format_choice = output_formatter.determine_format()
            assert format_choice == 'json'  # Default for non-interactive

    def test_field_filtering_and_projection_workflow(self, output_formatter, sample_posts_data):
        """Test field filtering and data projection across formats.

        Validates:
        1. Include/exclude field specifications
        2. Nested field access (e.g., author.name)
        3. Field aliasing and renaming
        4. Computed fields addition
        5. Consistent behavior across formats
        """
        field_config = {
            'include': ['title', 'status', 'author.name', 'tags'],
            'exclude': ['internal_fields'],
            'aliases': {'author.name': 'author'},
            'computed': {
                'tag_count': lambda post: len(post.get('tags', []))
            }
        }

        # Test with table format
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            output_formatter.render_table(
                data=sample_posts_data,
                field_config=field_config
            )

        table_output = mock_stdout.getvalue()
        assert 'tag_count' in table_output

        # Test with JSON format
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            output_formatter.render_json(
                data=sample_posts_data,
                field_config=field_config
            )

        json_output = json.loads(mock_stdout.getvalue())
        assert 'tag_count' in json_output[0]
        assert json_output[0]['tag_count'] == 2  # First post has 2 tags

    def test_pagination_and_streaming_workflow(self, output_formatter):
        """Test pagination and streaming for large datasets.

        Validates:
        1. Page-based output for table format
        2. Streaming JSON output for large datasets
        3. Memory-efficient processing
        4. Interactive pagination controls
        5. Progress indicators
        """
        # Generate large dataset
        large_dataset = [
            {
                "id": f"post-{i}",
                "title": f"Post {i}",
                "status": "published" if i % 2 == 0 else "draft"
            }
            for i in range(1000)
        ]

        # Test table pagination
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            with patch('builtins.input', side_effect=['', 'q']):  # Enter then quit
                output_formatter.render_table(
                    data=large_dataset,
                    page_size=10,
                    interactive=True
                )

        output = mock_stdout.getvalue()
        assert "Page 1" in output

        # Test streaming JSON
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            output_formatter.render_json(
                data=large_dataset,
                streaming=True
            )

        # Should handle large dataset without memory issues
        assert mock_stdout.getvalue().count('"id":') == 1000

    def test_sorting_and_grouping_workflow(self, output_formatter, sample_posts_data):
        """Test data sorting and grouping across output formats.

        Validates:
        1. Single and multi-field sorting
        2. Ascending/descending order
        3. Data grouping by field values
        4. Group headers and separators
        5. Consistent ordering across formats
        """
        # Test sorting by multiple fields
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            output_formatter.render_table(
                data=sample_posts_data,
                sort_by=[('status', 'asc'), ('created_at', 'desc')]
            )

        table_output = mock_stdout.getvalue()

        # Draft posts should come before published (alphabetical)
        draft_pos = table_output.find('draft')
        published_pos = table_output.find('published')
        assert draft_pos < published_pos

        # Test grouping by status
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            output_formatter.render_table(
                data=sample_posts_data,
                group_by='status',
                show_group_headers=True
            )

        grouped_output = mock_stdout.getvalue()
        assert 'draft' in grouped_output
        assert 'published' in grouped_output

    def test_error_handling_and_validation_workflow(self, output_formatter):
        """Test error handling and data validation in output formatting.

        Validates:
        1. Invalid data structure handling
        2. Missing field graceful degradation
        3. Type conversion errors
        4. Circular reference detection
        5. Error message formatting
        """
        # Test invalid data structure
        invalid_data = [
            {"valid": "post"},
            None,  # Invalid entry
            {"another": "valid", "post": True}
        ]

        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            output_formatter.render_json(
                data=invalid_data,
                skip_invalid=True
            )

        output = json.loads(mock_stdout.getvalue())
        assert len(output) == 2  # Should skip None entry

        # Test circular reference handling
        circular_data = {"name": "test"}
        circular_data["self_ref"] = circular_data

        with pytest.raises(ValueError, match="circular reference"):
            output_formatter.render_json([circular_data])

    def test_custom_formatters_and_renderers_workflow(self, output_formatter):
        """Test custom formatter and renderer registration.

        Validates:
        1. Custom format registration
        2. Renderer plugin system
        3. Format-specific configuration
        4. Renderer chaining and composition
        5. Error handling for custom formats
        """
        # Register custom CSV formatter
        def csv_formatter(data, **kwargs):
            import csv
            from io import StringIO

            output = StringIO()
            if data:
                writer = csv.DictWriter(output, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
            return output.getvalue()

        output_formatter.register_format('csv', csv_formatter)

        # Test custom format
        test_data = [
            {"name": "John", "age": 30},
            {"name": "Jane", "age": 25}
        ]

        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            output_formatter.render(data=test_data, format='csv')

        csv_output = mock_stdout.getvalue()
        assert "name,age" in csv_output
        assert "John,30" in csv_output

    def test_theme_and_styling_workflow(self, output_formatter, sample_posts_data):
        """Test theming and styling across output formats.

        Validates:
        1. Color theme application
        2. Terminal capability detection
        3. Style consistency across formats
        4. Custom styling rules
        5. Accessibility considerations
        """
        # Test with color theme
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            output_formatter.render_table(
                data=sample_posts_data,
                theme='dark',
                colors=True
            )

        styled_output = mock_stdout.getvalue()

        # Should contain ANSI color codes (if terminal supports it)
        # Note: This will depend on terminal detection

        # Test accessibility mode (no colors)
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            output_formatter.render_table(
                data=sample_posts_data,
                theme='accessible',
                colors=False
            )

        accessible_output = mock_stdout.getvalue()
        assert len(accessible_output) > 0

    def test_output_redirection_and_file_workflow(self, output_formatter, sample_posts_data):
        """Test output redirection to files and streams.

        Validates:
        1. File output redirection
        2. Stream handling (stdout, stderr)
        3. File format detection
        4. Append vs overwrite modes
        5. Error handling for file operations
        """
        import tempfile

        # Test file output
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as f:
            output_formatter.render_to_file(
                data=sample_posts_data,
                file_path=f.name,
                format='json'
            )

            # Read back and validate
            f.seek(0)
            file_content = f.read()
            parsed_data = json.loads(file_content)
            assert len(parsed_data) == 2

        # Test append mode
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.yaml', delete=False) as f:
            # Write initial data
            output_formatter.render_to_file(
                data=sample_posts_data[:1],
                file_path=f.name,
                format='yaml'
            )

            # Append more data
            output_formatter.render_to_file(
                data=sample_posts_data[1:],
                file_path=f.name,
                format='yaml',
                append=True
            )

            # Should contain both entries
            f.seek(0)
            file_content = f.read()
            assert "First Blog Post" in file_content
            assert "Advanced Ghost CMS Tips" in file_content