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
