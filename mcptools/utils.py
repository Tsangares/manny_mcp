"""
Shared utility functions for MCP server.
"""
import re
from pathlib import Path
from typing import List, Dict, Any
from mcp.types import TextContent
import json


def parse_maven_errors(output: str) -> List[Dict[str, Any]]:
    """
    Parse Maven output for compilation errors.

    Args:
        output: Maven command output (stdout + stderr)

    Returns:
        List of error dicts with file, line, message
    """
    errors = []
    # Match patterns like: [ERROR] /path/to/File.java:[42,15] error message
    error_pattern = re.compile(
        r'\[ERROR\]\s+([^:]+):?\[?(\d+)?[,\]]?\s*(.+)'
    )

    for line in output.split('\n'):
        if '[ERROR]' in line:
            match = error_pattern.match(line.strip())
            if match:
                file_path = match.group(1).strip()
                line_num = match.group(2)
                message = match.group(3).strip() if match.group(3) else line
                errors.append({
                    "file": file_path,
                    "line": int(line_num) if line_num else None,
                    "message": message
                })
            else:
                # Generic error line
                errors.append({
                    "file": None,
                    "line": None,
                    "message": line.replace('[ERROR]', '').strip()
                })
    return errors


def parse_maven_warnings(output: str) -> List[str]:
    """Parse Maven output for warnings"""
    warnings = []
    for line in output.split('\n'):
        if '[WARNING]' in line:
            warnings.append(line.replace('[WARNING]', '').strip())
    return warnings


def resolve_plugin_path(file: str | Path, plugin_dir: str | Path) -> Path:
    """
    Resolve file path relative to plugin directory.

    Args:
        file: Filename or path (absolute or relative)
        plugin_dir: Plugin directory root

    Returns:
        Resolved absolute path
    """
    file_path = Path(file)

    if file_path.is_absolute():
        return file_path

    # Relative path - search within plugin directory
    plugin_path = Path(plugin_dir)
    if (plugin_path / file).exists():
        return plugin_path / file

    # Search recursively using glob
    matches = list(plugin_path.rglob(file))
    if matches:
        return matches[0]  # Return first match

    # Not found - return path anyway (will error downstream)
    return plugin_path / file


def format_tool_response(data: Any) -> List[TextContent]:
    """
    Format tool response as MCP TextContent.

    Handles common patterns:
    - dict -> JSON
    - list of MCP content -> pass through
    - other -> str conversion

    Args:
        data: Tool response data

    Returns:
        List of MCP content objects
    """
    if isinstance(data, list) and all(hasattr(item, 'type') for item in data):
        # Already in MCP format (list of TextContent/ImageContent/etc)
        return data
    elif isinstance(data, dict):
        return [TextContent(type="text", text=json.dumps(data, indent=2))]
    else:
        return [TextContent(type="text", text=str(data))]


def extract_category_from_description(description: str) -> str:
    """
    Extract category from tool description.

    Descriptions follow format: "[Category] description text"

    Args:
        description: Tool description string

    Returns:
        Category name (or "general" if no category found)
    """
    match = re.match(r'\[([^\]]+)\]', description)
    if match:
        return match.group(1)
    return "general"


def group_tools_by_category(tools: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, str]]]:
    """
    Group tools by category extracted from descriptions.

    Args:
        tools: List of tool dicts with 'name' and 'description'

    Returns:
        Dict mapping category -> list of tools
    """
    by_category = {}

    for tool in tools:
        category = extract_category_from_description(tool.get("description", ""))

        if category not in by_category:
            by_category[category] = []

        by_category[category].append({
            "name": tool["name"],
            "description": tool.get("description", "")
        })

    return by_category
