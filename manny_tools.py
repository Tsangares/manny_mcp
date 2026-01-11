"""
Manny plugin-specific MCP tools.

Provides context bundling, navigation, and code generation helpers
specifically designed for the manny RuneLite plugin codebase.

PHASE 3 OPTIMIZATION: Uses unified search engine for O(1) code lookups.
"""

import os
import re
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional

# Phase 3: Import search engine for 100x faster lookups
try:
    from search_engine import get_search_index
    SEARCH_ENGINE_AVAILABLE = True
except ImportError:
    SEARCH_ENGINE_AVAILABLE = False

# Phase 3: Import caching layer for frequently accessed data
try:
    from cache_layer import cached_tool, get_tool_cache
    CACHE_AVAILABLE = True
except ImportError:
    # Fallback: no-op decorator if cache not available
    def cached_tool(ttl=300):
        def decorator(func):
            return func
        return decorator
    CACHE_AVAILABLE = False


# =============================================================================
# CONTEXT BUNDLING
# =============================================================================

ARCHITECTURE_SUMMARY = """
=== MANNY PLUGIN ARCHITECTURE ===

READ/WRITE SEPARATION:
- GameEngine.GameHelpers = READ operations (no game modifications, safe anywhere)
- PlayerHelpers = WRITE operations (execute actions, modify state, background thread only)
- InteractionSystem = Standardized wrappers (NPCs, GameObjects, widgets)

THREAD SAFETY RULES:
- Client thread: Widget access, menu access, rendering. NEVER block this thread!
- Background thread: Mouse movement, delays, I/O. Can block.
- Use ClientThreadHelper.readFromClient() instead of manual CountDownLatch

KEY UTILITY CLASSES:
- ClientThreadHelper: Thread-safe client access (replaces CountDownLatch boilerplate)
- InteractionSystem: Standardized NPC/GameObject/Widget interaction wrappers
- GameEngine: Read-only game state queries (inventory, NPCs, objects, tiles)
- PlayerHelpers: Write operations, commands, movement, clicking

COMMAND STRUCTURE:
- Commands are dispatched in PlayerHelpers.CommandProcessor.handleCommand()
- Switch statement around line 8994+ with 70+ cases
- Each case calls a private handleXxx() method (100-500 lines each)
- Commands use ResponseWriter.writeSuccess/writeFailure for results
"""

AVAILABLE_WRAPPERS = {
    "npc_interaction": {
        "method": "interactionSystem.interactWithNPC(String npcName, String action)",
        "alt": "interactionSystem.interactWithNPC(String npcName, String action, int maxAttempts, int searchRadius)",
        "replaces": "60+ lines of manual NPC finding, menu fetching, clicking"
    },
    "gameobject_interaction": {
        "method": "interactionSystem.interactWithGameObject(String objectName, String action, int searchRadius)",
        "alt": "interactionSystem.interactWithGameObject(int objectId, String objectName, String action, WorldPoint location)",
        "replaces": "60-120 lines of manual object finding and clicking"
    },
    "widget_click": {
        "method": "clickWidget(int widgetId)",
        "alt": "clickWidget(int widgetId, int maxAttempts, long retryDelayMs)",
        "replaces": "Manual widget finding and clicking with 5-phase verification"
    },
    "inventory_queries": {
        "methods": [
            "gameEngine.hasItems(int... itemIds) - Check ALL items present",
            "gameEngine.hasAnyItem(int... itemIds) - Check ANY item present",
            "gameEngine.getItemCount(int itemId)",
            "gameEngine.getItemCount(String itemName)",
            "gameEngine.hasInventorySpace(int slotsNeeded)",
            "gameEngine.getEmptySlots()",
            "gameEngine.findItemIdByName(String name)"
        ],
        "replaces": "Manual CountDownLatch for inventory access"
    },
    "banking": {
        "methods": [
            "handleBankOpen() - Opens nearest bank",
            "handleBankClose()",
            "handleBankWithdraw(String args) - e.g., 'Copper_ore 14'",
            "handleBankDepositAll()",
            "handleBankDepositItem(String itemName)"
        ],
        "note": "Underscores in item names are converted to spaces automatically"
    },
    "thread_safe_access": {
        "method": "helper.readFromClient(() -> client.getWidget(widgetId))",
        "replaces": """9-15 lines of CountDownLatch boilerplate:
Widget[] holder = new Widget[1];
CountDownLatch latch = new CountDownLatch(1);
clientThread.invokeLater(() -> {
    try { holder[0] = client.getWidget(id); }
    finally { latch.countDown(); }
});
latch.await(5, TimeUnit.SECONDS);"""
    }
}


