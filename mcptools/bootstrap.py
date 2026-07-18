"""
Shared in-process tool-registry bootstrap.

SINGLE-SERVER RULE: there is exactly ONE process type that owns command I/O
against the plugin -- whatever imports this module and calls ``init_registry()``.
Historically ``manny_driver`` spawned a second, independent copy of
``server.py`` as a stdio subprocess just to get access to the same tools this
module wires up. That meant two live control planes (the "real" MCP server
used by Claude Code, plus the driver's private subprocess) each capable of
racing writes to the same command/response files. This module exists so any
in-process caller (currently ``manny_driver``) gets the exact same tool
registrations and dependency wiring as ``server.py`` -- including the
canonical ``mcptools/transport.py`` command layer -- WITHOUT spawning another
server process. Do not spawn ``server.py`` from anywhere else; import and use
``mcptools.registry.registry`` (via ``init_registry()`` below) directly.

This mirrors server.py's module-level setup (config load, transport config
injection, dependency wiring for every tool module) so the two never drift
into registering different tool sets or wiring different dependencies.
"""
import os
import sys

from dotenv import load_dotenv

from . import transport
from .config import ServerConfig
from .registry import registry
from .runelite_manager import MultiRuneLiteManager

# Import tool modules (they register themselves on import, same as server.py).
from .tools import (
    code_changes,
    commands,
    core,
    manny_navigation,
    monitoring,
    quests,
    routine,
    screenshot,
    session,  # noqa: F401  (registers record_session / recording_to_routine)
    sessions,  # noqa: F401  (registers session_status / manage_session)
    spatial,
)

_initialized = False


def init_registry(config: ServerConfig = None, project_root: str = None) -> ServerConfig:
    """Idempotently wire the shared ToolRegistry for in-process use.

    Args:
        config: An already-loaded ServerConfig to reuse. If None, loads one
            (from ``RUNELITE_MCP_CONFIG`` or ``<project_root>/config.yaml``).
        project_root: Directory containing config.yaml / mcptools / manny_tools.py.
            Added to sys.path (if not already present) so the `from manny_tools
            import ...` / `from request_code_change import ...` imports inside
            tool modules resolve regardless of the caller's cwd -- mirroring
            the guarantee the old subprocess got for free via its `cwd=`.

    Returns:
        The ServerConfig now shared by ``transport`` and every tool module.
    """
    global _initialized

    if project_root and project_root not in sys.path:
        sys.path.insert(0, project_root)

    load_dotenv()

    if config is None:
        config_path = None
        if project_root:
            config_path = os.path.join(project_root, "config.yaml")
        config = ServerConfig.load(config_path)

    # Reuse one ServerConfig (and one account resolver) everywhere, same as server.py.
    transport.set_config(config)

    if _initialized:
        return config

    try:
        import google.generativeai as genai
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
    except ImportError:
        genai = None

    runelite_manager = MultiRuneLiteManager(config)

    async def send_command_with_response(command: str, timeout_ms: int = 3000, account_id: str = None) -> dict:
        """Thin wrapper over transport.send_command (see server.py's twin of this)."""
        return await transport.send_command(
            command,
            account_id=account_id,
            await_response=True,
            timeout=timeout_ms / 1000.0,
        )

    core.set_dependencies(runelite_manager, config)
    monitoring.set_dependencies(runelite_manager, config)
    screenshot.set_dependencies(runelite_manager, config, genai)
    routine.set_dependencies(send_command_with_response, config, runelite_manager)
    commands.set_dependencies(send_command_with_response, config)
    spatial.set_dependencies(send_command_with_response, config)
    code_changes.set_dependencies(config)
    manny_navigation.set_dependencies(config)
    quests.set_dependencies(runelite_manager, config)

    _initialized = True
    return config


def get_registry():
    """Return the shared ToolRegistry (only meaningful after init_registry())."""
    return registry
