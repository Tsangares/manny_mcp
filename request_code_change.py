"""
Code change tools for the RuneLite MCP.

Provides a staging workflow for plugin development:
1. prepare_code_change  - Gather context for code-writing subagent
2. validate_code_change - Compile in staging dir (safe, doesn't affect running instance)
3. deploy_code_change   - Real build + restart signal

This lets the controller Claude Code stay focused on testing while
a subagent handles the actual code modifications.
"""

import os
import json
import subprocess
import time
from pathlib import Path


def prepare_code_change(
    problem_description: str,
    relevant_files: list[str],
    logs: str = "",
    game_state: dict = None,
    manny_src: str = None,
    auto_include_guidelines: bool = True,
    compact: bool = False,
    max_file_lines: int = 0,
    smart_sectioning: bool = True
) -> dict:
    """
    Gather context for a code-writing subagent.

    Returns a structured prompt with file contents, logs, game state,
    and manny plugin guidelines that can be passed to a Task subagent.

    Args:
        problem_description: What's wrong, what behavior was observed
        relevant_files: List of file paths to include as context
        logs: Relevant log snippets
        game_state: State snapshot when issue occurred
        manny_src: Path to manny plugin source (for resolving relative paths)
        auto_include_guidelines: If True, include CLAUDE.md and architecture context
        compact: If True, minimize response size for subagent efficiency:
                 - Return only file paths and line counts (not full contents)
                 - Use ultra-condensed guidelines
                 - Omit game_state details
                 Subagent should use Read tool to get specific file sections
        max_file_lines: If >0, truncate each file to this many lines (0 = unlimited)
        smart_sectioning: If True, intelligently extract relevant sections from large files
                          (e.g., for PlayerHelpers.java, extract only mentioned commands)

    Returns:
        Dict with structured context ready for subagent
    """

    # Gather file contents (or just metadata in compact mode)
    file_contents = {}
    file_metadata = {}

    # Import manny_tools for smart sectioning
    if smart_sectioning:
        try:
            from manny_tools import find_command, get_section
        except ImportError:
            smart_sectioning = False

    for filepath in relevant_files:
        path = Path(filepath)

        # Try to resolve relative paths against manny_src
        if not path.is_absolute() and manny_src:
            path = Path(manny_src) / filepath

        if path.exists():
            try:
                content = path.read_text()
                lines = content.split('\n')
                file_metadata[str(path)] = {
                    "line_count": len(lines),
                    "size_bytes": len(content)
                }

                # SMART SECTIONING: For PlayerHelpers.java, extract only relevant commands
                if smart_sectioning and "PlayerHelpers.java" in str(path) and not compact:
                    commands_mentioned = _extract_commands_from_problem(problem_description, logs)

                    if commands_mentioned:
                        # Extract only the mentioned command handlers
                        extracted_sections = []
                        for cmd in commands_mentioned:
                            result = find_command(
                                plugin_dir=str(path.parent.parent),  # Go up to manny root
                                command=cmd,
                                include_handler=True,
                                max_handler_lines=200,
                                summary_only=False
                            )
                            if result.get("success") and "handler" in result:
                                extracted_sections.append(f"// ===== {cmd} =====\n")
                                extracted_sections.append(result["handler"]["preview"])
                                extracted_sections.append("\n\n")

                        if extracted_sections:
                            file_contents[str(path)] = "".join(extracted_sections)
                            file_metadata[str(path)]["smart_extraction"] = {
                                "commands": commands_mentioned,
                                "note": "Extracted only relevant command handlers (90% size reduction)"
                            }
                            continue

                # Default handling (compact, truncate, or full file)
                if compact:
                    # Don't include content in compact mode
                    file_contents[str(path)] = f"<{len(lines)} lines - use Read tool to access>"
                elif max_file_lines > 0 and len(lines) > max_file_lines:
                    # Truncate if requested
                    truncated = '\n'.join(lines[:max_file_lines])
                    file_contents[str(path)] = truncated + f"\n... [truncated at {max_file_lines} lines, {len(lines)} total]"
                else:
                    file_contents[str(path)] = content
            except Exception as e:
                file_contents[str(path)] = f"<error reading file: {e}>"
                file_metadata[str(path)] = {"error": str(e)}
        else:
            file_contents[str(path)] = "<file not found>"
            file_metadata[str(path)] = {"error": "not found"}

    # Build structured context
    context = {
        "success": True,
        "problem_description": problem_description,
        "logs": logs if logs else None,
        "files": file_contents,
        "file_paths": list(file_contents.keys()),
        "file_metadata": file_metadata,
        "compact_mode": compact
    }

    # In compact mode, simplify game_state to just key info
    if compact and game_state:
        player = game_state.get("player", {})
        context["game_state_summary"] = {
            "location": player.get("location"),
            "health": player.get("health"),
            "is_moving": player.get("is_moving"),
            "scenario": game_state.get("current_scenario")
        }
    else:
        context["game_state"] = game_state

    # Auto-include manny plugin guidelines
    if auto_include_guidelines and manny_src:
        if compact:
            # Ultra-condensed guidelines for subagent efficiency (~500 chars)
            context["manny_guidelines"] = """MANNY RULES:
- NPC: interactionSystem.interactWithNPC(name, action)
- Object: interactionSystem.interactWithGameObject(name, action, radius)
- Widget: clickWidget(widgetId)
- Inventory: gameEngine.hasItems(), getItemCount()
- Thread-safe: helper.readFromClient(() -> client.getWidget(id))
- AVOID: smartClick() for NPCs, manual CountDownLatch, long Thread.sleep()
- Pattern: log.info("[CMD]..."); try { ... responseWriter.writeSuccess(); } catch { responseWriter.writeFailure(); }
"""
            context["available_wrappers"] = "See manny_guidelines above"
        else:
            # Condensed essential guidelines (~3.5K chars instead of 26K - includes all critical patterns)
            context["manny_guidelines"] = """
=== MANNY PLUGIN ESSENTIAL GUIDELINES ===

## Architecture (READ/WRITE Separation)
- GameEngine.GameHelpers = READ operations (safe anywhere, no game modifications)
- PlayerHelpers = WRITE operations (background thread only, executes actions)
- InteractionSystem = Standardized wrappers for NPCs, GameObjects, widgets

## Thread Safety (CRITICAL)
- Client thread: Widget/menu access only. NEVER block this thread!
- Background thread: Mouse, delays, I/O. Can block.
- Pattern: helper.readFromClient(() -> client.getWidget(id))
  Replaces 10+ lines of CountDownLatch boilerplate

## Required Wrappers (DON'T reinvent these)

NPC interaction:
  interactionSystem.interactWithNPC("Banker", "Bank")
  interactionSystem.interactWithNPC(name, action, maxAttempts, searchRadius)

GameObject interaction:
  interactionSystem.interactWithGameObject("Tree", "Chop down", 15)
  interactionSystem.interactWithGameObject(id, name, action, worldPoint)
  Replaces 60-120 lines of manual GameObject boilerplate!

Widget clicking:
  clickWidget(widgetId)  // 5-phase verification, 3 retries
  clickWidgetWithParam(widgetId, param0, actionName)

Inventory queries:
  gameEngine.hasItems(itemId1, itemId2)  // ALL present
  gameEngine.hasAnyItem(itemId1, itemId2)  // ANY present
  gameEngine.getItemCount(itemId), getEmptySlots(), hasInventorySpace(n)

Banking:
  handleBankOpen(), handleBankClose()
  handleBankWithdraw("Iron_ore 14")  // underscores → spaces
  handleBankDepositAll(), handleBankDepositItem("Logs")

## Tab Switching (CRITICAL - F-keys are unreliable!)
❌ NEVER use F-key bindings (user-customizable, break!)
✅ ALWAYS use tab widget IDs:
  final int TOPLEVEL = 548;
  final int MAGIC_TAB = (TOPLEVEL << 16) | 0x56;  // 35913814
  clickWidget(MAGIC_TAB);

## Command Handler Pattern (MANDATORY)
private boolean handleMyCommand(String args) {
    log.info("[MY_COMMAND] Starting...");
    try {
        // 1. Parse args (replace underscores with spaces)
        String itemName = args.replace("_", " ");

        // 2. Use existing wrappers, NOT manual boilerplate

        // 3. Check shouldInterrupt in loops
        for (int i = 0; i < count; i++) {
            if (shouldInterrupt) {
                responseWriter.writeFailure("MY_COMMAND", "Interrupted");
                return false;
            }
            // ... work
        }

        // 4. ALWAYS write response
        responseWriter.writeSuccess("MY_COMMAND", "Done");
        return true;
    } catch (Exception e) {
        log.error("[MY_COMMAND] Error", e);
        responseWriter.writeFailure("MY_COMMAND", e);
        return false;
    }
}

## Anti-Patterns (AVOID THESE - will cause bugs!)
1. ❌ smartClick() for NPCs → use interactionSystem.interactWithNPC()
2. ❌ Manual CountDownLatch → use helper.readFromClient(() -> ...)
3. ❌ Manual retry loops → wrappers have built-in retry
4. ❌ Manual GameObject boilerplate → use interactWithGameObject()
5. ❌ Direct client.getMenuEntries() → wrap in clientThread.invokeLater()
6. ❌ Thread.sleep(5000+) → use shorter sleeps with interrupt checks
7. ❌ F-key for tabs → use widget IDs (TOPLEVEL << 16 | offset)
8. ❌ Missing shouldInterrupt checks in loops
9. ❌ Missing ResponseWriter calls in handlers
10. ❌ Forgetting underscore→space conversion for item names

## IMPORTANT: Use check_anti_patterns tool
Before finalizing changes, run:
  check_anti_patterns(file_path="path/to/modified/file.java")
Fix any errors before submitting!

## Key Files
- PlayerHelpers.java (24K lines): Commands, writes. Has section markers.
- GameEngine.java: Read-only queries (inventory, NPCs, objects)
- InteractionSystem.java: NPC/GameObject/Widget wrappers
- ClientThreadHelper.java: Thread-safe client access

For COMPLETE documentation, read: /home/wil/Desktop/manny/CLAUDE.md
"""

            # Add wrapper reference (compact)
            context["available_wrappers"] = {
                "npc": "interactionSystem.interactWithNPC(name, action)",
                "gameobject": "interactionSystem.interactWithGameObject(name, action, radius)",
                "widget": "clickWidget(widgetId)",
                "inventory": "gameEngine.hasItems(), getItemCount(), hasInventorySpace()",
                "bank": "handleBankOpen(), handleBankWithdraw('Item_name count')",
                "thread_safe": "helper.readFromClient(() -> ...)"
            }

    if compact:
        context["instructions"] = """Fix the manny RuneLite plugin issue described above.
Use Read tool to access file contents (not included to save context).
Follow manny_guidelines patterns. Make minimal targeted changes.
Use check_anti_patterns tool to validate before finalizing."""
    else:
        context["instructions"] = """
You are fixing a RuneLite plugin called "manny" that automates Old School RuneScape.

CRITICAL: Read the manny_guidelines (CLAUDE.md content) above before making changes!
It contains essential patterns, wrappers, and anti-patterns you must follow.

Based on the problem description, logs, game state, and source files provided,
make the necessary code changes to fix the issue.

KEY RULES:
1. Use existing wrappers - don't reinvent (see available_wrappers)
2. Thread safety - use ClientThreadHelper.readFromClient() for client access
3. Follow command handler patterns - proper logging, ResponseWriter calls
4. Minimal changes - fix only what's broken, don't refactor
5. VALIDATE with check_anti_patterns tool before finalizing your changes

After making changes, use check_anti_patterns to verify. The controller will validate the build.
"""

    return context


