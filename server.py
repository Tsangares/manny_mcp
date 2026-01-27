#!/home/wil/manny-mcp/venv/bin/python
"""RuneLite Debug MCP Server - Modular Architecture"""

import asyncio
import json
import os
import signal
import uuid
from pathlib import Path
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Import modular components
from mcptools.config import ServerConfig
from mcptools.registry import registry
from mcptools.runelite_manager import MultiRuneLiteManager

# Import tool modules (they register themselves on import)
from mcptools.tools import core, monitoring, screenshot, routine, commands, code_intelligence, testing, spatial, session, quests, sessions, location_history, routine_generator

# Import code change tools (not yet refactored)
from request_code_change import (
    prepare_code_change,
    validate_code_change,
    deploy_code_change,
    validate_with_anti_pattern_check,
    find_relevant_files,
    backup_files,
    rollback_code_change,
    diagnose_issues,
    PREPARE_CODE_CHANGE_TOOL,
    VALIDATE_CODE_CHANGE_TOOL,
    DEPLOY_CODE_CHANGE_TOOL,
    VALIDATE_WITH_ANTI_PATTERN_CHECK_TOOL,
    FIND_RELEVANT_FILES_TOOL,
    BACKUP_FILES_TOOL,
    ROLLBACK_CODE_CHANGE_TOOL,
    DIAGNOSE_ISSUES_TOOL
)

# Import manny-specific tools (not yet refactored)
from manny_tools import (
    get_manny_guidelines,
    get_plugin_context,
    get_section,
    find_command,
    find_pattern_in_plugin,
    generate_command_template,
    check_anti_patterns,
    get_class_summary,
    find_similar_fix,
    get_threading_patterns,
    find_blocking_patterns,
    generate_debug_instrumentation,
    get_blocking_trace,
    list_available_commands,
    get_command_examples,
    validate_routine_deep,
    generate_command_reference,
    get_teleport_info,
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
    GET_TELEPORT_INFO_TOOL
)

# Load environment variables (for GEMINI_API_KEY, session credentials)
load_dotenv()

# Try to import Gemini API
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
except ImportError:
    GEMINI_AVAILABLE = False

# Load config
config = ServerConfig.load()

# Response file for plugin command responses
RESPONSE_FILE = config.state_file.replace("state.json", "response.json")
if not RESPONSE_FILE.endswith("response.json"):
    RESPONSE_FILE = "/tmp/manny_response.json"


# ============================================================================
# EVENT-DRIVEN FILE MONITORING
# ============================================================================

class ResponseFileMonitor:
    """
    Event-driven file monitor using watchdog instead of polling.

    Replaces 50ms polling loops with instant event notification, reducing
    CPU usage and latency by 50x.
    """
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.file_dir = os.path.dirname(file_path) or "/tmp"
        self.file_name = os.path.basename(file_path)
        self.event = asyncio.Event()
        self.observer = None
        self.handler = None
        self._loop = None

    def start(self, loop: asyncio.AbstractEventLoop):
        """Start watching the file for changes."""
        self._loop = loop

        class ResponseFileHandler(FileSystemEventHandler):
            def __init__(self, monitor):
                self.monitor = monitor

            def on_modified(self, event):
                if event.src_path.endswith(self.monitor.file_name):
                    # Signal waiting coroutines
                    if self.monitor._loop:
                        self.monitor._loop.call_soon_threadsafe(self.monitor.event.set)

        self.handler = ResponseFileHandler(self)
        self.observer = Observer()
        self.observer.schedule(self.handler, self.file_dir, recursive=False)
        self.observer.start()

    def stop(self):
        """Stop watching the file."""
        if self.observer:
            self.observer.stop()
            self.observer.join()

    async def wait_for_change(self, timeout_sec: float) -> bool:
        """Wait for file to be modified, with timeout."""
        self.event.clear()
        try:
            await asyncio.wait_for(self.event.wait(), timeout=timeout_sec)
            return True
        except asyncio.TimeoutError:
            return False


# Global file monitor (initialized when server starts)
_response_monitor = None


