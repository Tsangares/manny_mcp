"""
RuneLite process management.
Extracted from server.py for better modularity.
"""
import os
import subprocess
import threading
import time
from collections import deque
from datetime import datetime
from typing import Dict, Any
from .config import ServerConfig


class RuneLiteManager:
    """Manages RuneLite process and log capture."""

    def __init__(self, config: ServerConfig):
        """
        Initialize RuneLiteManager.

        Args:
            config: Server configuration
        """
        self.config = config
        self.process = None
        self.log_buffer = deque(maxlen=config.log_buffer_size)
        self.log_lock = threading.Lock()
        self.log_thread = None

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

    def start(self, developer_mode: bool = True) -> Dict[str, Any]:
        """
        Start RuneLite process.

        Args:
            developer_mode: Enable RuneLite developer mode

        Returns:
            Dict with pid, status, startup_logs, command
        """
        if self.process and self.process.poll() is None:
            # Already running, restart
            self.stop()
            status = "restarted"
        else:
            status = "started"

        # Build the command based on config
        use_vgl = self.config.use_virtualgl
        vgl_display = self.config.vgl_display

        if self.config.use_exec_java:
            # Use mvn exec:java
            args = " ".join(self.config.runelite_args)
            base_cmd = [
                "mvn", "exec:java",
                "-pl", "runelite-client",
                "-Dexec.mainClass=net.runelite.client.RuneLite",
                "-Dsun.java2d.uiScale=2.0",  # HiDPI scaling
            ]
            if args:
                base_cmd.append(f"-Dexec.args={args}")
            cwd = str(self.config.runelite_root)
        else:
            # Use JAR directly
            base_cmd = [self.config.java_path, "-jar", str(self.config.runelite_jar)]
            base_cmd.extend(self.config.runelite_args)
            cwd = None

        # Wrap with vglrun if VirtualGL is enabled
        if use_vgl:
            cmd = ["vglrun", "-d", vgl_display] + base_cmd
        else:
            cmd = base_cmd

        env = os.environ.copy()
        env["DISPLAY"] = self.config.display
        # Jagex launcher session credentials for auto-login (from .env)
        env["JX_CHARACTER_ID"] = os.environ.get("JX_CHARACTER_ID", "")
        env["JX_DISPLAY_NAME"] = os.environ.get("JX_DISPLAY_NAME", "")
        env["JX_SESSION_ID"] = os.environ.get("JX_SESSION_ID", "")

        self.log_buffer.clear()

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            cwd=cwd,
            bufsize=1
        )

        # Start log capture thread
        self.log_thread = threading.Thread(target=self._capture_logs, daemon=True)
        self.log_thread.start()

        # Wait briefly for startup
        time.sleep(3)

        with self.log_lock:
            startup_logs = [line for _, line in list(self.log_buffer)[:50]]

        return {
            "pid": self.process.pid,
            "status": status,
            "startup_logs": startup_logs,
            "command": " ".join(cmd)
        }

    def stop(self) -> Dict[str, Any]:
        """
        Stop RuneLite process.

        Returns:
            Dict with stopped, exit_code, pid
        """
        if not self.process:
            return {"stopped": False, "exit_code": None, "message": "No process running"}

        pid = self.process.pid

        # Try graceful termination first
        self.process.terminate()
        try:
            exit_code = self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            exit_code = self.process.wait()

        self.process = None
        return {"stopped": True, "exit_code": exit_code, "pid": pid}

    def is_running(self) -> bool:
        """Check if RuneLite process is running"""
        return self.process is not None and self.process.poll() is None

    def get_logs(
        self,
        level: str = "WARN",
        since_seconds: float = 30,
        grep: str = None,
        max_lines: int = 100,
        plugin_only: bool = True
    ) -> Dict[str, Any]:
        """
        Get filtered logs from the buffer.

        Args:
            level: Minimum log level (DEBUG, INFO, WARN, ERROR, ALL)
            since_seconds: Only logs from last N seconds
            grep: Filter to lines containing this substring
            max_lines: Maximum number of lines to return
            plugin_only: Only show logs from the manny plugin

        Returns:
            Dict with lines, truncated, total_matching
        """
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

                # Time filter
                if ts < cutoff_time:
                    continue

                # Level filter
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

                # Plugin filter
                if plugin_only and plugin_prefix.lower() not in line.lower():
                    continue

                # Grep filter
                if grep and grep.lower() not in line.lower():
                    continue

                total_matching += 1
                if len(matching_lines) < max_lines:
                    matching_lines.append(line)

        return {
            "lines": matching_lines,
            "truncated": total_matching > max_lines,
            "total_matching": total_matching
        }
