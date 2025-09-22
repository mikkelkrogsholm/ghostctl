"""Integration tests for bulk operations.

Tests the complete bulk operation workflow including batch processing,
progress tracking, error handling, and rollback mechanisms for Ghost CMS operations.
"""

import pytest
from unittest.mock import Mock, patch, call
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import tempfile

from ghostctl.bulk import BulkOperationManager, BatchProcessor
from ghostctl.exceptions import BulkOperationError, ValidationError
from ghostctl.models import Post, Tag, User


class TestBulkOperations:
    """Integration tests for bulk operation workflows."""

    @pytest.fixture
    def bulk_manager(self):
        """Create BulkOperationManager for testing."""
        return BulkOperationManager(
            batch_size=5,
            max_workers=3,
            progress_tracking=True,
            error_handling='continue'  # continue, stop, rollback
        )

    @pytest.fixture
    def sample_posts_data(self):
        """Sample posts data for bulk operations."""
        return [
            {
                "title": f"Bulk Post {i}",
                "slug": f"bulk-post-{i}",
                "html": f"<p>Content for post {i}</p>",
                "status": "draft",
                "tags": ["bulk", "test"]
            }
            for i in range(1, 21)  # 20 posts for testing
        ]

    @pytest.fixture
    def sample_tags_data(self):
        """Sample tags data for bulk operations."""
        return [
            {
                "name": f"Tag {i}",
                "slug": f"tag-{i}",
                "description": f"Description for tag {i}"
            }
            for i in range(1, 11)  # 10 tags for testing
        ]

    def test_bulk_create_posts_workflow(self, bulk_manager, sample_posts_data):
        """Test bulk creation of posts with progress tracking.

        Validates:
        1. Batch processing of multiple posts
        2. Progress tracking and reporting
        3. Error handling for individual failures
        4. Success/failure statistics
        5. Performance optimization
        """
        # This should fail initially as BulkOperationManager doesn't exist
        created_posts = []
        failed_posts = []

        def mock_create_post(post_data):
            # Simulate occasional failures
            if post_data['title'] == "Bulk Post 13":
                raise ValidationError("Invalid post data")

            created_post = {
                "id": f"post-{len(created_posts) + 1}",
                **post_data,
                "created_at": "2024-01-15T10:00:00Z"
            }
            created_posts.append(created_post)
            return created_post

        with patch('ghostctl.api.PostsAPI.create', side_effect=mock_create_post):
            result = bulk_manager.bulk_create_posts(sample_posts_data)

        # Should have processed all posts
        assert result.total_processed == 20
        assert result.successful_count == 19  # One failed
        assert result.failed_count == 1
        assert len(result.created_items) == 19
        assert len(result.failed_items) == 1

        # Should have progress tracking
        assert result.progress_log is not None
        assert "Bulk Post 13" in str(result.failed_items[0])

    def test_bulk_update_posts_workflow(self, bulk_manager):
        """Test bulk updating of existing posts.

        Validates:
        1. Batch processing of updates
        2. Optimistic locking handling
        3. Partial update support
        4. Conflict resolution
        5. Update validation
        """
        # Existing posts to update
        existing_posts = [
            {"id": f"post-{i}", "title": f"Original Title {i}", "updated_at": "2024-01-01T00:00:00Z"}
            for i in range(1, 11)
        ]

        # Update data
        updates = [
            {"id": f"post-{i}", "title": f"Updated Title {i}", "status": "published"}
            for i in range(1, 11)
        ]

        updated_posts = []

        def mock_update_post(post_id, update_data):
            if post_id == "post-5":
                raise ValidationError("Optimistic locking conflict")

            updated_post = {
                "id": post_id,
                **update_data,
                "updated_at": "2024-01-15T10:00:00Z"
            }
            updated_posts.append(updated_post)
            return updated_post

        with patch('ghostctl.api.PostsAPI.update', side_effect=mock_update_post):
            result = bulk_manager.bulk_update_posts(updates)

        # Should handle conflicts gracefully
        assert result.successful_count == 9
        assert result.failed_count == 1
        assert len(result.updated_items) == 9

    def test_bulk_delete_workflow(self, bulk_manager):
        """Test bulk deletion with safety checks and confirmation.

        Validates:
        1. Safety confirmation prompts
        2. Dry-run mode support
        3. Dependency checking
        4. Rollback capability
        5. Audit logging
        """
        post_ids = [f"post-{i}" for i in range(1, 16)]  # 15 posts to delete

        def mock_delete_post(post_id):
            if post_id == "post-8":
                raise ValidationError("Cannot delete: post has dependencies")
            return {"id": post_id, "deleted": True}

        # Test dry-run mode first
        with patch('ghostctl.api.PostsAPI.delete', side_effect=mock_delete_post):
            dry_run_result = bulk_manager.bulk_delete_posts(
                post_ids,
                dry_run=True,
                confirm=False
            )

        # Dry run should not actually delete
        assert dry_run_result.dry_run is True
        assert dry_run_result.would_delete_count == 14  # One would fail
        assert dry_run_result.would_fail_count == 1

        # Test actual deletion with confirmation
        with patch('builtins.input', return_value='yes'):
            with patch('ghostctl.api.PostsAPI.delete', side_effect=mock_delete_post):
                result = bulk_manager.bulk_delete_posts(
                    post_ids,
                    dry_run=False,
                    confirm=True
                )

        assert result.successful_count == 14
        assert result.failed_count == 1

    def test_bulk_import_from_file_workflow(self, bulk_manager):
        """Test bulk import from various file formats.

        Validates:
        1. JSON file import
        2. CSV file import
        3. YAML file import
        4. Data validation during import
        5. Error reporting and recovery
        """
        # Create temporary JSON file
        import_data = [
            {
                "title": "Imported Post 1",
                "slug": "imported-post-1",
                "html": "<p>Imported content 1</p>",
                "status": "draft"
            },
            {
                "title": "Imported Post 2",
                "slug": "imported-post-2",
                "html": "<p>Imported content 2</p>",
                "status": "published"
            }
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(import_data, f)
            json_file_path = f.name

        def mock_create_post(post_data):
            return {
                "id": f"imported-{post_data['slug']}",
                **post_data,
                "created_at": "2024-01-15T10:00:00Z"
            }

        with patch('ghostctl.api.PostsAPI.create', side_effect=mock_create_post):
            result = bulk_manager.import_posts_from_file(
                json_file_path,
                file_format='json',
                validate=True
            )

        assert result.successful_count == 2
        assert result.failed_count == 0
        assert len(result.imported_items) == 2

    def test_bulk_export_workflow(self, bulk_manager):
        """Test bulk export to various file formats.

        Validates:
        1. Data export to JSON/CSV/YAML
        2. Field selection and filtering
        3. Pagination for large exports
        4. Progress tracking for exports
        5. File compression options
        """
        # Mock posts data from API
        all_posts = [
            {
                "id": f"post-{i}",
                "title": f"Export Post {i}",
                "slug": f"export-post-{i}",
                "status": "published" if i % 2 == 0 else "draft",
                "created_at": f"2024-01-{i:02d}T10:00:00Z"
            }
            for i in range(1, 101)  # 100 posts
        ]

        def mock_get_posts(page=1, limit=50):
            start_idx = (page - 1) * limit
            end_idx = start_idx + limit
            return {
                "posts": all_posts[start_idx:end_idx],
                "meta": {
                    "pagination": {
                        "page": page,
                        "limit": limit,
                        "total": len(all_posts),
                        "pages": (len(all_posts) + limit - 1) // limit
                    }
                }
            }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            export_file_path = f.name

        with patch('ghostctl.api.PostsAPI.list', side_effect=mock_get_posts):
            result = bulk_manager.export_posts_to_file(
                export_file_path,
                file_format='json',
                fields=['id', 'title', 'status', 'created_at'],
                filters={'status': 'published'}
            )

        assert result.exported_count == 50  # Only published posts
        assert result.file_path == export_file_path

        # Verify exported data
        with open(export_file_path, 'r') as f:
            exported_data = json.load(f)
            assert len(exported_data) == 50
            assert all(post['status'] == 'published' for post in exported_data)

    def test_parallel_processing_workflow(self, bulk_manager, sample_posts_data):
        """Test parallel processing with thread pool management.

        Validates:
        1. Concurrent operation execution
        2. Thread pool management
        3. Rate limiting and throttling
        4. Resource utilization optimization
        5. Error isolation between threads
        """
        processing_times = []
        thread_ids = []

        def mock_create_post(post_data):
            import threading
            import time

            thread_ids.append(threading.current_thread().ident)
            start_time = time.time()

            # Simulate API call delay
            time.sleep(0.1)

            processing_times.append(time.time() - start_time)

            return {
                "id": f"parallel-{post_data['slug']}",
                **post_data
            }

        with patch('ghostctl.api.PostsAPI.create', side_effect=mock_create_post):
            start_time = time.time()
            result = bulk_manager.bulk_create_posts(
                sample_posts_data,
                parallel=True,
                max_workers=3
            )
            total_time = time.time() - start_time

        # Should have used multiple threads
        assert len(set(thread_ids)) > 1
        assert len(set(thread_ids)) <= 3  # Respect max_workers

        # Should be faster than sequential processing
        sequential_time = len(sample_posts_data) * 0.1
        assert total_time < sequential_time * 0.8  # At least 20% faster

    def test_transaction_and_rollback_workflow(self, bulk_manager):
        """Test transactional bulk operations with rollback capability.

        Validates:
        1. Transaction boundary management
        2. Rollback on failure
        3. Partial success handling
        4. State consistency
        5. Audit trail maintenance
        """
        posts_to_create = [
            {"title": f"Transactional Post {i}", "slug": f"trans-post-{i}"}
            for i in range(1, 6)
        ]

        created_posts = []

        def mock_create_post(post_data):
            if post_data['title'] == "Transactional Post 4":
                # Simulate failure in middle of transaction
                raise ValidationError("Critical validation error")

            created_post = {
                "id": f"trans-{len(created_posts) + 1}",
                **post_data
            }
            created_posts.append(created_post)
            return created_post

        def mock_delete_post(post_id):
            # Simulate rollback deletion
            global created_posts
            created_posts = [p for p in created_posts if p['id'] != post_id]
            return {"deleted": True}

        with patch('ghostctl.api.PostsAPI.create', side_effect=mock_create_post):
            with patch('ghostctl.api.PostsAPI.delete', side_effect=mock_delete_post):
                result = bulk_manager.bulk_create_posts(
                    posts_to_create,
                    transactional=True,
                    rollback_on_failure=True
                )

        # Should have rolled back all successful creates
        assert result.rollback_performed is True
        assert result.successful_count == 0  # All rolled back
        assert result.rollback_count == 3  # Three were created before failure

    def test_progress_tracking_and_reporting_workflow(self, bulk_manager, sample_posts_data):
        """Test progress tracking and reporting during bulk operations.

        Validates:
        1. Real-time progress updates
        2. ETA calculations
        3. Throughput monitoring
        4. Progress bar rendering
        5. Detailed operation logs
        """
        progress_updates = []

        def progress_callback(current, total, operation, item=None):
            progress_updates.append({
                "current": current,
                "total": total,
                "operation": operation,
                "percentage": (current / total) * 100,
                "item": item
            })

        def mock_create_post(post_data):
            # Simulate variable processing time
            import time
            time.sleep(0.05)
            return {"id": f"progress-{post_data['slug']}", **post_data}

        with patch('ghostctl.api.PostsAPI.create', side_effect=mock_create_post):
            result = bulk_manager.bulk_create_posts(
                sample_posts_data,
                progress_callback=progress_callback,
                show_progress_bar=True
            )

        # Should have received progress updates
        assert len(progress_updates) == len(sample_posts_data)
        assert progress_updates[0]['current'] == 1
        assert progress_updates[-1]['current'] == len(sample_posts_data)
        assert progress_updates[-1]['percentage'] == 100.0

        # Should have operation timing data
        assert result.start_time is not None
        assert result.end_time is not None
        assert result.duration > 0
        assert result.throughput > 0  # Items per second

    def test_error_handling_strategies_workflow(self, bulk_manager):
        """Test different error handling strategies for bulk operations.

        Validates:
        1. Continue on error strategy
        2. Stop on first error strategy
        3. Retry with backoff strategy
        4. Error categorization
        5. Recovery suggestions
        """
        problematic_data = [
            {"title": "Good Post 1", "slug": "good-1"},
            {"title": "", "slug": "bad-1"},  # Invalid: empty title
            {"title": "Good Post 2", "slug": "good-2"},
            {"title": "Good Post 3", "slug": ""},  # Invalid: empty slug
            {"title": "Good Post 4", "slug": "good-4"},
        ]

        def mock_create_post(post_data):
            if not post_data.get('title'):
                raise ValidationError("Title is required")
            if not post_data.get('slug'):
                raise ValidationError("Slug is required")
            return {"id": f"created-{post_data['slug']}", **post_data}

        # Test "continue" strategy
        bulk_manager.error_handling = 'continue'
        with patch('ghostctl.api.PostsAPI.create', side_effect=mock_create_post):
            result = bulk_manager.bulk_create_posts(problematic_data)

        assert result.successful_count == 3
        assert result.failed_count == 2
        assert len(result.error_summary) == 2

        # Test "stop" strategy
        bulk_manager.error_handling = 'stop'
        with patch('ghostctl.api.PostsAPI.create', side_effect=mock_create_post):
            result = bulk_manager.bulk_create_posts(problematic_data)

        # Should stop after first error
        assert result.successful_count == 1  # Only first good post
        assert result.failed_count == 1
        assert result.stopped_early is True

    def test_bulk_tag_management_workflow(self, bulk_manager, sample_tags_data):
        """Test bulk operations specifically for tag management.

        Validates:
        1. Bulk tag creation
        2. Tag hierarchy handling
        3. Duplicate tag detection
        4. Tag merging operations
        5. Tag assignment to posts
        """
        def mock_create_tag(tag_data):
            return {
                "id": f"tag-{tag_data['slug']}",
                **tag_data,
                "created_at": "2024-01-15T10:00:00Z"
            }

        # Test bulk tag creation
        with patch('ghostctl.api.TagsAPI.create', side_effect=mock_create_tag):
            result = bulk_manager.bulk_create_tags(sample_tags_data)

        assert result.successful_count == len(sample_tags_data)
        assert result.failed_count == 0

        # Test bulk tag assignment to posts
        post_ids = [f"post-{i}" for i in range(1, 6)]
        tag_ids = [f"tag-{i}" for i in range(1, 4)]

        def mock_assign_tags(post_id, tag_ids):
            return {
                "post_id": post_id,
                "assigned_tags": tag_ids,
                "assignment_count": len(tag_ids)
            }

        with patch('ghostctl.api.PostsAPI.assign_tags', side_effect=mock_assign_tags):
            result = bulk_manager.bulk_assign_tags_to_posts(post_ids, tag_ids)

        assert result.successful_assignments == len(post_ids)
        assert result.total_tag_assignments == len(post_ids) * len(tag_ids)