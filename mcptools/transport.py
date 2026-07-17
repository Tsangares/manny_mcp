"""
Canonical command transport for the manny MCP server.

This is the ONE place that knows how to "write a command to the plugin's IPC
file and get the response back". Every caller (the MCP server, the routine
runner CLI, the Discord bot, and the routine tools) delegates here so behavior
is identical everywhere:

  - request-id (`--rid=`) correlated request/response matching,
  - ATOMIC command writes (temp file + os.rename) so the plugin's poller never
    reads a torn command,
  - a delivery check (the plugin DELETES the command file on receipt) so we
    fail fast instead of silently reporting success when the client is down or
    the account_id is wrong,
  - event-driven (watchdog) response waiting when a monitor is running, with a
    clean async poll fallback otherwise,
  - always-on command logging to /tmp/manny_sessions/commands_YYYY-MM-DD.yaml.

Historically there were FOUR divergent copies of this logic (server.py,
mcptools/tools/routine.py, run_routine.py, discord_bot/bot.py). Two of them
polled without a request id and one slept 0.1s before reading the response file
(returning STALE responses, because the plugin only polls the command file
every ~500ms). Consolidating removes lost commands, stale responses, and
inconsistent return shapes.
"""

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger("manny.transport")

# The plugin polls the command file every ~500ms and DELETES it on receipt.
# Give the deletion a short window before declaring the command undelivered.
DELIVERY_TIMEOUT_SEC = 1.5
DELIVERY_POLL_INTERVAL_SEC = 0.5

# Poll cadence used when no watchdog monitor is available.
_POLL_INTERVAL_SEC = 0.05

_NOT_CONSUMED_MSG = (
    "command not consumed within 1.5s — client may be down, "
    "logged-out-processor-idle, or wrong account_id"
)


# ============================================================================
# CONFIG (lazy-loaded, injectable so we reuse server.py's already-loaded copy)
# ============================================================================

_config = None


def set_config(cfg) -> None:
    """Inject an already-loaded ServerConfig (called from server.py startup)."""
    global _config
    _config = cfg


def _get_config():
    """Return the ServerConfig, loading it lazily for non-server callers."""
    global _config
    if _config is None:
        from .config import ServerConfig
        _config = ServerConfig.load()
    return _config


# ============================================================================
# EVENT-DRIVEN RESPONSE-FILE MONITOR (watchdog)
# ============================================================================