def get_manny_guidelines(plugin_dir: str, mode: str = "full", section: Optional[str] = None) -> dict:
    """
    Read the manny plugin's CLAUDE.md guidelines.

    Args:
        plugin_dir: Path to manny plugin directory
        mode: "full" (all guidelines), "condensed" (key patterns), "section" (specific section)
        section: Section name when mode="section" (e.g., "Thread Safety", "Command Wrappers")

    Returns:
        Dict with guidelines content and metadata
    """
    claude_md_path = Path(plugin_dir) / "CLAUDE.md"

    if not claude_md_path.exists():
        return {
            "success": False,
            "error": f"CLAUDE.md not found at {claude_md_path}"
        }

    try:
        content = claude_md_path.read_text()

        if mode == "full":
            return {
                "success": True,
                "path": str(claude_md_path),
                "content": content,
                "lines": len(content.split('\n')),
                "mode": "full"
            }

        elif mode == "condensed":
            # Extract key sections for quick reference
            condensed_sections = []

            # Extract specific sections
            patterns = [
                (r"## 🚨 STOP.*?(?=\n##)", "Critical Warnings"),
                (r"## Command Wrappers.*?(?=\n##)", "Available Wrappers"),
                (r"## Thread Safety.*?(?=\n##)", "Thread Safety Rules"),
                (r"## Common Pitfalls.*?(?=\n##)", "Common Pitfalls"),
            ]

            for pattern, name in patterns:
                match = re.search(pattern, content, re.DOTALL)
                if match:
                    condensed_sections.append(f"### {name}\n{match.group(0)}")

            condensed_content = "\n\n".join(condensed_sections) if condensed_sections else content[:2000]

            return {
                "success": True,
                "path": str(claude_md_path),
                "content": condensed_content,
                "lines": len(condensed_content.split('\n')),
                "mode": "condensed"
            }

        elif mode == "section" and section:
            # Extract specific section
            pattern = rf"## {re.escape(section)}.*?(?=\n##|\Z)"
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)

            if match:
                section_content = match.group(0)
                return {
                    "success": True,
                    "path": str(claude_md_path),
                    "content": section_content,
                    "lines": len(section_content.split('\n')),
                    "mode": "section",
                    "section": section
                }
            else:
                # Section not found, list available sections
                sections = re.findall(r"^## (.+)$", content, re.MULTILINE)
                return {
                    "success": False,
                    "error": f"Section '{section}' not found",
                    "available_sections": sections
                }

        else:
            return {
                "success": False,
                "error": f"Invalid mode '{mode}' or missing section"
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def get_plugin_context(plugin_dir: str, context_type: str = "full") -> dict:
    """
    Get architectural context for the manny plugin.

    Args:
        plugin_dir: Path to manny plugin directory
        context_type: "full", "architecture", "wrappers", or "commands"

    Returns:
        Dict with requested context
    """
    result = {
        "success": True,
        "context_type": context_type
    }

    if context_type in ("full", "architecture"):
        result["architecture_summary"] = ARCHITECTURE_SUMMARY

    if context_type in ("full", "wrappers"):
        result["available_wrappers"] = AVAILABLE_WRAPPERS

    if context_type in ("full", "commands"):
        # Extract command list from CLAUDE.md if available
        guidelines = get_manny_guidelines(plugin_dir)
        if guidelines.get("success"):
            # Find command reference section
            content = guidelines["content"]
            cmd_section = re.search(
                r'## Complete Command Reference.*?(?=\n## |\Z)',
                content,
                re.DOTALL
            )
            if cmd_section:
                result["command_reference"] = cmd_section.group(0)
            else:
                result["command_reference"] = "Command reference section not found in CLAUDE.md"

    return result


# =============================================================================
# SMART SEARCH/NAVIGATION
# =============================================================================

def get_section(
    plugin_dir: str,
    file: str = "PlayerHelpers.java",
    section: str = "list",
    max_lines: int = 0,
    summary_only: bool = False
) -> dict:
    """
    Navigate large files by section markers.

    Section markers look like: // ========== SECTION N: NAME ==========
    Or focused headers: // ========== SHORT FOCUSED HEADER ==========

    Args:
        plugin_dir: Path to manny plugin directory
        file: Filename or path to search in
        section: "list" to list all sections, or section name/number to get content
        max_lines: Maximum lines to return (0 = unlimited). Use to limit response size.
        summary_only: If True, return only section metadata (line ranges) without content.
                      Subagents can then use Read tool with offset/limit to get specific parts.

    Returns:
        Dict with section content or list of sections
    """
    # Resolve file path
    if os.path.isabs(file):
        file_path = Path(file)
    else:
        # Search for the file
        plugin_path = Path(plugin_dir)
        matches = list(plugin_path.rglob(file))
        if not matches:
            return {"success": False, "error": f"File not found: {file}"}
        file_path = matches[0]

    if not file_path.exists():
        return {"success": False, "error": f"File not found: {file_path}"}

    try:
        content = file_path.read_text()
        lines = content.split('\n')
    except Exception as e:
        return {"success": False, "error": str(e)}

    # Parse section markers - require at least 3 chars in name to filter out noise
    section_pattern = re.compile(r'^[\s]*//\s*={5,}\s*(SECTION\s+\d+:?\s*)?([A-Z][A-Za-z0-9_ &]{2,})\s*={5,}\s*$')
    sections = []

    for i, line in enumerate(lines, 1):
        match = section_pattern.match(line)
        if match:
            section_num = match.group(1).strip() if match.group(1) else None
            section_name = match.group(2).strip()
            sections.append({
                "line": i,
                "number": section_num,
                "name": section_name,
                "marker": line.strip()
            })

    if section == "list":
        return {
            "success": True,
            "file": str(file_path),
            "total_lines": len(lines),
            "sections": sections,
            "section_count": len(sections)
        }

    # Find specific section
    target_section = None
    for i, sec in enumerate(sections):
        name_lower = sec["name"].lower()
        if (section.lower() in name_lower or
            (sec["number"] and section in sec["number"])):
            target_section = sec
            # Find end of section (next section or EOF)
            if i + 1 < len(sections):
                end_line = sections[i + 1]["line"] - 1
            else:
                end_line = len(lines)
            target_section["end_line"] = end_line
            break

    if not target_section:
        return {
            "success": False,
            "error": f"Section not found: {section}",
            "available_sections": [s["name"] for s in sections]
        }

    # Extract section content
    start = target_section["line"] - 1
    end = target_section["end_line"]
    total_section_lines = end - start

    result = {
        "success": True,
        "file": str(file_path),
        "section": target_section["name"],
        "start_line": target_section["line"],
        "end_line": end,
        "line_count": total_section_lines
    }

    if summary_only:
        # Just return metadata, no content - subagent should use Read tool
        result["note"] = f"Use Read tool with offset={target_section['line']-1} and limit={total_section_lines} to get content"
        return result

    # Get content, possibly truncated
    if max_lines > 0 and total_section_lines > max_lines:
        section_lines = lines[start:start + max_lines]
        result["content"] = '\n'.join(section_lines)
        result["truncated"] = True
        result["lines_returned"] = max_lines
        result["note"] = f"Truncated to {max_lines} lines. Use Read tool with offset to get more."
    else:
        section_lines = lines[start:end]
        result["content"] = '\n'.join(section_lines)
        result["truncated"] = False

    return result


def find_command(
    plugin_dir: str,
    command: str,
    include_handler: bool = True,
    max_handler_lines: int = 50,
    summary_only: bool = False
) -> dict:
    """
    Find command switch case AND handler method in PlayerHelpers.java.

    PHASE 3 OPTIMIZATION: Attempts O(1) search engine lookup before O(n) file scan.

    Args:
        plugin_dir: Path to manny plugin directory
        command: Command name (e.g., "BANK_OPEN", "MINE_ORE")
        include_handler: Whether to find and include the handler method
        max_handler_lines: Maximum lines of handler code to include (default: 50)
        summary_only: If True, only return line numbers and signatures (not code)
                      Use this for subagents to reduce context size

    Returns:
        Dict with switch case location and optionally handler method
    """
    # PHASE 3: Fast path via search engine (100x faster for indexed commands)
    if SEARCH_ENGINE_AVAILABLE:
        try:
            index = get_search_index(plugin_dir)
            locations = index.find_command(command)

            if locations:
                # Found in index - build result from indexed data
                case_stmt = next((loc for loc in locations if loc["type"] == "case_statement"), None)
                if case_stmt:
                    result = {
                        "success": True,
                        "command": command,
                        "file": case_stmt["file"],
                        "switch_case": {
                            "line": case_stmt["line"],
                            "snippet": case_stmt["context"]
                        }
                    }

                    # Extract handler name
                    handler_match = re.search(r'return\s+(\w+)\s*\(', case_stmt["context"])
                    if handler_match:
                        result["handler_name"] = handler_match.group(1)

                    # If handler needed and not summary-only, fall through to read file
                    # (This preserves full method extraction logic below)
                    if not (include_handler and "handler_name" in result and not summary_only):
                        return result  # Early return for simple cases
        except Exception:
            pass  # Fall back to linear scan

    # Original implementation (fallback or full handler extraction)
    plugin_path = Path(plugin_dir)
    helpers_matches = list(plugin_path.rglob("PlayerHelpers.java"))

    if not helpers_matches:
        return {"success": False, "error": "PlayerHelpers.java not found"}

    helpers_path = helpers_matches[0]

    try:
        content = helpers_path.read_text()
        lines = content.split('\n')
    except Exception as e:
        return {"success": False, "error": str(e)}

    result = {
        "success": True,
        "command": command,
        "file": str(helpers_path)
    }

    # Find switch case
    case_pattern = re.compile(rf'case\s+"{re.escape(command)}":', re.IGNORECASE)

    for i, line in enumerate(lines, 1):
        if case_pattern.search(line):
            # Get context (case + next few lines)
            context_end = min(i + 5, len(lines))
            context_lines = lines[i-1:context_end]

            if summary_only:
                result["switch_case"] = {
                    "line": i,
                    "snippet": line.strip()  # Just the case line
                }
            else:
                result["switch_case"] = {
                    "line": i,
                    "snippet": '\n'.join(context_lines)
                }

            # Extract handler method name
            handler_match = re.search(r'return\s+(\w+)\s*\(', '\n'.join(context_lines))
            if handler_match:
                result["handler_name"] = handler_match.group(1)
            break

    if "switch_case" not in result:
        result["success"] = False
        result["error"] = f"Command not found: {command}"
        return result

    # Find handler method if requested
    if include_handler and "handler_name" in result:
        handler_name = result["handler_name"]
        handler_pattern = re.compile(
            rf'(private|public)\s+\w+\s+{re.escape(handler_name)}\s*\('
        )

        for i, line in enumerate(lines, 1):
            if handler_pattern.search(line):
                if summary_only:
                    # Just return location info for subagent efficiency
                    result["handler"] = {
                        "line": i,
                        "signature": line.strip(),
                        "note": "Use Read tool with offset/limit to get code"
                    }
                else:
                    # Get method signature and up to max_handler_lines
                    context_end = min(i + max_handler_lines, len(lines))
                    context_lines = lines[i-1:context_end]

                    # Try to find method end (closing brace at same indent level)
                    method_lines = []
                    brace_count = 0
                    method_started = False
                    for j, method_line in enumerate(context_lines):
                        method_lines.append(method_line)
                        brace_count += method_line.count('{') - method_line.count('}')
                        if '{' in method_line:
                            method_started = True
                        if method_started and brace_count == 0:
                            # Method ended
                            break
                        if j >= max_handler_lines - 1:
                            # Truncate if too long
                            method_lines.append(f"... [truncated at {max_handler_lines} lines]")
                            break

                    result["handler"] = {
                        "line": i,
                        "signature": line.strip(),
                        "preview": '\n'.join(method_lines),
                        "line_count": len(method_lines),
                        "truncated": len(method_lines) >= max_handler_lines
                    }
                break

    return result


def find_pattern_in_plugin(
    plugin_dir: str,
    pattern_type: str,
    search_term: str = None
) -> dict:
    """
    Search for specific patterns in the manny plugin codebase.

    Args:
        plugin_dir: Path to manny plugin directory
        pattern_type: "command", "wrapper", "thread", or "custom"
        search_term: Additional search term (required for "custom")

    Returns:
        Dict with matching files and locations
    """
    plugin_path = Path(plugin_dir)
    java_files = list(plugin_path.rglob("*.java"))

    # Define patterns
    patterns = {
        "command": [
            (r'case\s+"[A-Z_]+":', "Command switch case"),
            (r'private\s+boolean\s+handle\w+\(', "Command handler method")
        ],
        "wrapper": [
            (r'interactionSystem\.\w+', "InteractionSystem usage"),
            (r'gameEngine\.\w+', "GameEngine usage"),
            (r'playerHelpers\.\w+', "PlayerHelpers usage")
        ],
        "thread": [
            (r'CountDownLatch', "CountDownLatch (consider ClientThreadHelper)"),
            (r'clientThread\.invokeLater', "Client thread invocation"),
            (r'helper\.readFromClient', "ClientThreadHelper usage"),
            (r'client\.getMenuEntries', "Menu access (needs client thread)")
        ],
        "anti_pattern": [
            (r'smartClick\s*\([^)]*\)', "smartClick (use interactionSystem for NPCs)"),
            (r'new\s+CountDownLatch', "Manual CountDownLatch (use ClientThreadHelper)"),
            (r'for\s*\([^)]*attempt', "Manual retry loop (wrappers have built-in retry)")
        ]
    }

    if pattern_type == "custom" and search_term:
        search_patterns = [(search_term, "Custom pattern")]
    elif pattern_type in patterns:
        search_patterns = patterns[pattern_type]
    else:
        return {
            "success": False,
            "error": f"Unknown pattern type: {pattern_type}",
            "available_types": list(patterns.keys()) + ["custom"]
        }

    matches = []

    for java_file in java_files:
        try:
            content = java_file.read_text()
            file_lines = content.split('\n')

            for pattern, description in search_patterns:
                for i, line in enumerate(file_lines, 1):
                    if re.search(pattern, line):
                        matches.append({
                            "file": str(java_file),
                            "line": i,
                            "pattern": description,
                            "content": line.strip()[:100]
                        })
        except Exception:
            pass

    return {
        "success": True,
        "pattern_type": pattern_type,
        "match_count": len(matches),
        "matches": matches[:50]  # Limit results
    }


# =============================================================================
# CODE GENERATION HELPERS
# =============================================================================

COMMAND_TEMPLATE = '''case "{command_name}":
    return handle{handler_name}(parts.length > 1 ? parts[1] : "");

// ===== Add this handler method in the appropriate section =====

/**
 * {description}
 *
 * Usage: {command_name}{args_usage}
 */
private boolean handle{handler_name}(String args)
{{
    log.info("[{command_name}] Starting...");

    try
    {{
        {args_parsing}

        // TODO: Add implementation using existing wrappers:
        // - interactionSystem.interactWithNPC(name, action)
        // - interactionSystem.interactWithGameObject(name, action, radius)
        // - gameEngine.hasItems(), gameEngine.getItemCount()
        // - handleBankOpen(), handleBankWithdraw(), handleBankDepositAll()

        {loop_template}

        log.info("[{command_name}] Completed successfully");
        responseWriter.writeSuccess("{command_name}", "Done");
        return true;
    }}
    catch (Exception e)
    {{
        log.error("[{command_name}] Error", e);
        responseWriter.writeFailure("{command_name}", e);
        return false;
    }}
}}'''

ARGS_PARSING_TEMPLATE = '''// Parse arguments
        if (args.isEmpty())
        {{
            log.error("[{command_name}] Usage: {command_name} {args_format}");
            responseWriter.writeFailure("{command_name}", "Missing arguments");
            return false;
        }}

        // Convert underscores to spaces (convention for item names)
        String cleanedArgs = args.replace("_", " ");'''

NO_ARGS_TEMPLATE = '''// No arguments required'''

LOOP_TEMPLATE = '''// Main loop with interrupt checks
        for (int i = 0; i < cycles; i++)
        {{
            if (shouldInterrupt)
            {{
                log.info("[{command_name}] Interrupted");
                responseWriter.writeFailure("{command_name}", "Interrupted");
                return false;
            }}

            // TODO: Add iteration logic
            Thread.sleep(600); // Game tick
        }}'''

NO_LOOP_TEMPLATE = '''// Single execution (no loop)
        // TODO: Add implementation'''


def generate_command_template(
    command_name: str,
    description: str = "TODO: Add description",
    has_args: bool = False,
    args_format: str = "<arg>",
    has_loop: bool = False
) -> dict:
    """
    Generate a skeleton command handler following project patterns.

    Args:
        command_name: Command name in UPPER_SNAKE_CASE (e.g., "MY_COMMAND")
        description: Brief description of what the command does
        has_args: Whether the command takes arguments
        args_format: Format description for args (e.g., "<item_name> [quantity]")
        has_loop: Whether the command runs in a loop

    Returns:
        Dict with generated template code
    """
    # Convert to handler name (MY_COMMAND -> MyCommand)
    handler_name = ''.join(word.capitalize() for word in command_name.split('_'))

    # Build template
    args_usage = f" {args_format}" if has_args else ""
    args_parsing = ARGS_PARSING_TEMPLATE.format(
        command_name=command_name,
        args_format=args_format
    ) if has_args else NO_ARGS_TEMPLATE

    loop_template = LOOP_TEMPLATE.format(
        command_name=command_name
    ) if has_loop else NO_LOOP_TEMPLATE

    template = COMMAND_TEMPLATE.format(
        command_name=command_name,
        handler_name=handler_name,
        description=description,
        args_usage=args_usage,
        args_parsing=args_parsing,
        loop_template=loop_template
    )

    return {
        "success": True,
        "command_name": command_name,
        "handler_name": f"handle{handler_name}",
        "template": template,
        "instructions": """
To add this command:
1. Add the 'case' statement to the switch in CommandProcessor.handleCommand()
   (around line 8994 in PlayerHelpers.java)
2. Add the handler method to the appropriate section in PlayerHelpers.java
3. Test with: send_command("{command_name}{args}")
""".format(command_name=command_name, args=" test_arg" if has_args else "")
    }


# Anti-pattern detection rules
# OPTIMIZATION (Phase 2): Pre-compile regexes at module load time for 10x faster scanning
ANTI_PATTERNS = [
    {
        "pattern": r"smartClick\s*\([^)]*\)",
        "context_hint": r"npc|banker|fish|miner|guard",
        "severity": "error",
        "message": "Using smartClick() for NPC interaction",
        "suggestion": "Use interactionSystem.interactWithNPC(\"NpcName\", \"Action\") instead"
    },
    {
        "pattern": r"new\s+CountDownLatch\s*\(\s*1\s*\)",
        "severity": "warning",
        "message": "Manual CountDownLatch for client thread access",
        "suggestion": "Use helper.readFromClient(() -> client.getWidget(widgetId)) instead"
    },
    {
        "pattern": r"client\.getMenuEntries\s*\(\s*\)",
        "severity": "warning",
        "message": "Accessing client.getMenuEntries() potentially outside client thread",
        "suggestion": "Wrap in clientThread.invokeLater() or use interactionSystem methods"
    },
    {
        "pattern": r"for\s*\([^)]*attempt\s*[<>=]+\s*\d+",
        "context_hint": r"interactWith|handleBank|clickWidget",
        "severity": "info",
        "message": "Manual retry loop around wrapper that already has built-in retry",
        "suggestion": "Wrapper methods have built-in retry logic, remove outer loop"
    },
    {
        "pattern": r"Thread\.sleep\s*\(\s*\d{4,}\s*\)",
        "severity": "warning",
        "message": "Long sleep (>1 second) blocks thread",
        "suggestion": "Use shorter sleeps with interrupt checks, or game tick timing (600ms)"
    },
    {
        "pattern": r"\.getWidget\s*\([^)]+\)\.getBounds\s*\(\s*\)",
        "severity": "error",
        "message": "Chained widget access potentially on wrong thread",
        "suggestion": "Use helper.readFromClient(() -> widget.getBounds()) for thread safety"
    },
    # NEW: Manual GameObject boilerplate
    {
        "pattern": r"(gameEngine\.getGameObject|GameObject.*getClickbox|TileObject.*getClickbox).*CountDownLatch",
        "severity": "error",
        "message": "Manual GameObject interaction boilerplate detected",
        "suggestion": "Use interactionSystem.interactWithGameObject(name, action, radius) instead (replaces 60-120 lines)"
    },
    # NEW: F-key usage for tabs
    {
        "pattern": r"(keyboard\.pressKey\s*\(\s*KeyEvent\.VK_F[0-9]|tabSwitcher\.open)",
        "severity": "error",
        "message": "Using F-keys for tab switching (unreliable - user can rebind!)",
        "suggestion": "Use clickWidget((548 << 16) | offset) for tab switching instead"
    },
    # NEW: Missing interrupt checks in loops (warning, not error - some loops are short)
    {
        "pattern": r"(for|while)\s*\([^)]*\)\s*\{",
        "context_hint": r"shouldInterrupt",
        "context_negative": True,  # Report issue if context DOESN'T match
        "severity": "warning",
        "message": "Loop without shouldInterrupt check (may not be cancellable)",
        "suggestion": "Add 'if (shouldInterrupt) { responseWriter.writeFailure(...); return false; }' in loop body"
    },
    # NEW: Missing ResponseWriter in command handlers
    {
        "pattern": r"private\s+boolean\s+handle[A-Z]\w+\s*\([^)]*\)",
        "context_hint": r"responseWriter\.write",
        "context_negative": True,  # Report issue if context DOESN'T match
        "severity": "warning",
        "message": "Command handler missing ResponseWriter calls",
        "suggestion": "Add responseWriter.writeSuccess/writeFailure calls"
    },
    # NEW: Item name underscore handling
    {
        "pattern": r'(handleBank\w+|getItemCount|findItemByName)\s*\([^)]*"[^"]*\s[^"]*"',
        "severity": "info",
        "message": "Item name with spaces - consider underscore support",
        "suggestion": "Use args.replace(\"_\", \" \") to support both formats"
    }
]

# Pre-compile all regex patterns at module load time (Phase 2 optimization)
# Compiling once saves ~100μs per pattern per invocation = ~10x faster for full scans
_COMPILED_ANTI_PATTERNS = []
for rule in ANTI_PATTERNS:
    compiled_rule = rule.copy()
    compiled_rule["compiled_pattern"] = re.compile(rule["pattern"], re.IGNORECASE)
    if "context_hint" in rule:
        compiled_rule["compiled_context_hint"] = re.compile(rule["context_hint"], re.IGNORECASE)
    _COMPILED_ANTI_PATTERNS.append(compiled_rule)


def check_anti_patterns(code: str = None, file_path: str = None) -> dict:
    """
    Scan code for known anti-patterns and suggest fixes.

    Args:
        code: Code snippet to check (if no file_path)
        file_path: Path to file to check (if no code)

    Returns:
        Dict with found issues and suggestions
    """
    if file_path:
        try:
            code = Path(file_path).read_text()
        except Exception as e:
            return {"success": False, "error": str(e)}

    if not code:
        return {"success": False, "error": "No code or file_path provided"}

    lines = code.split('\n')
    issues = []

    # Use pre-compiled patterns (Phase 2 optimization - 10x faster)
    for rule in _COMPILED_ANTI_PATTERNS:
        compiled_pattern = rule["compiled_pattern"]

        for i, line in enumerate(lines, 1):
            match = compiled_pattern.search(line)
            if match:
                # Check context hint if specified (using pre-compiled regex)
                if "compiled_context_hint" in rule:
                    context = '\n'.join(lines[max(0, i-3):min(len(lines), i+3)])
                    context_found = rule["compiled_context_hint"].search(context) is not None

                    # Handle positive vs negative context checking
                    if rule.get("context_negative", False):
                        # Report if context DOESN'T match (e.g., missing shouldInterrupt)
                        if context_found:
                            continue
                    else:
                        # Report if context DOES match (default behavior)
                        if not context_found:
                            continue

                issues.append({
                    "line": i,
                    "severity": rule["severity"],
                    "message": rule["message"],
                    "code": line.strip()[:100],
                    "suggestion": rule["suggestion"]
                })

    # Categorize by severity
    errors = [i for i in issues if i["severity"] == "error"]
    warnings = [i for i in issues if i["severity"] == "warning"]
    info = [i for i in issues if i["severity"] == "info"]

    return {
        "success": True,
        "file": file_path,
        "total_issues": len(issues),
        "errors": len(errors),
        "warnings": len(warnings),
        "info": len(info),
        "issues": issues,
        "summary": f"Found {len(errors)} error(s), {len(warnings)} warning(s), {len(info)} info"
    }


# =============================================================================
# CLASS SUMMARY & ANALYSIS TOOLS
# =============================================================================

@cached_tool(ttl=300)  # Cache for 5 minutes
def get_class_summary(plugin_dir: str, class_name: str) -> dict:
    """
    Get a quick summary of a Java class without reading all lines.

    PHASE 3 OPTIMIZATION: Results cached for 5 minutes.

    Extracts:
    - Purpose (from class Javadoc or first comment)
    - Key methods with signatures
    - Dependencies (@Inject fields)
    - Threading indicators (schedulers, latches, etc.)
    - Potential issues

    Args:
        plugin_dir: Path to manny plugin directory
        class_name: Class name (e.g., "CombatSystem" or "CombatSystem.java")

    Returns:
        Dict with class summary
    """
    # Find the class file
    if not class_name.endswith('.java'):
        class_name = f"{class_name}.java"

    plugin_path = Path(plugin_dir)
    matches = list(plugin_path.rglob(class_name))

    if not matches:
        return {"success": False, "error": f"Class not found: {class_name}"}

    file_path = matches[0]

    try:
        content = file_path.read_text()
        lines = content.split('\n')
    except Exception as e:
        return {"success": False, "error": str(e)}

    result = {
        "success": True,
        "class_name": class_name.replace('.java', ''),
        "file": str(file_path),
        "total_lines": len(lines),
        "purpose": None,
        "dependencies": [],
        "key_methods": [],
        "threading": {
            "indicators": [],
            "issues": []
        },
        "inner_classes": []
    }

    # Extract class Javadoc/purpose
    in_javadoc = False
    javadoc_lines = []
    for i, line in enumerate(lines):
        if '/**' in line:
            in_javadoc = True
            javadoc_lines = []
        elif in_javadoc:
            if '*/' in line:
                in_javadoc = False
                # Next non-empty line should be class declaration
                for j in range(i+1, min(i+5, len(lines))):
                    if re.search(r'(public|private)?\s*(class|interface|enum)\s+\w+', lines[j]):
                        result["purpose"] = ' '.join(javadoc_lines).strip()[:300]
                        break
                break
            else:
                cleaned = re.sub(r'^\s*\*\s*', '', line).strip()
                if cleaned and not cleaned.startswith('@'):
                    javadoc_lines.append(cleaned)

    # Extract @Inject dependencies
    inject_pattern = re.compile(r'@Inject\s+(?:private\s+)?(\w+)\s+(\w+)')
    for line in lines:
        match = inject_pattern.search(line)
        if match:
            result["dependencies"].append({
                "type": match.group(1),
                "name": match.group(2)
            })

    # Extract public/important methods
    method_pattern = re.compile(r'^\s*(public|private|protected)\s+(\w+(?:<[^>]+>)?)\s+(\w+)\s*\(([^)]*)\)')
    for i, line in enumerate(lines, 1):
        match = method_pattern.match(line)
        if match:
            visibility, return_type, name, params = match.groups()
            # Skip getters/setters and simple accessors
            if name.startswith(('get', 'set', 'is')) and len(params.split(',')) <= 1:
                continue
            # Focus on public methods or important-sounding private ones
            if visibility == 'public' or any(kw in name.lower() for kw in
                ['start', 'stop', 'handle', 'process', 'execute', 'run', 'check', 'update']):
                result["key_methods"].append({
                    "line": i,
                    "visibility": visibility,
                    "return_type": return_type,
                    "name": name,
                    "params": params.strip()[:100]
                })

    # Limit methods
    result["key_methods"] = result["key_methods"][:15]

    # Detect threading patterns
    threading_patterns = [
        (r'ScheduledExecutorService|scheduleAtFixedRate|scheduleWithFixedDelay',
         'Scheduled executor', 'Uses scheduled polling - may cause UI stutter if blocking'),
        (r'CountDownLatch',
         'CountDownLatch', 'Manual thread synchronization - consider ClientThreadHelper'),
        (r'clientThread\.invokeLater',
         'clientThread.invokeLater', 'Proper client thread access'),
        (r'helper\.readFromClient|readFromClient',
         'ClientThreadHelper', 'Good - using thread-safe helper'),
        (r'@Subscribe.*GameTick|onGameTick',
         'GameTick subscriber', 'Good - event-driven, no polling'),
        (r'synchronized\s*\(|synchronized\s+\w+',
         'synchronized blocks', 'Manual synchronization'),
        (r'\.await\s*\(',
         'Latch await', 'Blocking wait - potential UI freeze'),
        (r'ExecutorService|ThreadPoolExecutor|newFixedThreadPool',
         'Thread pool', 'Background thread execution'),
    ]

    for pattern, name, note in threading_patterns:
        matches_found = []
        for i, line in enumerate(lines, 1):
            if re.search(pattern, line):
                matches_found.append(i)
        if matches_found:
            result["threading"]["indicators"].append({
                "pattern": name,
                "lines": matches_found[:5],
                "note": note
            })

    # Detect threading issues
    # Issue 1: scheduleAtFixedRate with readFromClient/CountDownLatch
    has_scheduler = any('Scheduled' in ind["pattern"] for ind in result["threading"]["indicators"])
    has_blocking = any(ind["pattern"] in ['CountDownLatch', 'Latch await']
                       for ind in result["threading"]["indicators"])

    if has_scheduler and has_blocking:
        result["threading"]["issues"].append({
            "severity": "high",
            "issue": "Scheduled polling with blocking client access",
            "description": "scheduleAtFixedRate combined with CountDownLatch/await causes UI stutter",
            "fix": "Replace scheduled polling with @Subscribe GameTick event handler"
        })

    if has_scheduler and not any('GameTick' in ind["pattern"] for ind in result["threading"]["indicators"]):
        result["threading"]["issues"].append({
            "severity": "medium",
            "issue": "Scheduled polling without GameTick",
            "description": "Using scheduled executor when GameTick events would be more efficient",
            "fix": "Consider using @Subscribe GameTick for game-state dependent logic"
        })

    # Detect inner classes
    inner_class_pattern = re.compile(r'^\s+(public|private|protected)?\s*(static\s+)?(class|enum)\s+(\w+)')
    for i, line in enumerate(lines, 1):
        match = inner_class_pattern.match(line)
        if match:
            result["inner_classes"].append({
                "line": i,
                "name": match.group(4),
                "static": bool(match.group(2))
            })

    return result


def find_similar_fix(plugin_dir: str, problem: str) -> dict:
    """
    Find precedents for a fix type in the codebase.

    Searches for similar problems that were already fixed and shows the pattern used.

    Args:
        plugin_dir: Path to manny plugin directory
        problem: Problem description (e.g., "scheduled polling causing UI lag")

    Returns:
        Dict with similar fixes and patterns
    """
    plugin_path = Path(plugin_dir)

    # Known fix patterns with search terms and solutions
    fix_patterns = {
        "polling": {
            "keywords": ["polling", "scheduled", "executor", "ui lag", "stutter", "timer"],
            "search_terms": [r"@Subscribe.*GameTick", r"onGameTick", r"scheduleAtFixedRate"],
            "description": "Scheduled polling replaced with GameTick events",
            "examples": []
        },
        "thread_safety": {
            "keywords": ["thread", "countdownlatch", "latch", "blocking", "client thread", "freeze"],
            "search_terms": [r"readFromClient", r"ClientThreadHelper", r"clientThread\.invokeLater"],
            "description": "Blocking client access replaced with thread-safe helpers",
            "examples": []
        },
        "npc_interaction": {
            "keywords": ["npc", "click", "smartclick", "interact", "menu"],
            "search_terms": [r"interactionSystem\.interactWithNPC", r"interactWithNPC"],
            "description": "Manual NPC clicking replaced with interactionSystem wrapper",
            "examples": []
        },
        "gameobject_interaction": {
            "keywords": ["object", "gameobject", "click", "interact", "tree", "rock", "bank"],
            "search_terms": [r"interactionSystem\.interactWithGameObject", r"interactWithGameObject"],
            "description": "Manual object clicking replaced with interactionSystem wrapper",
            "examples": []
        },
        "inventory_check": {
            "keywords": ["inventory", "item", "check", "has item", "count"],
            "search_terms": [r"gameEngine\.hasItems", r"gameEngine\.getItemCount", r"hasInventorySpace"],
            "description": "Manual inventory checking replaced with gameEngine helpers",
            "examples": []
        }
    }

    # Find matching pattern based on problem description
    problem_lower = problem.lower()
    matched_patterns = []

    for pattern_name, pattern_info in fix_patterns.items():
        score = sum(1 for kw in pattern_info["keywords"] if kw in problem_lower)
        if score > 0:
            matched_patterns.append((pattern_name, pattern_info, score))

    if not matched_patterns:
        return {
            "success": True,
            "problem": problem,
            "matches": [],
            "message": "No matching fix patterns found. Try describing the problem differently.",
            "suggestions": list(fix_patterns.keys())
        }

    # Sort by match score
    matched_patterns.sort(key=lambda x: x[2], reverse=True)

    results = []
    java_files = list(plugin_path.rglob("*.java"))

    for pattern_name, pattern_info, score in matched_patterns[:2]:
        pattern_result = {
            "pattern": pattern_name,
            "description": pattern_info["description"],
            "examples": []
        }

        # Search for examples of the fix
        for search_term in pattern_info["search_terms"]:
            for java_file in java_files:
                try:
                    content = java_file.read_text()
                    file_lines = content.split('\n')

                    for i, line in enumerate(file_lines, 1):
                        if re.search(search_term, line):
                            # Get context
                            start = max(0, i - 3)
                            end = min(len(file_lines), i + 3)
                            context = '\n'.join(file_lines[start:end])

                            pattern_result["examples"].append({
                                "file": str(java_file.name),
                                "line": i,
                                "match": line.strip()[:100],
                                "context": context[:500]
                            })

                            if len(pattern_result["examples"]) >= 3:
                                break
                except Exception:
                    pass

                if len(pattern_result["examples"]) >= 3:
                    break

            if len(pattern_result["examples"]) >= 3:
                break

        results.append(pattern_result)

    return {
        "success": True,
        "problem": problem,
        "matches": results,
        "message": f"Found {len(results)} relevant fix pattern(s)"
    }


# Threading patterns reference
THREADING_PATTERNS = """
=== MANNY PLUGIN THREADING PATTERNS ===

## The Problem: UI Stutter

RuneLite's client thread handles rendering. If you block it or poll too frequently
with blocking operations, the game UI freezes/stutters.

## BAD Patterns (cause UI stutter)

### 1. Scheduled polling with blocking client access
```java
// BAD - polls every 600ms, each poll blocks for up to 5 seconds
scheduler.scheduleAtFixedRate(() -> {
    CountDownLatch latch = new CountDownLatch(1);
    clientThread.invokeLater(() -> {
        try { result = client.getSomething(); }
        finally { latch.countDown(); }
    });
    latch.await(5, TimeUnit.SECONDS);  // BLOCKS!
    processResult(result);
}, 0, 600, TimeUnit.MILLISECONDS);
```

### 2. Direct client access from background thread
```java
// BAD - client access must be on client thread
executor.submit(() -> {
    Widget widget = client.getWidget(123);  // WRONG THREAD!
    widget.getBounds();  // May crash or return stale data
});
```

## GOOD Patterns

### 1. GameTick event subscription (PREFERRED)
```java
// GOOD - runs on client thread, no blocking, natural game tick timing
@Subscribe
public void onGameTick(GameTick event) {
    // Already on client thread - safe to access client directly
    Widget widget = client.getWidget(123);
    if (widget != null) {
        processWidget(widget);
    }
}
```

### 2. ClientThreadHelper for one-off reads
```java
// GOOD - clean, no boilerplate
Widget widget = helper.readFromClient(() -> client.getWidget(123));
Rectangle bounds = helper.readFromClient(() -> widget.getBounds());
```

### 3. clientThread.invokeLater for fire-and-forget
```java
// GOOD - schedules on client thread, doesn't block caller
clientThread.invokeLater(() -> {
    client.setMenuEntries(newEntries);
});
```

## Fix Recipe: Scheduled Polling → GameTick

### Before (BAD):
```java
private ScheduledExecutorService scheduler;

public void startPolling() {
    scheduler = Executors.newSingleThreadScheduledExecutor();
    scheduler.scheduleAtFixedRate(this::checkState, 0, 600, TimeUnit.MILLISECONDS);
}

private void checkState() {
    // Blocking client access...
    CountDownLatch latch = new CountDownLatch(1);
    clientThread.invokeLater(() -> { ... latch.countDown(); });
    latch.await(5, TimeUnit.SECONDS);
}
```

### After (GOOD):
```java
private boolean isActive = false;

public void startMonitoring() {
    isActive = true;
    // No scheduler needed - GameTick fires every 600ms naturally
}

public void stopMonitoring() {
    isActive = false;
}

@Subscribe
public void onGameTick(GameTick event) {
    if (!isActive) return;

    // Already on client thread - direct access is safe
    checkState();
}

private void checkState() {
    // Direct client access - no latch needed
    Widget widget = client.getWidget(123);
    if (widget != null) {
        processWidget(widget);
    }
}
```

## When to Use What

| Scenario | Solution |
|----------|----------|
| Periodic game state checks | @Subscribe GameTick |
| One-off client data read | helper.readFromClient(() -> ...) |
| Update client state | clientThread.invokeLater(() -> ...) |
| Long-running background task | ExecutorService (no client access inside) |
| React to game events | @Subscribe (ChatMessage, MenuOptionClicked, etc.) |
"""


def get_threading_patterns() -> dict:
    """
    Get codebase-specific threading guidance.

    Returns comprehensive documentation about:
    - What causes UI stutter
    - Bad patterns to avoid
    - Good patterns to use
    - Fix recipes for common issues

    Returns:
        Dict with threading patterns documentation
    """
    return {
        "success": True,
        "documentation": THREADING_PATTERNS,
        "quick_reference": {
            "bad_patterns": [
                "scheduleAtFixedRate + CountDownLatch = UI stutter",
                "Direct client access from background thread = crashes/stale data",
                "Long Thread.sleep() on any thread = blocking"
            ],
            "good_patterns": [
                "@Subscribe GameTick for periodic checks (runs on client thread)",
                "helper.readFromClient(() -> ...) for one-off reads",
                "clientThread.invokeLater(() -> ...) for fire-and-forget updates"
            ],
            "fix_recipe": "Replace ScheduledExecutorService with @Subscribe GameTick + boolean flag"
        }
    }


# =============================================================================
# RUNTIME DEBUGGING TOOLS
# =============================================================================

# Blocking patterns to detect
BLOCKING_PATTERNS = [
    {
        "name": "readFromClient in scheduled task",
        "pattern": r"schedule(?:AtFixedRate|WithFixedDelay)\s*\([^)]*\)\s*[^;]*readFromClient",
        "multiline_pattern": r"schedule(?:AtFixedRate|WithFixedDelay)\s*\([^{]*\{[^}]*readFromClient",
        "severity": "high",
        "description": "readFromClient() inside scheduled task blocks scheduler thread",
        "suggestion": "Replace scheduled polling with @Subscribe GameTick event handler"
    },
    {
        "name": "readFromClient in for loop",
        "pattern": r"for\s*\([^)]+\)[^{]*\{[^}]*readFromClient",
        "severity": "high",
        "description": "readFromClient() inside loop - each iteration blocks",
        "suggestion": "Batch multiple reads into single readFromClient() call returning a list/tuple"
    },
    {
        "name": "readFromClient in while loop",
        "pattern": r"while\s*\([^)]+\)[^{]*\{[^}]*readFromClient",
        "severity": "high",
        "description": "readFromClient() inside while loop - repeated blocking",
        "suggestion": "Batch reads or restructure to avoid loop"
    },
    {
        "name": "sequential readFromClient calls",
        "pattern": r"readFromClient\s*\([^)]+\)[^;]*;[^r]*readFromClient\s*\([^)]+\)",
        "severity": "medium",
        "description": "Multiple sequential readFromClient() calls - should batch",
        "suggestion": "Combine into single readFromClient() call that returns multiple values"
    },
    {
        "name": "readFromClient in event handler",
        "pattern": r"@Subscribe[^{]*void\s+on\w+\s*\([^)]*\)[^{]*\{[^}]*readFromClient",
        "severity": "medium",
        "description": "readFromClient() in event handler - may block if event fires frequently",
        "suggestion": "Consider caching result or using GameTick for periodic reads"
    },
    {
        "name": "CountDownLatch await without timeout",
        "pattern": r"\.await\s*\(\s*\)",
        "severity": "high",
        "description": "await() without timeout - can block forever",
        "suggestion": "Use await(timeout, TimeUnit) or replace with ClientThreadHelper.readFromClient()"
    },
    {
        "name": "Long Thread.sleep in client thread path",
        "pattern": r"Thread\.sleep\s*\(\s*\d{4,}\s*\)",
        "severity": "medium",
        "description": "Sleep >1 second may cause noticeable delay",
        "suggestion": "Use shorter sleeps with interrupt checks, or game tick timing (600ms)"
    },
    # Constructor I/O patterns (learned from ObjectLocationCache issue)
    {
        "name": "File I/O in constructor",
        "pattern": r"(?:public|private|protected)\s+\w+\s*\([^)]*\)\s*(?:throws[^{]*)?\{[^}]*(?:new\s+(?:File(?:Reader|Writer|InputStream|OutputStream)|BufferedReader|BufferedWriter)|Files\.(?:read|write|lines|exists)|\.load\(|\.loadFromDisk\()",
        "severity": "high",
        "description": "File I/O in constructor - blocks on disk access every instantiation",
        "suggestion": "Use singleton pattern or lazy initialization; load data once at startup"
    },
    {
        "name": "loadFromDisk in constructor",
        "pattern": r"(?:public|private|protected)\s+\w+\s*\([^)]*\)\s*(?:throws[^{]*)?\{[^}]*loadFromDisk\s*\(",
        "severity": "high",
        "description": "loadFromDisk() called in constructor - disk I/O on every instantiation",
        "suggestion": "Convert to singleton pattern with getInstance(); load once at startup"
    },
    {
        "name": "Network I/O in constructor",
        "pattern": r"(?:public|private|protected)\s+\w+\s*\([^)]*\)\s*(?:throws[^{]*)?\{[^}]*(?:new\s+(?:URL|Socket|HttpURLConnection)|\.openConnection\(|\.connect\(|HttpClient)",
        "severity": "high",
        "description": "Network I/O in constructor - blocks on network every instantiation",
        "suggestion": "Use singleton pattern or lazy initialization; fetch data once and cache"
    },
    {
        "name": "Heavy object created in loop",
        "pattern": r"for\s*\([^)]+\)[^{]*\{[^}]*new\s+(?:GameHelpers|ObjectLocationCache|InteractionSystem|ClientThreadHelper)",
        "severity": "high",
        "description": "Heavy object instantiated inside loop - repeated initialization overhead",
        "suggestion": "Create object once before loop and reuse, or use singleton pattern"
    },
    {
        "name": "new GameHelpers without singleton",
        "pattern": r"new\s+GameHelpers\s*\(",
        "severity": "medium",
        "description": "Creating new GameHelpers instance - may cause repeated cache loading",
        "suggestion": "Consider using a shared GameHelpers instance or singleton pattern"
    },
    {
        "name": "Potential missing singleton",
        "pattern": r"class\s+\w*Cache\w*[^{]*\{(?![^}]*getInstance)[^}]*loadFromDisk",
        "severity": "medium",
        "description": "Cache class with loadFromDisk but no getInstance() - may need singleton",
        "suggestion": "Implement singleton pattern: private constructor + static getInstance()"
    }
]


def find_blocking_patterns(plugin_dir: str, file_path: str = None) -> dict:
    """
    Scan source code for blocking call anti-patterns that cause UI freezes.

    Detects:
    - readFromClient() inside scheduled tasks
    - readFromClient() inside loops
    - Multiple sequential readFromClient() calls
    - readFromClient() in event handlers
    - CountDownLatch.await() without timeout
    - Long Thread.sleep() calls

    Args:
        plugin_dir: Path to manny plugin directory
        file_path: Specific file to scan (None = scan all Java files)

    Returns:
        Dict with issues found and summary
    """
    plugin_path = Path(plugin_dir)

    if file_path:
        if os.path.isabs(file_path):
            files_to_scan = [Path(file_path)]
        else:
            matches = list(plugin_path.rglob(file_path))
            files_to_scan = matches if matches else []
    else:
        files_to_scan = list(plugin_path.rglob("*.java"))

    if not files_to_scan:
        return {
            "success": False,
            "error": f"No files found to scan in {plugin_dir}"
        }

    issues = []
    files_scanned = 0
    files_with_issues = set()

    for java_file in files_to_scan:
        try:
            content = java_file.read_text()
            file_lines = content.split('\n')
            files_scanned += 1

            # Check each pattern
            for pattern_info in BLOCKING_PATTERNS:
                # Try single-line pattern first
                pattern = re.compile(pattern_info["pattern"], re.IGNORECASE | re.DOTALL)

                for match in pattern.finditer(content):
                    # Find line number
                    line_num = content[:match.start()].count('\n') + 1

                    # Get code snippet (the matching line + context)
                    start_line = max(0, line_num - 2)
                    end_line = min(len(file_lines), line_num + 3)
                    snippet = '\n'.join(file_lines[start_line:end_line])

                    issues.append({
                        "file": str(java_file.name),
                        "full_path": str(java_file),
                        "line": line_num,
                        "pattern": pattern_info["name"],
                        "severity": pattern_info["severity"],
                        "description": pattern_info["description"],
                        "suggestion": pattern_info["suggestion"],
                        "code": snippet[:300]
                    })
                    files_with_issues.add(str(java_file.name))

        except Exception as e:
            pass  # Skip files that can't be read

    # Count by severity
    high = len([i for i in issues if i["severity"] == "high"])
    medium = len([i for i in issues if i["severity"] == "medium"])
    low = len([i for i in issues if i["severity"] == "low"])

    # Deduplicate issues (same file+line+pattern)
    seen = set()
    unique_issues = []
    for issue in issues:
        key = (issue["file"], issue["line"], issue["pattern"])
        if key not in seen:
            seen.add(key)
            unique_issues.append(issue)

    return {
        "success": True,
        "files_scanned": files_scanned,
        "files_with_issues": len(files_with_issues),
        "total_issues": len(unique_issues),
        "by_severity": {
            "high": high,
            "medium": medium,
            "low": low
        },
        "issues": unique_issues[:50],  # Limit output
        "summary": f"Found {len(unique_issues)} blocking patterns ({high} high, {medium} medium, {low} low) in {len(files_with_issues)} files"
    }


# Instrumentation code templates
BLOCKING_TRACE_INSTRUMENTATION = '''
// ===== BLOCKING TRACE INSTRUMENTATION =====
// Add these imports at the top of the file:
import java.io.FileWriter;
import java.io.IOException;
import java.time.LocalDateTime;

// Add these fields to ClientThreadHelper class:
private static final String BLOCKING_LOG = "/tmp/manny_blocking.log";
private static final long BLOCKING_THRESHOLD_MS = {threshold_ms};

// Rename existing readFromClient to readFromClientInternal, then add this wrapper:
public <T> T readFromClient(Supplier<T> reader) {{
    long start = System.currentTimeMillis();
    T result = readFromClientInternal(reader);
    long duration = System.currentTimeMillis() - start;

    if (duration > BLOCKING_THRESHOLD_MS) {{
        logBlockingCall(duration, Thread.currentThread().getStackTrace());
    }}
    return result;
}}

// Add this helper method:
private void logBlockingCall(long durationMs, StackTraceElement[] stack) {{
    try (FileWriter fw = new FileWriter(BLOCKING_LOG, true)) {{
        fw.write(String.format("[%s] BLOCKING: %dms%n",
            LocalDateTime.now(), durationMs));
        for (int i = 2; i < Math.min(10, stack.length); i++) {{
            fw.write(String.format("  at %s%n", stack[i]));
        }}
        fw.write("\\n");
    }} catch (IOException e) {{ /* ignore */ }}
}}
'''

GAMETICK_PROFILE_INSTRUMENTATION = '''
// ===== GAMETICK PROFILING INSTRUMENTATION =====
// Add this field to MannyPlugin class:
private static final long GAMETICK_THRESHOLD_MS = {threshold_ms};

// Modify onGameTick to add timing:
@Subscribe
public void onGameTick(GameTick event) {{
    long start = System.currentTimeMillis();

    // Call each handler with timing
    stateExporter.onGameTick();
    long afterState = System.currentTimeMillis();

    // Add timing for other handlers here...
    // combatSystem.onGameTick();
    // long afterCombat = System.currentTimeMillis();

    long total = System.currentTimeMillis() - start;

    // Log if tick processing took too long
    if (total > GAMETICK_THRESHOLD_MS) {{
        log.warn("[GAMETICK] Slow tick: state={}ms, total={}ms",
            afterState - start, total);
    }}
}}
'''


def generate_debug_instrumentation(
    instrumentation_type: str,
    threshold_ms: int = 100
) -> dict:
    """
    Generate Java code that instruments the plugin for runtime debugging.

    A Claude Code subagent should add this code to the plugin source files.

    Args:
        instrumentation_type: "blocking_trace" or "gametick_profile"
        threshold_ms: Threshold in milliseconds to trigger logging (default: 100)

    Returns:
        Dict with generated code and insertion instructions
    """
    if instrumentation_type == "blocking_trace":
        code = BLOCKING_TRACE_INSTRUMENTATION.format(threshold_ms=threshold_ms)
        return {
            "success": True,
            "type": "blocking_trace",
            "target_file": "utility/ClientThreadHelper.java",
            "code_to_add": code,
            "insertion_instructions": """
1. Add the imports at the top of the file
2. Add the BLOCKING_LOG and BLOCKING_THRESHOLD_MS fields
3. Rename the existing readFromClient() method to readFromClientInternal()
4. Add the new readFromClient() wrapper method
5. Add the logBlockingCall() helper method

After building and running, slow blocking calls will be logged to /tmp/manny_blocking.log
Use get_blocking_trace() to read and analyze the results.
""",
            "output_file": "/tmp/manny_blocking.log",
            "how_to_read": "Use get_blocking_trace() MCP tool to read and analyze results"
        }

    elif instrumentation_type == "gametick_profile":
        code = GAMETICK_PROFILE_INSTRUMENTATION.format(threshold_ms=threshold_ms)
        return {
            "success": True,
            "type": "gametick_profile",
            "target_file": "MannyPlugin.java",
            "code_to_add": code,
            "insertion_instructions": """
1. Add the GAMETICK_THRESHOLD_MS field to MannyPlugin class
2. Modify the onGameTick() method to add timing around each handler call
3. Add log.warn() call when total time exceeds threshold

After building and running, slow game ticks will appear in RuneLite logs.
Use get_logs(grep="GAMETICK") to see the profiling output.
""",
            "output_file": "RuneLite logs (use get_logs)",
            "how_to_read": "Use get_logs(grep='GAMETICK') to see slow tick events"
        }

    else:
        return {
            "success": False,
            "error": f"Unknown instrumentation type: {instrumentation_type}",
            "available_types": ["blocking_trace", "gametick_profile"]
        }


def get_blocking_trace(
    since_seconds: int = 60,
    min_duration_ms: int = 100,
    log_file: str = "/tmp/manny_blocking.log"
) -> dict:
    """
    Read and parse the blocking trace log after instrumentation is added.

    Args:
        since_seconds: Only show events from last N seconds
        min_duration_ms: Only show events with duration >= this value
        log_file: Path to the blocking trace log file

    Returns:
        Dict with parsed events and summary statistics
    """
    if not os.path.exists(log_file):
        return {
            "success": False,
            "error": f"Blocking trace log not found at {log_file}",
            "hint": "Add blocking trace instrumentation first using generate_debug_instrumentation()"
        }

    try:
        with open(log_file, 'r') as f:
            content = f.read()
    except Exception as e:
        return {"success": False, "error": str(e)}

    # Parse the log entries
    # Format: [2025-12-21T10:30:45] BLOCKING: 523ms
    #           at package.Class.method(File.java:123)
    #           at ...
    entry_pattern = re.compile(
        r'\[([^\]]+)\]\s+BLOCKING:\s+(\d+)ms\n((?:\s+at [^\n]+\n)*)',
        re.MULTILINE
    )

    events = []
    cutoff_time = datetime.now().timestamp() - since_seconds

    for match in entry_pattern.finditer(content):
        timestamp_str = match.group(1)
        duration = int(match.group(2))
        stack_trace = match.group(3).strip()

        # Parse timestamp
        try:
            # Handle ISO format
            event_time = datetime.fromisoformat(timestamp_str.replace('T', ' ').split('.')[0])
            if event_time.timestamp() < cutoff_time:
                continue
        except:
            pass  # Keep events with unparseable timestamps

        # Filter by duration
        if duration < min_duration_ms:
            continue

        # Parse stack trace
        stack_lines = []
        caller = None
        for line in stack_trace.split('\n'):
            line = line.strip()
            if line.startswith('at '):
                # Extract just the relevant part
                # at net.runelite.client.plugins.manny.PlayerHelpers.handleBankOpen(PlayerHelpers.java:1234)
                match_stack = re.match(r'at\s+([^\(]+)\(([^)]+)\)', line)
                if match_stack:
                    full_method = match_stack.group(1)
                    location = match_stack.group(2)
                    # Simplify to just class.method
                    parts = full_method.split('.')
                    if len(parts) >= 2:
                        simple = f"{parts[-2]}.{parts[-1]}"
                    else:
                        simple = full_method
                    stack_lines.append(f"{simple} ({location})")

                    # First non-ClientThreadHelper entry is the caller
                    if caller is None and 'ClientThreadHelper' not in full_method:
                        caller = simple

        events.append({
            "timestamp": timestamp_str,
            "duration_ms": duration,
            "caller": caller or "Unknown",
            "stack": stack_lines[:5]  # Top 5 frames
        })

    if not events:
        return {
            "success": True,
            "events": [],
            "summary": {
                "total_events": 0,
                "message": f"No blocking events found in last {since_seconds}s with duration >= {min_duration_ms}ms"
            }
        }

    # Calculate summary statistics
    durations = [e["duration_ms"] for e in events]
    callers = {}
    for e in events:
        caller = e["caller"]
        callers[caller] = callers.get(caller, 0) + 1

    worst_caller = max(callers, key=callers.get) if callers else None
    worst_duration = max(durations) if durations else 0

    return {
        "success": True,
        "events": events[-50:],  # Most recent 50
        "summary": {
            "total_events": len(events),
            "avg_duration_ms": round(sum(durations) / len(durations), 1),
            "max_duration_ms": worst_duration,
            "min_duration_ms": min(durations),
            "worst_caller": worst_caller,
            "caller_counts": dict(sorted(callers.items(), key=lambda x: -x[1])[:10])
        }
    }


# =============================================================================
# MCP TOOL DEFINITIONS
# =============================================================================

GET_MANNY_GUIDELINES_TOOL = {
    "name": "get_manny_guidelines",
    "description": """Get manny plugin development guidelines from CLAUDE.md.

Returns formatted guidelines with syntax highlighting and structure.

Modes:
- 'full': Complete CLAUDE.md (use for in-depth understanding)
- 'condensed': Key patterns only (use for quick reference)
- 'section': Specific section (e.g., 'Thread Safety', 'Command Wrappers')

Use 'condensed' or 'section' mode for subagents to minimize context.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["full", "condensed", "section"],
                "description": "Content mode: 'full', 'condensed', or 'section'",
                "default": "full"
            },
            "section": {
                "type": "string",
                "description": "Section name when mode='section' (e.g., 'Thread Safety')"
            }
        },
        "required": []
    }
}

GET_PLUGIN_CONTEXT_TOOL = {
    "name": "get_plugin_context",
    "description": """Get architectural context for the manny plugin.

Returns architecture summary, available wrappers, and optionally command reference.
Use this to understand the plugin structure before making changes.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "context_type": {
                "type": "string",
                "enum": ["full", "architecture", "wrappers", "commands"],
                "description": "[Plugin Navigation] Type of context to retrieve (default: full)",
                "default": "full"
            }
        }
    }
}

