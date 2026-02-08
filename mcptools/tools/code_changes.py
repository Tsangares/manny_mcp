"""
Code change tools - registry wrappers for request_code_change.py functions.

Provides a staging workflow for plugin development:
1. prepare_code_change  - Gather context for code-writing subagent
2. validate_code_change - Compile to verify changes
3. deploy_code_change   - Real build + restart signal
"""
import json
from ..registry import registry

# Import the actual implementations
from request_code_change import (
    prepare_code_change as _prepare_code_change,
    validate_code_change as _validate_code_change,
    deploy_code_change as _deploy_code_change,
    validate_with_anti_pattern_check as _validate_with_anti_pattern_check,
    find_relevant_files as _find_relevant_files,
    backup_files as _backup_files,
    rollback_code_change as _rollback_code_change,
    diagnose_issues as _diagnose_issues,
    PREPARE_CODE_CHANGE_TOOL,
    VALIDATE_CODE_CHANGE_TOOL,
    DEPLOY_CODE_CHANGE_TOOL,
    VALIDATE_WITH_ANTI_PATTERN_CHECK_TOOL,
    FIND_RELEVANT_FILES_TOOL,
    BACKUP_FILES_TOOL,
    ROLLBACK_CODE_CHANGE_TOOL,
    DIAGNOSE_ISSUES_TOOL,
)

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


@registry.register(VALIDATE_CODE_CHANGE_TOOL)
async def handle_validate_code_change(arguments: dict) -> dict:
    return _validate_code_change(
        runelite_root=config.runelite_root,
        modified_files=arguments.get("modified_files"),
    )


@registry.register(DEPLOY_CODE_CHANGE_TOOL)
async def handle_deploy_code_change(arguments: dict) -> dict:
    return _deploy_code_change(
        runelite_root=config.runelite_root,
        restart_after=arguments.get("restart_after", True),
    )


@registry.register(VALIDATE_WITH_ANTI_PATTERN_CHECK_TOOL)
async def handle_validate_with_anti_pattern_check(arguments: dict) -> dict:
    return _validate_with_anti_pattern_check(
        runelite_root=config.runelite_root,
        modified_files=arguments["modified_files"],
        manny_src=config.plugin_directory,
    )


@registry.register(FIND_RELEVANT_FILES_TOOL)
async def handle_find_relevant_files(arguments: dict) -> dict:
    return _find_relevant_files(
        manny_src=config.plugin_directory,
        search_term=arguments.get("search_term"),
        class_name=arguments.get("class_name"),
        error_message=arguments.get("error_message"),
    )


@registry.register(BACKUP_FILES_TOOL)
async def handle_backup_files(arguments: dict) -> dict:
    return _backup_files(file_paths=arguments["file_paths"])


@registry.register(ROLLBACK_CODE_CHANGE_TOOL)
async def handle_rollback_code_change(arguments: dict) -> dict:
    return _rollback_code_change(file_paths=arguments.get("file_paths"))


@registry.register(DIAGNOSE_ISSUES_TOOL)
async def handle_diagnose_issues(arguments: dict) -> dict:
    return _diagnose_issues(
        log_lines=arguments["log_lines"],
        game_state=arguments.get("game_state"),
        manny_src=config.plugin_directory,
    )
