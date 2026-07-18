"""
Session management MCP tools.

Wave-5 consolidation: two canonical tools for multi-client session management.
- session_status  (read):  sessions, displays, per-account playtime/availability
- manage_session  (write): end sessions, cleanup, display reset/reassign
"""
from ..credentials import credential_manager
from ..registry import registry
from ..session_manager import session_manager


@registry.register({
    "name": "session_status",
    "description": """[Sessions] Canonical session/display/playtime status tool (read-only).

- session_status()                    - all running sessions + per-account availability (12hr/24hr playtime limit) + display pool summary
- session_status(account_id="main")   - one account: session state + playtime detail
- session_status(include_displays=true) - add detailed display-pool diagnostics (Xvfb responsiveness etc.)""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "account_id": {
                "type": "string",
                "description": "Optional: status for a specific account (includes playtime detail)"
            },
            "include_displays": {
                "type": "boolean",
                "description": "Include detailed display-pool status (default: false)",
                "default": False
            }
        }
    }
})
async def handle_session_status(arguments: dict) -> dict:
    """Merged read-only status: get_session_status + get_available_accounts + get_playtime + get_display_status."""
    account_id = arguments.get("account_id")
    include_displays = arguments.get("include_displays", False)

    status = session_manager.get_session_status(account_id)

    if account_id:
        # Per-account playtime detail (absorbs get_playtime)
        playtime_hours = session_manager.get_playtime_24h(account_id)
        limit = session_manager.MAX_PLAYTIME_24H_HOURS
        status["playtime"] = {
            "playtime_24h_hours": round(playtime_hours, 2),
            "limit_hours": limit,
            "remaining_hours": round(max(0, limit - playtime_hours), 2),
            "under_limit": playtime_hours < limit,
            "percentage_used": round((playtime_hours / limit) * 100, 1)
        }
    else:
        # All-accounts availability (absorbs get_available_accounts)
        accounts = credential_manager.get_accounts_info()
        account_ids = [a["alias"] for a in accounts]
        active_accounts = [s["account"] for s in session_manager.get_active_sessions()]
        inactive = [a for a in account_ids if a not in active_accounts]
        available = session_manager.get_accounts_under_limit(inactive)

        account_details = []
        for acct in account_ids:
            info = next((a for a in accounts if a["alias"] == acct), {})
            playtime = session_manager.get_playtime_24h(acct)
            account_details.append({
                "account": acct,
                "display_name": info.get("display_name", ""),
                "active": acct in active_accounts,
                "playtime_24h_hours": round(playtime, 2),
                "under_limit": session_manager.is_under_playtime_limit(acct),
                "available": acct in available
            })

        status["configured_accounts"] = account_ids
        status["accounts"] = account_details
        status["available_to_run"] = available
        status["active_count"] = len(active_accounts)
        status["available_displays"] = len(
            [d for d, s in session_manager.displays.items() if s is None])

    if include_displays:
        # Detailed display diagnostics (absorbs get_display_status)
        status["displays"] = session_manager.get_display_status()

    return status


@registry.register({
    "name": "manage_session",
    "description": """[Sessions] Canonical session/display management tool (write actions).

Actions:
- manage_session(action="end", account_id=...)              - stop tracking a session's playtime (use stop_runelite to stop the client)
- manage_session(action="cleanup")                          - clean up sessions whose RuneLite process died (+ stale Xvfb by default)
- manage_session(action="reset_display", account_id=...)    - clear an account's display assignment (next start allocates fresh)
- manage_session(action="reassign_display", account_id=..., display=":3") - pin an account to a specific display""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["end", "cleanup", "reset_display", "reassign_display"],
                "description": "What to do"
            },
            "account_id": {
                "type": "string",
                "description": "Account to act on (required except for cleanup)"
            },
            "display": {
                "type": "string",
                "description": "Display (e.g., ':2'). For end: alternative to account_id. For reassign_display: required."
            },
            "cleanup_displays": {
                "type": "boolean",
                "description": "cleanup: also clean up stale Xvfb processes and sockets (default: true)",
                "default": True
            }
        },
        "required": ["action"]
    }
})
async def handle_manage_session(arguments: dict) -> dict:
    """Merged write actions: end_session + cleanup_stale_sessions + reset/reassign display."""
    action = arguments.get("action")
    account_id = arguments.get("account_id")
    display = arguments.get("display")

    if action == "end":
        if not account_id and not display:
            return {"success": False, "error": "end requires account_id or display"}
        return session_manager.end_session(account_id=account_id, display=display)

    if action == "cleanup":
        return session_manager.cleanup_stale_sessions(
            cleanup_displays=arguments.get("cleanup_displays", True))

    if action == "reset_display":
        if not account_id:
            return {"success": False, "error": "reset_display requires account_id"}
        return session_manager.reset_account_display(account_id)

    if action == "reassign_display":
        if not account_id or not display:
            return {"success": False, "error": "reassign_display requires account_id and display"}
        return session_manager.reassign_account_display(account_id, display)

    return {"success": False, "error": f"Unknown action: {action}"}