GET_SECTION_TOOL = {
    "name": "get_section",
    "description": """Navigate large files by section markers.

PlayerHelpers.java (24K lines) uses section markers like:
// ========== SECTION 4: SKILLING OPERATIONS ==========

Use section="list" to see all sections, or specify a section name/number to get its content.

TIP: For subagents, use summary_only=true to get just line ranges, then use
Read tool to fetch only the lines needed. Use max_lines to limit response size.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "file": {
                "type": "string",
                "description": "[Plugin Navigation] Filename or path (default: PlayerHelpers.java)",
                "default": "PlayerHelpers.java"
            },
            "section": {
                "type": "string",
                "description": "Section name, number, or 'list' to show all sections",
                "default": "list"
            },
            "max_lines": {
                "type": "integer",
                "description": "Maximum lines to return (0 = unlimited). Use to limit response size for large sections.",
                "default": 0
            },
            "summary_only": {
                "type": "boolean",
                "description": "If true, return only line ranges (no content). Best for subagents to minimize context.",
                "default": False
            }
        }
    }
}

FIND_COMMAND_TOOL = {
    "name": "find_command",
    "description": """Find a command's switch case AND handler method in PlayerHelpers.java.

Given a command like "BANK_OPEN", finds:
1. The switch case (e.g., case "BANK_OPEN": return handleBankOpen();)
2. The handler method (e.g., private boolean handleBankOpen())

Returns line numbers and code snippets for both.

TIP: For subagents with limited context, use summary_only=true to get just
line numbers and signatures. The subagent can then use Read tool to fetch
only the specific lines it needs.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "[Plugin Navigation] Command name in UPPER_SNAKE_CASE (e.g., BANK_OPEN, MINE_ORE)"
            },
            "include_handler": {
                "type": "boolean",
                "description": "Whether to include the handler method content (default: true)",
                "default": True
            },
            "max_handler_lines": {
                "type": "integer",
                "description": "Maximum lines of handler code to return (default: 50). Use lower values to reduce response size.",
                "default": 50
            },
            "summary_only": {
                "type": "boolean",
                "description": "If true, return only line numbers and signatures (not full code). Best for subagents to minimize context usage.",
                "default": False
            }
        },
        "required": ["command"]
    }
}

