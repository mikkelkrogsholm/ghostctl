"""Integration tests for Ghost CMS CLI.

This package contains integration tests that validate complete user workflows
and end-to-end functionality of the Ghost CMS CLI tool.

Test Structure:
- test_config_profiles.py: Configuration profile management
- test_auth_flow.py: JWT authentication workflows
- test_retry_logic.py: Retry mechanism and error handling
- test_output_formats.py: Output formatting (table/json/yaml)
- test_bulk_operations.py: Bulk operation workflows
- test_dry_run.py: Dry-run mode functionality

All tests follow TDD principles and will initially fail until implementation
is complete.
"""