def validate_code_change(
    runelite_root: str,
    modified_files: list[str] = None
) -> dict:
    """
    Validate code changes by running a compile check.

    Uses Gradle compile for validation.
    For safety, use backup_files() before making changes so you can
    rollback_code_change() if the fix doesn't work.

    Args:
        runelite_root: Path to RuneLite source root
        modified_files: Optional list of files that were modified (for reporting)

    Returns:
        Dict with compilation success/failure and any errors
    """
    start_time = time.time()

    try:
        # Run compilation with Gradle
        result = subprocess.run(
            ["./gradlew", ":client:compileJava", "-q"],  # quiet mode
            cwd=runelite_root,
            capture_output=True,
            text=True,
            timeout=180  # 3 minute timeout
        )
        compile_time = time.time() - start_time

        # Parse errors if compilation failed
        errors = []
        if result.returncode != 0:
            errors = _parse_gradle_errors(result.stdout + result.stderr)

        return {
            "success": result.returncode == 0,
            "compile_time_seconds": round(compile_time, 2),
            "modified_files": modified_files or [],
            "errors": errors,
            "return_code": result.returncode,
            "message": "Validation successful - changes compile correctly" if result.returncode == 0
                      else f"Compilation failed with {len(errors)} error(s)",
            "note": "Use backup_files() before changes and rollback_code_change() if needed"
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Compilation timed out (>3 minutes)"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def deploy_code_change(
    runelite_root: str,
    restart_after: bool = True
) -> dict:
    """
    Deploy validated changes by doing a real build.

    WARNING: This will affect the running RuneLite instance!
    Only call this after validate_code_change succeeds and
    the controller is ready to restart.

    Args:
        runelite_root: Path to RuneLite source root
        restart_after: If True, signals that RuneLite should be restarted

    Returns:
        Dict with build success and restart instructions
    """

    start_time = time.time()

    try:
        # Build with Gradle, skipping tests and code quality checks
        result = subprocess.run(
            ["./gradlew", "build", "-x", "test", "-x", "javadoc", "-x", "javadocJar",
             "-x", "checkstyleMain", "-x", "pmdMain"],
            cwd=runelite_root,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        build_time = time.time() - start_time

        errors = []
        if result.returncode != 0:
            errors = _parse_gradle_errors(result.stdout + result.stderr)

        response = {
            "success": result.returncode == 0,
            "build_time_seconds": round(build_time, 2),
            "errors": errors,
            "return_code": result.returncode
        }

        if result.returncode == 0:
            if restart_after:
                response["message"] = "Build successful. RuneLite should be restarted to apply changes."
                response["action_required"] = "restart_runelite"
            else:
                response["message"] = "Build successful. Changes will apply on next RuneLite start."
        else:
            response["message"] = f"Build failed with {len(errors)} error(s)"

        return response

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Build timed out (>5 minutes)"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def validate_with_anti_pattern_check(
    runelite_root: str,
    modified_files: list[str],
    manny_src: str
) -> dict:
    """
    Validate code changes with both compilation AND anti-pattern checks.

    Combines validate_code_change + check_anti_patterns for comprehensive validation.
    This is the recommended validation function as it catches both compilation errors
    and common code quality issues.

    Args:
        runelite_root: Path to RuneLite source root
        modified_files: List of modified files to check
        manny_src: Path to manny plugin source

    Returns:
        Dict with combined validation results
    """
    from manny_tools import check_anti_patterns

    # Step 1: Compilation check
    compile_result = validate_code_change(runelite_root, modified_files)

    if not compile_result["success"]:
        return {
            "success": False,
            "compilation": compile_result,
            "anti_patterns": None,
            "message": "Compilation failed - fix errors before checking anti-patterns",
            "ready_to_deploy": False
        }

    # Step 2: Anti-pattern check
    all_issues = []
    error_count = 0
    warning_count = 0

    for file_path in modified_files:
        # Resolve relative paths
        full_path = file_path if os.path.isabs(file_path) else os.path.join(manny_src, file_path)

        if os.path.exists(full_path):
            pattern_result = check_anti_patterns(file_path=full_path)

            if pattern_result.get("success"):
                all_issues.extend(pattern_result.get("issues", []))
                error_count += pattern_result.get("errors", 0)
                warning_count += pattern_result.get("warnings", 0)

    # Determine overall success
    # Compilation passed, but error-severity anti-patterns = FAIL
    overall_success = error_count == 0

    return {
        "success": overall_success,
        "compilation": compile_result,
        "anti_patterns": {
            "total_issues": len(all_issues),
            "errors": error_count,
            "warnings": warning_count,
            "issues": all_issues
        },
        "message": (
            "All validations passed - ready to deploy" if overall_success
            else f"Anti-pattern validation failed: {error_count} error(s) found. Fix before deploying."
        ),
        "ready_to_deploy": overall_success,
        "note": "Warnings don't block deployment but should be addressed" if warning_count > 0 and error_count == 0 else None
    }


