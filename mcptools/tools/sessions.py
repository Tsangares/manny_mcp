"""
Session management MCP tools.

Provides tools for managing multi-client sessions, display allocation,
and playtime tracking.
"""
from ..registry import registry
from ..session_manager import session_manager
from ..credentials import credential_manager


@registry.register({
    "name": "get_session_status",
    "description": "[Sessions] Get status of all running sessions or a specific account. Shows active displays, playtime, and availability.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "account_id": {
                "type": "string",
                "description": "Optional: Get status for a specific account"
            }
        }
    }
})
async def handle_get_session_status(arguments: dict) -> dict:
    """Get session status."""
    account_id = arguments.get("account_id")
    status = session_manager.get_session_status(account_id)

    # Add account list if getting all sessions
    if not account_id:
        accounts = credential_manager.get_accounts_info()
        status["configured_accounts"] = [a["alias"] for a in accounts]

    return status


@registry.register({
    "name": "get_available_accounts",
    "description": "[Sessions] Get accounts that are available to run (not currently active AND under 12hr/24hr playtime limit).",
    "inputSchema": {
        "type": "object",
        "properties": {}
    }
})
async def handle_get_available_accounts(arguments: dict) -> dict:
    """Get accounts available to run."""
    accounts = credential_manager.get_accounts_info()
    account_ids = [a["alias"] for a in accounts]

    # Filter to those not currently running
    active_accounts = [s["account"] for s in session_manager.get_active_sessions()]
    inactive = [a for a in account_ids if a not in active_accounts]

    # Filter to those under playtime limit
    available = session_manager.get_accounts_under_limit(inactive)

    # Build response with details
    result = []
    for account_id in account_ids:
        info = next((a for a in accounts if a["alias"] == account_id), {})
        playtime = session_manager.get_playtime_24h(account_id)
        is_active = account_id in active_accounts
        under_limit = session_manager.is_under_playtime_limit(account_id)

        result.append({
            "account": account_id,
            "display_name": info.get("display_name", ""),
            "active": is_active,
            "playtime_24h_hours": round(playtime, 2),
            "under_limit": under_limit,
            "available": account_id in available
        })

    return {
        "accounts": result,
        "available_to_run": available,
        "active_count": len(active_accounts),
        "available_displays": len([d for d, s in session_manager.displays.items() if s is None])
    }


@registry.register({
    "name": "cleanup_stale_sessions",
    "description": "[Sessions] Clean up sessions where the RuneLite process has crashed or been killed. Also cleans up stale Xvfb processes and sockets.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "cleanup_displays": {
                "type": "boolean",
                "description": "Also clean up stale Xvfb processes and sockets (default: true)",
                "default": True
            }
        }
    }
})
async def handle_cleanup_stale_sessions(arguments: dict) -> dict:
    """Clean up stale sessions."""
    cleanup_displays = arguments.get("cleanup_displays", True)
    return session_manager.cleanup_stale_sessions(cleanup_displays=cleanup_displays)


@registry.register({
    "name": "get_display_status",
    "description": "[Sessions] Get detailed status of all displays in the pool. Shows which displays are running, assigned, and responsive. Useful for debugging display allocation issues.",
    "inputSchema": {
        "type": "object",
        "properties": {}
    }
})
async def handle_get_display_status(arguments: dict) -> dict:
    """Get detailed display status."""
    return session_manager.get_display_status()


@registry.register({
    "name": "get_playtime",
    "description": "[Sessions] Get playtime statistics for an account (last 24 hours).",
    "inputSchema": {
        "type": "object",
        "properties": {
            "account_id": {
                "type": "string",
                "description": "Account to check playtime for"
            }
        },
        "required": ["account_id"]
    }
})
async def handle_get_playtime(arguments: dict) -> dict:
    """Get playtime for an account."""
    account_id = arguments["account_id"]
    playtime_hours = session_manager.get_playtime_24h(account_id)
    limit = session_manager.MAX_PLAYTIME_24H_HOURS

    return {
        "account": account_id,
        "playtime_24h_hours": round(playtime_hours, 2),
        "limit_hours": limit,
        "remaining_hours": round(max(0, limit - playtime_hours), 2),
        "under_limit": playtime_hours < limit,
        "percentage_used": round((playtime_hours / limit) * 100, 1)
    }


@registry.register({
    "name": "end_session",
    "description": "[Sessions] Manually end a session (stop tracking playtime). Use stop_runelite to actually stop the client.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "account_id": {
                "type": "string",
                "description": "Account to end session for"
            },
            "display": {
                "type": "string",
                "description": "Or specify display directly (e.g., ':2')"
            }
        }
    }
})
async def handle_end_session(arguments: dict) -> dict:
    """End a session."""
    return session_manager.end_session(
        account_id=arguments.get("account_id"),
        display=arguments.get("display")
    )


@registry.register({
    "name": "reset_account_display",
    "description": "[Sessions] Reset an account's display assignment. Use when an account's assigned display is persistently failing. The next start_runelite will assign a new display.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "account_id": {
                "type": "string",
                "description": "Account to reset display assignment for"
            }
        },
        "required": ["account_id"]
    }
})
async def handle_reset_account_display(arguments: dict) -> dict:
    """Reset an account's display assignment."""
    return session_manager.reset_account_display(arguments["account_id"])


@registry.register({
    "name": "reassign_account_display",
    "description": "[Sessions] Manually reassign an account to a specific display. Use for troubleshooting display allocation issues.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "account_id": {
                "type": "string",
                "description": "Account to reassign"
            },
            "display": {
                "type": "string",
                "description": "Display to assign (e.g., ':2')"
            }
        },
        "required": ["account_id", "display"]
    }
})
async def handle_reassign_account_display(arguments: dict) -> dict:
    """Reassign an account to a specific display."""
    return session_manager.reassign_account_display(
        arguments["account_id"],
        arguments["display"]
    )