async def send_command_with_response(command: str, timeout_ms: int = 3000, account_id: str = None) -> dict:
    """
    Send a command to the plugin and wait for the response.

    OPTIMIZATION: Uses event-driven file watching (watchdog) instead of polling.
    Reduces latency from avg 50ms to <1ms and eliminates CPU waste.

    The plugin writes responses to /tmp/manny_response.json after processing commands.
    This function sends the command and waits for file modification events.

    REQUEST ID CORRELATION: Appends --rid=xxx to command for unique request/response matching.
    This prevents race conditions when multiple commands of the same type are sent rapidly.

    Args:
        command: Command to send to the plugin
        timeout_ms: Timeout in milliseconds
        account_id: Optional account ID for multi-client support
    """
    global _response_monitor

    # Get account-specific file paths
    command_file = config.get_command_file(account_id)
    response_file = config.get_response_file(account_id)
    timeout_sec = timeout_ms / 1000.0

    import time

    # Generate unique request ID for correlation
    request_id = uuid.uuid4().hex[:8]

    # Record time BEFORE writing command - response must be newer than this
    command_write_time = time.time()

    # Write the command with request ID appended
    command_with_rid = f"{command} --rid={request_id}"
    with open(command_file, "w") as f:
        f.write(command_with_rid + "\n")
    start = command_write_time  # Also use as start time for timeout

    def _check_response():
        """Check if response file has a valid response to our command."""
        if os.path.exists(response_file):
            current_mtime = os.path.getmtime(response_file)
            # Response must be newer than when we wrote the command
            if current_mtime >= command_write_time:
                try:
                    with open(response_file) as f:
                        response = json.load(f)
                    # PRIMARY: Match by request_id (bulletproof correlation)
                    if response.get("request_id") == request_id:
                        return response
                    # FALLBACK: For backwards compat with old Java plugin, match by command name
                    # (only if response has no request_id)
                    if response.get("request_id") is None:
                        if response.get("command", "").upper() == command.split()[0].upper():
                            return response
                except (json.JSONDecodeError, IOError):
                    pass
        return None

    while (time.time() - start) < timeout_sec:
        # FIRST: Check if response is already available (fixes race condition)
        response = _check_response()
        if response:
            return response

        # THEN: Wait for file change event or poll
        if _response_monitor and (account_id is None or account_id == config.default_account):
            remaining_time = timeout_sec - (time.time() - start)
            if remaining_time <= 0:
                break
            # Wait for file change event (instant notification)
            changed = await _response_monitor.wait_for_change(remaining_time)
            if not changed:
                # Timeout from wait_for_change, but still check one more time
                response = _check_response()
                if response:
                    return response
                break
        else:
            # Fallback to polling for non-default accounts
            await asyncio.sleep(0.05)

    return {
        "command": command,
        "status": "timeout",
        "error": f"No response received within {timeout_ms}ms"
    }


# ============================================================================
# INITIALIZE COMPONENTS
# ============================================================================

# Initialize multi-client RuneLite manager
runelite_manager = MultiRuneLiteManager(config)

# Inject dependencies into tool modules
core.set_dependencies(runelite_manager, config)
monitoring.set_dependencies(runelite_manager, config)
screenshot.set_dependencies(runelite_manager, config, genai if GEMINI_AVAILABLE else None)
routine.set_dependencies(send_command_with_response, config)
commands.set_dependencies(send_command_with_response, config)
spatial.set_dependencies(send_command_with_response, config)
quests.set_dependencies(runelite_manager, config)


# ============================================================================
# MCP SERVER
# ============================================================================

server = Server("runelite-debug")