def _parse_gradle_errors(output: str) -> list:
    """Parse Gradle/javac output for compilation errors."""
    import re

    errors = []
    # Match javac error patterns like: /path/to/File.java:42: error: message
    javac_pattern = re.compile(r'^(/[^:]+\.java):(\d+):\s*error:\s*(.+)$')

    for line in output.split('\n'):
        match = javac_pattern.match(line.strip())
        if match:
            errors.append({
                "file": match.group(1),
                "line": int(match.group(2)),
                "message": match.group(3)
            })
        elif 'FAILURE' in line or 'error:' in line.lower():
            # Capture other error indicators
            errors.append({
                "file": None,
                "line": None,
                "message": line.strip()
            })
    return errors


# MCP Tool definitions

PREPARE_CODE_CHANGE_TOOL = {
    "name": "prepare_code_change",
    "description": """Gather context for requesting code changes to the manny plugin.

Returns file contents, logs, game state, AND manny plugin guidelines in a structured
format suitable for passing to a code-writing subagent (via Claude Code's Task tool).

Automatically includes:
- CLAUDE.md (condensed guidelines)
- Architecture summary (READ/WRITE separation, thread safety)
- Available wrappers reference

TIP: For subagents with limited context, use compact=true to minimize response size.
The subagent will get file paths and line counts (not full contents) and can use
Read tool to fetch only the specific sections it needs.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "problem_description": {
                "type": "string",
                "description": "[Code Change] Detailed description of the problem: what behavior was observed, what was expected"
            },
            "relevant_files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of file paths to include (can be relative to manny_src or absolute)"
            },
            "logs": {
                "type": "string",
                "description": "Relevant log snippets from around the time of the issue"
            },
            "game_state": {
                "type": "object",
                "description": "Game state snapshot when the issue occurred"
            },
            "auto_include_guidelines": {
                "type": "boolean",
                "description": "Include CLAUDE.md and architecture context (default: true)",
                "default": True
            },
            "compact": {
                "type": "boolean",
                "description": "Minimize response size for subagent efficiency: returns file metadata (not contents), ultra-condensed guidelines. Subagent uses Read tool for file contents.",
                "default": False
            },
            "max_file_lines": {
                "type": "integer",
                "description": "Truncate each file to this many lines (0 = unlimited). Use to reduce response size when files are large.",
                "default": 0
            }
        },
        "required": ["problem_description", "relevant_files"]
    }
}

VALIDATE_CODE_CHANGE_TOOL = {
    "name": "validate_code_change",
    "description": """[Code Change] Validate code changes by running a compile check.

Runs Gradle compile to verify changes compile correctly.
For safety, use backup_files() before making changes so you can
rollback_code_change() if the fix doesn't work.

Use this after making code changes to verify they compile before testing.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "modified_files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of files that were modified (for reporting)"
            }
        }
    }
}

