"""Configuration management for Ghost CMS CLI.

This module provides configuration profile management, including creating,
updating, deleting, and switching between different Ghost CMS instances.
"""

import os
import tomllib
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urlparse
import re

from pydantic import BaseModel, Field, field_validator, HttpUrl
import requests

from .exceptions import ConfigError


class Profile(BaseModel):
    """Configuration profile for a Ghost CMS instance."""

    name: str = Field(..., description="Profile name")
    url: HttpUrl = Field(..., description="Ghost CMS instance URL")
    admin_key: Optional[str] = Field(None, description="Admin API key")
    content_key: Optional[str] = Field(None, description="Content API key")
    version: str = Field(default="v5.0", description="Ghost API version")
    timeout: int = Field(default=30, description="Request timeout in seconds")
    retry_attempts: int = Field(default=3, description="Number of retry attempts")
    active: bool = Field(default=False, description="Whether this is the active profile")

    @field_validator("admin_key")
    @classmethod
    def validate_admin_key(cls, v: Optional[str]) -> Optional[str]:
        """Validate admin key format."""
        if v is None:
            return v

        # Ghost admin keys should be in format: id:secret
        if ":" not in v:
            raise ValueError("Invalid admin key format. Expected format: id:secret")

        parts = v.split(":")
        if len(parts) != 2:
            raise ValueError("Invalid admin key format. Expected format: id:secret")

        key_id, secret = parts
        if not key_id or not secret:
            raise ValueError("Admin key ID and secret cannot be empty")

        # Validate key ID format (should be hex string)
        if not re.match(r"^[a-f0-9]{24}$", key_id):
            raise ValueError("Invalid admin key ID format")

        return v

    @field_validator("content_key")
    @classmethod
    def validate_content_key(cls, v: Optional[str]) -> Optional[str]:
        """Validate content key format."""
        if v is None:
            return v

        # Content keys should be hex strings (typically 24-26 characters)
        if not re.match(r"^[a-f0-9]{24,26}$", v):
            raise ValueError("Invalid content key format")

        return v

    @field_validator("timeout")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        """Validate timeout value."""
        if v <= 0:
            raise ValueError("Timeout must be greater than 0")
        if v > 300:  # 5 minutes max
            raise ValueError("Timeout cannot exceed 300 seconds")
        return v

    @field_validator("retry_attempts")
    @classmethod
    def validate_retry_attempts(cls, v: int) -> int:
        """Validate retry attempts value."""
        if v < 0:
            raise ValueError("Retry attempts cannot be negative")
        if v > 10:
            raise ValueError("Retry attempts cannot exceed 10")
        return v

    def model_dump(self, **kwargs: Any) -> Dict[str, Any]:
        """Convert profile to dictionary with proper string conversion."""
        data = super().model_dump(**kwargs)
        # Convert HttpUrl to string and remove trailing slash for consistency
        if "url" in data:
            data["url"] = str(data["url"]).rstrip("/")
        return data

    def get_admin_key_parts(self) -> tuple[str, str]:
        """Get admin key ID and secret."""
        if not self.admin_key:
            raise ValueError("Admin key not configured")

        key_id, secret = self.admin_key.split(":", 1)
        return key_id, secret


