"""
RuneLite process management.
Extracted from server.py for better modularity.
Supports multi-client via account_id parameter.

Credential Flow:
1. Credentials stored in ~/.manny/credentials.yaml (secure, gitignored)
2. On start_instance(), writes to ~/.runelite/credentials.properties
3. RuneLite reads credentials.properties for JX_REFRESH_TOKEN and JX_ACCESS_TOKEN
"""
import os
import subprocess
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from .config import ServerConfig, AccountConfig
from .credentials import credential_manager
from .session_manager import session_manager


class RuneLiteInstance:
    """Manages a single RuneLite process instance."""

    def __init__(self, config: ServerConfig, account_id: str = None):
        """
        Initialize RuneLiteInstance.

        Args:
            config: Server configuration
            account_id: Account identifier (for multi-client support)
        """
        self.config = config
        self.account_id = account_id or "default"
        self.process = None
        self.log_buffer = deque(maxlen=config.log_buffer_size)
        self.log_lock = threading.Lock()
        self.log_thread = None
        self.log_file = None
        self.log_file_path = None

    def _capture_logs(self):
        """Background thread to capture process output."""
        if not self.process:
            return
        try:
            for line in iter(self.process.stdout.readline, ''):
                if not line:
                    break
                timestamp = datetime.now().isoformat()
                with self.log_lock:
                    self.log_buffer.append((timestamp, line.rstrip()))
        except Exception:
            pass

    def _setup_proxychains(self, proxy_url: str) -> Optional[str]:
        """
        Set up proxychains config for the given proxy URL.

        Proxychains intercepts all network calls and routes them through the proxy,
        handling authentication transparently (unlike Java's built-in proxy support).

        Returns path to config file, or None if setup fails.
        """
        try:
            from urllib.parse import urlparse
            import shutil
            import socket

            # Check if proxychains is installed
            if not shutil.which("proxychains4"):
                return None

            parsed = urlparse(proxy_url)
            if not parsed.hostname or not parsed.port:
                return None

            # Resolve hostname to IP (proxychains needs IP for first proxy in strict chain)
            try:
                proxy_ip = socket.gethostbyname(parsed.hostname)
            except socket.gaierror:
                proxy_ip = parsed.hostname  # Fall back to hostname if resolution fails

            # Determine proxy type for proxychains config
            if parsed.scheme in ("socks5", "socks"):
                proxy_type = "socks5"
            elif parsed.scheme == "socks4":
                proxy_type = "socks4"
            elif parsed.scheme in ("http", "https"):
                proxy_type = "http"
            else:
                return None

            # Build proxy line: type ip port [user pass]
            if parsed.username and parsed.password:
                proxy_line = f"{proxy_type} {proxy_ip} {parsed.port} {parsed.username} {parsed.password}"
            else:
                proxy_line = f"{proxy_type} {proxy_ip} {parsed.port}"

            # Write config file
            config_path = Path.home() / ".manny" / "proxychains.conf"
            config_path.parent.mkdir(parents=True, exist_ok=True)

            config_content = f"""# Proxychains config for manny RuneLite
# Auto-generated - do not edit manually

strict_chain
proxy_dns
tcp_read_time_out 15000
tcp_connect_time_out 8000

[ProxyList]
{proxy_line}
"""
            config_path.write_text(config_content)
            return str(config_path)

        except Exception:
            return None

    def start(self, developer_mode: bool = True, display: str = None, proxy: str = None) -> Dict[str, Any]:
        """Start RuneLite process for this account.

        Args:
            developer_mode: Enable RuneLite developer mode
            display: Display to run on (e.g., ":2"). If None, uses config default.
            proxy: Optional proxy URL (e.g., "socks5://user:pass@host:port")
        """
        if self.process and self.process.poll() is None:
            self.stop()
            status = "restarted"
        else:
            status = "started"

        # Get account-specific config
        account_config = self.config.get_account_config(self.account_id)

        # Use provided display or fall back to config
        target_display = display or account_config.display

        # Build the command
        use_vgl = self.config.use_virtualgl
        vgl_display = self.config.vgl_display

        # Determine launch mode: prefer exec:java if source exists, fall back to JAR
        use_exec_java = self.config.use_exec_java
        runelite_root_exists = self.config.runelite_root and self.config.runelite_root.exists()
        runelite_jar_exists = self.config.runelite_jar and self.config.runelite_jar.exists()

        # Fall back to JAR if exec:java requested but source dir doesn't exist
        if use_exec_java and not runelite_root_exists:
            if runelite_jar_exists:
                use_exec_java = False  # Fall back to JAR
            else:
                return {
                    "account_id": self.account_id,
                    "pid": None,
                    "status": "error",
                    "error": f"RuneLite source not found at {self.config.runelite_root} and no JAR configured"
                }

        # If not using exec:java, verify JAR exists
        if not use_exec_java and not runelite_jar_exists:
            return {
                "account_id": self.account_id,
                "pid": None,
                "status": "error",
                "error": f"RuneLite JAR not found at {self.config.runelite_jar}"
            }

        if use_exec_java:
            args = " ".join(self.config.runelite_args)
            base_cmd = [
                "mvn", "exec:java",
                "-pl", "runelite-client",
                "-Dexec.mainClass=net.runelite.client.RuneLite",
                # Note: Removed -Dsun.java2d.uiScale=2.0 - it caused coordinate mismatch
                # with gamescope/Xwayland, making the sidebar unclickable
            ]
            if args:
                base_cmd.append(f"-Dexec.args={args}")
            cwd = str(self.config.runelite_root)
        else:
            base_cmd = [self.config.java_path, "-jar", str(self.config.runelite_jar)]
            base_cmd.extend(self.config.runelite_args)
            cwd = None

        if use_vgl:
            cmd = ["vglrun", "-d", vgl_display] + base_cmd
        else:
            cmd = base_cmd

        # Set up proxychains if proxy is specified
        proxychains_config = None
        if proxy:
            proxychains_config = self._setup_proxychains(proxy)
            if proxychains_config:
                # Prepend proxychains to command - intercepts all network calls
                cmd = ["proxychains4", "-q", "-f", proxychains_config] + cmd

        env = os.environ.copy()

        # Java heap size - reduced for VPS with limited RAM
        env["_JAVA_OPTIONS"] = "-Xmx768m -XX:MaxMetaspaceSize=128m"

        # Use allocated display
        env["DISPLAY"] = target_display

        # Account-specific credentials from credential_manager (not config/.env)
        # This ensures we use the correct account's credentials, not hardcoded .env values
        creds = credential_manager.get_account(self.account_id)
        if creds:
            env["JX_CHARACTER_ID"] = creds.get("jx_character_id", "")
            env["JX_DISPLAY_NAME"] = creds.get("display_name", "")
            env["JX_SESSION_ID"] = creds.get("jx_session_id", "")
        else:
            # Fall back to config (which may read from .env) only if no creds in store
            env["JX_CHARACTER_ID"] = account_config.jx_character_id
            env["JX_DISPLAY_NAME"] = account_config.jx_display_name
            env["JX_SESSION_ID"] = account_config.jx_session_id

        # Set account ID for plugin to use in file paths
        if self.account_id and self.account_id != "default":
            env["MANNY_ACCOUNT_ID"] = self.account_id

        self.log_buffer.clear()

        # Use file output instead of PIPE to prevent subprocess deadlock
        # PIPE can block when buffer fills during heavy logging (e.g., plugin loading)
        log_suffix = f"_{self.account_id}" if self.account_id and self.account_id != "default" else ""
        self.log_file_path = f"/tmp/runelite{log_suffix}.log"
        self.log_file = open(self.log_file_path, "w")

        self.process = subprocess.Popen(
            cmd,
            stdout=self.log_file,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=cwd
        )

        time.sleep(3)

        # Read startup logs from file
        startup_logs = []
        try:
            self.log_file.flush()
            with open(self.log_file_path, "r") as f:
                startup_logs = f.read().splitlines()[:50]
        except Exception:
            pass

        result = {
            "account_id": self.account_id,
            "pid": self.process.pid,
            "status": status,
            "display": target_display,
            "startup_logs": startup_logs,
            "log_file": self.log_file_path,
            "command": " ".join(cmd)
        }

        # Add proxy info if used
        if proxy:
            from urllib.parse import urlparse
            parsed = urlparse(proxy)
            result["proxy"] = {
                "enabled": True,
                "method": "proxychains" if proxychains_config else "jvm_opts",
                "config_file": proxychains_config,
                "scheme": parsed.scheme,
                "host": parsed.hostname,
                "port": parsed.port
            }

        return result

    def stop(self) -> Dict[str, Any]:
        """Stop this RuneLite instance."""
        if not self.process:
            return {"stopped": False, "account_id": self.account_id, "message": "No process running"}

        pid = self.process.pid

        self.process.terminate()
        try:
            exit_code = self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            exit_code = self.process.wait()

        self.process = None

        # Close log file
        if self.log_file:
            try:
                self.log_file.close()
            except Exception:
                pass
            self.log_file = None

        return {"stopped": True, "account_id": self.account_id, "exit_code": exit_code, "pid": pid}

    def is_running(self) -> bool:
        """Check if this instance is running."""
        return self.process is not None and self.process.poll() is None

    def get_logs(
        self,
        level: str = "WARN",
        since_seconds: float = 30,
        grep: str = None,
        max_lines: int = 100,
        plugin_only: bool = True
    ) -> Dict[str, Any]:
        """Get filtered logs from this instance."""
        level_priority = {"DEBUG": 0, "INFO": 1, "WARN": 2, "ERROR": 3, "ALL": -1}
        min_level = level_priority.get(level.upper(), 2)

        cutoff_time = datetime.now().timestamp() - since_seconds
        plugin_prefix = self.config.plugin_logger_prefix

        matching_lines = []
        total_matching = 0

        with self.log_lock:
            for timestamp_str, line in self.log_buffer:
                try:
                    ts = datetime.fromisoformat(timestamp_str).timestamp()
                except:
                    ts = 0

                if ts < cutoff_time:
                    continue

                if min_level >= 0:
                    line_level = -1
                    if "[DEBUG]" in line or " DEBUG " in line:
                        line_level = 0
                    elif "[INFO]" in line or " INFO " in line:
                        line_level = 1
                    elif "[WARN]" in line or " WARN " in line:
                        line_level = 2
                    elif "[ERROR]" in line or " ERROR " in line:
                        line_level = 3

                    if line_level < min_level:
                        continue

                if plugin_only and plugin_prefix.lower() not in line.lower():
                    continue

                if grep and grep.lower() not in line.lower():
                    continue

                total_matching += 1
                if len(matching_lines) < max_lines:
                    matching_lines.append(line)

        return {
            "account_id": self.account_id,
            "lines": matching_lines,
            "truncated": total_matching > max_lines,
            "total_matching": total_matching
        }