FIND_PATTERN_TOOL = {
    "name": "find_pattern",
    "description": """Search for specific patterns in the manny plugin codebase.

Pattern types:
- "command": Find command switch cases and handlers
- "wrapper": Find usage of interactionSystem, gameEngine, playerHelpers
- "thread": Find thread-related code (CountDownLatch, clientThread, etc.)
- "anti_pattern": Find known anti-patterns that should be refactored
- "custom": Search for a custom regex pattern""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "pattern_type": {
                "type": "string",
                "enum": ["command", "wrapper", "thread", "anti_pattern", "custom"],
                "description": "[Plugin Navigation] Type of pattern to search for"
            },
            "search_term": {
                "type": "string",
                "description": "Custom search term (required for pattern_type='custom')"
            }
        },
        "required": ["pattern_type"]
    }
}

GENERATE_COMMAND_TEMPLATE_TOOL = {
    "name": "generate_command_template",
    "description": """Generate a skeleton command handler following project patterns.

Creates a complete template with:
- Switch case entry
- Handler method skeleton
- Proper logging tags [COMMAND_NAME]
- ResponseWriter.writeSuccess/writeFailure calls
- Interrupt checks for loops
- Comments pointing to standard wrappers""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "command_name": {
                "type": "string",
                "description": "[Plugin Navigation] Command name in UPPER_SNAKE_CASE (e.g., MY_COMMAND)"
            },
            "description": {
                "type": "string",
                "description": "Brief description of what the command does",
                "default": "TODO: Add description"
            },
            "has_args": {
                "type": "boolean",
                "description": "Whether the command takes arguments",
                "default": False
            },
            "args_format": {
                "type": "string",
                "description": "Format description for args (e.g., '<item_name> [quantity]')",
                "default": "<arg>"
            },
            "has_loop": {
                "type": "boolean",
                "description": "Whether the command runs in a loop",
                "default": False
            }
        },
        "required": ["command_name"]
    }
}

