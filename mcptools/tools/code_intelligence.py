"""
Code intelligence tools for manny plugin development.

Provides IDE-like features: find usages, call graph, go-to-definition, etc.
"""

import json
import re
import subprocess
from pathlib import Path
from typing import Optional
from mcp.types import Tool, TextContent

from ..config import ServerConfig
from ..registry import registry
from ..path_utils import normalize_path, to_symlink_path, list_java_files
from ..utils import maybe_truncate_response


# =============================================================================
# FIND_USAGES
# =============================================================================

def find_usages_impl(symbol: str, context_lines: int = 3, plugin_dir: str = None) -> dict:
    """
    Find all usages of a symbol (method, class, field) in the manny plugin.

    Uses ripgrep for fast searching.

    Args:
        symbol: Symbol to search for (e.g., "interactWithNPC", "GameEngine", "shouldInterrupt")
        context_lines: Number of context lines to show
        plugin_dir: Path to manny plugin directory

    Returns:
        {"usages": [{"file": str, "line": int, "context": str, "match": str}], "total": int}
    """
    if plugin_dir is None:
        config = ServerConfig.load()
        plugin_dir = str(config.plugin_directory)

    plugin_dir = Path(plugin_dir)

    # Use ripgrep to find usages (fast and respects .gitignore)
    try:
        # Pattern: whole word match to avoid partial matches
        result = subprocess.run(
            ["rg", "--json", "-w", "-C", str(context_lines), symbol, str(plugin_dir)],
            capture_output=True,
            text=True
        )

        usages = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue

            try:
                entry = json.loads(line)  # ripgrep JSON output
                if entry.get('type') == 'match':
                    data = entry['data']
                    file_path = data['path']['text']
                    line_number = data['line_number']
                    match_text = data['lines']['text'].strip()

                    usages.append({
                        "file": to_symlink_path(plugin_dir / file_path, plugin_dir),
                        "line": line_number,
                        "match": match_text
                    })
            except:
                continue

        return {
            "symbol": symbol,
            "usages": usages,
            "total": len(usages),
            "context_lines": context_lines
        }

    except FileNotFoundError:
        # Fallback to grep if ripgrep not available
        try:
            result = subprocess.run(
                ["grep", "-rn", "-w", "-C", str(context_lines), symbol, "."],
                cwd=plugin_dir,
                capture_output=True,
                text=True
            )

            usages = []
            for line in result.stdout.strip().split('\n'):
                if not line or line.startswith('--'):
                    continue

                match = re.match(r'([^:]+):(\d+):(.*)', line)
                if match:
                    file_path, line_num, match_text = match.groups()
                    usages.append({
                        "file": to_symlink_path(plugin_dir / file_path, plugin_dir),
                        "line": int(line_num),
                        "match": match_text.strip()
                    })

            return {
                "symbol": symbol,
                "usages": usages,
                "total": len(usages),
                "context_lines": context_lines
            }

        except Exception as e:
            return {
                "error": f"Search failed: {e}",
                "symbol": symbol
            }


@registry.tool(
    name="find_usages",
    description=(
        "Find all usages of a symbol (method, class, field) in the manny plugin.\n\n"
        "Returns file locations and context for each usage.\n\n"
        "Examples:\n"
        "- find_usages(symbol='interactWithNPC') - Find where this method is called\n"
        "- find_usages(symbol='GameEngine') - Find where this class is used\n"
        "- find_usages(symbol='shouldInterrupt', context_lines=5) - More context"
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Symbol to search for (method, class, field name)"
            },
            "context_lines": {
                "type": "integer",
                "description": "Number of context lines to show (default: 3)",
                "default": 3
            }
        },
        "required": ["symbol"]
    }
)
async def find_usages(symbol: str, context_lines: int = 3) -> list[TextContent]:
    """MCP tool: Find all usages of a symbol"""
    result = find_usages_impl(symbol=symbol, context_lines=context_lines)

    if "error" in result:
        return [TextContent(type="text", text=f"Error: {result['error']}")]

    # Truncate large results (writes to file, returns summary)
    truncated = maybe_truncate_response(result, prefix="find_usages_output")

    if truncated.get("truncated"):
        # Return summary with file path
        output = f"# Usages of '{result['symbol']}'\n\n"
        output += f"Found {result['total']} usage(s) - **response truncated**\n\n"
        output += f"Full results written to: `{truncated['full_output_path']}`\n\n"
        output += "## Preview (first 5 usages):\n\n"
        for usage in result['usages'][:5]:
            output += f"- {usage['file']}:{usage['line']}\n"
        return [TextContent(type="text", text=output)]

    # Normal output for small results
    output = f"# Usages of '{result['symbol']}'\n\n"
    output += f"Found {result['total']} usage(s)\n\n"

    if result['usages']:
        for usage in result['usages']:
            output += f"## {usage['file']}:{usage['line']}\n"
            output += f"```java\n{usage['match']}\n```\n\n"
    else:
        output += f"No usages found for '{result['symbol']}'\n"

    return [TextContent(type="text", text=output)]