DEPLOY_CODE_CHANGE_TOOL = {
    "name": "deploy_code_change",
    "description": """Deploy validated changes by doing a real build.

WARNING: This will compile changes that affect the running RuneLite!
Only call this after validate_code_change succeeds.

After deployment, RuneLite should be restarted to apply the changes.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "restart_after": {
                "type": "boolean",
                "default": True,
                "description": "[Code Change] If True, signals that RuneLite should be restarted"
            }
        }
    }
}

# Legacy tool name for backwards compatibility
REQUEST_CODE_CHANGE_TOOL = PREPARE_CODE_CHANGE_TOOL


# =============================================================================
# Additional Helper Tools
# =============================================================================

# Global backup storage for rollback
_file_backups = {}


def find_relevant_files(
    manny_src: str,
    search_term: str = None,
    class_name: str = None,
    error_message: str = None
) -> dict:
    """
    Search the manny plugin source for relevant files.

    Helps the controller find which files to include in prepare_code_change
    when they don't know exactly where the problem is.

    Args:
        manny_src: Path to manny plugin source
        search_term: General search term to grep for
        class_name: Java class name to find (e.g., "PathingManager")
        error_message: Error message to search for in code

    Returns:
        Dict with matching files and context
    """
    results = {
        "success": True,
        "matches": [],
        "suggested_files": []
    }

    src_path = Path(manny_src)
    if not src_path.exists():
        return {"success": False, "error": f"manny_src not found: {manny_src}"}

    java_files = list(src_path.rglob("*.java"))

    # Search by class name
    if class_name:
        for java_file in java_files:
            if class_name.lower() in java_file.stem.lower():
                results["matches"].append({
                    "file": str(java_file),
                    "match_type": "class_name",
                    "matched": class_name
                })
                results["suggested_files"].append(str(java_file))

    # Search by term or error message in file contents
    search = search_term or error_message
    if search:
        search_lower = search.lower()
        for java_file in java_files:
            try:
                content = java_file.read_text()
                if search_lower in content.lower():
                    # Find the matching lines
                    matching_lines = []
                    for i, line in enumerate(content.split('\n'), 1):
                        if search_lower in line.lower():
                            matching_lines.append({"line": i, "content": line.strip()[:100]})
                            if len(matching_lines) >= 3:
                                break

                    results["matches"].append({
                        "file": str(java_file),
                        "match_type": "content",
                        "matched": search[:50],
                        "lines": matching_lines
                    })
                    if str(java_file) not in results["suggested_files"]:
                        results["suggested_files"].append(str(java_file))
            except Exception:
                pass

    # Limit suggestions
    results["suggested_files"] = results["suggested_files"][:10]
    results["total_matches"] = len(results["matches"])

    if not results["matches"]:
        results["message"] = "No matches found"
    else:
        results["message"] = f"Found {len(results['matches'])} matching file(s)"

    return results


def backup_files(file_paths: list[str]) -> dict:
    """
    Create backups of files before modification.

    Call this before spawning a code-writing subagent to enable rollback.

    Args:
        file_paths: List of absolute file paths to backup

    Returns:
        Dict with backup status
    """
    global _file_backups

    backed_up = []
    failed = []

    for filepath in file_paths:
        path = Path(filepath)
        if path.exists():
            try:
                content = path.read_text()
                _file_backups[filepath] = {
                    "content": content,
                    "timestamp": time.time()
                }
                backed_up.append(filepath)
            except Exception as e:
                failed.append({"file": filepath, "error": str(e)})
        else:
            failed.append({"file": filepath, "error": "File not found"})

    return {
        "success": len(failed) == 0,
        "backed_up": backed_up,
        "failed": failed,
        "total_backups": len(_file_backups),
        "message": f"Backed up {len(backed_up)} file(s)"
    }


def rollback_code_change(file_paths: list[str] = None) -> dict:
    """
    Restore files from backup after a failed code change.

    Args:
        file_paths: Specific files to restore (None = restore all backups)

    Returns:
        Dict with restore status
    """
    global _file_backups

    if not _file_backups:
        return {
            "success": False,
            "error": "No backups available",
            "message": "Call backup_files before making changes to enable rollback"
        }

    files_to_restore = file_paths or list(_file_backups.keys())
    restored = []
    failed = []

    for filepath in files_to_restore:
        if filepath in _file_backups:
            try:
                Path(filepath).write_text(_file_backups[filepath]["content"])
                restored.append(filepath)
                del _file_backups[filepath]
            except Exception as e:
                failed.append({"file": filepath, "error": str(e)})
        else:
            failed.append({"file": filepath, "error": "No backup found"})

    return {
        "success": len(failed) == 0,
        "restored": restored,
        "failed": failed,
        "remaining_backups": len(_file_backups),
        "message": f"Restored {len(restored)} file(s)"
    }


def diagnose_issues(
    log_lines: list[str],
    game_state: dict = None,
    manny_src: str = None
) -> dict:
    """
    Analyze logs and game state to detect issues that may need code fixes.

    Scans for error patterns, exceptions, and anomalies that suggest
    the plugin code needs modification.

    Args:
        log_lines: Recent log lines from get_logs
        game_state: Current game state from get_game_state
        manny_src: Path to search for relevant files

    Returns:
        Dict with diagnosed issues and suggested actions
    """
    import re

    issues = []
    suggested_files = set()

    # Patterns that suggest code issues
    error_patterns = [
        (r'NullPointerException', 'null_pointer', 'Null reference - missing null check'),
        (r'ArrayIndexOutOfBoundsException', 'array_bounds', 'Array access out of bounds'),
        (r'IllegalStateException', 'illegal_state', 'Invalid state transition'),
        (r'ConcurrentModificationException', 'concurrent_mod', 'Collection modified during iteration'),
        (r'ClassCastException', 'class_cast', 'Invalid type cast'),
        (r'NumberFormatException', 'number_format', 'Failed to parse number'),
        (r'IndexOutOfBoundsException', 'index_bounds', 'Index out of bounds'),
        (r'StackOverflowError', 'stack_overflow', 'Infinite recursion detected'),
        (r'\[ERROR\].*manny', 'plugin_error', 'Plugin-specific error'),
        (r'Exception in thread', 'thread_exception', 'Uncaught thread exception'),
    ]

    # Patterns to extract class/method info
    class_pattern = re.compile(r'at\s+[\w.]+\.(\w+)\.(\w+)\((\w+\.java):(\d+)\)')

    for line in log_lines:
        for pattern, issue_type, description in error_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                issue = {
                    "type": issue_type,
                    "description": description,
                    "log_line": line[:200],
                    "files": []
                }

                # Try to extract file/line info from stack trace
                match = class_pattern.search(line)
                if match:
                    class_name, method, filename, line_num = match.groups()
                    issue["class"] = class_name
                    issue["method"] = method
                    issue["file"] = filename
                    issue["line"] = int(line_num)

                    # Search for the file if manny_src provided
                    if manny_src:
                        for java_file in Path(manny_src).rglob(filename):
                            issue["files"].append(str(java_file))
                            suggested_files.add(str(java_file))

                issues.append(issue)
                break

    # Analyze game state for anomalies
    state_issues = []
    if game_state:
        player = game_state.get("player", {})

        # Check for stuck player
        if player.get("is_moving") and player.get("idle_ticks", 0) > 10:
            state_issues.append({
                "type": "player_stuck",
                "description": "Player appears stuck (moving but high idle ticks)",
                "data": {"idle_ticks": player.get("idle_ticks")}
            })

        # Check for invalid location
        loc = player.get("location", {})
        if loc.get("x") == 0 and loc.get("y") == 0:
            state_issues.append({
                "type": "invalid_location",
                "description": "Player location is (0,0) - possible crash or logout",
                "data": loc
            })

    needs_fix = len(issues) > 0 or len(state_issues) > 0

    return {
        "success": True,
        "needs_code_fix": needs_fix,
        "log_issues": issues,
        "state_issues": state_issues,
        "suggested_files": list(suggested_files),
        "summary": f"Found {len(issues)} error(s) in logs, {len(state_issues)} state anomalies"
            if needs_fix else "No issues detected"
    }


# Tool definitions for new helpers

FIND_RELEVANT_FILES_TOOL = {
    "name": "find_relevant_files",
    "description": """Search the manny plugin source for relevant files.

Use this when you need to find which files to include in prepare_code_change
but don't know exactly where the problem is. Can search by:
- class_name: Find files containing a class (e.g., "PathingManager")
- search_term: Grep for any term in file contents
- error_message: Search for text from an error message""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "search_term": {
                "type": "string",
                "description": "[Code Change] General term to search for in file contents"
            },
            "class_name": {
                "type": "string",
                "description": "Java class name to find"
            },
            "error_message": {
                "type": "string",
                "description": "Error message text to search for"
            }
        }
    }
}