CHECK_ANTI_PATTERNS_TOOL = {
    "name": "check_anti_patterns",
    "description": """Scan code for known anti-patterns and suggest fixes.

Detects:
- smartClick() for NPCs (should use interactionSystem.interactWithNPC)
- Manual CountDownLatch (should use ClientThreadHelper.readFromClient)
- Unsafe client.getMenuEntries() access
- Manual retry loops around wrappers
- Long Thread.sleep() blocking
- Chained widget access on wrong thread

Returns issues with line numbers, severity, and suggested fixes.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "[Plugin Navigation] Code snippet to check"
            },
            "file_path": {
                "type": "string",
                "description": "Path to file to check (alternative to code)"
            }
        }
    }
}

GET_CLASS_SUMMARY_TOOL = {
    "name": "get_class_summary",
    "description": """Get a quick summary of a Java class without reading all lines.

Extracts:
- Purpose (from class Javadoc)
- Key methods with signatures and line numbers
- Dependencies (@Inject fields)
- Threading indicators and potential issues
- Inner classes

Much faster than reading a 2000-line file. Use this first to understand a class.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "class_name": {
                "type": "string",
                "description": "[Plugin Navigation] Class name (e.g., 'CombatSystem' or 'CombatSystem.java')"
            }
        },
        "required": ["class_name"]
    }
}