# =============================================================================
# FIND_DEFINITION
# =============================================================================

def find_definition_impl(symbol: str, symbol_type: Optional[str] = None, plugin_dir: str = None) -> dict:
    """
    Find the definition of a symbol (class, method, field).

    Args:
        symbol: Symbol name (e.g., "GameEngine", "interactWithNPC")
        symbol_type: Optional type hint: "class", "method", "field" (improves accuracy)
        plugin_dir: Path to manny plugin directory

    Returns:
        {"file": str, "line": int, "signature": str, "type": str} or {"error": str}
    """
    if plugin_dir is None:
        config = ServerConfig.load()
        plugin_dir = str(config.plugin_directory)

    plugin_dir = Path(plugin_dir)

    # Build search patterns based on type
    patterns = []

    if symbol_type == "class" or symbol_type is None:
        patterns.append((f"class {symbol}", "class"))
        patterns.append((f"interface {symbol}", "interface"))
        patterns.append((f"enum {symbol}", "enum"))

    if symbol_type == "method" or symbol_type is None:
        patterns.append((f"\\s{symbol}\\s*\\(", "method"))

    if symbol_type == "field" or symbol_type is None:
        patterns.append((f"\\s{symbol}\\s*;", "field"))
        patterns.append((f"\\s{symbol}\\s*=", "field"))

    # Try each pattern
    for pattern, detected_type in patterns:
        try:
            result = subprocess.run(
                ["rg", "--json", "-n", pattern, str(plugin_dir)],
                capture_output=True,
                text=True
            )

            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                    if entry.get('type') == 'match':
                        data = entry['data']
                        file_path = data['path']['text']
                        line_number = data['line_number']
                        signature = data['lines']['text'].strip()

                        return {
                            "symbol": symbol,
                            "type": detected_type,
                            "file": to_symlink_path(plugin_dir / file_path, plugin_dir),
                            "line": line_number,
                            "signature": signature
                        }
                except:
                    continue

        except:
            continue

    return {
        "error": f"Definition not found for '{symbol}'",
        "symbol": symbol,
        "searched_types": [symbol_type] if symbol_type else ["class", "method", "field"]
    }


@registry.tool(
    name="find_definition",
    description=(
        "Find the definition of a symbol (class, method, field) in the manny plugin.\n\n"
        "Returns file location, line number, and signature.\n\n"
        "Examples:\n"
        "- find_definition(symbol='GameEngine', symbol_type='class')\n"
        "- find_definition(symbol='interactWithNPC', symbol_type='method')\n"
        "- find_definition(symbol='shouldInterrupt')"
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Symbol name (class, method, or field)"
            },
            "symbol_type": {
                "type": "string",
                "enum": ["class", "method", "field"],
                "description": "Optional type hint for better accuracy"
            }
        },
        "required": ["symbol"]
    }
)
async def find_definition(symbol: str, symbol_type: Optional[str] = None) -> list[TextContent]:
    """MCP tool: Find the definition of a symbol"""
    result = find_definition_impl(symbol=symbol, symbol_type=symbol_type)

    if "error" in result:
        return [TextContent(
            type="text",
            text=f"Error: {result['error']}\n\nSearched for: {', '.join(result['searched_types'])}"
        )]

    output = f"# Definition of '{result['symbol']}' ({result['type']})\n\n"
    output += f"**File:** {result['file']}:{result['line']}\n\n"
    output += f"**Signature:**\n```java\n{result['signature']}\n```\n"

    return [TextContent(type="text", text=output)]


# =============================================================================
# GET_CALL_GRAPH
# =============================================================================

