"""
Manny plugin navigation and code intelligence tools - registry wrappers for manny_tools.py.

Wave-5 consolidation: this module now registers only the canonical plugin-source
navigation tools. Everything else in manny_tools.py (guidelines, context bundles,
pattern search, template/reference generation, teleport info, blocking traces)
remains importable as plain functions but is no longer on the MCP tool surface.
Command discovery lives in the canonical list_commands tool (mcptools/tools/routine.py).
"""
from manny_tools import (
    CHECK_ANTI_PATTERNS_TOOL,
    FIND_COMMAND_TOOL,
    GET_SECTION_TOOL,
    VALIDATE_ROUTINE_DEEP_TOOL,
)
from manny_tools import (
    check_anti_patterns as _check_anti_patterns,
)
from manny_tools import (
    find_command as _find_command,
)
from manny_tools import (
    get_section as _get_section,
)
from manny_tools import (
    validate_routine_deep as _validate_routine_deep,
)

from ..registry import registry

# Dependencies injected from server.py
config = None


def set_dependencies(server_config):
    """Inject dependencies (called from server.py startup)"""
    global config
    config = server_config


@registry.register(GET_SECTION_TOOL)
async def handle_get_section(arguments: dict) -> dict:
    return _get_section(
        plugin_dir=config.plugin_directory,
        file=arguments.get("file", "PlayerHelpers.java"),
        section=arguments.get("section", "list"),
        max_lines=arguments.get("max_lines", 0),
        summary_only=arguments.get("summary_only", False),
    )


@registry.register(FIND_COMMAND_TOOL)
async def handle_find_command(arguments: dict) -> dict:
    return _find_command(
        plugin_dir=config.plugin_directory,
        command=arguments["command"],
        include_handler=arguments.get("include_handler", True),
        max_handler_lines=arguments.get("max_handler_lines", 50),
        summary_only=arguments.get("summary_only", False),
    )


@registry.register(CHECK_ANTI_PATTERNS_TOOL)
async def handle_check_anti_patterns(arguments: dict) -> dict:
    return _check_anti_patterns(
        code=arguments.get("code"),
        file_path=arguments.get("file_path"),
    )


@registry.register(VALIDATE_ROUTINE_DEEP_TOOL)
async def handle_validate_routine_deep(arguments: dict) -> dict:
    return _validate_routine_deep(
        routine_path=arguments["routine_path"],
        plugin_dir=str(config.plugin_directory),
        check_commands=arguments.get("check_commands", True),
        suggest_fixes=arguments.get("suggest_fixes", True),
    )
