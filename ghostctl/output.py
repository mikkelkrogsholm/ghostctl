"""Output formatting utilities.

This module re-exports output classes for backward compatibility
with test imports.
"""

# Re-export from render for backward compatibility
from .render import OutputFormatter

# Aliases for compatibility
TableRenderer = OutputFormatter
JSONRenderer = OutputFormatter
YAMLRenderer = OutputFormatter

__all__ = ["OutputFormatter", "TableRenderer", "JSONRenderer", "YAMLRenderer"]