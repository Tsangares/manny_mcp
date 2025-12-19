"""
Code change request tool for the RuneLite MCP.

This lets the monitoring Claude Code instance request code fixes
without polluting its runtime context. The API call gets fresh
context with just the relevant code and problem description.
"""

import os
import json
import subprocess
import re
from pathlib import Path
from anthropic import Anthropic

# Initialize client (uses ANTHROPIC_API_KEY env var)
anthropic_client = None


def get_anthropic_client():
    global anthropic_client
    if anthropic_client is None:
        anthropic_client = Anthropic()
    return anthropic_client


def request_code_change(
    problem_description: str,
    relevant_files: list[str],
    logs: str = "",
    game_state: dict = None,
    auto_apply: bool = False,
    auto_rebuild: bool = False,
    runelite_root: str = None
) -> dict:
    """
    Use Claude API to generate a code fix for an observed problem.

    Args:
        problem_description: What's wrong, what behavior was observed
        relevant_files: List of file paths to include as context
        logs: Relevant log snippets
        game_state: State snapshot when issue occurred
        auto_apply: If True, apply the patch automatically
        auto_rebuild: If True, rebuild after applying (requires auto_apply)
        runelite_root: Path to RuneLite root for rebuilding

    Returns:
        Dict with patch, explanation, and apply status
    """

    # Gather file contents
    file_contents = {}
    for filepath in relevant_files:
        path = Path(filepath)
        if path.exists():
            try:
                file_contents[filepath] = path.read_text()
            except Exception as e:
                file_contents[filepath] = f"<error reading file: {e}>"
        else:
            file_contents[filepath] = "<file not found>"

    # Build the prompt
    prompt = f"""You are editing a RuneLite plugin called "manny" that automates Old School RuneScape.

## Problem Description
{problem_description}

## Relevant Logs
```
{logs if logs else "No logs provided"}
```

## Game State at Time of Issue
```json
{json.dumps(game_state, indent=2) if game_state else "No state provided"}
```

## Source Files
"""

    for filepath, content in file_contents.items():
        prompt += f"\n### {filepath}\n```java\n{content}\n```\n"

    prompt += """
## Instructions

Analyze the problem and provide a fix. Your response must include:

1. **Analysis**: Brief explanation of what's causing the issue (2-3 sentences)

2. **Fix**: The actual code changes. Format as a series of SEARCH/REPLACE blocks:

```
<<<<<<< SEARCH
exact code to find
=======
replacement code
>>>>>>> REPLACE
```

Each SEARCH block must match exactly (including whitespace). Keep changes minimal and focused.

3. **Testing**: How to verify the fix works (what behavior to look for)

Do not include unchanged code. Only show the specific lines that need to change.
"""

    try:
        client = get_anthropic_client()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.content[0].text

        result = {
            "success": True,
            "response": response_text,
            "files_analyzed": list(file_contents.keys()),
            "applied": False,
            "rebuilt": False
        }

        # Parse out the SEARCH/REPLACE blocks if auto_apply
        if auto_apply:
            patches = parse_search_replace_blocks(response_text)
            if patches:
                apply_results = apply_patches(patches, file_contents)
                result["applied"] = apply_results["success"]
                result["apply_details"] = apply_results

                if auto_rebuild and apply_results["success"]:
                    rebuild_result = rebuild_plugin(runelite_root)
                    result["rebuilt"] = rebuild_result["success"]
                    result["rebuild_details"] = rebuild_result

        return result

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def parse_search_replace_blocks(text: str) -> list[dict]:
    """Extract SEARCH/REPLACE blocks from response."""
    pattern = r'<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>> REPLACE'
    matches = re.findall(pattern, text, re.DOTALL)

    patches = []
    for search, replace in matches:
        patches.append({
            "search": search,
            "replace": replace
        })

    return patches


def apply_patches(patches: list[dict], file_contents: dict) -> dict:
    """Apply SEARCH/REPLACE patches to files."""
    results = {
        "success": True,
        "applied": [],
        "failed": []
    }

    for patch in patches:
        search = patch["search"]
        replace = patch["replace"]
        applied = False

        for filepath, content in file_contents.items():
            if search in content:
                new_content = content.replace(search, replace, 1)
                try:
                    Path(filepath).write_text(new_content)
                    file_contents[filepath] = new_content  # Update for subsequent patches
                    results["applied"].append({
                        "file": filepath,
                        "search_preview": search[:100] + "..." if len(search) > 100 else search
                    })
                    applied = True
                    break
                except Exception as e:
                    results["failed"].append({
                        "file": filepath,
                        "error": str(e)
                    })
                    results["success"] = False

        if not applied and patch not in [f.get("patch") for f in results["failed"]]:
            results["failed"].append({
                "search_preview": search[:100] + "..." if len(search) > 100 else search,
                "error": "Pattern not found in any file"
            })
            results["success"] = False

    return results


def rebuild_plugin(runelite_root: str = None) -> dict:
    """Trigger a plugin rebuild via Maven."""
    if runelite_root is None:
        runelite_root = os.path.expanduser("~/Desktop/runelite")

    try:
        result = subprocess.run(
            ["mvn", "compile", "-pl", "runelite-client", "-T", "1C", "-DskipTests"],
            cwd=runelite_root,
            capture_output=True,
            text=True,
            timeout=300
        )

        return {
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "stdout_tail": result.stdout[-2000:] if result.stdout else "",
            "stderr_tail": result.stderr[-1000:] if result.stderr else ""
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# MCP Tool definition to add to list_tools()
REQUEST_CODE_CHANGE_TOOL = {
    "name": "request_code_change",
    "description": """Request an AI-generated code fix for an observed problem.

This spawns a fresh Claude API call with clean context containing only the
relevant source files and problem description. Use this when you've identified
a bug or improvement that requires code changes.

The response includes analysis, a patch in SEARCH/REPLACE format, and testing guidance.
Set auto_apply=True to automatically apply the patch, and auto_rebuild=True to
rebuild after applying.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "problem_description": {
                "type": "string",
                "description": "Detailed description of the problem: what behavior was observed, what was expected, any patterns noticed"
            },
            "relevant_files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of file paths to include as context (e.g., ['/home/wil/Desktop/manny/src/.../PathingManager.java'])"
            },
            "logs": {
                "type": "string",
                "description": "Relevant log snippets from around the time of the issue"
            },
            "game_state": {
                "type": "object",
                "description": "Game state snapshot when the issue occurred"
            },
            "auto_apply": {
                "type": "boolean",
                "default": False,
                "description": "Automatically apply the generated patch"
            },
            "auto_rebuild": {
                "type": "boolean",
                "default": False,
                "description": "Rebuild the plugin after applying (requires auto_apply=True)"
            }
        },
        "required": ["problem_description", "relevant_files"]
    }
}
