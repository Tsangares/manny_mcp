"""
Server configuration management.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any
import yaml
import os


@dataclass
class AccountConfig:
    """Configuration for a single OSRS account"""
    display: str
    jx_character_id: str = ""
    jx_display_name: str = ""
    jx_session_id: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "AccountConfig":
        return cls(
            display=data.get("display", ":2"),
            jx_character_id=data.get("jx_character_id", ""),
            jx_display_name=data.get("jx_display_name", ""),
            jx_session_id=data.get("jx_session_id", ""),
        )


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

    # Default account credentials (can also be set via env vars)
    jx_character_id: str = ""
    jx_display_name: str = ""
    jx_session_id: str = ""

    # Multi-client support
    accounts: Dict[str, AccountConfig] = field(default_factory=dict)
    default_account: str = "default"

    def get_account_config(self, account_id: str = None) -> AccountConfig:
        """Get account config, falling back to default if not specified"""
        account_id = account_id or self.default_account
        if account_id in self.accounts:
            return self.accounts[account_id]
        # Return default config based on top-level settings
        return AccountConfig(
            display=self.display,
            jx_character_id=self.jx_character_id,
            jx_display_name=self.jx_display_name,
            jx_session_id=self.jx_session_id,
        )

    def get_command_file(self, account_id: str = None) -> str:
        """Get command file path for account"""
        if account_id and account_id != "default":
            return f"/tmp/manny_{account_id}_command.txt"
        return self.command_file

    def get_state_file(self, account_id: str = None) -> str:
        """Get state file path for account"""
        if account_id and account_id != "default":
            return f"/tmp/manny_{account_id}_state.json"
        return self.state_file

    def get_response_file(self, account_id: str = None) -> str:
        """Get response file path for account"""
        if account_id and account_id != "default":
            return f"/tmp/manny_{account_id}_response.json"
        # Default response file path
        return self.state_file.replace("state.json", "response.json")

    def get_display(self, account_id: str = None) -> str:
        """Get display for account (e.g., ':2', ':3')"""
        account_config = self.get_account_config(account_id)
        return account_config.display or self.display

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

        # Parse default account credentials (fall back to env vars if not in config)
        data.setdefault("jx_character_id", os.environ.get("JX_CHARACTER_ID", ""))
        data.setdefault("jx_display_name", os.environ.get("JX_DISPLAY_NAME", ""))
        data.setdefault("jx_session_id", os.environ.get("JX_SESSION_ID", ""))

        # Parse multi-client accounts configuration
        accounts_data = data.pop("accounts", {})
        accounts = {}
        for account_id, account_config in accounts_data.items():
            accounts[account_id] = AccountConfig.from_dict(account_config)
        data["accounts"] = accounts
        data.setdefault("default_account", "default")

        return cls(**data)

    def to_dict(self) -> dict:
        """Convert config to dict (for logging/debugging)"""
        return {
            "runelite_root": str(self.runelite_root),
            "plugin_directory": str(self.plugin_directory),
            "display": self.display,
            "use_exec_java": self.use_exec_java,
        }
