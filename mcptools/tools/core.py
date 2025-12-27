"""
Core RuneLite control tools.
Handles building, starting, stopping, and checking status.
"""
import subprocess
import time
from pathlib import Path
from ..registry import registry
from ..utils import parse_maven_errors, parse_maven_warnings


# Note: runelite_manager will be injected when server starts
runelite_manager = None
config = None


def set_dependencies(manager, server_config):
    """Inject dependencies (called from server.py startup)"""
    global runelite_manager, config
    runelite_manager = manager
    config = server_config


@registry.register({
    "name": "build_plugin",
    "description": "[RuneLite] Compile the manny RuneLite plugin using Maven. Returns structured build results with any errors.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "clean": {
                "type": "boolean",
                "description": "Whether to run 'mvn clean' first (default: true)",
                "default": True
            }
        }
    }
})
async def handle_build_plugin(arguments: dict) -> dict:
    """Run Maven to compile the plugin."""
    clean = arguments.get("clean", True)
    start_time = time.time()

    cmd = ["mvn"]
    if clean:
        cmd.append("clean")
    cmd.extend(["compile", "-pl", "runelite-client", "-T", "1C", "-DskipTests"])

    result = subprocess.run(
        cmd,
        cwd=str(config.runelite_root),
        capture_output=True,
        text=True,
        timeout=300  # 5 minute timeout
    )

    build_time = time.time() - start_time
    output = result.stdout + result.stderr

    errors = parse_maven_errors(output)
    warnings = parse_maven_warnings(output)

    return {
        "success": result.returncode == 0,
        "build_time_seconds": round(build_time, 2),
        "errors": errors,
        "warnings": warnings[:10],  # Truncate warnings
        "return_code": result.returncode
    }


@registry.register({
    "name": "start_runelite",
    "description": "[RuneLite] Start or restart the RuneLite client with the manny plugin loaded. Runs on display :2.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "developer_mode": {
                "type": "boolean",
                "description": "Enable RuneLite developer mode (default: true)",
                "default": True
            }
        }
    }
})
async def handle_start_runelite(arguments: dict) -> dict:
    """Start RuneLite process."""
    developer_mode = arguments.get("developer_mode", True)
    return runelite_manager.start(developer_mode=developer_mode)


@registry.register({
    "name": "stop_runelite",
    "description": "[RuneLite] Stop the managed RuneLite process.",
    "inputSchema": {
        "type": "object",
        "properties": {}
    }
})
async def handle_stop_runelite(arguments: dict) -> dict:
    """Stop RuneLite process."""
    return runelite_manager.stop()


@registry.register({
    "name": "runelite_status",
    "description": "[RuneLite] Check if RuneLite is currently running.",
    "inputSchema": {
        "type": "object",
        "properties": {}
    }
})
async def handle_runelite_status(arguments: dict) -> dict:
    """Check RuneLite status."""
    return {
        "running": runelite_manager.is_running(),
        "pid": runelite_manager.process.pid if runelite_manager.process else None
    }
