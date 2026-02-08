"""
Manny plugin navigation and code intelligence tools - registry wrappers for manny_tools.py.

Provides context bundling, navigation, code generation, routine validation,
and command discovery helpers for the manny RuneLite plugin codebase.
"""
from mcp.types import TextContent
from ..registry import registry

# Import the actual implementations
from manny_tools import (
    get_manny_guidelines as _get_manny_guidelines,
    get_plugin_context as _get_plugin_context,
    get_section as _get_section,
    find_command as _find_command,
    find_pattern_in_plugin as _find_pattern_in_plugin,
    generate_command_template as _generate_command_template,
    check_anti_patterns as _check_anti_patterns,
    get_class_summary as _get_class_summary,
    find_similar_fix as _find_similar_fix,
    get_threading_patterns as _get_threading_patterns,
    find_blocking_patterns as _find_blocking_patterns,
    generate_debug_instrumentation as _generate_debug_instrumentation,
    get_blocking_trace as _get_blocking_trace,
    list_available_commands as _list_available_commands,
    get_command_examples as _get_command_examples,
    validate_routine_deep as _validate_routine_deep,
    generate_command_reference as _generate_command_reference,
    get_teleport_info as _get_teleport_info,
    GET_MANNY_GUIDELINES_TOOL,
    GET_PLUGIN_CONTEXT_TOOL,
    GET_SECTION_TOOL,
    FIND_COMMAND_TOOL,
    FIND_PATTERN_TOOL,
    GENERATE_COMMAND_TEMPLATE_TOOL,
    CHECK_ANTI_PATTERNS_TOOL,
    GET_CLASS_SUMMARY_TOOL,
    FIND_SIMILAR_FIX_TOOL,
    GET_THREADING_PATTERNS_TOOL,
    FIND_BLOCKING_PATTERNS_TOOL,
    GENERATE_DEBUG_INSTRUMENTATION_TOOL,
    GET_BLOCKING_TRACE_TOOL,
    LIST_AVAILABLE_COMMANDS_TOOL,
    GET_COMMAND_EXAMPLES_TOOL,
    VALIDATE_ROUTINE_DEEP_TOOL,
    GENERATE_COMMAND_REFERENCE_TOOL,
    GET_TELEPORT_INFO_TOOL,
)

# Dependencies injected from server.py
config = None


def set_dependencies(server_config):
    """Inject dependencies (called from server.py startup)"""
    global config
    config = server_config


# Note: get_manny_guidelines has special formatting, so it returns MCP content directly
@registry.register(GET_MANNY_GUIDELINES_TOOL)
async def handle_get_manny_guidelines(arguments: dict) -> list:
    result = _get_manny_guidelines(
        plugin_dir=config.plugin_directory,
        mode=arguments.get("mode", "full"),
        section=arguments.get("section"),
    )
    if result.get("success"):
        content_text = f"# Manny Plugin Guidelines ({result['mode']} mode)\n\n"
        if result.get("section"):
            content_text += f"Section: {result['section']}\n\n"
        content_text += f"Path: {result['path']}\n\n"
        content_text += "---\n\n"
        content_text += result["content"]
        return [TextContent(type="text", text=content_text)]
    else:
        error_text = f"Error: {result['error']}"
        if result.get("available_sections"):
            error_text += f"\n\nAvailable sections: {', '.join(result['available_sections'])}"
        return [TextContent(type="text", text=error_text)]


@registry.register(GET_PLUGIN_CONTEXT_TOOL)
async def handle_get_plugin_context(arguments: dict) -> dict:
    return _get_plugin_context(
        plugin_dir=config.plugin_directory,
        context_type=arguments.get("context_type", "full"),
    )


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


@registry.register(FIND_PATTERN_TOOL)
async def handle_find_pattern(arguments: dict) -> dict:
    return _find_pattern_in_plugin(
        plugin_dir=config.plugin_directory,
        pattern_type=arguments["pattern_type"],
        search_term=arguments.get("search_term"),
    )


@registry.register(GENERATE_COMMAND_TEMPLATE_TOOL)
async def handle_generate_command_template(arguments: dict) -> dict:
    return _generate_command_template(
        command_name=arguments["command_name"],
        description=arguments.get("description", "TODO: Add description"),
        has_args=arguments.get("has_args", False),
        args_format=arguments.get("args_format", "<arg>"),
        has_loop=arguments.get("has_loop", False),
    )


@registry.register(CHECK_ANTI_PATTERNS_TOOL)
async def handle_check_anti_patterns(arguments: dict) -> dict:
    return _check_anti_patterns(
        code=arguments.get("code"),
        file_path=arguments.get("file_path"),
    )


@registry.register(GET_CLASS_SUMMARY_TOOL)
async def handle_get_class_summary(arguments: dict) -> dict:
    return _get_class_summary(
        plugin_dir=config.plugin_directory,
        class_name=arguments["class_name"],
    )


@registry.register(FIND_SIMILAR_FIX_TOOL)
async def handle_find_similar_fix(arguments: dict) -> dict:
    return _find_similar_fix(
        plugin_dir=config.plugin_directory,
        problem=arguments["problem"],
    )


@registry.register(GET_THREADING_PATTERNS_TOOL)
async def handle_get_threading_patterns(arguments: dict) -> dict:
    return _get_threading_patterns()


@registry.register(FIND_BLOCKING_PATTERNS_TOOL)
async def handle_find_blocking_patterns(arguments: dict) -> dict:
    return _find_blocking_patterns(
        plugin_dir=config.plugin_directory,
        file_path=arguments.get("file_path"),
    )


@registry.register(GENERATE_DEBUG_INSTRUMENTATION_TOOL)
async def handle_generate_debug_instrumentation(arguments: dict) -> dict:
    return _generate_debug_instrumentation(
        instrumentation_type=arguments["type"],
        threshold_ms=arguments.get("threshold_ms", 100),
    )


@registry.register(GET_BLOCKING_TRACE_TOOL)
async def handle_get_blocking_trace(arguments: dict) -> dict:
    return _get_blocking_trace(
        since_seconds=arguments.get("since_seconds", 60),
        min_duration_ms=arguments.get("min_duration_ms", 100),
    )


@registry.register(LIST_AVAILABLE_COMMANDS_TOOL)
async def handle_list_available_commands(arguments: dict) -> dict:
    return _list_available_commands(
        plugin_dir=str(config.plugin_directory),
        category=arguments.get("category", "all"),
        search=arguments.get("search"),
    )


@registry.register(GET_COMMAND_EXAMPLES_TOOL)
async def handle_get_command_examples(arguments: dict) -> dict:
    return _get_command_examples(command=arguments["command"])


@registry.register(VALIDATE_ROUTINE_DEEP_TOOL)
async def handle_validate_routine_deep(arguments: dict) -> dict:
    return _validate_routine_deep(
        routine_path=arguments["routine_path"],
        plugin_dir=str(config.plugin_directory),
        check_commands=arguments.get("check_commands", True),
        suggest_fixes=arguments.get("suggest_fixes", True),
    )


@registry.register(GENERATE_COMMAND_REFERENCE_TOOL)
async def handle_generate_command_reference(arguments: dict) -> dict:
    return _generate_command_reference(
        plugin_dir=str(config.plugin_directory),
        format=arguments.get("format", "markdown"),
        category_filter=arguments.get("category_filter"),
    )


@registry.register(GET_TELEPORT_INFO_TOOL)
async def handle_get_teleport_info(arguments: dict) -> dict:
    return _get_teleport_info(
        destination=arguments.get("destination"),
        include_all=arguments.get("include_all", False),
    )
