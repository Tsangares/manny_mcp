"""
Multi-client session management.

Manages display allocation, account-to-display mapping, and playtime tracking.
Each RuneLite client runs on its own display (:2, :3, :4, etc.) to avoid mouse conflicts.

Usage:
    from mcptools.session_manager import session_manager

    # Get an available display for an account
    display = session_manager.allocate_display("aux")

    # Record session start
    session_manager.start_session("aux", display, pid=12345)

    # Check playtime
    hours = session_manager.get_playtime_24h("aux")

    # End session
    session_manager.end_session("aux")
"""
import os
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml


class SessionManager:
    """
    Manages multi-client sessions with display allocation and playtime tracking.
    """

    SESSIONS_FILE = Path.home() / ".manny" / "sessions.yaml"

    # Display pool configuration
    MIN_DISPLAY = 2  # Start from :2
    MAX_DISPLAYS = 4  # :2, :3, :4, :5

    # Playtime limits
    MAX_PLAYTIME_24H_HOURS = 12  # Max 12 hours per account in 24h window

    def __init__(self):
        self.displays: Dict[str, Optional[Dict]] = {}  # ":2" -> {account, pid, started}
        self.playtime: Dict[str, List[Dict]] = {}  # account -> [{start, end}, ...]
        self._load()

    def _ensure_dir(self) -> None:
        """Ensure sessions directory exists."""
        self.SESSIONS_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)

    def _load(self) -> None:
        """Load sessions from file."""
        if not self.SESSIONS_FILE.exists():
            self._init_displays()
            return

        try:
            with open(self.SESSIONS_FILE, 'r') as f:
                data = yaml.safe_load(f) or {}

            self.displays = data.get("displays", {})
            self.playtime = data.get("playtime", {})

            # Ensure all displays in pool exist
            self._init_displays()

        except Exception as e:
            print(f"Warning: Could not load sessions: {e}")
            self._init_displays()

    def _init_displays(self) -> None:
        """Initialize display pool."""
        for i in range(self.MIN_DISPLAY, self.MIN_DISPLAY + self.MAX_DISPLAYS):
            display = f":{i}"
            if display not in self.displays:
                self.displays[display] = None

    def _save(self) -> None:
        """Save sessions to file."""
        self._ensure_dir()

        data = {
            "displays": self.displays,
            "playtime": self.playtime
        }

        with open(self.SESSIONS_FILE, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def _is_display_running(self, display: str) -> bool:
        """Check if a display server is running."""
        try:
            # Check if X server is listening on this display
            result = subprocess.run(
                ["xdpyinfo", "-display", display],
                capture_output=True,
                timeout=2
            )
            return result.returncode == 0
        except Exception:
            return False

    def _start_display(self, display: str) -> Dict[str, Any]:
        """Start a new display server using start_screen.sh."""
        display_num = display.lstrip(":")

        # Check if already running
        if self._is_display_running(display):
            return {"success": True, "display": display, "status": "already_running"}

        try:
            # Use start_screen.sh to start the display
            # Primary display (:2) uses gamescope, additional displays use Xwayland
            script_path = Path(__file__).parent.parent / "start_screen.sh"

            if display_num == "2":
                # Primary display - run without argument (uses gamescope)
                cmd = [str(script_path)]
            else:
                # Additional display - pass display number (uses Xwayland)
                cmd = [str(script_path), display_num]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0 and self._is_display_running(display):
                return {
                    "success": True,
                    "display": display,
                    "status": "started",
                    "output": result.stdout.strip()
                }

            return {
                "success": False,
                "display": display,
                "error": result.stderr.strip() or "Display did not start",
                "output": result.stdout.strip()
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "display": display,
                "error": "start_screen.sh timed out after 30s"
            }
        except Exception as e:
            return {
                "success": False,
                "display": display,
                "error": str(e)
            }

    def get_available_display(self) -> Optional[str]:
        """Get the first available (unused) display."""
        for display, session in self.displays.items():
            if session is None:
                return display
        return None

    def get_display_for_account(self, account_id: str) -> Optional[str]:
        """Get the display an account is currently using, if any."""
        for display, session in self.displays.items():
            if session and session.get("account") == account_id:
                return display
        return None

    def allocate_display(self, account_id: str) -> Dict[str, Any]:
        """
        Allocate a display for an account.

        Returns existing display if account is already running,
        or allocates a new one from the pool.

        IMPORTANT: Always reloads from disk first to prevent conflicts
        between multiple MCP server instances.
        """
        # CRITICAL: Reload from disk to see what other sessions have claimed
        # This prevents conflicts when multiple Claude sessions are running
        self._load()

        # Check if account already has a display
        existing = self.get_display_for_account(account_id)
        if existing:
            return {
                "success": True,
                "display": existing,
                "status": "existing",
                "session": self.displays[existing]
            }

        # Find an available display
        display = self.get_available_display()
        if not display:
            return {
                "success": False,
                "error": f"No available displays. All {self.MAX_DISPLAYS} slots in use.",
                "active_sessions": self.get_active_sessions()
            }

        # Ensure display server is running
        display_result = self._start_display(display)
        if not display_result.get("success"):
            # Try using start_screen.sh as fallback
            pass  # For now, assume display management is external

        return {
            "success": True,
            "display": display,
            "status": "allocated"
        }

    def start_session(self, account_id: str, display: str, pid: int) -> Dict[str, Any]:
        """Record that an account session has started on a display."""
        now = datetime.now().isoformat()

        self.displays[display] = {
            "account": account_id,
            "pid": pid,
            "started": now
        }

        # Initialize playtime tracking for this account if needed
        if account_id not in self.playtime:
            self.playtime[account_id] = []

        # Add session start (end will be filled when session ends)
        self.playtime[account_id].append({
            "start": now,
            "end": None,
            "display": display
        })

        self._save()

        return {
            "success": True,
            "account": account_id,
            "display": display,
            "pid": pid,
            "started": now
        }

    def end_session(self, account_id: str = None, display: str = None) -> Dict[str, Any]:
        """
        End a session by account_id or display.
        Records the end time for playtime tracking.
        """
        # Find the session
        target_display = None

        if display:
            target_display = display
        elif account_id:
            target_display = self.get_display_for_account(account_id)

        if not target_display or not self.displays.get(target_display):
            return {
                "success": False,
                "error": "Session not found"
            }

        session = self.displays[target_display]
        session_account = session["account"]
        now = datetime.now().isoformat()

        # Update playtime - find the open session and close it
        if session_account in self.playtime:
            for pt in reversed(self.playtime[session_account]):
                if pt.get("end") is None:
                    pt["end"] = now
                    break

        # Free the display
        self.displays[target_display] = None
        self._save()

        return {
            "success": True,
            "account": session_account,
            "display": target_display,
            "ended": now
        }

    def get_playtime_24h(self, account_id: str) -> float:
        """
        Get total playtime for an account in the last 24 hours.
        Returns hours as a float.
        """
        if account_id not in self.playtime:
            return 0.0

        cutoff = datetime.now() - timedelta(hours=24)
        total_seconds = 0

        for session in self.playtime[account_id]:
            start = datetime.fromisoformat(session["start"])
            end = datetime.fromisoformat(session["end"]) if session.get("end") else datetime.now()

            # Only count time within the 24h window
            if end < cutoff:
                continue

            effective_start = max(start, cutoff)
            effective_end = end

            total_seconds += (effective_end - effective_start).total_seconds()

        return total_seconds / 3600  # Convert to hours

    def is_under_playtime_limit(self, account_id: str) -> bool:
        """Check if account is under the 24h playtime limit."""
        return self.get_playtime_24h(account_id) < self.MAX_PLAYTIME_24H_HOURS

    def get_accounts_under_limit(self, account_ids: List[str]) -> List[str]:
        """Filter accounts to those under the playtime limit."""
        return [a for a in account_ids if self.is_under_playtime_limit(a)]

    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Get all currently active sessions."""
        active = []
        for display, session in self.displays.items():
            if session:
                session_copy = session.copy()
                session_copy["display"] = display
                active.append(session_copy)
        return active

    def get_session_status(self, account_id: str = None) -> Dict[str, Any]:
        """Get status of all sessions or a specific account."""
        if account_id:
            display = self.get_display_for_account(account_id)
            if display:
                return {
                    "active": True,
                    "account": account_id,
                    "display": display,
                    "session": self.displays[display],
                    "playtime_24h": self.get_playtime_24h(account_id),
                    "under_limit": self.is_under_playtime_limit(account_id)
                }
            else:
                return {
                    "active": False,
                    "account": account_id,
                    "playtime_24h": self.get_playtime_24h(account_id),
                    "under_limit": self.is_under_playtime_limit(account_id)
                }

        # Return all sessions
        return {
            "active_sessions": self.get_active_sessions(),
            "available_displays": [d for d, s in self.displays.items() if s is None],
            "total_displays": len(self.displays)
        }

    def cleanup_stale_sessions(self) -> Dict[str, Any]:
        """
        Clean up sessions where the process is no longer running.
        Call this periodically to free up displays from crashed clients.
        """
        cleaned = []

        for display, session in list(self.displays.items()):
            if session is None:
                continue

            pid = session.get("pid")
            if pid:
                # Check if process is still running
                try:
                    os.kill(pid, 0)  # Signal 0 = check if process exists
                except ProcessLookupError:
                    # Process is dead, clean up
                    self.end_session(display=display)
                    cleaned.append({
                        "display": display,
                        "account": session.get("account"),
                        "pid": pid
                    })
                except PermissionError:
                    # Process exists but we can't signal it (still running)
                    pass

        return {
            "cleaned": cleaned,
            "count": len(cleaned)
        }

    def reload(self) -> None:
        """Reload sessions from disk."""
        self._load()


# Global singleton instance
session_manager = SessionManager()