class ResponseFileMonitor:
    """
    Event-driven file monitor using watchdog instead of polling.

    Replaces 50ms polling loops with instant event notification, reducing CPU
    usage and latency. One monitor watches the whole directory and matches any
    ``manny*_response.json`` file, so it can wake waiters for every account;
    each waiter still re-validates the response is its own (request_id + mtime)
    before returning, so a spurious wakeup from another account is harmless.
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
        """Start watching the directory for response-file changes."""
        self._loop = loop

        class ResponseFileHandler(FileSystemEventHandler):
            def __init__(self, monitor):
                self.monitor = monitor

            @staticmethod
            def _matches(path: Optional[str]) -> bool:
                """Match any manny response file (default or account-suffixed).

                e.g. "manny_response.json" or "manny_<account>_response.json".
                """
                if not path:
                    return False
                name = os.path.basename(path)
                return name.startswith("manny") and name.endswith("_response.json")

            def _notify(self):
                # Signal waiting coroutines on their event loop thread.
                if self.monitor._loop:
                    self.monitor._loop.call_soon_threadsafe(self.monitor.event.set)

            def on_modified(self, event):
                if self._matches(event.src_path):
                    self._notify()

            def on_created(self, event):
                # Some filesystems/edit patterns emit create instead of modify.
                if self._matches(event.src_path):
                    self._notify()

            def on_moved(self, event):
                # The plugin publishes responses via an atomic rename
                # (response.json.tmp -> response.json), which watchdog delivers
                # as a FileMovedEvent (dest_path = final response file), NOT a
                # FileModifiedEvent. Without this handler the rename is invisible
                # to the monitor and every awaited command silently waits out the
                # full timeout. (Wave 1 fix — preserved here.)
                dest_path = getattr(event, "dest_path", None)
                if self._matches(dest_path) or self._matches(event.src_path):
                    self._notify()

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
        """Wait for a response-file event, with timeout."""
        self.event.clear()
        try:
            await asyncio.wait_for(self.event.wait(), timeout=timeout_sec)
            return True
        except asyncio.TimeoutError:
            return False


# Global monitor (started by the MCP server; None for sync/one-shot callers,
# which fall back to polling).
_response_monitor: Optional[ResponseFileMonitor] = None


def start_response_monitor(loop: asyncio.AbstractEventLoop, file_path: str) -> ResponseFileMonitor:
    """Create and start the shared response-file monitor. Returns it."""
    global _response_monitor
    _response_monitor = ResponseFileMonitor(file_path)
    _response_monitor.start(loop)
    return _response_monitor


def stop_response_monitor() -> None:
    """Stop the shared response-file monitor if running."""
    global _response_monitor
    if _response_monitor:
        _response_monitor.stop()
        _response_monitor = None


def get_response_monitor() -> Optional[ResponseFileMonitor]:
    """Return the shared response-file monitor (or None)."""
    return _response_monitor


# ============================================================================
# INTERNALS
# ============================================================================

def _atomic_write(command_file: str, content: str, request_id: str) -> None:
    """Write ``content`` to ``command_file`` atomically via temp + os.rename.

    The plugin polls the command file on a timer; a plain ``open(w)`` can be
    read mid-write (torn read). Writing to a unique temp file on the same
    filesystem and renaming onto the target is atomic on POSIX, so the poller
    always sees either the old file or the fully-written new one.
    """
    tmp = f"{command_file}.{request_id}.tmp"
    with open(tmp, "w") as f:
        f.write(content)
    os.rename(tmp, command_file)


def _log_command(command: str) -> None:
    """Append to the always-on daily command log (best-effort)."""
    try:
        from .tools.session import command_log
        command_log.log_command(command)
    except Exception:
        # Never let logging failures break command delivery.
        pass


def _make_response_checker(response_file: str, request_id: str, command: str,
                           command_write_time: float):
    """Build a closure that returns the matching plugin response, or None."""

    def _check():
        if not os.path.exists(response_file):
            return None
        try:
            current_mtime = os.path.getmtime(response_file)
        except OSError:
            return None
        # Response must be at least as new as when we wrote the command.
        if current_mtime < command_write_time:
            return None
        try:
            with open(response_file) as f:
                response = json.load(f)
        except (json.JSONDecodeError, IOError):
            return None
        # PRIMARY: match by request_id (bulletproof correlation).
        if response.get("request_id") == request_id:
            return response
        # FALLBACK: old Java plugins have no request_id — match by command name.
        if response.get("request_id") is None:
            if response.get("command", "").upper() == command.split()[0].upper():
                return response
        return None

    return _check


async def _await_delivery(command_file: str, window_sec: float) -> bool:
    """Poll for the plugin to consume (delete) the command file."""
    waited = 0.0
    while waited < window_sec:
        await asyncio.sleep(DELIVERY_POLL_INTERVAL_SEC)
        waited += DELIVERY_POLL_INTERVAL_SEC
        if not os.path.exists(command_file):
            return True
    return not os.path.exists(command_file)


async def _await_response(command: str, command_file: str, response_file: str,
                          request_id: str, command_write_time: float,
                          timeout: float, account_id: str = None) -> dict:
    """Wait for a request-id-correlated response, with fast-fail on non-delivery."""
    check = _make_response_checker(response_file, request_id, command, command_write_time)
    monitor = _response_monitor
    start = command_write_time
    delivered = False

    while (time.time() - start) < timeout:
        # 1. Is our response already available?
        response = check()
        if response is not None:
            return response

        # 2. Track delivery (command file deleted == plugin consumed it).
        if not delivered and not os.path.exists(command_file):
            delivered = True

        # 3. Fast-fail: past the delivery window and STILL not consumed means
        #    the client is down / idle / wrong account — don't wait the full
        #    timeout for a response that will never come.
        if not delivered and (time.time() - start) >= DELIVERY_TIMEOUT_SEC:
            if not os.path.exists(command_file):
                delivered = True
            else:
                result = {
                    "delivered": False,
                    "status": "error",
                    "command": command,
                    "error": _NOT_CONSUMED_MSG,
                    "command_file": command_file,
                }
                if account_id:
                    result["account_id"] = account_id
                return result

        remaining = timeout - (time.time() - start)
        if remaining <= 0:
            break

        if monitor:
            # Cap the wait so the delivery fast-fail above can still fire even
            # if the plugin never emits a response event.
            await monitor.wait_for_change(min(remaining, 0.5))
        else:
            await asyncio.sleep(min(remaining, _POLL_INTERVAL_SEC))

    # Final check in case the response landed on the last iteration.
    response = check()
    if response is not None:
        return response

    result = {
        "timeout": True,
        "status": "timeout",
        "command": command,
        "error": f"No response received within {int(timeout * 1000)}ms",
    }
    if account_id:
        result["account_id"] = account_id
    return result


# ============================================================================
# PUBLIC API
# ============================================================================

async def send_command(command: str, account_id: str = None,
                       await_response: bool = True, timeout: float = 3.0) -> dict:
    """
    Send a command to the manny plugin and (optionally) await its response.

    Args:
        command: The command to send (e.g. "GOTO 3200 3200 0").
        account_id: Account alias for multi-client. None resolves via
            ``config.resolve_account_id`` (the ONE shared resolver).
        await_response: If True (default), wait for the plugin's response and
            return the parsed response dict. If False, only confirm delivery.
        timeout: Seconds to wait for a response (when ``await_response``).

    Returns:
        - await_response=True, success: the parsed plugin response dict.
        - await_response=True, undelivered:
              {"delivered": False, "status": "error", "error": ..., ...}
        - await_response=True, timeout:
              {"timeout": True, "status": "timeout", "error": ..., ...}
        - await_response=False, success:
              {"dispatched": True, "delivered": True, "command": ..., ...}
        - await_response=False, undelivered:
              {"dispatched": False, "delivered": False, "error": ..., ...}
    """
    cfg = _get_config()
    command_file = cfg.get_command_file(account_id)
    response_file = cfg.get_response_file(account_id)

    request_id = uuid.uuid4().hex[:8]
    command_with_rid = f"{command} --rid={request_id}"
    command_write_time = time.time()

    # Atomic write (temp + rename) so the plugin's poller never sees a torn command.
    try:
        _atomic_write(command_file, command_with_rid + "\n", request_id)
    except Exception as e:
        result = {
            "dispatched": False,
            "delivered": False,
            "status": "error",
            "command": command,
            "error": f"Failed to write command: {e}",
            "command_file": command_file,
        }
        if account_id:
            result["account_id"] = account_id
        return result

    # Always-on command logging.
    _log_command(command)

    if not await_response:
        delivered = await _await_delivery(command_file, DELIVERY_TIMEOUT_SEC)
        if not delivered:
            result = {
                "dispatched": False,
                "delivered": False,
                "command": command,
                "error": _NOT_CONSUMED_MSG,
                "command_file": command_file,
            }
            if account_id:
                result["account_id"] = account_id
            return result
        result = {
            "dispatched": True,
            "delivered": True,
            "command": command,
            "note": "Command queued. Use get_logs() or get_command_response() to verify execution.",
            "command_file": command_file,
        }
        if account_id:
            result["account_id"] = account_id
        return result

    return await _await_response(command, command_file, response_file,
                                 request_id, command_write_time, timeout, account_id)


def send_command_sync(command: str, account_id: str = None,
                      await_response: bool = True, timeout: float = 3.0) -> dict:
    """
    Synchronous wrapper around :func:`send_command` for non-async callers.

    Runs the async transport on a fresh event loop via ``asyncio.run``. Intended
    for CLI / synchronous contexts (there is no watchdog monitor there, so the
    async poll fallback is used). Must NOT be called from within a running event
    loop — use ``await send_command(...)`` there instead.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError(
            "send_command_sync() called from a running event loop; "
            "use `await send_command(...)` instead."
        )
    return asyncio.run(send_command(command, account_id=account_id,
                                    await_response=await_response, timeout=timeout))