class ConfigManager:
    """Manages configuration profiles for Ghost CMS instances."""

    def __init__(self, config_dir: Optional[Path] = None) -> None:
        """Initialize configuration manager.

        Args:
            config_dir: Configuration directory path. If None, uses default.
        """
        self.config_dir = config_dir or Path.home() / ".ghostctl"
        self.config_file = self.config_dir / "config.toml"
        self.profiles_dir = self.config_dir / "profiles"

        # Ensure directories exist
        self.config_dir.mkdir(exist_ok=True)
        self.profiles_dir.mkdir(exist_ok=True)

        # Load existing configuration
        self._profiles: Dict[str, Profile] = {}
        self._active_profile: Optional[str] = None
        self._load_config()

    def create_profile(
        self,
        name: str,
        url: str,
        admin_key: Optional[str] = None,
        content_key: Optional[str] = None,
        version: str = "v5.0",
        timeout: int = 30,
        retry_attempts: int = 3,
        validate_connection: bool = False,
    ) -> Profile:
        """Create a new configuration profile.

        Args:
            name: Profile name
            url: Ghost CMS instance URL
            admin_key: Admin API key
            content_key: Content API key
            version: Ghost API version
            timeout: Request timeout in seconds
            retry_attempts: Number of retry attempts
            validate_connection: Whether to validate connection during creation

        Returns:
            Created profile

        Raises:
            ConfigError: If profile creation fails
        """
        if name in self._profiles:
            raise ConfigError(f"Profile '{name}' already exists")

        # Validate required fields
        if not admin_key and not content_key:
            raise ConfigError("Either admin_key or content_key is required")

        try:
            # Validate URL format
            parsed_url = urlparse(url)
            if not parsed_url.scheme or not parsed_url.netloc:
                raise ConfigError("Invalid URL format")

            profile = Profile(
                name=name,
                url=url,
                admin_key=admin_key,
                content_key=content_key,
                version=version,
                timeout=timeout,
                retry_attempts=retry_attempts,
            )

            if validate_connection:
                self._validate_connection(profile)

            self._profiles[name] = profile
            self._save_profile(profile)
            self._save_config()

            return profile

        except Exception as e:
            if isinstance(e, ConfigError):
                raise
            raise ConfigError(f"Failed to create profile: {e}")

    def get_profile_config(self, name: str) -> Dict[str, Any]:
        """Get configuration for a specific profile.

        Args:
            name: Profile name

        Returns:
            Profile configuration as dictionary

        Raises:
            ConfigError: If profile doesn't exist
        """
        if name not in self._profiles:
            raise ConfigError(f"Profile '{name}' not found")

        return self._profiles[name].model_dump()

    def list_profiles(self) -> List[Dict[str, Any]]:
        """List all available profiles.

        Returns:
            List of profile configurations
        """
        profiles = []
        for profile in self._profiles.values():
            profile_dict = profile.model_dump()
            profile_dict["active"] = profile.name == self._active_profile
            profiles.append(profile_dict)

        return profiles

    def set_active_profile(self, name: str) -> None:
        """Set the active profile.

        Args:
            name: Profile name to set as active

        Raises:
            ConfigError: If profile doesn't exist
        """
        if name not in self._profiles:
            raise ConfigError(f"Profile '{name}' not found")

        # Update active status
        for profile in self._profiles.values():
            profile.active = profile.name == name

        self._active_profile = name
        self._save_config()

    def get_active_profile(self) -> Optional[str]:
        """Get the name of the active profile.

        Returns:
            Active profile name or None if no profile is active
        """
        return self._active_profile

    def get_default_profile(self) -> Profile:
        """Get the default (active) profile.

        Returns:
            Default profile

        Raises:
            ConfigError: If no default profile is set
        """
        if not self._active_profile:
            raise ConfigError("No default profile set")

        return self._profiles[self._active_profile]

    def get_profile(self, name: str) -> Profile:
        """Get a specific profile by name.

        Args:
            name: Profile name

        Returns:
            Profile instance

        Raises:
            ConfigError: If profile doesn't exist
        """
        if name not in self._profiles:
            raise ConfigError(f"Profile '{name}' not found")

        return self._profiles[name]

    def get_active_config(self) -> Dict[str, Any]:
        """Get configuration for the active profile.

        Returns:
            Active profile configuration

        Raises:
            ConfigError: If no active profile is set
        """
        if not self._active_profile:
            raise ConfigError("No active profile set")

        return self.get_profile_config(self._active_profile)

    def delete_profile(self, name: str) -> None:
        """Delete a configuration profile.

        Args:
            name: Profile name to delete

        Raises:
            ConfigError: If profile doesn't exist
        """
        if name not in self._profiles:
            raise ConfigError(f"Profile '{name}' not found")

        # Clear active profile if deleting the active one
        if self._active_profile == name:
            self._active_profile = None

        # Remove profile
        del self._profiles[name]

        # Remove profile file
        profile_file = self.profiles_dir / f"{name}.json"
        if profile_file.exists():
            profile_file.unlink()

        self._save_config()

    def export_profile(self, name: str, file_path: Path) -> None:
        """Export a profile to a file.

        Args:
            name: Profile name to export
            file_path: Path to export file

        Raises:
            ConfigError: If profile doesn't exist or export fails
        """
        if name not in self._profiles:
            raise ConfigError(f"Profile '{name}' not found")

        try:
            profile_data = self._profiles[name].model_dump()
            # Remove sensitive data for export
            if "admin_key" in profile_data:
                del profile_data["admin_key"]

            with open(file_path, "w") as f:
                json.dump(profile_data, f, indent=2, default=str)

        except Exception as e:
            raise ConfigError(f"Failed to export profile: {e}")

    def import_profile(self, file_path: Path, overwrite: bool = False) -> Profile:
        """Import a profile from a file.

        Args:
            file_path: Path to import file
            overwrite: Whether to overwrite existing profile

        Returns:
            Imported profile

        Raises:
            ConfigError: If import fails
        """
        try:
            with open(file_path, "r") as f:
                profile_data = json.load(f)

            name = profile_data.get("name")
            if not name:
                raise ConfigError("Profile name not found in import file")

            if name in self._profiles and not overwrite:
                raise ConfigError(f"Profile '{name}' already exists. Use overwrite=True to replace.")

            # Create profile from imported data
            profile = Profile(**profile_data)
            self._profiles[name] = profile
            self._save_profile(profile)
            self._save_config()

            return profile

        except Exception as e:
            if isinstance(e, ConfigError):
                raise
            raise ConfigError(f"Failed to import profile: {e}")

    def has_environment_config(self) -> bool:
        """Check if environment variables provide sufficient configuration.

        Returns:
            True if environment variables can be used for configuration
        """
        env_url = os.getenv("GHOST_API_URL")
        env_admin_key = os.getenv("GHOST_ADMIN_API_KEY")
        env_content_key = os.getenv("GHOST_CONTENT_API_KEY")

        return bool(env_url and (env_admin_key or env_content_key))

    def get_environment_config(self) -> Dict[str, Any]:
        """Get configuration from environment variables.

        Returns:
            Configuration dictionary from environment variables

        Raises:
            ConfigError: If insufficient environment configuration
        """
        env_url = os.getenv("GHOST_API_URL")
        env_admin_key = os.getenv("GHOST_ADMIN_API_KEY")
        env_content_key = os.getenv("GHOST_CONTENT_API_KEY")

        if not env_url:
            raise ConfigError("GHOST_API_URL environment variable is required")

        if not (env_admin_key or env_content_key):
            raise ConfigError(
                "Either GHOST_ADMIN_API_KEY or GHOST_CONTENT_API_KEY environment variable is required"
            )

        return {
            "name": "environment",
            "url": env_url,
            "admin_key": env_admin_key,
            "content_key": env_content_key,
            "version": "v5.0",
            "timeout": 30,
            "retry_attempts": 3,
            "active": True,
        }

    def _validate_connection(self, profile: Profile) -> None:
        """Validate connection to Ghost instance.

        Args:
            profile: Profile to validate

        Raises:
            ConfigError: If connection validation fails
        """
        try:
            # Make a simple request to check connectivity
            url = f"{profile.url}/ghost/api/admin/site/"
            response = requests.get(url, timeout=profile.timeout)

            if response.status_code not in [200, 401]:  # 401 is expected without auth
                raise ConfigError(f"Failed to connect to Ghost instance: HTTP {response.status_code}")

        except requests.exceptions.RequestException as e:
            raise ConfigError(f"Failed to connect to Ghost instance: {e}")

    def _load_config(self) -> None:
        """Load configuration from file."""
        if not self.config_file.exists():
            return

        try:
            with open(self.config_file, "rb") as f:
                config_data = tomllib.load(f)

            self._active_profile = config_data.get("active_profile")

            # Load individual profile files
            for profile_file in self.profiles_dir.glob("*.json"):
                try:
                    with open(profile_file, "r") as f:
                        profile_data = json.load(f)

                    profile = Profile(**profile_data)
                    self._profiles[profile.name] = profile
                except Exception as e:
                    # Log warning but continue loading other profiles
                    print(f"Warning: Failed to load profile {profile_file}: {e}")

        except Exception as e:
            raise ConfigError(f"Failed to load configuration: {e}")

    def _save_config(self) -> None:
        """Save configuration to file."""
        try:
            config_data = {
                "active_profile": self._active_profile,
                "version": "1.0",
            }

            # Create TOML content manually since tomllib is read-only
            toml_content = f"""# Ghost CMS CLI Configuration
version = "{config_data['version']}"
active_profile = {f'"{config_data["active_profile"]}"' if config_data["active_profile"] else "null"}
"""

            with open(self.config_file, "w") as f:
                f.write(toml_content)

        except Exception as e:
            raise ConfigError(f"Failed to save configuration: {e}")

    def _save_profile(self, profile: Profile) -> None:
        """Save individual profile to file.

        Args:
            profile: Profile to save
        """
        try:
            profile_file = self.profiles_dir / f"{profile.name}.json"
            profile_data = profile.model_dump()

            with open(profile_file, "w") as f:
                json.dump(profile_data, f, indent=2, default=str)

        except Exception as e:
            raise ConfigError(f"Failed to save profile: {e}")