def get_call_graph_impl(method: str, depth: int = 2, plugin_dir: str = None) -> dict:
    """
    Show what a method calls (dependencies) and what calls it (dependents).

    Args:
        method: Method name (e.g., "handleBankOpen")
        depth: How many levels to traverse (default: 2)
        plugin_dir: Path to manny plugin directory

    Returns:
        {
            "method": str,
            "callers": [{"method": str, "file": str, "line": int}],
            "callees": [{"method": str, "file": str, "line": int}],
            "depth": int
        }
    """
    if plugin_dir is None:
        config = ServerConfig.load()
        plugin_dir = str(config.plugin_directory)

    plugin_dir = Path(plugin_dir)

    # Find callers (what calls this method)
    callers = []
    caller_pattern = f"{method}\\s*\\("

    try:
        result = subprocess.run(
            ["rg", "--json", "-n", caller_pattern, str(plugin_dir)],
            capture_output=True,
            text=True
        )

        for line in result.stdout.strip().split('\n'):
            if not line:
                continue

            try:
                entry = json.loads(line)
                if entry.get('type') == 'match':
                    data = entry['data']
                    file_path = data['path']['text']
                    line_number = data['line_number']
                    context = data['lines']['text'].strip()

                    # Extract calling method name if possible
                    match = re.search(r'(\w+)\s*\([^)]*\)\s*\{[^}]*' + re.escape(method), context)
                    calling_method = match.group(1) if match else "unknown"

                    callers.append({
                        "method": calling_method,
                        "file": to_symlink_path(plugin_dir / file_path, plugin_dir),
                        "line": line_number,
                        "context": context
                    })
            except:
                continue

    except:
        pass

    # Find callees (what this method calls)
    # This is more complex - need to find the method definition first
    callees = []

    # Find method definition
    definition = find_definition_impl(symbol=method, symbol_type="method", plugin_dir=str(plugin_dir))

    if "error" not in definition:
        # Read the method body
        try:
            file_path = normalize_path(definition['file'], plugin_dir)
            with open(file_path, 'r') as f:
                lines = f.readlines()

            start_line = definition['line'] - 1
            # Find end of method (simple heuristic: look for closing brace at same indent level)
            indent_level = 0
            method_lines = []

            for i in range(start_line, min(start_line + 200, len(lines))):  # Limit to 200 lines
                line = lines[i]
                method_lines.append(line)

                indent_level += line.count('{') - line.count('}')

                if indent_level <= 0 and i > start_line:
                    break

            method_body = ''.join(method_lines)

            # Find method calls in the body (simple pattern)
            call_pattern = r'(\w+)\s*\('
            for match in re.finditer(call_pattern, method_body):
                called_method = match.group(1)

                # Filter out keywords and common methods
                if called_method not in ['if', 'for', 'while', 'switch', 'return', 'new', 'super', 'this']:
                    callees.append({
                        "method": called_method,
                        "file": definition['file'],
                        "line": definition['line']
                    })

            # Deduplicate callees
            seen = set()
            unique_callees = []
            for callee in callees:
                if callee['method'] not in seen:
                    seen.add(callee['method'])
                    unique_callees.append(callee)
            callees = unique_callees

        except:
            pass

    return {
        "method": method,
        "callers": callers[:20],  # Limit to 20 callers
        "callees": callees[:20],  # Limit to 20 callees
        "depth": depth,
        "total_callers": len(callers),
        "total_callees": len(callees)
    }


@registry.tool(
    name="get_call_graph",
    description=(
        "Show what a method calls (dependencies) and what calls it (dependents).\n\n"
        "Returns a call graph showing callers and callees.\n\n"
        "Example:\n"
        "- get_call_graph(method='handleBankOpen', depth=2)"
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "description": "Method name to analyze"
            },
            "depth": {
                "type": "integer",
                "description": "How many levels to traverse (default: 2)",
                "default": 2
            }
        },
        "required": ["method"]
    }
)
async def get_call_graph(method: str, depth: int = 2) -> list[TextContent]:
    """MCP tool: Get call graph for a method"""
    result = get_call_graph_impl(method=method, depth=depth)

    output = f"# Call Graph: {result['method']}\n\n"

    output += f"## Callers (what calls {result['method']})\n"
    output += f"Showing {len(result['callers'])} of {result['total_callers']} callers\n\n"

    if result['callers']:
        for caller in result['callers']:
            output += f"- **{caller['method']}** at {caller['file']}:{caller['line']}\n"
    else:
        output += "No callers found\n"

    output += f"\n## Callees (what {result['method']} calls)\n"
    output += f"Showing {len(result['callees'])} of {result['total_callees']} callees\n\n"

    if result['callees']:
        for callee in result['callees']:
            output += f"- **{callee['method']}**\n"
    else:
        output += "No callees found\n"

    return [TextContent(type="text", text=output)]