class MultiRuneLiteManager:
    """Manages multiple RuneLite instances for multi-client support."""

    def __init__(self, config: ServerConfig):
        self.config = config
        self.instances: Dict[str, RuneLiteInstance] = {}

    def _kill_all_runelite(self) -> Dict[str, Any]:
        """
        Kill ALL RuneLite processes (not just tracked ones).

        This ensures a clean slate before starting a new instance,
        preventing credential conflicts between accounts.
        """
        killed_tracked = []
        killed_external = 0

        # Stop all tracked instances first
        for aid in list(self.instances.keys()):
            if self.instances[aid].is_running():
                self.instances[aid].stop()
                killed_tracked.append(aid)
        self.instances.clear()

        # Kill any external RuneLite processes (pkill by pattern)
        try:
            # Kill by java process running RuneLite
            result = subprocess.run(
                ["pkill", "-f", "net.runelite.client.RuneLite"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                killed_external += 1
        except Exception:
            pass

        try:
            # Also try killing by mvn exec pattern
            subprocess.run(
                ["pkill", "-f", "runelite-client.*exec:java"],
                capture_output=True,
                text=True
            )
        except Exception:
            pass

        # Brief pause to ensure clean shutdown
        time.sleep(1)

        return {
            "killed_tracked": killed_tracked,
            "killed_external": killed_external > 0
        }

    def _write_credentials(self, account_id: str) -> Dict[str, Any]:
        """
        Write credentials.properties for the selected account.

        RuneLite reads ~/.runelite/credentials.properties for JX_REFRESH_TOKEN
        and JX_ACCESS_TOKEN. This method overwrites that file with the
        credentials for the specified account.

        Args:
            account_id: Account alias from credentials.yaml

        Returns:
            Dict with success status and any warnings.
        """
        creds = credential_manager.get_account(account_id)

        if not creds:
            # No credentials in store - this is OK, will use manual login
            return {
                "success": True,
                "warning": f"No credentials found for '{account_id}'. Manual login required.",
                "credentials_written": False
            }

        refresh_token = creds.get("jx_refresh_token", "")
        access_token = creds.get("jx_access_token", "")
        character_id = creds.get("jx_character_id", "")
        session_id = creds.get("jx_session_id", "")
        display_name = creds.get("display_name", "")

        # We can proceed with just identity fields (character_id, session_id, display_name)
        # Tokens are optional - Bolt/Jagex launcher handle auth differently
        if not character_id and not session_id and not refresh_token and not access_token:
            return {
                "success": True,
                "warning": f"Account '{account_id}' has no credentials. Manual login required.",
                "credentials_written": False
            }

        # Write to ~/.runelite/credentials.properties
        creds_file = Path.home() / ".runelite" / "credentials.properties"

        try:
            # Ensure .runelite directory exists
            creds_file.parent.mkdir(parents=True, exist_ok=True)

            # Build content with all available fields
            # Order matters - some fields may be required by RuneLite
            lines = ["#Do not share this file with anyone"]
            lines.append(f"#Generated by manny-mcp for account: {account_id}")
            if character_id:
                lines.append(f"JX_CHARACTER_ID={character_id}")
            if session_id:
                lines.append(f"JX_SESSION_ID={session_id}")
            if display_name:
                lines.append(f"JX_DISPLAY_NAME={display_name}")
            lines.append(f"JX_REFRESH_TOKEN={refresh_token}")
            lines.append(f"JX_ACCESS_TOKEN={access_token}")

            content = "\n".join(lines) + "\n"
            creds_file.write_text(content)

            return {
                "success": True,
                "credentials_written": True,
                "account": account_id,
                "display_name": creds.get("display_name", "")
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to write credentials: {e}",
                "credentials_written": False
            }

    def start_instance(self, account_id: str = None, developer_mode: bool = True, display: str = None, proxy: str = None) -> Dict[str, Any]:
        """
        Start a RuneLite instance for the given account.

        This method:
        1. Checks playtime limit (12hr/24hr)
        2. Allocates a display from the pool (or uses specified display)
        3. Kills ALL running RuneLite instances (ensures clean slate)
        4. Writes credentials.properties for the specified account
        5. Starts a new RuneLite instance
        6. Records the session start for playtime tracking

        Args:
            account_id: Account alias from credentials.yaml, or None for default
            developer_mode: Enable RuneLite developer mode
            display: Optional specific display to use (e.g., ":2")
            proxy: Optional proxy URL (e.g., "socks5://user:pass@host:port")

        Returns:
            Dict with startup result and credential status.
        """
        # Reload config to pick up any changes (e.g., use_exec_java toggle)
        self.config = ServerConfig.load()

        # Resolve account_id: credential_manager.default -> config.default_account -> "default"
        if account_id is None:
            if credential_manager.default and credential_manager.default != "default":
                account_id = credential_manager.default
            else:
                account_id = self.config.default_account

        # Use stored proxy if none provided
        if not proxy:
            creds = credential_manager.get_account(account_id)
            if creds and creds.get("proxy"):
                proxy = creds["proxy"]

        # Step 0: Check playtime limit (warning only, doesn't block)
        playtime_warning = None
        if not session_manager.is_under_playtime_limit(account_id):
            playtime = session_manager.get_playtime_24h(account_id)
            playtime_warning = {
                "warning": f"Account '{account_id}' has exceeded 12hr playtime limit in 24h",
                "playtime_24h_hours": round(playtime, 2),
                "limit_hours": session_manager.MAX_PLAYTIME_24H_HOURS
            }

        # Step 1: Allocate display (or use specified)
        if display:
            allocated_display = display
        else:
            alloc_result = session_manager.allocate_display(account_id)
            if not alloc_result.get("success"):
                return {
                    "success": False,
                    "error": alloc_result.get("error", "Failed to allocate display"),
                    "active_sessions": alloc_result.get("active_sessions", [])
                }
            allocated_display = alloc_result["display"]

        # Step 2: Only kill instance for this account if already running (allows concurrent clients)
        kill_result = {"killed_tracked": [], "killed_external": False}
        if account_id in self.instances and self.instances[account_id].is_running():
            self.instances[account_id].stop()
            kill_result["killed_tracked"].append(account_id)

        # Step 3: Write credentials for this account
        creds_result = self._write_credentials(account_id)

        # Step 4: Start new instance on allocated display
        instance = RuneLiteInstance(self.config, account_id)
        # Override display with allocated one
        instance.config = self.config  # Keep config reference
        self.instances[account_id] = instance
        start_result = instance.start(developer_mode, display=allocated_display, proxy=proxy)

        # Step 5: Record session start
        if start_result.get("pid"):
            session_manager.start_session(
                account_id=account_id,
                display=allocated_display,
                pid=start_result["pid"]
            )
            start_result["session"] = {
                "display": allocated_display,
                "playtime_tracking": True
            }

        # Combine results
        start_result["credentials"] = creds_result
        start_result["killed_previous"] = kill_result
        if playtime_warning:
            start_result["playtime_warning"] = playtime_warning

        return start_result

    def stop_instance(self, account_id: str = None) -> Dict[str, Any]:
        """Stop a specific RuneLite instance and end session tracking."""
        account_id = account_id or self.config.default_account

        if account_id not in self.instances:
            # Still try to end any session tracking
            session_manager.end_session(account_id=account_id)
            return {"stopped": False, "account_id": account_id, "message": f"No instance for account: {account_id}"}

        result = self.instances[account_id].stop()
        del self.instances[account_id]

        # End session tracking (records playtime)
        session_result = session_manager.end_session(account_id=account_id)
        result["session_ended"] = session_result.get("success", False)

        return result

    def get_instance(self, account_id: str = None) -> Optional[RuneLiteInstance]:
        """Get instance by account ID."""
        account_id = account_id or self.config.default_account
        return self.instances.get(account_id)

    def list_instances(self) -> List[Dict[str, Any]]:
        """List all running instances."""
        return [
            {
                "account_id": aid,
                "pid": inst.process.pid if inst.process else None,
                "running": inst.is_running()
            }
            for aid, inst in self.instances.items()
        ]

    def stop_all(self) -> List[Dict[str, Any]]:
        """Stop all running instances."""
        results = []
        for account_id in list(self.instances.keys()):
            results.append(self.stop_instance(account_id))
        return results


# Backwards-compatible alias
class RuneLiteManager:
    """Backwards-compatible single-instance manager (wraps MultiRuneLiteManager)."""

    def __init__(self, config: ServerConfig):
        self.config = config
        self._multi = MultiRuneLiteManager(config)
        self._default_account = config.default_account

    @property
    def process(self):
        instance = self._multi.get_instance(self._default_account)
        return instance.process if instance else None

    @property
    def log_buffer(self):
        instance = self._multi.get_instance(self._default_account)
        return instance.log_buffer if instance else deque()

    @property
    def log_lock(self):
        instance = self._multi.get_instance(self._default_account)
        return instance.log_lock if instance else threading.Lock()

    def start(self, developer_mode: bool = True) -> Dict[str, Any]:
        """Start default RuneLite instance."""
        return self._multi.start_instance(self._default_account, developer_mode)

    def stop(self) -> Dict[str, Any]:
        """Stop default RuneLite instance."""
        return self._multi.stop_instance(self._default_account)

    def is_running(self) -> bool:
        """Check if default instance is running."""
        instance = self._multi.get_instance(self._default_account)
        return instance.is_running() if instance else False

    def get_logs(
        self,
        level: str = "WARN",
        since_seconds: float = 30,
        grep: str = None,
        max_lines: int = 100,
        plugin_only: bool = True
    ) -> Dict[str, Any]:
        """Get logs from default instance."""
        instance = self._multi.get_instance(self._default_account)
        if instance:
            return instance.get_logs(level, since_seconds, grep, max_lines, plugin_only)
        return {"lines": [], "truncated": False, "total_matching": 0}
