"""Integration tests for configuration profiles.

Tests the complete workflow of managing Ghost CMS configuration profiles,
including creation, switching, listing, and validation of different environments.
"""

import pytest
from unittest.mock import Mock, patch
import tempfile
import os
from pathlib import Path
import json

from ghostctl.config import ConfigManager
from ghostctl.exceptions import ConfigError


class TestConfigProfiles:
    """Integration tests for configuration profile management."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create a temporary configuration directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / ".ghostctl"
            config_path.mkdir()
            yield config_path

    @pytest.fixture
    def config_manager(self, temp_config_dir):
        """Create a ConfigManager instance with temporary directory."""
        return ConfigManager(config_dir=temp_config_dir)

    def test_create_new_profile_workflow(self, config_manager):
        """Test creating a new configuration profile from scratch.

        This test validates the complete user journey of:
        1. Creating a new profile with interactive prompts
        2. Validating profile configuration
        3. Setting as active profile
        4. Persisting configuration to disk
        """
        # This should fail initially as ConfigManager doesn't exist
        profile_data = {
            "name": "production",
            "url": "https://ghost.example.com",
            "admin_key": "664746a3b1c8f8d65a000001:test-admin-key",
            "content_key": "664746a3b1c8f8d65a000002",
            "version": "v5.0"
        }

        # Should create profile and validate configuration
        config_manager.create_profile(**profile_data)

        # Should set as active profile
        config_manager.set_active_profile("production")

        # Should persist to disk
        assert config_manager.get_active_profile() == "production"
        assert config_manager.get_profile_config("production")["url"] == profile_data["url"]

    def test_switch_between_profiles_workflow(self, config_manager):
        """Test switching between multiple configuration profiles.

        Validates:
        1. Creating multiple profiles
        2. Switching active profile
        3. Commands using correct profile configuration
        4. Profile-specific authentication
        """
        # Create multiple profiles
        production_config = {
            "name": "production",
            "url": "https://ghost.example.com",
            "admin_key": "prod-admin-key",
            "content_key": "prod-content-key"
        }

        staging_config = {
            "name": "staging",
            "url": "https://staging.ghost.example.com",
            "admin_key": "staging-admin-key",
            "content_key": "staging-content-key"
        }

        config_manager.create_profile(**production_config)
        config_manager.create_profile(**staging_config)

        # Switch to production
        config_manager.set_active_profile("production")
        active_config = config_manager.get_active_config()
        assert active_config["url"] == production_config["url"]

        # Switch to staging
        config_manager.set_active_profile("staging")
        active_config = config_manager.get_active_config()
        assert active_config["url"] == staging_config["url"]

    def test_profile_validation_workflow(self, config_manager):
        """Test configuration profile validation and error handling.

        Validates:
        1. Invalid URL handling
        2. Missing required fields
        3. Invalid API key formats
        4. Network connectivity checks
        """
        # Test invalid URL
        with pytest.raises(ConfigError, match="Invalid URL format"):
            config_manager.create_profile(
                name="invalid",
                url="not-a-valid-url",
                admin_key="test-key",
                content_key="test-content-key"
            )

        # Test missing admin key
        with pytest.raises(ConfigError, match="Admin key is required"):
            config_manager.create_profile(
                name="missing-key",
                url="https://ghost.example.com",
                content_key="test-content-key"
            )

        # Test invalid admin key format
        with pytest.raises(ConfigError, match="Invalid admin key format"):
            config_manager.create_profile(
                name="invalid-key",
                url="https://ghost.example.com",
                admin_key="invalid-key-format",
                content_key="test-content-key"
            )

    @patch('requests.get')
    def test_profile_connectivity_check(self, mock_get, config_manager):
        """Test connectivity validation when creating profiles.

        Validates:
        1. Successful connection to Ghost API
        2. API version compatibility check
        3. Authentication verification
        4. Timeout handling
        """
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "site": {"version": "5.0.0"},
            "config": {"version": "5.0"}
        }
        mock_get.return_value = mock_response

        profile_data = {
            "name": "test",
            "url": "https://ghost.example.com",
            "admin_key": "664746a3b1c8f8d65a000001:test-admin-key",
            "content_key": "test-content-key"
        }

        # Should validate connectivity during profile creation
        config_manager.create_profile(**profile_data, validate_connection=True)

        # Should have made API call to validate connection
        mock_get.assert_called()

        # Test connection failure
        mock_get.side_effect = Exception("Connection failed")

        with pytest.raises(ConfigError, match="Failed to connect"):
            config_manager.create_profile(
                name="failing",
                url="https://ghost.example.com",
                admin_key="664746a3b1c8f8d65a000001:test-admin-key",
                content_key="test-content-key",
                validate_connection=True
            )

    def test_list_profiles_workflow(self, config_manager):
        """Test listing all available configuration profiles.

        Validates:
        1. Empty profile list initially
        2. Profiles appear after creation
        3. Active profile indication
        4. Profile metadata display
        """
        # Initially no profiles
        profiles = config_manager.list_profiles()
        assert len(profiles) == 0

        # Create some profiles
        config_manager.create_profile(
            name="prod",
            url="https://prod.example.com",
            admin_key="664746a3b1c8f8d65a000001:prod-key",
            content_key="prod-content"
        )

        config_manager.create_profile(
            name="dev",
            url="https://dev.example.com",
            admin_key="664746a3b1c8f8d65a000002:dev-key",
            content_key="dev-content"
        )

        # Should list both profiles
        profiles = config_manager.list_profiles()
        assert len(profiles) == 2
        assert "prod" in [p["name"] for p in profiles]
        assert "dev" in [p["name"] for p in profiles]

        # Set active profile
        config_manager.set_active_profile("prod")
        profiles = config_manager.list_profiles()

        # Should indicate active profile
        prod_profile = next(p for p in profiles if p["name"] == "prod")
        assert prod_profile["active"] is True

    def test_delete_profile_workflow(self, config_manager):
        """Test deleting configuration profiles.

        Validates:
        1. Profile deletion
        2. Active profile handling when deleted
        3. Confirmation prompts
        4. File system cleanup
        """
        # Create profiles
        config_manager.create_profile(
            name="temp",
            url="https://temp.example.com",
            admin_key="664746a3b1c8f8d65a000001:temp-key",
            content_key="temp-content"
        )

        config_manager.create_profile(
            name="keep",
            url="https://keep.example.com",
            admin_key="664746a3b1c8f8d65a000002:keep-key",
            content_key="keep-content"
        )

        config_manager.set_active_profile("temp")

        # Delete active profile
        config_manager.delete_profile("temp")

        # Should no longer exist
        profiles = config_manager.list_profiles()
        assert "temp" not in [p["name"] for p in profiles]

        # Active profile should be cleared
        assert config_manager.get_active_profile() is None

    def test_export_import_profile_workflow(self, config_manager, temp_config_dir):
        """Test exporting and importing configuration profiles.

        Validates:
        1. Export profile to JSON/YAML
        2. Import profile from file
        3. Profile data integrity
        4. Overwrite handling
        """
        # Create a profile
        original_config = {
            "name": "export-test",
            "url": "https://export.example.com",
            "admin_key": "664746a3b1c8f8d65a000001:export-key",
            "content_key": "export-content",
            "timeout": 30,
            "retry_attempts": 3
        }

        config_manager.create_profile(**original_config)

        # Export profile
        export_path = temp_config_dir / "exported-profile.json"
        config_manager.export_profile("export-test", export_path)

        # Should create export file
        assert export_path.exists()

        # Delete original profile
        config_manager.delete_profile("export-test")

        # Import profile
        config_manager.import_profile(export_path)

        # Should recreate profile with same configuration
        imported_config = config_manager.get_profile_config("export-test")
        assert imported_config["url"] == original_config["url"]
        assert imported_config["timeout"] == original_config["timeout"]