FIND_SIMILAR_FIX_TOOL = {
    "name": "find_similar_fix",
    "description": """Find precedents for a fix type in the codebase.

Given a problem description, finds similar problems that were already fixed
and shows the pattern used. Great for learning from existing solutions.

Example problems:
- "scheduled polling causing UI lag"
- "thread safety with client access"
- "NPC interaction boilerplate"
- "inventory checking"

Returns matching patterns with code examples from the codebase.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "problem": {
                "type": "string",
                "description": "[Plugin Navigation] Problem description (e.g., 'scheduled polling causing UI lag')"
            }
        },
        "required": ["problem"]
    }
}

GET_THREADING_PATTERNS_TOOL = {
    "name": "get_threading_patterns",
    "description": """[Plugin Navigation] Get comprehensive threading guidance for the manny plugin.

Returns documentation about:
- What causes UI stutter
- BAD patterns to avoid (with code examples)
- GOOD patterns to use (with code examples)
- Fix recipe: how to convert scheduled polling to GameTick events

Essential reading before fixing any threading-related issues.""",
    "inputSchema": {
        "type": "object",
        "properties": {}
    }
}

FIND_BLOCKING_PATTERNS_TOOL = {
    "name": "find_blocking_patterns",
    "description": """Scan source code for blocking call anti-patterns that cause UI freezes.

Detects:
- readFromClient() inside scheduled tasks (high severity)
- readFromClient() inside loops (high severity)
- Multiple sequential readFromClient() calls (medium severity)
- readFromClient() in event handlers (medium severity)
- CountDownLatch.await() without timeout (high severity)
- Long Thread.sleep() calls (medium severity)

Use this BEFORE adding instrumentation to find obvious issues statically.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "[Plugin Navigation] Specific file to scan (default: scan all Java files)"
            }
        }
    }
}