BACKUP_FILES_TOOL = {
    "name": "backup_files",
    "description": """[Code Change] Create backups of files before modification.

Call this BEFORE spawning a code-writing subagent. If the fix doesn't work,
you can use rollback_code_change to restore the original files.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "file_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of absolute file paths to backup"
            }
        },
        "required": ["file_paths"]
    }
}

ROLLBACK_CODE_CHANGE_TOOL = {
    "name": "rollback_code_change",
    "description": """[Code Change] Restore files from backup after a failed code change.

Use this if a fix made things worse and you want to revert to the original code.
Requires backup_files to have been called first.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "file_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific files to restore (omit to restore all backups)"
            }
        }
    }
}

DIAGNOSE_ISSUES_TOOL = {
    "name": "diagnose_issues",
    "description": """[Code Change] Analyze logs and game state to detect issues needing code fixes.

Scans for error patterns, exceptions, and anomalies. Returns:
- needs_code_fix: Whether issues were detected
- log_issues: Errors found in logs with file/line info when available
- state_issues: Anomalies in game state
- suggested_files: Files that may need modification""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "log_lines": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Recent log lines from get_logs"
            },
            "game_state": {
                "type": "object",
                "description": "Current game state from get_game_state"
            }
        },
        "required": ["log_lines"]
    }
}

VALIDATE_WITH_ANTI_PATTERN_CHECK_TOOL = {
    "name": "validate_with_anti_pattern_check",
    "description": """[Code Change] Validate code changes with BOTH compilation and anti-pattern checks.

This is the recommended validation function - it combines validate_code_change with
check_anti_patterns for comprehensive validation. Use this instead of validate_code_change
to catch both compilation errors and common code quality issues.

Returns:
- success: True only if compilation succeeds AND no error-severity anti-patterns found
- compilation: Compilation results
- anti_patterns: Anti-pattern detection results
- ready_to_deploy: Whether the code is safe to deploy

Note: Warnings don't block deployment but should be addressed.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "modified_files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of modified files to check"
            }
        },
        "required": ["modified_files"]
    }
}