@server.list_tools()
async def list_tools():
    """Return all tools from registry plus non-refactored tools."""
    # Get tools from registry
    registry_tools = registry.list_tools()

    # Add non-refactored tools (code change and manny-specific)
    additional_tools = [
        Tool(
            name=PREPARE_CODE_CHANGE_TOOL["name"],
            description=PREPARE_CODE_CHANGE_TOOL["description"],
            inputSchema=PREPARE_CODE_CHANGE_TOOL["inputSchema"]
        ),
        Tool(
            name=VALIDATE_CODE_CHANGE_TOOL["name"],
            description=VALIDATE_CODE_CHANGE_TOOL["description"],
            inputSchema=VALIDATE_CODE_CHANGE_TOOL["inputSchema"]
        ),
        Tool(
            name=DEPLOY_CODE_CHANGE_TOOL["name"],
            description=DEPLOY_CODE_CHANGE_TOOL["description"],
            inputSchema=DEPLOY_CODE_CHANGE_TOOL["inputSchema"]
        ),
        Tool(
            name=VALIDATE_WITH_ANTI_PATTERN_CHECK_TOOL["name"],
            description=VALIDATE_WITH_ANTI_PATTERN_CHECK_TOOL["description"],
            inputSchema=VALIDATE_WITH_ANTI_PATTERN_CHECK_TOOL["inputSchema"]
        ),
        Tool(
            name=FIND_RELEVANT_FILES_TOOL["name"],
            description=FIND_RELEVANT_FILES_TOOL["description"],
            inputSchema=FIND_RELEVANT_FILES_TOOL["inputSchema"]
        ),
        Tool(
            name=BACKUP_FILES_TOOL["name"],
            description=BACKUP_FILES_TOOL["description"],
            inputSchema=BACKUP_FILES_TOOL["inputSchema"]
        ),
        Tool(
            name=ROLLBACK_CODE_CHANGE_TOOL["name"],
            description=ROLLBACK_CODE_CHANGE_TOOL["description"],
            inputSchema=ROLLBACK_CODE_CHANGE_TOOL["inputSchema"]
        ),
        Tool(
            name=DIAGNOSE_ISSUES_TOOL["name"],
            description=DIAGNOSE_ISSUES_TOOL["description"],
            inputSchema=DIAGNOSE_ISSUES_TOOL["inputSchema"]
        ),
        Tool(
            name=GET_MANNY_GUIDELINES_TOOL["name"],
            description=GET_MANNY_GUIDELINES_TOOL["description"],
            inputSchema=GET_MANNY_GUIDELINES_TOOL["inputSchema"]
        ),
        Tool(
            name=GET_PLUGIN_CONTEXT_TOOL["name"],
            description=GET_PLUGIN_CONTEXT_TOOL["description"],
            inputSchema=GET_PLUGIN_CONTEXT_TOOL["inputSchema"]
        ),
        Tool(
            name=GET_SECTION_TOOL["name"],
            description=GET_SECTION_TOOL["description"],
            inputSchema=GET_SECTION_TOOL["inputSchema"]
        ),
        Tool(
            name=FIND_COMMAND_TOOL["name"],
            description=FIND_COMMAND_TOOL["description"],
            inputSchema=FIND_COMMAND_TOOL["inputSchema"]
        ),
        Tool(
            name=FIND_PATTERN_TOOL["name"],
            description=FIND_PATTERN_TOOL["description"],
            inputSchema=FIND_PATTERN_TOOL["inputSchema"]
        ),
        Tool(
            name=GENERATE_COMMAND_TEMPLATE_TOOL["name"],
            description=GENERATE_COMMAND_TEMPLATE_TOOL["description"],
            inputSchema=GENERATE_COMMAND_TEMPLATE_TOOL["inputSchema"]
        ),
        Tool(
            name=CHECK_ANTI_PATTERNS_TOOL["name"],
            description=CHECK_ANTI_PATTERNS_TOOL["description"],
            inputSchema=CHECK_ANTI_PATTERNS_TOOL["inputSchema"]
        ),
        Tool(
            name=GET_CLASS_SUMMARY_TOOL["name"],
            description=GET_CLASS_SUMMARY_TOOL["description"],
            inputSchema=GET_CLASS_SUMMARY_TOOL["inputSchema"]
        ),
        Tool(
            name=FIND_SIMILAR_FIX_TOOL["name"],
            description=FIND_SIMILAR_FIX_TOOL["description"],
            inputSchema=FIND_SIMILAR_FIX_TOOL["inputSchema"]
        ),
        Tool(
            name=GET_THREADING_PATTERNS_TOOL["name"],
            description=GET_THREADING_PATTERNS_TOOL["description"],
            inputSchema=GET_THREADING_PATTERNS_TOOL["inputSchema"]
        ),
        Tool(
            name=FIND_BLOCKING_PATTERNS_TOOL["name"],
            description=FIND_BLOCKING_PATTERNS_TOOL["description"],
            inputSchema=FIND_BLOCKING_PATTERNS_TOOL["inputSchema"]
        ),
        Tool(
            name=GENERATE_DEBUG_INSTRUMENTATION_TOOL["name"],
            description=GENERATE_DEBUG_INSTRUMENTATION_TOOL["description"],
            inputSchema=GENERATE_DEBUG_INSTRUMENTATION_TOOL["inputSchema"]
        ),
        Tool(
            name=GET_BLOCKING_TRACE_TOOL["name"],
            description=GET_BLOCKING_TRACE_TOOL["description"],
            inputSchema=GET_BLOCKING_TRACE_TOOL["inputSchema"]
        ),
        Tool(
            name=LIST_AVAILABLE_COMMANDS_TOOL["name"],
            description=LIST_AVAILABLE_COMMANDS_TOOL["description"],
            inputSchema=LIST_AVAILABLE_COMMANDS_TOOL["inputSchema"]
        ),
        Tool(
            name=GET_COMMAND_EXAMPLES_TOOL["name"],
            description=GET_COMMAND_EXAMPLES_TOOL["description"],
            inputSchema=GET_COMMAND_EXAMPLES_TOOL["inputSchema"]
        ),
        Tool(
            name=VALIDATE_ROUTINE_DEEP_TOOL["name"],
            description=VALIDATE_ROUTINE_DEEP_TOOL["description"],
            inputSchema=VALIDATE_ROUTINE_DEEP_TOOL["inputSchema"]
        ),
        Tool(
            name=GENERATE_COMMAND_REFERENCE_TOOL["name"],
            description=GENERATE_COMMAND_REFERENCE_TOOL["description"],
            inputSchema=GENERATE_COMMAND_REFERENCE_TOOL["inputSchema"]
        ),
        Tool(
            name=GET_TELEPORT_INFO_TOOL["name"],
            description=GET_TELEPORT_INFO_TOOL["description"],
            inputSchema=GET_TELEPORT_INFO_TOOL["inputSchema"]
        )
    ]

    return registry_tools + additional_tools


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Route tool calls to registry or non-refactored handlers."""

    # Try registry first
    if registry.has_tool(name):
        return await registry.call_tool(name, arguments)

    # Handle non-refactored tools
    if name == "prepare_code_change":
        result = prepare_code_change(
            problem_description=arguments["problem_description"],
            relevant_files=arguments["relevant_files"],
            logs=arguments.get("logs", ""),
            game_state=arguments.get("game_state"),
            manny_src=config.plugin_directory,
            auto_include_guidelines=arguments.get("auto_include_guidelines", True),
            compact=arguments.get("compact", False),
            max_file_lines=arguments.get("max_file_lines", 0)
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "validate_code_change":
        result = validate_code_change(
            runelite_root=config.runelite_root,
            modified_files=arguments.get("modified_files")
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "deploy_code_change":
        result = deploy_code_change(
            runelite_root=config.runelite_root,
            restart_after=arguments.get("restart_after", True)
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "validate_with_anti_pattern_check":
        result = validate_with_anti_pattern_check(
            runelite_root=config.runelite_root,
            modified_files=arguments["modified_files"],
            manny_src=config.plugin_directory
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "find_relevant_files":
        result = find_relevant_files(
            manny_src=config.plugin_directory,
            search_term=arguments.get("search_term"),
            class_name=arguments.get("class_name"),
            error_message=arguments.get("error_message")
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "backup_files":
        result = backup_files(
            file_paths=arguments["file_paths"]
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "rollback_code_change":
        result = rollback_code_change(
            file_paths=arguments.get("file_paths")
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "diagnose_issues":
        result = diagnose_issues(
            log_lines=arguments["log_lines"],
            game_state=arguments.get("game_state"),
            manny_src=config.plugin_directory
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # Manny-specific tools
    elif name == "get_manny_guidelines":
        result = get_manny_guidelines(
            plugin_dir=config.plugin_directory,
            mode=arguments.get("mode", "full"),
            section=arguments.get("section")
        )
        if result.get("success"):
            content_text = f"# Manny Plugin Guidelines ({result['mode']} mode)\n\n"
            if result.get('section'):
                content_text += f"Section: {result['section']}\n\n"
            content_text += f"Path: {result['path']}\n\n"
            content_text += "---\n\n"
            content_text += result['content']
            return [TextContent(type="text", text=content_text)]
        else:
            error_text = f"Error: {result['error']}"
            if result.get('available_sections'):
                error_text += f"\n\nAvailable sections: {', '.join(result['available_sections'])}"
            return [TextContent(type="text", text=error_text)]

    elif name == "get_plugin_context":
        result = get_plugin_context(
            plugin_dir=config.plugin_directory,
            context_type=arguments.get("context_type", "full")
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_section":
        result = get_section(
            plugin_dir=config.plugin_directory,
            file=arguments.get("file", "PlayerHelpers.java"),
            section=arguments.get("section", "list"),
            max_lines=arguments.get("max_lines", 0),
            summary_only=arguments.get("summary_only", False)
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "find_command":
        result = find_command(
            plugin_dir=config.plugin_directory,
            command=arguments["command"],
            include_handler=arguments.get("include_handler", True),
            max_handler_lines=arguments.get("max_handler_lines", 50),
            summary_only=arguments.get("summary_only", False)
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "find_pattern":
        result = find_pattern_in_plugin(
            plugin_dir=config.plugin_directory,
            pattern_type=arguments["pattern_type"],
            search_term=arguments.get("search_term")
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "generate_command_template":
        result = generate_command_template(
            command_name=arguments["command_name"],
            description=arguments.get("description", "TODO: Add description"),
            has_args=arguments.get("has_args", False),
            args_format=arguments.get("args_format", "<arg>"),
            has_loop=arguments.get("has_loop", False)
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "check_anti_patterns":
        result = check_anti_patterns(
            code=arguments.get("code"),
            file_path=arguments.get("file_path")
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_class_summary":
        result = get_class_summary(
            plugin_dir=config.plugin_directory,
            class_name=arguments["class_name"]
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "find_similar_fix":
        result = find_similar_fix(
            plugin_dir=config.plugin_directory,
            problem=arguments["problem"]
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_threading_patterns":
        result = get_threading_patterns()
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # Runtime debugging tools
    elif name == "find_blocking_patterns":
        result = find_blocking_patterns(
            plugin_dir=config.plugin_directory,
            file_path=arguments.get("file_path")
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "generate_debug_instrumentation":
        result = generate_debug_instrumentation(
            instrumentation_type=arguments["type"],
            threshold_ms=arguments.get("threshold_ms", 100)
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_blocking_trace":
        result = get_blocking_trace(
            since_seconds=arguments.get("since_seconds", 60),
            min_duration_ms=arguments.get("min_duration_ms", 100)
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # Routine building and command discovery tools
    elif name == "list_available_commands":
        result = list_available_commands(
            plugin_dir=str(config.plugin_directory),
            category=arguments.get("category", "all"),
            search=arguments.get("search")
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_command_examples":
        result = get_command_examples(
            command=arguments["command"]
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "validate_routine_deep":
        result = validate_routine_deep(
            routine_path=arguments["routine_path"],
            plugin_dir=str(config.plugin_directory),
            check_commands=arguments.get("check_commands", True),
            suggest_fixes=arguments.get("suggest_fixes", True)
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "generate_command_reference":
        result = generate_command_reference(
            plugin_dir=str(config.plugin_directory),
            format=arguments.get("format", "markdown"),
            category_filter=arguments.get("category_filter")
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_teleport_info":
        result = get_teleport_info(
            destination=arguments.get("destination"),
            include_all=arguments.get("include_all", False)
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Start the MCP server."""
    global _response_monitor

    # Initialize event-driven file monitor
    _response_monitor = ResponseFileMonitor(RESPONSE_FILE)
    _response_monitor.start(asyncio.get_event_loop())

    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())
    finally:
        # Clean up file monitor on shutdown
        if _response_monitor:
            _response_monitor.stop()


if __name__ == "__main__":
    asyncio.run(main())