GENERATE_DEBUG_INSTRUMENTATION_TOOL = {
    "name": "generate_debug_instrumentation",
    "description": """Generate Java code that instruments the plugin for runtime debugging.

Types:
- "blocking_trace": Logs when readFromClient() calls take >threshold ms to /tmp/manny_blocking.log
- "gametick_profile": Logs time spent in each GameTick handler

Returns Java code that a subagent should add to the plugin source files.
After building and running, use get_blocking_trace() or get_logs() to see results.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "enum": ["blocking_trace", "gametick_profile"],
                "description": "[Plugin Navigation] Type of instrumentation to generate"
            },
            "threshold_ms": {
                "type": "integer",
                "description": "Threshold in milliseconds to trigger logging (default: 100)",
                "default": 100
            }
        },
        "required": ["type"]
    }
}

GET_BLOCKING_TRACE_TOOL = {
    "name": "get_blocking_trace",
    "description": """Read and parse the blocking trace log after instrumentation is added.

Returns parsed events with:
- Timestamp and duration
- Caller method (which code triggered the blocking call)
- Stack trace (top 5 frames)

Also returns summary statistics:
- Total events, average/max/min duration
- Worst caller (most frequent blocker)
- Caller counts (ranked by frequency)

Requires blocking_trace instrumentation to be added first.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "since_seconds": {
                "type": "integer",
                "description": "[Plugin Navigation] Only show events from last N seconds (default: 60)",
                "default": 60
            },
            "min_duration_ms": {
                "type": "integer",
                "description": "Only show events with duration >= this value (default: 100)",
                "default": 100
            }
        }
    }
}


# =============================================================================
# ROUTINE BUILDING & DISCOVERY TOOLS
# =============================================================================

@cached_tool(ttl=600)  # Cache for 10 minutes (commands rarely change)
def list_available_commands(plugin_dir: str, category: str = "all", search: str = None) -> dict:
    """
    List all available plugin commands by parsing PlayerHelpers.java.

    PHASE 3 OPTIMIZATION: Results cached for 10 minutes.

    Extracts commands from the switch statement and categorizes them.
    Much faster than manually grepping the source.

    Args:
        plugin_dir: Path to manny plugin directory
        category: Filter by category (movement, combat, skilling, banking, inventory, query, system, all)
        search: Filter by keyword in command name

    Returns:
        Dict with command list, metadata, and categorization
    """
    plugin_path = Path(plugin_dir)
    helpers_matches = list(plugin_path.rglob("PlayerHelpers.java"))

    if not helpers_matches:
        return {"success": False, "error": "PlayerHelpers.java not found"}

    helpers_path = helpers_matches[0]

    try:
        content = helpers_path.read_text()
        lines = content.split('\n')
    except Exception as e:
        return {"success": False, "error": str(e)}

    # Find switch statement (look for case statements)
    commands = []
    case_pattern = re.compile(r'case\s+"([A-Z_]+)":')

    for i, line in enumerate(lines, 1):
        match = case_pattern.search(line)
        if match:
            cmd_name = match.group(1)

            # Extract handler method name from next few lines
            handler_name = None
            for j in range(i, min(i + 5, len(lines))):
                handler_match = re.search(r'return\s+(\w+)\s*\(', lines[j])
                if handler_match:
                    handler_name = handler_match.group(1)
                    break

            # Categorize command
            cmd_category = categorize_command(cmd_name)

            # Apply filters
            if category != "all" and cmd_category != category:
                continue
            if search and search.lower() not in cmd_name.lower():
                continue

            commands.append({
                "name": cmd_name,
                "line": i,
                "handler": handler_name,
                "category": cmd_category
            })

    # Group by category
    by_category = {}
    for cmd in commands:
        cat = cmd["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(cmd["name"])

    return {
        "success": True,
        "commands": commands,
        "total_count": len(commands),
        "by_category": by_category,
        "categories": list(by_category.keys()),
        "file": str(helpers_path)
    }


def categorize_command(cmd_name: str) -> str:
    """Categorize a command based on its name."""
    cmd_lower = cmd_name.lower()

    if any(kw in cmd_lower for kw in ['goto', 'walk', 'path', 'move', 'navigate']):
        return "movement"
    elif any(kw in cmd_lower for kw in ['attack', 'kill', 'combat', 'fight', 'spell']):
        return "combat"
    elif any(kw in cmd_lower for kw in ['mine', 'fish', 'chop', 'cook', 'fire', 'skill', 'collect']):
        return "skilling"
    elif any(kw in cmd_lower for kw in ['bank', 'deposit', 'withdraw']):
        return "banking"
    elif any(kw in cmd_lower for kw in ['pick', 'drop', 'use_item', 'equip', 'bury', 'inventory']):
        return "inventory"
    elif any(kw in cmd_lower for kw in ['query', 'scan', 'find', 'get_', 'list', 'search']):
        return "query"
    elif any(kw in cmd_lower for kw in ['click', 'interact', 'dialogue', 'widget']):
        return "interaction"
    elif any(kw in cmd_lower for kw in ['camera', 'tab', 'mouse', 'key']):
        return "input"
    elif any(kw in cmd_lower for kw in ['start', 'stop', 'pause', 'resume', 'load', 'emergency']):
        return "system"
    else:
        return "other"


def get_command_examples(
    command: str,
    routines_dir: str = "/home/wil/manny-mcp/routines"
) -> dict:
    """
    Find real usage examples of a command in routine YAML files.

    Searches all routine files for uses of the specified command
    and returns context showing how it's used in practice.

    Args:
        command: Command name to search for (e.g., "INTERACT_OBJECT")
        routines_dir: Directory to search for routine files

    Returns:
        Dict with examples and usage statistics
    """
    examples = []
    routines_path = Path(routines_dir)

    if not routines_path.exists():
        return {
            "success": False,
            "error": f"Routines directory not found: {routines_dir}"
        }

    yaml_files = list(routines_path.rglob("*.yaml")) + list(routines_path.rglob("*.yml"))

    for yaml_file in yaml_files:
        try:
            routine = yaml.safe_load(yaml_file.read_text())

            if not routine or 'steps' not in routine:
                continue

            for step in routine.get('steps', []):
                if step.get('action') == command:
                    examples.append({
                        "routine": yaml_file.name,
                        "routine_path": str(yaml_file),
                        "routine_name": routine.get('name', 'Unknown'),
                        "step_id": step.get('id'),
                        "phase": step.get('phase'),
                        "args": step.get('args'),
                        "description": step.get('description'),
                        "location": step.get('location'),
                        "notes": step.get('notes'),
                        "expected_result": step.get('expected_result')
                    })
        except Exception as e:
            # Skip files that can't be parsed
            pass

    # Generate usage summary
    arg_patterns = {}
    for ex in examples:
        if ex.get('args'):
            arg_patterns[ex['args']] = arg_patterns.get(ex['args'], 0) + 1

    return {
        "success": True,
        "command": command,
        "examples": examples,
        "total_uses": len(examples),
        "used_in_routines": len(set(ex["routine"] for ex in examples)),
        "common_arg_patterns": sorted(arg_patterns.items(), key=lambda x: -x[1])[:5],
        "message": f"Found {len(examples)} uses of {command} across {len(set(ex['routine'] for ex in examples))} routines"
    }


# Tool definitions for new functions

LIST_AVAILABLE_COMMANDS_TOOL = {
    "name": "list_available_commands",
    "description": """List all available plugin commands with categorization.

Parses PlayerHelpers.java switch statement to extract all commands.
Returns structured list with metadata for each command.

Much faster than manually grepping source files.
Useful for discovering what commands exist before building routines.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["all", "movement", "combat", "skilling", "banking", "inventory", "query", "interaction", "input", "system", "other"],
                "description": "[Plugin Navigation] Filter by command category (default: all)",
                "default": "all"
            },
            "search": {
                "type": "string",
                "description": "Filter by keyword in command name"
            }
        }
    }
}

GET_COMMAND_EXAMPLES_TOOL = {
    "name": "get_command_examples",
    "description": """Get real-world usage examples of a command from routine files.

Searches all YAML routines for uses of the specified command.
Returns examples with full context (args, description, location, etc.).

Great for learning how to use a command or finding proven patterns.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "[Plugin Navigation] Command name to search for (e.g., 'INTERACT_OBJECT', 'GOTO')"
            }
        },
        "required": ["command"]
    }
}


# =============================================================================
# ROUTINE VALIDATION TOOLS
# =============================================================================

