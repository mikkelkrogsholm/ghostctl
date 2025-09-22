"""Contract tests for Ghost CMS API endpoints.

This module contains contract tests that define the expected behavior
of Ghost CMS API endpoints. These tests follow TDD principles and will
fail initially until the actual API client implementations are created.

Test files:
- test_posts_api.py: Tests for Posts API (GET, POST, PUT, DELETE)
- test_images_api.py: Tests for Images API (POST /images/upload)
- test_themes_api.py: Tests for Themes API (GET, POST, PUT)
- test_tags_api.py: Tests for Tags API (GET, POST, PUT, DELETE)

Each test file includes:
- Request format validation (URL, headers, authentication)
- Response schema validation using Pydantic models
- Error handling scenarios
- Edge cases and validation rules

All tests are designed to FAIL initially (NotImplementedError) until
the corresponding API client implementations are created.
"""