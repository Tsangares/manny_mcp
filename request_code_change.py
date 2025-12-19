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
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


def prepare_code_change(
    problem_description: str,
    relevant_files: list[str],
    logs: str = "",
    game_state: dict = None,
    manny_src: str = None
) -> dict:
    """
    Gather context for a code-writing subagent.

    Returns a structured prompt with file contents, logs, and game state
    that can be passed to a Task subagent for code modifications.

    Args:
        problem_description: What's wrong, what behavior was observed
        relevant_files: List of file paths to include as context
        logs: Relevant log snippets
        game_state: State snapshot when issue occurred
        manny_src: Path to manny plugin source (for resolving relative paths)

    Returns:
        Dict with structured context ready for subagent
    """

    # Gather file contents
    file_contents = {}
    for filepath in relevant_files:
        path = Path(filepath)

        # Try to resolve relative paths against manny_src
        if not path.is_absolute() and manny_src:
            path = Path(manny_src) / filepath

        if path.exists():
            try:
                file_contents[str(path)] = path.read_text()
            except Exception as e:
                file_contents[str(path)] = f"<error reading file: {e}>"
        else:
            file_contents[str(path)] = "<file not found>"

    # Build structured context
    context = {
        "success": True,
        "problem_description": problem_description,
        "logs": logs if logs else None,
        "game_state": game_state,
        "files": file_contents,
        "file_paths": list(file_contents.keys()),
        "instructions": """
You are fixing a RuneLite plugin called "manny" that automates Old School RuneScape.

Based on the problem description, logs, game state, and source files provided,
make the necessary code changes to fix the issue.

IMPORTANT: After making changes, the controller will run validate_code_change
to compile in a staging directory. This ensures changes compile without
affecting the running game instance.

Focus on minimal, targeted fixes. Don't refactor unrelated code.
"""
    }

    return context


def validate_code_change(
    runelite_root: str,
    modified_files: list[str] = None
) -> dict:
    """
    Validate code changes by compiling in a staging directory.

    This copies the source to a temp directory and compiles there,
    so the running RuneLite instance is not affected.

    Args:
        runelite_root: Path to RuneLite source root
        modified_files: Optional list of files that were modified (for reporting)

    Returns:
        Dict with compilation success/failure and any errors
    """

    staging_dir = None
    start_time = time.time()

    try:
        # Create staging directory
        staging_dir = tempfile.mkdtemp(prefix="runelite_staging_")

        # Copy only what's needed for compilation
        # We need: pom.xml files, src directories, and .mvn if it exists
        src_root = Path(runelite_root)
        staging_root = Path(staging_dir)

        # Copy root pom.xml
        if (src_root / "pom.xml").exists():
            shutil.copy2(src_root / "pom.xml", staging_root / "pom.xml")

        # Copy runelite-client module (where manny plugin lives)
        client_src = src_root / "runelite-client"
        client_staging = staging_root / "runelite-client"

        if client_src.exists():
            # Copy pom.xml
            client_staging.mkdir(parents=True, exist_ok=True)
            if (client_src / "pom.xml").exists():
                shutil.copy2(client_src / "pom.xml", client_staging / "pom.xml")

            # Copy src directory
            if (client_src / "src").exists():
                shutil.copytree(client_src / "src", client_staging / "src")

        # Copy runelite-api if it exists (dependency)
        api_src = src_root / "runelite-api"
        if api_src.exists():
            api_staging = staging_root / "runelite-api"
            api_staging.mkdir(parents=True, exist_ok=True)
            if (api_src / "pom.xml").exists():
                shutil.copy2(api_src / "pom.xml", api_staging / "pom.xml")
            if (api_src / "src").exists():
                shutil.copytree(api_src / "src", api_staging / "src")

        # Copy .mvn directory if exists (for maven wrapper settings)
        if (src_root / ".mvn").exists():
            shutil.copytree(src_root / ".mvn", staging_root / ".mvn")

        copy_time = time.time() - start_time

        # Run compilation in staging directory
        compile_start = time.time()
        result = subprocess.run(
            ["mvn", "compile", "-pl", "runelite-client", "-T", "1C",
             "-DskipTests", "-q", "-o"],  # quiet mode, offline (use cached deps)
            cwd=staging_dir,
            capture_output=True,
            text=True,
            timeout=180  # 3 minute timeout
        )
        compile_time = time.time() - compile_start

        # Parse errors if compilation failed
        errors = []
        if result.returncode != 0:
            errors = _parse_maven_errors(result.stdout + result.stderr)

        return {
            "success": result.returncode == 0,
            "staging_dir": staging_dir,
            "copy_time_seconds": round(copy_time, 2),
            "compile_time_seconds": round(compile_time, 2),
            "modified_files": modified_files or [],
            "errors": errors,
            "return_code": result.returncode,
            "message": "Validation successful - changes compile correctly" if result.returncode == 0
                      else f"Compilation failed with {len(errors)} error(s)"
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Compilation timed out (>3 minutes)",
            "staging_dir": staging_dir
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "staging_dir": staging_dir
        }
    finally:
        # Clean up staging directory
        if staging_dir and os.path.exists(staging_dir):
            try:
                shutil.rmtree(staging_dir)
            except:
                pass  # Best effort cleanup


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
        result = subprocess.run(
            ["mvn", "compile", "-pl", "runelite-client", "-T", "1C", "-DskipTests"],
            cwd=runelite_root,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        build_time = time.time() - start_time

        errors = []
        if result.returncode != 0:
            errors = _parse_maven_errors(result.stdout + result.stderr)

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


def _parse_maven_errors(output: str) -> list:
    """Parse Maven output for compilation errors."""
    import re

    errors = []
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
                errors.append({
                    "file": None,
                    "line": None,
                    "message": line.replace('[ERROR]', '').strip()
                })
    return errors


# MCP Tool definitions

PREPARE_CODE_CHANGE_TOOL = {
    "name": "prepare_code_change",
    "description": """Gather context for requesting code changes to the manny plugin.

Returns file contents, logs, and game state in a structured format suitable
for passing to a code-writing subagent (via Claude Code's Task tool).

Use this when the controller has identified a problem that needs a code fix.
The returned context can be given to a subagent to analyze and implement the fix.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "problem_description": {
                "type": "string",
                "description": "Detailed description of the problem: what behavior was observed, what was expected"
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
            }
        },
        "required": ["problem_description", "relevant_files"]
    }
}

VALIDATE_CODE_CHANGE_TOOL = {
    "name": "validate_code_change",
    "description": """Validate code changes by compiling in a staging directory.

This is SAFE to call while RuneLite is running - it copies source to a temp
directory and compiles there, so the running instance is not affected.

Use this after making code changes to verify they compile before deploying.""",
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
                "description": "If True, signals that RuneLite should be restarted"
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
                "description": "General term to search for in file contents"
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
    "description": """Create backups of files before modification.

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
    "description": """Restore files from backup after a failed code change.

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
    "description": """Analyze logs and game state to detect issues needing code fixes.

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
