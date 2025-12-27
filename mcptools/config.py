"""
Server configuration management.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import yaml
import os


@dataclass
class ServerConfig:
    """MCP Server configuration"""

    # RuneLite paths
    runelite_root: Path
    plugin_directory: Path
    runelite_jar: Optional[Path]

    # Execution settings
    use_exec_java: bool
    java_path: str
    runelite_args: List[str]
    display: str

    # VirtualGL settings
    use_virtualgl: bool
    vgl_display: str

    # Logging
    log_file: Path
    log_buffer_size: int
    plugin_logger_prefix: str

    # Command interface
    command_file: str
    state_file: str
    session_file: Path

    # Video streaming (dashboard)
    video_streaming: dict

    @classmethod
    def load(cls, path: str | Path = None) -> "ServerConfig":
        """
        Load configuration from YAML file.

        Args:
            path: Path to config.yaml. If None, uses environment variable
                  RUNELITE_MCP_CONFIG or defaults to ./config.yaml

        Returns:
            ServerConfig instance
        """
        if path is None:
            path = os.environ.get("RUNELITE_MCP_CONFIG", Path.cwd() / "config.yaml")

        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path) as f:
            data = yaml.safe_load(f)

        # Expand ~ in path fields
        for key in ["log_file", "session_file", "runelite_jar", "runelite_root", "plugin_directory"]:
            if key in data and data[key] is not None:
                if isinstance(data[key], str):
                    data[key] = Path(data[key]).expanduser()

        # Convert to Path objects
        data["runelite_root"] = Path(data["runelite_root"])
        data["plugin_directory"] = Path(data["plugin_directory"])
        if data.get("runelite_jar"):
            data["runelite_jar"] = Path(data["runelite_jar"])
        data["log_file"] = Path(data["log_file"])
        data["session_file"] = Path(data["session_file"])

        # Default values
        data.setdefault("use_exec_java", False)
        data.setdefault("java_path", "java")
        data.setdefault("runelite_args", [])
        data.setdefault("display", ":2")
        data.setdefault("use_virtualgl", False)
        data.setdefault("vgl_display", ":0")
        data.setdefault("log_buffer_size", 10000)
        data.setdefault("plugin_logger_prefix", "manny")
        data.setdefault("command_file", "/tmp/manny_command.txt")
        data.setdefault("state_file", "/tmp/manny_state.json")
        data.setdefault("video_streaming", {})

        return cls(**data)

    def to_dict(self) -> dict:
        """Convert config to dict (for logging/debugging)"""
        return {
            "runelite_root": str(self.runelite_root),
            "plugin_directory": str(self.plugin_directory),
            "display": self.display,
            "use_exec_java": self.use_exec_java,
        }
