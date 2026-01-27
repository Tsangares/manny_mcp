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
        """Check if a display server is running and responsive."""
        display_num = display.lstrip(":")
        socket_path = f"/tmp/.X11-unix/X{display_num}"

        # Check for X11 socket
        if not os.path.exists(socket_path):
            return False

        # Verify socket is a valid socket file (not stale)
        import stat
        try:
            mode = os.stat(socket_path).st_mode
            if not stat.S_ISSOCK(mode):
                return False
        except Exception:
            return False

        # Verify the display is actually responsive using xdpyinfo
        try:
            result = subprocess.run(
                ["xdpyinfo", "-display", display],
                capture_output=True,
                timeout=5,
                env={**os.environ, "DISPLAY": display}
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # xdpyinfo not installed or timed out - fall back to socket check
            return True
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

    def _cleanup_stale_display(self, display: str) -> bool:
        """
        Clean up stale socket and processes for a display.
        Returns True if cleanup was performed.
        """
        display_num = display.lstrip(":")
        socket_path = f"/tmp/.X11-unix/X{display_num}"
        cleaned = False

        # Kill any Xvfb processes for this specific display
        try:
            result = subprocess.run(
                ["pkill", "-f", f"Xvfb :{display_num}\\b"],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                cleaned = True
                time.sleep(0.5)  # Give process time to die
        except Exception:
            pass

        # Remove stale socket if it exists but no server is running
        if os.path.exists(socket_path):
            try:
                os.unlink(socket_path)
                cleaned = True
            except PermissionError:
                pass  # Socket is in use by running server
            except Exception:
                pass

        return cleaned

    def _start_display(self, display: str, max_retries: int = 3) -> Dict[str, Any]:
        """
        Start a new display server with retry logic.

        For headless instances, uses Xvfb directly for reliability.
        Falls back to start_screen.sh for primary display (:2).

        Args:
            display: Display to start (e.g., ":3")
            max_retries: Number of retry attempts

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

        last_error = None

        for attempt in range(max_retries):
            # Clean up any stale state before attempting
            self._cleanup_stale_display(display)

            # Record displays before starting
            displays_before = set(self._get_running_displays())

            try:
                if display_num == "2":
                    # Primary display - use start_screen.sh for gamescope support
                    script_path = Path(__file__).parent.parent / "start_screen.sh"
                    cmd = [str(script_path)]
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    stdout = result.stdout.strip()
                    stderr = result.stderr.strip()
                else:
                    # Additional displays - start Xvfb directly for reliability
                    # This avoids issues with start_screen.sh interaction
                    xvfb_proc = subprocess.Popen(
                        ["Xvfb", f":{display_num}", "-screen", "0", "1920x1080x24"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        start_new_session=True  # Detach from parent
                    )

                    # Wait for Xvfb to initialize
                    socket_path = f"/tmp/.X11-unix/X{display_num}"
                    for _ in range(20):  # Wait up to 10 seconds
                        time.sleep(0.5)
                        if os.path.exists(socket_path):
                            # Verify process is still running
                            if xvfb_proc.poll() is None:
                                return {
                                    "success": True,
                                    "display": display,
                                    "actual_display": display,
                                    "status": "started",
                                    "pid": xvfb_proc.pid,
                                    "output": f"Xvfb started on :{display_num} (PID: {xvfb_proc.pid})"
                                }
                            break

                    # Xvfb failed - capture error
                    try:
                        stdout_bytes, stderr_bytes = xvfb_proc.communicate(timeout=2)
                        stdout = stdout_bytes.decode() if stdout_bytes else ""
                        stderr = stderr_bytes.decode() if stderr_bytes else ""
                    except subprocess.TimeoutExpired:
                        xvfb_proc.kill()
                        stdout, stderr = "", "Xvfb startup timed out"

                    last_error = stderr or "Xvfb did not create socket"
                    if attempt < max_retries - 1:
                        time.sleep(1)  # Wait before retry
                        continue
                    else:
                        return {
                            "success": False,
                            "display": display,
                            "error": last_error,
                            "attempts": attempt + 1
                        }

                # For primary display (start_screen.sh path)
                displays_after = set(self._get_running_displays())
                new_displays = displays_after - displays_before

                if new_displays:
                    actual_display = sorted(new_displays)[0]
                    return {
                        "success": True,
                        "display": display,
                        "actual_display": actual_display,
                        "status": "started",
                        "output": stdout
                    }

                if self._is_display_running(display):
                    return {
                        "success": True,
                        "display": display,
                        "actual_display": display,
                        "status": "started",
                        "output": stdout
                    }

                last_error = stderr or "Display did not start"
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue

                return {
                    "success": False,
                    "display": display,
                    "error": last_error,
                    "output": stdout,
                    "attempts": attempt + 1
                }

            except subprocess.TimeoutExpired:
                last_error = "start_screen.sh timed out after 30s"
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
            except FileNotFoundError as e:
                return {
                    "success": False,
                    "display": display,
                    "error": f"Required command not found: {e.filename}",
                    "attempts": attempt + 1
                }
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue

        return {
            "success": False,
            "display": display,
            "error": last_error or "Unknown error after retries",
            "attempts": max_retries
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

    def allocate_display(self, account_id: str, allow_reassign: bool = True) -> Dict[str, Any]:
        """
        Allocate a display for an account.

        Robust approach:
        1. Check if account has a persistent display assignment
        2. If yes, try to start that display (with retries)
        3. If display fails and allow_reassign=True, try an alternate display
        4. If no assignment, assign the next available display number

        Args:
            account_id: Account to allocate display for
            allow_reassign: If True, reassign to different display on failure
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
                    # Display failed to start - try fallback if allowed
                    if allow_reassign:
                        fallback_result = self._try_fallback_display(account_id, exclude=[display])
                        if fallback_result.get("success"):
                            fallback_result["original_display"] = display
                            fallback_result["fallback_reason"] = start_result.get("error", "Display failed to start")
                            return fallback_result

                    return {
                        "success": False,
                        "display": display,
                        "error": f"Failed to start assigned display {display}",
                        "start_result": start_result,
                        "hint": "Try running cleanup_stale_sessions() or manually check Xvfb processes"
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
        return self._assign_new_display(account_id)

    def _try_fallback_display(self, account_id: str, exclude: List[str]) -> Dict[str, Any]:
        """
        Try to start a fallback display when the primary fails.

        Args:
            account_id: Account to allocate for
            exclude: List of displays to skip (already failed)
        """
        assigned_displays = set(self.account_displays.values())

        for i in range(self.MIN_DISPLAY, self.MIN_DISPLAY + self.MAX_DISPLAYS):
            display = f":{i}"
            if display in exclude:
                continue

            # Try this display
            if self._is_display_running(display):
                # Display is running - check if it's assigned to someone else
                if display in assigned_displays:
                    continue  # Skip, already assigned

                # Unassigned running display - use it
                self.account_displays[account_id] = display
                self._save()
                return {
                    "success": True,
                    "display": display,
                    "status": "fallback_assigned",
                    "note": f"Account {account_id} reassigned to available display {display}"
                }
            else:
                # Try to start this display
                start_result = self._start_display(display)
                if start_result.get("success"):
                    actual_display = start_result.get("actual_display", display)
                    self.account_displays[account_id] = actual_display
                    self._save()
                    return {
                        "success": True,
                        "display": actual_display,
                        "status": "fallback_started",
                        "note": f"Account {account_id} reassigned to new display {actual_display}"
                    }

        return {
            "success": False,
            "error": "No fallback displays available"
        }

    def _assign_new_display(self, account_id: str) -> Dict[str, Any]:
        """Assign a new display to an account that doesn't have one."""
        assigned_displays = set(self.account_displays.values())

        for i in range(self.MIN_DISPLAY, self.MIN_DISPLAY + self.MAX_DISPLAYS):
            display = f":{i}"
            if display in assigned_displays:
                continue

            # Try to start this display
            if not self._is_display_running(display):
                start_result = self._start_display(display)
                if not start_result.get("success"):
                    # This display failed, try next one
                    continue
                display = start_result.get("actual_display", display)

            # Assign this display to the account
            self.account_displays[account_id] = display
            self._save()

            return {
                "success": True,
                "display": display,
                "status": "newly_assigned",
                "note": f"Account {account_id} permanently assigned to {display}"
            }

        return {
            "success": False,
            "error": f"No available displays. All {self.MAX_DISPLAYS} slots assigned or failed to start.",
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

    def cleanup_stale_sessions(self, cleanup_displays: bool = True) -> Dict[str, Any]:
        """
        Clean up sessions where the process is no longer running.
        Call this periodically to free up displays from crashed clients.

        Args:
            cleanup_displays: Also clean up stale Xvfb processes and sockets
        """
        cleaned_sessions = []
        cleaned_displays = []

        # Clean up stale sessions (processes that died)
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
                    cleaned_sessions.append({
                        "display": display,
                        "account": session.get("account"),
                        "pid": pid
                    })
                except PermissionError:
                    # Process exists but we can't signal it (still running)
                    pass

        # Optionally clean up stale display servers
        if cleanup_displays:
            for i in range(self.MIN_DISPLAY, self.MIN_DISPLAY + self.MAX_DISPLAYS):
                display = f":{i}"
                display_num = str(i)

                # Check if socket exists but display is not responsive
                socket_path = f"/tmp/.X11-unix/X{display_num}"
                if os.path.exists(socket_path) and not self._is_display_running(display):
                    # Stale socket - clean it up
                    if self._cleanup_stale_display(display):
                        cleaned_displays.append(display)

        return {
            "cleaned_sessions": cleaned_sessions,
            "cleaned_displays": cleaned_displays,
            "session_count": len(cleaned_sessions),
            "display_count": len(cleaned_displays)
        }

    def get_display_status(self) -> Dict[str, Any]:
        """
        Get detailed status of all displays in the pool.
        Useful for debugging display allocation issues.
        """
        displays_status = {}

        for i in range(self.MIN_DISPLAY, self.MIN_DISPLAY + self.MAX_DISPLAYS):
            display = f":{i}"
            display_num = str(i)
            socket_path = f"/tmp/.X11-unix/X{display_num}"

            status = {
                "socket_exists": os.path.exists(socket_path),
                "responsive": self._is_display_running(display),
                "assigned_to": None,
                "active_session": None
            }

            # Check if assigned to an account
            for account, assigned_display in self.account_displays.items():
                if assigned_display == display:
                    status["assigned_to"] = account
                    break

            # Check if has active session
            session = self.displays.get(display)
            if session:
                status["active_session"] = session

            displays_status[display] = status

        # Count summary
        running = sum(1 for d in displays_status.values() if d["responsive"])
        assigned = sum(1 for d in displays_status.values() if d["assigned_to"])
        active = sum(1 for d in displays_status.values() if d["active_session"])

        return {
            "displays": displays_status,
            "summary": {
                "total": len(displays_status),
                "running": running,
                "assigned": assigned,
                "active_sessions": active,
                "available": len(displays_status) - assigned
            },
            "account_assignments": self.account_displays
        }

    def reload(self) -> None:
        """Reload sessions from disk."""
        self._load()

    def reset_account_display(self, account_id: str) -> Dict[str, Any]:
        """
        Reset an account's display assignment, allowing it to be reassigned.
        Use when an account's assigned display is persistently problematic.

        Args:
            account_id: Account to reset
        """
        self._load()

        old_display = self.account_displays.get(account_id)
        if old_display is None:
            return {
                "success": False,
                "error": f"Account '{account_id}' has no display assignment"
            }

        # End any active session first
        if self.displays.get(old_display):
            self.end_session(display=old_display)

        # Remove the assignment
        del self.account_displays[account_id]
        self._save()

        return {
            "success": True,
            "account": account_id,
            "previous_display": old_display,
            "note": f"Display assignment cleared. Next start_runelite will assign a new display."
        }

    def reassign_account_display(self, account_id: str, new_display: str) -> Dict[str, Any]:
        """
        Manually reassign an account to a specific display.

        Args:
            account_id: Account to reassign
            new_display: Display to assign (e.g., ":2")
        """
        self._load()

        # Validate display is in pool
        display_num = new_display.lstrip(":")
        if not display_num.isdigit():
            return {
                "success": False,
                "error": f"Invalid display format: {new_display}"
            }

        num = int(display_num)
        if not (self.MIN_DISPLAY <= num < self.MIN_DISPLAY + self.MAX_DISPLAYS):
            return {
                "success": False,
                "error": f"Display {new_display} not in pool (:{self.MIN_DISPLAY} to :{self.MIN_DISPLAY + self.MAX_DISPLAYS - 1})"
            }

        # Check if display is already assigned to another account
        for other_account, assigned_display in self.account_displays.items():
            if assigned_display == new_display and other_account != account_id:
                return {
                    "success": False,
                    "error": f"Display {new_display} is already assigned to {other_account}"
                }

        old_display = self.account_displays.get(account_id)

        # End any active session on old display
        if old_display and self.displays.get(old_display):
            self.end_session(display=old_display)

        # Assign new display
        self.account_displays[account_id] = new_display
        self._save()

        return {
            "success": True,
            "account": account_id,
            "previous_display": old_display,
            "new_display": new_display
        }


# Global singleton instance
session_manager = SessionManager()