# ============================================================================
# HELPER FUNCTIONS FOR SMART SECTIONING (Phase 2)
# ============================================================================

def _extract_commands_from_problem(problem_description: str, logs: str = "") -> list[str]:
    """
    Extract command names mentioned in problem description or logs.

    Looks for patterns like:
    - BANK_OPEN, MINE_ORE (uppercase snake case)
    - [BANK_OPEN] in logs
    - handleBankOpen (method names)

    Returns:
        List of uppercase command names (e.g., ["BANK_OPEN", "MINE_ORE"])
    """
    import re

    commands = set()
    combined_text = f"{problem_description} {logs}"

    # Pattern 1: Direct command names (UPPERCASE_SNAKE_CASE)
    for match in re.finditer(r'\b([A-Z][A-Z_]{3,})\b', combined_text):
        cmd = match.group(1)
        # Filter out common non-command words
        if cmd not in ['ERROR', 'WARN', 'INFO', 'DEBUG', 'NULL', 'TRUE', 'FALSE', 'SECTION']:
            commands.add(cmd)

    # Pattern 2: Log tags [COMMAND_NAME]
    for match in re.finditer(r'\[([A-Z][A-Z_]+)\]', combined_text):
        commands.add(match.group(1))

    # Pattern 3: handleXxx method names → XXX command
    for match in re.finditer(r'handle([A-Z][a-zA-Z]+)', combined_text):
        # Convert camelCase to SNAKE_CASE
        camel = match.group(1)
        snake = re.sub(r'([A-Z])', r'_\1', camel).upper().lstrip('_')
        commands.add(snake)

    return sorted(list(commands))