def validate_routine_deep(
    routine_path: str,
    plugin_dir: str,
    check_commands: bool = True,
    suggest_fixes: bool = True
) -> dict:
    """
    Comprehensive routine validation with command verification.

    Validates:
    - YAML syntax and structure
    - Required fields (action, description)
    - Command existence in plugin
    - Argument formats
    - Location coordinates
    - Logic flow

    Args:
        routine_path: Path to routine YAML file
        plugin_dir: Path to manny plugin directory
        check_commands: Verify all commands exist in PlayerHelpers.java
        suggest_fixes: Auto-suggest fixes for common errors

    Returns:
        Dict with validation results, errors, warnings, and suggestions
    """
    errors = []
    warnings = []
    suggestions = []

    # Load routine YAML
    try:
        with open(routine_path, 'r') as f:
            routine = yaml.safe_load(f)
    except FileNotFoundError:
        return {
            "success": False,
            "error": f"Routine file not found: {routine_path}"
        }
    except yaml.YAMLError as e:
        return {
            "success": False,
            "error": f"YAML syntax error: {e}"
        }

    if not routine:
        return {
            "success": False,
            "error": "Empty routine file"
        }

    # Structural validation
    if 'steps' not in routine:
        errors.append("Missing required field: 'steps'")
    else:
        steps = routine['steps']
        if not isinstance(steps, list):
            errors.append("Field 'steps' must be a list")
        elif len(steps) == 0:
            warnings.append("Routine has no steps")

    # Get available commands if checking
    available_commands = set()
    if check_commands and 'steps' in routine:
        cmd_result = list_available_commands(plugin_dir)
        if cmd_result.get("success"):
            available_commands = {cmd["name"] for cmd in cmd_result["commands"]}

    # Validate each step
    if 'steps' in routine and isinstance(routine['steps'], list):
        for i, step in enumerate(routine['steps'], 1):
            step_errors = []
            step_warnings = []

            # Required fields
            if 'action' not in step:
                step_errors.append(f"Step {i}: Missing required field 'action'")
            else:
                action = step['action']

                # Check command exists
                if check_commands and available_commands and action not in available_commands:
                    step_errors.append(f"Step {i}: Unknown command '{action}'")
                    if suggest_fixes:
                        # Suggest similar commands (fuzzy matching)
                        action_normalized = action.replace('_', '').lower()
                        similar = []
                        for cmd in available_commands:
                            cmd_normalized = cmd.replace('_', '').lower()
                            # Substring match
                            if action.lower() in cmd.lower() or cmd.lower() in action.lower():
                                similar.append(cmd)
                            # Normalized match (e.g., PICKUP_ITEM vs PICK_UP_ITEM)
                            elif action_normalized in cmd_normalized or cmd_normalized in action_normalized:
                                similar.append(cmd)

                        if similar:
                            # Remove duplicates and limit
                            similar = list(dict.fromkeys(similar))[:3]
                            suggestions.append(f"Step {i}: Did you mean one of: {', '.join(similar)}?")

            if 'description' not in step:
                step_warnings.append(f"Step {i}: Missing recommended field 'description'")

            # Validate GOTO coordinates
            if step.get('action') == 'GOTO' and 'args' in step:
                args = step['args']
                if isinstance(args, str):
                    parts = args.split()
                    if len(parts) != 3:
                        step_errors.append(f"Step {i}: GOTO requires 3 args (x y plane), got {len(parts)}")
                    else:
                        try:
                            x, y, plane = int(parts[0]), int(parts[1]), int(parts[2])
                            if not (0 <= x <= 15000):
                                step_errors.append(f"Step {i}: X coordinate {x} out of range (0-15000)")
                            if not (0 <= y <= 15000):
                                step_errors.append(f"Step {i}: Y coordinate {y} out of range (0-15000)")
                            if not (0 <= plane <= 3):
                                step_errors.append(f"Step {i}: Plane {plane} out of range (0-3)")
                        except ValueError:
                            step_errors.append(f"Step {i}: GOTO args must be integers")

            # Validate location references
            if 'location' in step:
                loc_name = step['location']
                if 'locations' in routine:
                    if loc_name not in routine['locations']:
                        step_errors.append(f"Step {i}: Unknown location '{loc_name}'")
                    else:
                        loc = routine['locations'][loc_name]
                        if 'x' not in loc or 'y' not in loc or 'plane' not in loc:
                            step_errors.append(f"Step {i}: Location '{loc_name}' missing x/y/plane")

            errors.extend(step_errors)
            warnings.extend(step_warnings)

    # Validate locations section
    if 'locations' in routine:
        locs = routine['locations']
        if not isinstance(locs, dict):
            errors.append("Field 'locations' must be a dictionary")
        else:
            for loc_name, loc_data in locs.items():
                if not isinstance(loc_data, dict):
                    errors.append(f"Location '{loc_name}' must be a dictionary")
                    continue
                for field in ['x', 'y', 'plane']:
                    if field not in loc_data:
                        errors.append(f"Location '{loc_name}' missing field '{field}'")

    # Logic validation
    if 'steps' in routine and isinstance(routine['steps'], list):
        # Check for BANK_WITHDRAW before BANK_OPEN
        for i, step in enumerate(routine['steps']):
            action = step.get('action')
            if action in ['BANK_WITHDRAW', 'BANK_DEPOSIT_ALL', 'BANK_CLOSE']:
                # Look backwards for BANK_OPEN
                found_open = False
                for j in range(i - 1, -1, -1):
                    prev_action = routine['steps'][j].get('action')
                    if prev_action == 'BANK_OPEN':
                        found_open = True
                        break
                    if prev_action == 'BANK_CLOSE':
                        break  # Bank was closed
                if not found_open:
                    warnings.append(f"Step {i + 1}: {action} without prior BANK_OPEN")

    # Generate stats
    stats = {
        "total_steps": len(routine.get('steps', [])),
        "total_locations": len(routine.get('locations', {})),
        "commands_used": len(set(step.get('action') for step in routine.get('steps', []) if 'action' in step)),
        "phases": len(set(step.get('phase') for step in routine.get('steps', []) if 'phase' in step))
    }

    return {
        "success": len(errors) == 0,
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "suggestions": suggestions,
        "stats": stats,
        "routine_name": routine.get('name', 'Unknown'),
        "routine_type": routine.get('type', 'Unknown')
    }


VALIDATE_ROUTINE_DEEP_TOOL = {
    "name": "validate_routine_deep",
    "description": """Comprehensive routine validation with command verification.

Validates:
- YAML syntax and structure
- Required fields (action, description)
- Command existence (checks against PlayerHelpers.java)
- Argument formats (GOTO coordinates, etc.)
- Location coordinate sanity checks
- Logic flow (e.g., BANK_WITHDRAW after BANK_OPEN)

Returns detailed errors, warnings, and auto-suggested fixes.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "routine_path": {
                "type": "string",
                "description": "[Plugin Navigation] Path to routine YAML file"
            },
            "check_commands": {
                "type": "boolean",
                "description": "Verify all commands exist in plugin (default: true)",
                "default": True
            },
            "suggest_fixes": {
                "type": "boolean",
                "description": "Auto-suggest fixes for errors (default: true)",
                "default": True
            }
        },
        "required": ["routine_path"]
    }
}


# =============================================================================
# COMMAND DOCUMENTATION GENERATION
# =============================================================================

def generate_command_reference(
    plugin_dir: str,
    format: str = "markdown",
    category_filter: str = None
) -> dict:
    """
    Generate comprehensive command reference documentation.

    Creates formatted documentation showing all available commands,
    organized by category, with usage examples from real routines.

    Args:
        plugin_dir: Path to manny plugin directory
        format: Output format (markdown, json, or text)
        category_filter: Only include specific category

    Returns:
        Dict with formatted documentation and metadata
    """
    # Get all commands
    cmd_result = list_available_commands(plugin_dir, category=category_filter or "all")
    if not cmd_result.get("success"):
        return cmd_result

    commands = cmd_result["commands"]
    by_category = cmd_result["by_category"]

    # Get examples for each command
    commands_with_examples = []
    for cmd in commands:
        cmd_name = cmd["name"]
        examples_result = get_command_examples(cmd_name)
        cmd["example_count"] = examples_result.get("total_uses", 0)
        cmd["example"] = examples_result.get("examples", [{}])[0] if examples_result.get("examples") else None
        commands_with_examples.append(cmd)

    # Generate documentation based on format
    if format == "markdown":
        doc = generate_markdown_reference(by_category, commands_with_examples)
    elif format == "json":
        doc = {
            "total_commands": len(commands),
            "categories": list(by_category.keys()),
            "commands_by_category": by_category,
            "commands": commands_with_examples
        }
    else:  # text
        doc = generate_text_reference(by_category, commands_with_examples)

    return {
        "success": True,
        "format": format,
        "total_commands": len(commands),
        "categories": list(by_category.keys()),
        "documentation": doc
    }


def generate_markdown_reference(by_category: dict, commands: list) -> str:
    """Generate markdown-formatted command reference."""
    lines = ["# Manny Plugin Command Reference", ""]
    lines.append("**Auto-generated command documentation**")
    lines.append(f"**Total Commands**: {len(commands)}")
    lines.append(f"**Categories**: {len(by_category)}")
    lines.append("")

    # Table of contents
    lines.append("## Table of Contents")
    for category in sorted(by_category.keys()):
        lines.append(f"- [{category.title()}](#{category})")
    lines.append("")

    # Commands by category
    for category in sorted(by_category.keys()):
        lines.append(f"## {category.title()}")
        lines.append("")

        # Get commands in this category
        cat_commands = [cmd for cmd in commands if cmd["category"] == category]

        for cmd in sorted(cat_commands, key=lambda x: x["name"]):
            lines.append(f"### `{cmd['name']}`")
            lines.append("")
            lines.append(f"**Handler**: `{cmd.get('handler', 'Unknown')}`")
            lines.append(f"**Location**: PlayerHelpers.java:{cmd.get('line', '?')}")

            # Add example if available
            if cmd.get("example"):
                ex = cmd["example"]
                lines.append("")
                lines.append("**Example Usage**:")
                lines.append("```yaml")
                lines.append(f"- action: {cmd['name']}")
                if ex.get("args"):
                    lines.append(f"  args: \"{ex['args']}\"")
                if ex.get("description"):
                    lines.append(f"  description: \"{ex['description']}\"")
                lines.append("```")

                if ex.get("notes"):
                    lines.append(f"> *Note: {ex['notes']}*")

            elif cmd.get("example_count", 0) > 0:
                lines.append(f"")
                lines.append(f"*({cmd['example_count']} usage examples found in routines)*")
            else:
                lines.append("")
                lines.append("*No usage examples found yet*")

            lines.append("")

    return "\n".join(lines)


def generate_text_reference(by_category: dict, commands: list) -> str:
    """Generate plain text command reference."""
    lines = ["=" * 60]
    lines.append("MANNY PLUGIN COMMAND REFERENCE")
    lines.append("=" * 60)
    lines.append(f"Total Commands: {len(commands)}")
    lines.append(f"Categories: {len(by_category)}")
    lines.append("")

    for category in sorted(by_category.keys()):
        lines.append("")
        lines.append("-" * 60)
        lines.append(f"{category.upper()}")
        lines.append("-" * 60)

        cat_commands = [cmd for cmd in commands if cmd["category"] == category]

        for cmd in sorted(cat_commands, key=lambda x: x["name"]):
            lines.append(f"\n{cmd['name']}")
            lines.append(f"  Handler: {cmd.get('handler', 'Unknown')}")
            lines.append(f"  Location: PlayerHelpers.java:{cmd.get('line', '?')}")

            if cmd.get("example"):
                ex = cmd["example"]
                lines.append(f"  Example: {ex.get('args', 'N/A')}")
                if ex.get("description"):
                    lines.append(f"    → {ex['description']}")

    return "\n".join(lines)


GENERATE_COMMAND_REFERENCE_TOOL = {
    "name": "generate_command_reference",
    "description": """Generate comprehensive command reference documentation.

Creates formatted documentation showing all available commands organized by category,
with usage examples from real routines.

Useful for:
- Creating command documentation
- Onboarding new developers
- Quick reference guide""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "format": {
                "type": "string",
                "enum": ["markdown", "json", "text"],
                "description": "Output format (default: markdown)",
                "default": "markdown"
            },
            "category_filter": {
                "type": "string",
                "description": "Only include specific category (optional)"
            }
        }
    }
}
