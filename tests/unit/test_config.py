"""Unit tests for config.py module.

Tests the Profile and ConfigManager classes for configuration management
including validation, file operations, profile switching, and environment handling.
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from pydantic import ValidationError
import requests

from ghostctl.config import Profile, ConfigManager
from ghostctl.exceptions import ConfigError


class TestProfile:
    """Test cases for the Profile model."""

    def test_profile_creation_with_valid_data(self):
        """Test creating a profile with valid data."""
        profile = Profile(
            name="test-profile",
            url="https://myblog.ghost.io",
            admin_key="5f3d4a9b8c7e2f1a9b8c7e2f:1234567890abcdef1234567890abcdef12345678",
            content_key="1234567890abcdef1234567890abcdef",
            version="v5.0",
            timeout=30,
            retry_attempts=3,
        )

        assert profile.name == "test-profile"
        assert str(profile.url) == "https://myblog.ghost.io"
        assert profile.admin_key == "5f3d4a9b8c7e2f1a9b8c7e2f:1234567890abcdef1234567890abcdef12345678"
        assert profile.content_key == "1234567890abcdef1234567890abcdef"
        assert profile.version == "v5.0"
        assert profile.timeout == 30
        assert profile.retry_attempts == 3
        assert profile.active is False

    def test_profile_creation_minimal_data(self):
        """Test creating a profile with minimal required data."""
        profile = Profile(
            name="minimal",
            url="https://blog.example.com",
            admin_key="5f3d4a9b8c7e2f1a9b8c7e2f:1234567890abcdef1234567890abcdef12345678",
        )

        assert profile.name == "minimal"
        assert profile.version == "v5.0"  # default
        assert profile.timeout == 30  # default
        assert profile.retry_attempts == 3  # default
        assert profile.active is False  # default

    def test_profile_admin_key_validation_valid(self):
        """Test admin key validation with valid keys."""
        valid_keys = [
            "5f3d4a9b8c7e2f1a9b8c7e2f:1234567890abcdef1234567890abcdef12345678",
            "abcdef1234567890abcdef12:secret123",
        ]

        for key in valid_keys:
            profile = Profile(
                name="test",
                url="https://example.com",
                admin_key=key,
            )
            assert profile.admin_key == key

    def test_profile_admin_key_validation_invalid_format(self):
        """Test admin key validation with invalid formats."""
        invalid_keys = [
            "invalid_key_without_colon",
            "too:many:colons:here",
            ":missing_id",
            "missing_secret:",
            "",
            "short_id:secret",  # ID too short
            "invalid-chars!@#$:secret",  # Invalid characters in ID
        ]

        for key in invalid_keys:
            with pytest.raises(ValidationError):
                Profile(
                    name="test",
                    url="https://example.com",
                    admin_key=key,
                )

    def test_profile_content_key_validation_valid(self):
        """Test content key validation with valid keys."""
        valid_keys = [
            "1234567890abcdef1234567890abcdef",  # 32 chars
            "abcdef1234567890abcdef12",  # 24 chars
            "1234567890abcdef1234567890abcdef12",  # 26 chars
        ]

        for key in valid_keys:
            profile = Profile(
                name="test",
                url="https://example.com",
                content_key=key,
            )
            assert profile.content_key == key

    def test_profile_content_key_validation_invalid(self):
        """Test content key validation with invalid keys."""
        invalid_keys = [
            "short",  # Too short
            "invalid-chars!@#$1234567890abcdef",  # Invalid characters
            "1234567890ABCDEF1234567890ABCDEF",  # Uppercase not allowed
            "",  # Empty
        ]

        for key in invalid_keys:
            with pytest.raises(ValidationError):
                Profile(
                    name="test",
                    url="https://example.com",
                    content_key=key,
                )

    def test_profile_timeout_validation(self):
        """Test timeout validation."""
        # Valid timeouts
        for timeout in [1, 30, 300]:
            profile = Profile(
                name="test",
                url="https://example.com",
                admin_key="5f3d4a9b8c7e2f1a9b8c7e2f:secret",
                timeout=timeout,
            )
            assert profile.timeout == timeout

        # Invalid timeouts
        for timeout in [0, -1, 301]:
            with pytest.raises(ValidationError):
                Profile(
                    name="test",
                    url="https://example.com",
                    admin_key="5f3d4a9b8c7e2f1a9b8c7e2f:secret",
                    timeout=timeout,
                )

    def test_profile_retry_attempts_validation(self):
        """Test retry attempts validation."""
        # Valid retry attempts
        for retries in [0, 1, 5, 10]:
            profile = Profile(
                name="test",
                url="https://example.com",
                admin_key="5f3d4a9b8c7e2f1a9b8c7e2f:secret",
                retry_attempts=retries,
            )
            assert profile.retry_attempts == retries

        # Invalid retry attempts
        for retries in [-1, 11]:
            with pytest.raises(ValidationError):
                Profile(
                    name="test",
                    url="https://example.com",
                    admin_key="5f3d4a9b8c7e2f1a9b8c7e2f:secret",
                    retry_attempts=retries,
                )

    def test_profile_model_dump(self):
        """Test converting profile to dictionary."""
        profile = Profile(
            name="test",
            url="https://example.com/",  # Note trailing slash
            admin_key="5f3d4a9b8c7e2f1a9b8c7e2f:secret",
        )

        data = profile.model_dump()

        # URL should have trailing slash removed
        assert data["url"] == "https://example.com"
        assert data["name"] == "test"
        assert data["admin_key"] == "5f3d4a9b8c7e2f1a9b8c7e2f:secret"

    def test_get_admin_key_parts(self):
        """Test extracting admin key parts."""
        profile = Profile(
            name="test",
            url="https://example.com",
            admin_key="my_key_id:my_secret_key",
        )

        key_id, secret = profile.get_admin_key_parts()
        assert key_id == "my_key_id"
        assert secret == "my_secret_key"

    def test_get_admin_key_parts_no_key(self):
        """Test extracting admin key parts when no key is set."""
        profile = Profile(
            name="test",
            url="https://example.com",
            content_key="1234567890abcdef1234567890abcdef",
        )

        with pytest.raises(ValueError, match="Admin key not configured"):
            profile.get_admin_key_parts()


class TestConfigManager:
    """Test cases for the ConfigManager class."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create a temporary configuration directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def config_manager(self, temp_config_dir):
        """Create a ConfigManager with temporary directory."""
        return ConfigManager(config_dir=temp_config_dir)

    def test_config_manager_initialization(self, temp_config_dir):
        """Test ConfigManager initialization."""
        manager = ConfigManager(config_dir=temp_config_dir)

        assert manager.config_dir == temp_config_dir
        assert manager.config_file == temp_config_dir / "config.toml"
        assert manager.profiles_dir == temp_config_dir / "profiles"

        # Directories should be created
        assert temp_config_dir.exists()
        assert (temp_config_dir / "profiles").exists()

    def test_config_manager_default_initialization(self):
        """Test ConfigManager with default configuration directory."""
        with patch("pathlib.Path.home") as mock_home:
            mock_home.return_value = Path("/fake/home")

            with patch("pathlib.Path.mkdir"):
                manager = ConfigManager()

                assert manager.config_dir == Path("/fake/home") / ".ghostctl"

    def test_create_profile_success(self, config_manager):
        """Test creating a new profile successfully."""
        profile = config_manager.create_profile(
            name="test-blog",
            url="https://test.ghost.io",
            admin_key="5f3d4a9b8c7e2f1a9b8c7e2f:1234567890abcdef1234567890abcdef12345678",
            content_key="1234567890abcdef1234567890abcdef",
        )

        assert profile.name == "test-blog"
        assert str(profile.url) == "https://test.ghost.io"
        assert "test-blog" in config_manager._profiles

        # Profile file should be created
        profile_file = config_manager.profiles_dir / "test-blog.json"
        assert profile_file.exists()

    def test_create_profile_duplicate_name(self, config_manager):
        """Test creating a profile with duplicate name."""
        config_manager.create_profile(
            name="duplicate",
            url="https://test1.ghost.io",
            admin_key="5f3d4a9b8c7e2f1a9b8c7e2f:secret1",
        )

        with pytest.raises(ConfigError, match="Profile 'duplicate' already exists"):
            config_manager.create_profile(
                name="duplicate",
                url="https://test2.ghost.io",
                admin_key="5f3d4a9b8c7e2f1a9b8c7e2f:secret2",
            )

    def test_create_profile_no_api_keys(self, config_manager):
        """Test creating a profile without any API keys."""
        with pytest.raises(ConfigError, match="Either admin_key or content_key is required"):
            config_manager.create_profile(
                name="no-keys",
                url="https://test.ghost.io",
            )

    def test_create_profile_invalid_url(self, config_manager):
        """Test creating a profile with invalid URL."""
        with pytest.raises(ConfigError, match="Invalid URL format"):
            config_manager.create_profile(
                name="invalid-url",
                url="not-a-valid-url",
                admin_key="5f3d4a9b8c7e2f1a9b8c7e2f:secret",
            )

    @patch("requests.get")
    def test_create_profile_with_validation_success(self, mock_get, config_manager):
        """Test creating a profile with connection validation (success)."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        profile = config_manager.create_profile(
            name="validated",
            url="https://test.ghost.io",
            admin_key="5f3d4a9b8c7e2f1a9b8c7e2f:secret",
            validate_connection=True,
        )

        assert profile.name == "validated"
        mock_get.assert_called_once()

    @patch("requests.get")
    def test_create_profile_with_validation_failure(self, mock_get, config_manager):
        """Test creating a profile with connection validation (failure)."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        with pytest.raises(ConfigError, match="Failed to connect to Ghost instance"):
            config_manager.create_profile(
                name="invalid",
                url="https://test.ghost.io",
                admin_key="5f3d4a9b8c7e2f1a9b8c7e2f:secret",
                validate_connection=True,
            )

    def test_get_profile_config(self, config_manager):
        """Test getting profile configuration."""
        config_manager.create_profile(
            name="test",
            url="https://test.ghost.io",
            admin_key="5f3d4a9b8c7e2f1a9b8c7e2f:secret",
        )

        config = config_manager.get_profile_config("test")
        assert config["name"] == "test"
        assert config["url"] == "https://test.ghost.io"

    def test_get_profile_config_not_found(self, config_manager):
        """Test getting configuration for non-existent profile."""
        with pytest.raises(ConfigError, match="Profile 'nonexistent' not found"):
            config_manager.get_profile_config("nonexistent")

    def test_list_profiles(self, config_manager):
        """Test listing all profiles."""
        # Initially empty
        profiles = config_manager.list_profiles()
        assert len(profiles) == 0

        # Add profiles
        config_manager.create_profile(
            name="blog1",
            url="https://blog1.ghost.io",
            admin_key="5f3d4a9b8c7e2f1a9b8c7e2f:secret1",
        )
        config_manager.create_profile(
            name="blog2",
            url="https://blog2.ghost.io",
            admin_key="5f3d4a9b8c7e2f1a9b8c7e2f:secret2",
        )

        profiles = config_manager.list_profiles()
        assert len(profiles) == 2

        profile_names = [p["name"] for p in profiles]
        assert "blog1" in profile_names
        assert "blog2" in profile_names

    def test_set_active_profile(self, config_manager):
        """Test setting active profile."""
        config_manager.create_profile(
            name="test",
            url="https://test.ghost.io",
            admin_key="5f3d4a9b8c7e2f1a9b8c7e2f:secret",
        )

        config_manager.set_active_profile("test")
        assert config_manager.get_active_profile() == "test"

    def test_set_active_profile_not_found(self, config_manager):
        """Test setting active profile that doesn't exist."""
        with pytest.raises(ConfigError, match="Profile 'nonexistent' not found"):
            config_manager.set_active_profile("nonexistent")

    def test_get_default_profile(self, config_manager):
        """Test getting default profile."""
        config_manager.create_profile(
            name="default",
            url="https://default.ghost.io",
            admin_key="5f3d4a9b8c7e2f1a9b8c7e2f:secret",
        )
        config_manager.set_active_profile("default")

        profile = config_manager.get_default_profile()
        assert profile.name == "default"

    def test_get_default_profile_none_set(self, config_manager):
        """Test getting default profile when none is set."""
        with pytest.raises(ConfigError, match="No default profile set"):
            config_manager.get_default_profile()

    def test_get_profile(self, config_manager):
        """Test getting specific profile by name."""
        config_manager.create_profile(
            name="specific",
            url="https://specific.ghost.io",
            admin_key="5f3d4a9b8c7e2f1a9b8c7e2f:secret",
        )

        profile = config_manager.get_profile("specific")
        assert profile.name == "specific"

    def test_get_profile_not_found(self, config_manager):
        """Test getting non-existent profile."""
        with pytest.raises(ConfigError, match="Profile 'missing' not found"):
            config_manager.get_profile("missing")

    def test_get_active_config(self, config_manager):
        """Test getting active configuration."""
        config_manager.create_profile(
            name="active",
            url="https://active.ghost.io",
            admin_key="5f3d4a9b8c7e2f1a9b8c7e2f:secret",
        )
        config_manager.set_active_profile("active")

        config = config_manager.get_active_config()
        assert config["name"] == "active"

    def test_get_active_config_none_set(self, config_manager):
        """Test getting active configuration when none is set."""
        with pytest.raises(ConfigError, match="No active profile set"):
            config_manager.get_active_config()

    def test_delete_profile(self, config_manager):
        """Test deleting a profile."""
        config_manager.create_profile(
            name="to-delete",
            url="https://delete.ghost.io",
            admin_key="5f3d4a9b8c7e2f1a9b8c7e2f:secret",
        )

        # Verify profile exists
        assert "to-delete" in config_manager._profiles
        profile_file = config_manager.profiles_dir / "to-delete.json"
        assert profile_file.exists()

        # Delete profile
        config_manager.delete_profile("to-delete")

        # Verify profile is removed
        assert "to-delete" not in config_manager._profiles
        assert not profile_file.exists()

    def test_delete_active_profile(self, config_manager):
        """Test deleting the active profile."""
        config_manager.create_profile(
            name="active-delete",
            url="https://active.ghost.io",
            admin_key="5f3d4a9b8c7e2f1a9b8c7e2f:secret",
        )
        config_manager.set_active_profile("active-delete")

        config_manager.delete_profile("active-delete")

        # Active profile should be cleared
        assert config_manager.get_active_profile() is None

    def test_delete_profile_not_found(self, config_manager):
        """Test deleting non-existent profile."""
        with pytest.raises(ConfigError, match="Profile 'missing' not found"):
            config_manager.delete_profile("missing")

    def test_export_profile(self, config_manager, temp_config_dir):
        """Test exporting a profile."""
        config_manager.create_profile(
            name="export-test",
            url="https://export.ghost.io",
            admin_key="5f3d4a9b8c7e2f1a9b8c7e2f:secret",
            content_key="1234567890abcdef1234567890abcdef",
        )

        export_file = temp_config_dir / "exported.json"
        config_manager.export_profile("export-test", export_file)

        assert export_file.exists()

        with open(export_file) as f:
            data = json.load(f)

        assert data["name"] == "export-test"
        assert data["url"] == "https://export.ghost.io"
        # Admin key should be removed for security
        assert "admin_key" not in data
        # Content key should remain
        assert data["content_key"] == "1234567890abcdef1234567890abcdef"

    def test_export_profile_not_found(self, config_manager, temp_config_dir):
        """Test exporting non-existent profile."""
        export_file = temp_config_dir / "exported.json"

        with pytest.raises(ConfigError, match="Profile 'missing' not found"):
            config_manager.export_profile("missing", export_file)

    def test_import_profile(self, config_manager, temp_config_dir):
        """Test importing a profile."""
        import_data = {
            "name": "imported",
            "url": "https://imported.ghost.io",
            "content_key": "1234567890abcdef1234567890abcdef",
            "version": "v5.0",
            "timeout": 30,
            "retry_attempts": 3,
        }

        import_file = temp_config_dir / "import.json"
        with open(import_file, "w") as f:
            json.dump(import_data, f)

        profile = config_manager.import_profile(import_file)

        assert profile.name == "imported"
        assert "imported" in config_manager._profiles

    def test_import_profile_overwrite(self, config_manager, temp_config_dir):
        """Test importing profile with overwrite."""
        # Create existing profile
        config_manager.create_profile(
            name="existing",
            url="https://old.ghost.io",
            admin_key="5f3d4a9b8c7e2f1a9b8c7e2f:old",
        )

        # Import data with same name
        import_data = {
            "name": "existing",
            "url": "https://new.ghost.io",
            "content_key": "1234567890abcdef1234567890abcdef",
        }

        import_file = temp_config_dir / "import.json"
        with open(import_file, "w") as f:
            json.dump(import_data, f)

        # Should fail without overwrite
        with pytest.raises(ConfigError, match="already exists"):
            config_manager.import_profile(import_file)

        # Should succeed with overwrite
        profile = config_manager.import_profile(import_file, overwrite=True)
        assert str(profile.url) == "https://new.ghost.io"

    @patch.dict("os.environ", {
        "GHOST_API_URL": "https://env.ghost.io",
        "GHOST_ADMIN_API_KEY": "5f3d4a9b8c7e2f1a9b8c7e2f:env_secret",
    })
    def test_has_environment_config_true(self, config_manager):
        """Test environment configuration detection (available)."""
        assert config_manager.has_environment_config() is True

    @patch.dict("os.environ", {}, clear=True)
    def test_has_environment_config_false(self, config_manager):
        """Test environment configuration detection (not available)."""
        assert config_manager.has_environment_config() is False

    @patch.dict("os.environ", {
        "GHOST_API_URL": "https://env.ghost.io",
        "GHOST_CONTENT_API_KEY": "1234567890abcdef1234567890abcdef",
    })
    def test_get_environment_config(self, config_manager):
        """Test getting configuration from environment."""
        config = config_manager.get_environment_config()

        assert config["name"] == "environment"
        assert config["url"] == "https://env.ghost.io"
        assert config["content_key"] == "1234567890abcdef1234567890abcdef"

    @patch.dict("os.environ", {}, clear=True)
    def test_get_environment_config_missing_url(self, config_manager):
        """Test environment configuration with missing URL."""
        with pytest.raises(ConfigError, match="GHOST_API_URL environment variable is required"):
            config_manager.get_environment_config()

    @patch.dict("os.environ", {"GHOST_API_URL": "https://env.ghost.io"})
    def test_get_environment_config_missing_keys(self, config_manager):
        """Test environment configuration with missing API keys."""
        with pytest.raises(ConfigError, match="Either GHOST_ADMIN_API_KEY or GHOST_CONTENT_API_KEY"):
            config_manager.get_environment_config()

    def test_load_config_with_existing_profiles(self, config_manager):
        """Test loading configuration with existing profile files."""
        # Create profile file manually
        profile_data = {
            "name": "manual",
            "url": "https://manual.ghost.io",
            "admin_key": "5f3d4a9b8c7e2f1a9b8c7e2f:manual",
            "version": "v5.0",
            "timeout": 30,
            "retry_attempts": 3,
            "active": False,
        }

        profile_file = config_manager.profiles_dir / "manual.json"
        with open(profile_file, "w") as f:
            json.dump(profile_data, f)

        # Create config file
        config_content = '''version = "1.0"\nactive_profile = "manual"'''
        with open(config_manager.config_file, "w") as f:
            f.write(config_content)

        # Reload configuration
        new_manager = ConfigManager(config_dir=config_manager.config_dir)

        assert "manual" in new_manager._profiles
        assert new_manager.get_active_profile() == "manual"

    def test_load_config_corrupted_profile(self, config_manager, capsys):
        """Test loading configuration with corrupted profile file."""
        # Create corrupted profile file
        profile_file = config_manager.profiles_dir / "corrupted.json"
        with open(profile_file, "w") as f:
            f.write("invalid json content")

        # Should continue loading despite corrupted file
        new_manager = ConfigManager(config_dir=config_manager.config_dir)

        # Should print warning
        captured = capsys.readouterr()
        assert "Warning: Failed to load profile" in captured.out
        assert "corrupted" not in new_manager._profiles