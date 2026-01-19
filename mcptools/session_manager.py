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
        self.account_displays: Dict[str, str] = {}  # Persistent account -> display mapping (e.g., "aux" -> ":2")
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
            self.account_displays = data.get("account_displays", {})

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
            "playtime": self.playtime,
            "account_displays": self.account_displays
        }

        with open(self.SESSIONS_FILE, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def _is_display_running(self, display: str) -> bool:
        """Check if a display server is running."""
        # Check for X11 socket first (faster than xdpyinfo)
        display_num = display.lstrip(":")
        socket_path = f"/tmp/.X11-unix/X{display_num}"
        if not os.path.exists(socket_path):
            return False

        # Verify with xdpyinfo that it's actually responsive
        try:
            result = subprocess.run(
                ["xdpyinfo", "-display", display],
                capture_output=True,
                timeout=2
            )
            return result.returncode == 0
        except Exception:
            return False

    def _get_running_displays(self) -> List[str]:
        """Find all running X displays from socket files."""
        running = []
        socket_dir = "/tmp/.X11-unix"

        if not os.path.exists(socket_dir):
            return running

        try:
            for entry in os.listdir(socket_dir):
                if entry.startswith("X"):
                    display_num = entry[1:]  # Remove 'X' prefix
                    if display_num.isdigit():
                        num = int(display_num)
                        # Only consider displays in our pool range (2-5)
                        if self.MIN_DISPLAY <= num < self.MIN_DISPLAY + self.MAX_DISPLAYS:
                            display = f":{display_num}"
                            # Verify it's actually responsive
                            if self._is_display_running(display):
                                running.append(display)
        except Exception:
            pass

        return sorted(running)

    def _start_display(self, display: str) -> Dict[str, Any]:
        """
        Start a new display server using start_screen.sh.

        Note: Gamescope picks its own display number, so we track displays
        before and after to find which one was actually created.
        """
        display_num = display.lstrip(":")

        # Check if already running
        if self._is_display_running(display):
            return {
                "success": True,
                "display": display,
                "actual_display": display,
                "status": "already_running"
            }

        # Record displays before starting
        displays_before = set(self._get_running_displays())

        try:
            script_path = Path(__file__).parent.parent / "start_screen.sh"

            if display_num == "2":
                # Primary display - run without argument (uses gamescope)
                cmd = [str(script_path)]
            else:
                # Additional display - pass display number (uses gamescope)
                cmd = [str(script_path), display_num]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            # Find what display was actually created
            displays_after = set(self._get_running_displays())
            new_displays = displays_after - displays_before

            if new_displays:
                # Use the first new display (should only be one)
                actual_display = sorted(new_displays)[0]
                return {
                    "success": True,
                    "display": display,
                    "actual_display": actual_display,
                    "status": "started",
                    "output": result.stdout.strip()
                }

            # Check if requested display is now running (might have been created)
            if self._is_display_running(display):
                return {
                    "success": True,
                    "display": display,
                    "actual_display": display,
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

        Simple approach:
        1. Check if account has a persistent display assignment
        2. If yes, use that display (start display server if needed)
        3. If no, assign the next available display number permanently

        Each account gets one display, forever. No reassignment.
        """
        # Reload to prevent conflicts
        self._load()

        # Check if account already has a permanent display assignment
        if account_id in self.account_displays:
            display = self.account_displays[account_id]

            # Ensure display server is running
            if not self._is_display_running(display):
                start_result = self._start_display(display)
                if not start_result.get("success"):
                    return {
                        "success": False,
                        "display": display,
                        "error": f"Failed to start assigned display {display}",
                        "start_result": start_result
                    }
                # Use actual display if gamescope picked a different one
                display = start_result.get("actual_display", display)
                self.account_displays[account_id] = display
                self._save()

            return {
                "success": True,
                "display": display,
                "status": "assigned",
                "note": f"Account {account_id} permanently assigned to {display}"
            }

        # Account has no display yet - assign the next available one
        assigned_displays = set(self.account_displays.values())

        for i in range(self.MIN_DISPLAY, self.MIN_DISPLAY + self.MAX_DISPLAYS):
            display = f":{i}"
            if display not in assigned_displays:
                # Assign this display to the account permanently
                self.account_displays[account_id] = display
                self._save()

                # Start display server if not running
                if not self._is_display_running(display):
                    start_result = self._start_display(display)
                    if start_result.get("success"):
                        actual_display = start_result.get("actual_display", display)
                        if actual_display != display:
                            self.account_displays[account_id] = actual_display
                            self._save()
                        display = actual_display

                return {
                    "success": True,
                    "display": display,
                    "status": "newly_assigned",
                    "note": f"Account {account_id} permanently assigned to {display}"
                }

        return {
            "success": False,
            "error": f"No available displays. All {self.MAX_DISPLAYS} slots assigned.",
            "account_displays": self.account_displays
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
