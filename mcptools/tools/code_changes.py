"""
Code change tools - registry wrappers for request_code_change.py functions.

Provides a staging workflow for plugin development:
1. prepare_code_change  - Gather context for code-writing subagent
2. validate_code_change - Compile to verify changes (optionally with anti-pattern scan)
3. deploy_code_change   - Real build + restart signal

Pruned in the Wave-5 tool consolidation:
- validate_with_anti_pattern_check -> validate_code_change(check_anti_patterns=true)
- find_relevant_files / backup_files / rollback_code_change / diagnose_issues ->
  removed from the MCP surface (use git + direct file access; the underlying
  functions remain importable from request_code_change).
"""
import asyncio

from request_code_change import (
    DEPLOY_CODE_CHANGE_TOOL,
    PREPARE_CODE_CHANGE_TOOL,
    VALIDATE_CODE_CHANGE_TOOL,
)
from request_code_change import (
    deploy_code_change as _deploy_code_change,
)

# Import the actual implementations
from request_code_change import (
    prepare_code_change as _prepare_code_change,
)
from request_code_change import (
    validate_code_change as _validate_code_change,
)
from request_code_change import (
    validate_with_anti_pattern_check as _validate_with_anti_pattern_check,
)

from ..registry import registry

# Dependencies injected from server.py
config = None


def set_dependencies(server_config):
    """Inject dependencies (called from server.py startup)"""
    global config
    config = server_config


@registry.register(PREPARE_CODE_CHANGE_TOOL)
async def handle_prepare_code_change(arguments: dict) -> dict:
    return _prepare_code_change(
        problem_description=arguments["problem_description"],
        relevant_files=arguments["relevant_files"],
        logs=arguments.get("logs", ""),
        game_state=arguments.get("game_state"),
        manny_src=config.plugin_directory,
        auto_include_guidelines=arguments.get("auto_include_guidelines", True),
        compact=arguments.get("compact", False),
        max_file_lines=arguments.get("max_file_lines", 0),
    )


# Extend the imported schema with the merged anti-pattern option
_VALIDATE_TOOL = dict(VALIDATE_CODE_CHANGE_TOOL)
_VALIDATE_TOOL["inputSchema"] = {
    **VALIDATE_CODE_CHANGE_TOOL.get("inputSchema", {"type": "object", "properties": {}}),
}
_VALIDATE_TOOL["inputSchema"]["properties"] = {
    **_VALIDATE_TOOL["inputSchema"].get("properties", {}),
    "check_anti_patterns": {
        "type": "boolean",
        "description": "Also scan modified_files for known anti-patterns before compiling (default: false). Requires modified_files.",
        "default": False,
    },
}
_VALIDATE_TOOL["description"] = (
    _VALIDATE_TOOL.get("description", "")
    + " Pass check_anti_patterns=true to also run the anti-pattern scan on modified_files."
)


@registry.register(_VALIDATE_TOOL)
async def handle_validate_code_change(arguments: dict) -> dict:
    modified_files = arguments.get("modified_files")
    if arguments.get("check_anti_patterns") and modified_files:
        # Merged path (absorbs the old validate_with_anti_pattern_check tool).
        # Runs a Gradle compile (subprocess, up to 180s) - keep off the event loop.
        return await asyncio.to_thread(
            _validate_with_anti_pattern_check,
            runelite_root=config.runelite_root,
            modified_files=modified_files,
            manny_src=config.plugin_directory,
        )
    return await asyncio.to_thread(
        _validate_code_change,
        runelite_root=config.runelite_root,
        modified_files=modified_files,
    )


@registry.register(DEPLOY_CODE_CHANGE_TOOL)
async def handle_deploy_code_change(arguments: dict) -> dict:
    # Runs a full Gradle build (subprocess, up to 300s) - keep off the event loop.
    return await asyncio.to_thread(
        _deploy_code_change,
        runelite_root=config.runelite_root,
        restart_after=arguments.get("restart_after", True),
    )
