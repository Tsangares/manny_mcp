"""
Path normalization utilities for manny plugin development.

Handles conversion between:
- Absolute paths: /home/wil/Desktop/manny/utility/File.java
- Symlink paths: manny_src/utility/File.java
- Relative paths: utility/File.java
"""

import os
from pathlib import Path
from typing import Union


# Project root (where manny-mcp lives)
MCP_ROOT = Path(__file__).parent.parent.absolute()

# Symlink to manny plugin (manny_src -> /home/wil/Desktop/manny)
MANNY_SYMLINK = MCP_ROOT / "manny_src"


def normalize_path(path: Union[str, Path], plugin_directory: Union[str, Path]) -> Path:
    """
    Normalize a path to absolute form, handling symlinks and relative paths.

    Accepts:
    - Absolute paths: /home/wil/Desktop/manny/utility/File.java
    - Symlink paths: manny_src/utility/File.java
    - Relative paths: utility/File.java (resolved against plugin_directory)

    Args:
        path: Path to normalize
        plugin_directory: Absolute path to manny plugin (from config)

    Returns:
        Absolute Path object

    Examples:
        >>> normalize_path("manny_src/utility/File.java", "/home/wil/Desktop/manny")
        Path('/home/wil/Desktop/manny/utility/File.java')

        >>> normalize_path("/home/wil/Desktop/manny/CLAUDE.md", "/home/wil/Desktop/manny")
        Path('/home/wil/Desktop/manny/CLAUDE.md')

        >>> normalize_path("utility/File.java", "/home/wil/Desktop/manny")
        Path('/home/wil/Desktop/manny/utility/File.java')
    """
    path = Path(path)
    plugin_directory = Path(plugin_directory)

    # Already absolute - validate it's within plugin_directory or return as-is
    if path.is_absolute():
        return path.resolve()

    # Check if it starts with manny_src (symlink-based path)
    parts = path.parts
    if parts and parts[0] == "manny_src":
        # Remove manny_src prefix and resolve against plugin_directory
        relative_path = Path(*parts[1:]) if len(parts) > 1 else Path(".")
        return (plugin_directory / relative_path).resolve()

    # Otherwise, treat as relative to plugin_directory
    return (plugin_directory / path).resolve()


def to_symlink_path(absolute_path: Union[str, Path], plugin_directory: Union[str, Path]) -> str:
    """
    Convert an absolute path to symlink-relative form for display.

    Args:
        absolute_path: Absolute path to manny plugin file
        plugin_directory: Absolute path to manny plugin (from config)

    Returns:
        Symlink-relative path string (e.g., "manny_src/utility/File.java")

    Examples:
        >>> to_symlink_path("/home/wil/Desktop/manny/CLAUDE.md", "/home/wil/Desktop/manny")
        'manny_src/CLAUDE.md'
    """
    absolute_path = Path(absolute_path).resolve()
    plugin_directory = Path(plugin_directory).resolve()

    try:
        # Get relative path from plugin_directory
        relative = absolute_path.relative_to(plugin_directory)
        return f"manny_src/{relative}"
    except ValueError:
        # Path is not relative to plugin_directory, return as-is
        return str(absolute_path)


def ensure_within_plugin(path: Union[str, Path], plugin_directory: Union[str, Path]) -> Path:
    """
    Ensure a path is within the plugin directory (security check).

    Args:
        path: Path to check
        plugin_directory: Absolute path to manny plugin

    Returns:
        Normalized absolute path

    Raises:
        ValueError: If path is outside plugin_directory
    """
    normalized = normalize_path(path, plugin_directory)
    plugin_directory = Path(plugin_directory).resolve()

    try:
        normalized.relative_to(plugin_directory)
        return normalized
    except ValueError:
        raise ValueError(
            f"Path {path} is outside plugin directory {plugin_directory}. "
            f"For security, only paths within the plugin directory are allowed."
        )


def list_java_files(base_path: Union[str, Path], plugin_directory: Union[str, Path], pattern: str = "**/*.java") -> list[str]:
    """
    List Java files in a directory, returning symlink-relative paths.

    Args:
        base_path: Base directory to search (can be symlink-relative)
        plugin_directory: Absolute path to manny plugin
        pattern: Glob pattern (default: **/*.java)

    Returns:
        List of symlink-relative paths

    Example:
        >>> list_java_files("manny_src/utility", "/home/wil/Desktop/manny")
        ['manny_src/utility/PlayerHelpers.java', 'manny_src/utility/CombatSystem.java', ...]
    """
    base_path = normalize_path(base_path, plugin_directory)

    if not base_path.exists():
        return []

    java_files = []
    for file_path in base_path.glob(pattern):
        if file_path.is_file():
            symlink_path = to_symlink_path(file_path, plugin_directory)
            java_files.append(symlink_path)

    return sorted(java_files)
