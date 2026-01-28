"""
Core RuneLite control tools.
Handles building, starting, stopping, and checking status.
Supports multi-client via account_id parameter.
"""
import subprocess
import time
from pathlib import Path
from ..registry import registry
from ..utils import parse_maven_errors, parse_maven_warnings, maybe_truncate_response


# Note: runelite_manager (MultiRuneLiteManager) will be injected when server starts
runelite_manager = None
config = None


def set_dependencies(manager, server_config):
    """Inject dependencies (called from server.py startup)"""
    global runelite_manager, config
    runelite_manager = manager
    config = server_config


# Common account_id schema property used across tools
ACCOUNT_ID_SCHEMA = {
    "type": "string",
    "description": "Account ID for multi-client support. Omit for default account."
}


@registry.register({
    "name": "build_plugin",
    "description": "[RuneLite] Compile the manny RuneLite plugin using Maven. Returns structured build results with any errors.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "clean": {
                "type": "boolean",
                "description": "Whether to run 'mvn clean' first (default: true)",
                "default": True
            }
        }
    }
})
async def handle_build_plugin(arguments: dict) -> dict:
    """Run Maven to compile the plugin."""
    clean = arguments.get("clean", True)
    start_time = time.time()

    cmd = ["mvn"]
    if clean:
        cmd.append("clean")
    cmd.extend(["compile", "-pl", "runelite-client", "-T", "1C", "-DskipTests"])

    result = subprocess.run(
        cmd,
        cwd=str(config.runelite_root),
        capture_output=True,
        text=True,
        timeout=300  # 5 minute timeout
    )

    build_time = time.time() - start_time
    output = result.stdout + result.stderr

    errors = parse_maven_errors(output)
    warnings = parse_maven_warnings(output)

    response = {
        "success": result.returncode == 0,
        "build_time_seconds": round(build_time, 2),
        "errors": errors,
        "warnings": warnings[:10],  # Truncate warnings
        "return_code": result.returncode
    }

    # Write large responses to file to avoid filling context
    return maybe_truncate_response(response, prefix="build_output")


@registry.register({
    "name": "start_runelite",
    "description": "[RuneLite] Start the RuneLite client with manny plugin. Auto-allocates display from pool (:2-:5). Checks 12hr/24hr playtime limit before starting.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "developer_mode": {
                "type": "boolean",
                "description": "Enable RuneLite developer mode (default: true)",
                "default": True
            },
            "account_id": {
                "type": "string",
                "description": "Account alias from credentials (e.g., 'main', 'aux'). Uses default if omitted."
            },
            "display": {
                "type": "string",
                "description": "Optional: Specific display to use (e.g., ':2'). If omitted, auto-allocates from pool."
            },
            "proxy": {
                "type": "string",
                "description": "Optional: SOCKS5 proxy URL (e.g., 'socks5://user:pass@host:port'). Supports socks5:// and http:// schemes."
            }
        }
    }
})
async def handle_start_runelite(arguments: dict) -> dict:
    """
    Start RuneLite process for specified account.

    This will:
    1. Check playtime limit (12hr/24hr)
    2. Allocate display from pool (or use specified)
    3. Kill ALL running RuneLite instances (TODO: support concurrent)
    4. Write credentials.properties for the selected account
    5. Start a fresh RuneLite instance
    6. Record session for playtime tracking
    """
    developer_mode = arguments.get("developer_mode", True)
    account_id = arguments.get("account_id")
    display = arguments.get("display")
    proxy = arguments.get("proxy")
    return runelite_manager.start_instance(account_id=account_id, developer_mode=developer_mode, display=display, proxy=proxy)


@registry.register({
    "name": "stop_runelite",
    "description": "[RuneLite] Stop the managed RuneLite process.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "account_id": ACCOUNT_ID_SCHEMA
        }
    }
})
async def handle_stop_runelite(arguments: dict) -> dict:
    """Stop RuneLite process for specified account."""
    account_id = arguments.get("account_id")
    return runelite_manager.stop_instance(account_id)


@registry.register({
    "name": "runelite_status",
    "description": "[RuneLite] Check if RuneLite is currently running.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "account_id": ACCOUNT_ID_SCHEMA,
            "list_all": {
                "type": "boolean",
                "description": "If true, list all running instances instead of checking specific account",
                "default": False
            }
        }
    }
})
async def handle_runelite_status(arguments: dict) -> dict:
    """Check RuneLite status for specified account or list all instances."""
    list_all = arguments.get("list_all", False)
    account_id = arguments.get("account_id")

    if list_all:
        instances = runelite_manager.list_instances()
        return {
            "instances": instances,
            "count": len(instances)
        }

    # Check specific account
    instance = runelite_manager.get_instance(account_id)
    if instance:
        return {
            "account_id": instance.account_id,
            "running": instance.is_running(),
            "pid": instance.process.pid if instance.process else None
        }
    else:
        return {
            "account_id": account_id or config.default_account,
            "running": False,
            "pid": None
        }


# ============================================================================
# CREDENTIAL MANAGEMENT TOOLS
# ============================================================================

from ..credentials import credential_manager


@registry.register({
    "name": "list_accounts",
    "description": "[Credentials] List all configured account aliases. Does not expose token secrets.",
    "inputSchema": {
        "type": "object",
        "properties": {}
    }
})
async def handle_list_accounts(arguments: dict) -> dict:
    """List all accounts in the credential store."""
    accounts = credential_manager.get_accounts_info()

    return {
        "accounts": accounts,
        "count": len(accounts),
        "default": credential_manager.default,
        "credentials_file": str(credential_manager.CREDENTIALS_FILE)
    }


@registry.register({
    "name": "add_account",
    "description": "[Credentials] Add or update an account's credentials. Get tokens by running RuneLite with --insecure-write-credentials flag after logging in via Jagex Launcher.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "alias": {
                "type": "string",
                "description": "Account alias (e.g., 'main', 'alt1', 'fishing_bot')"
            },
            "display_name": {
                "type": "string",
                "description": "In-game display name for this account"
            },
            "jx_character_id": {
                "type": "string",
                "description": "JX_CHARACTER_ID from Bolt credentials (~/.local/share/bolt-launcher/creds)",
                "default": ""
            },
            "jx_session_id": {
                "type": "string",
                "description": "JX_SESSION_ID from Bolt credentials (~/.local/share/bolt-launcher/creds)",
                "default": ""
            },
            "proxy": {
                "type": "string",
                "description": "Optional: Proxy URL (e.g., 'socks5://user:pass@host:port'). Used automatically when starting this account.",
                "default": ""
            },
            "set_default": {
                "type": "boolean",
                "description": "Make this the default account",
                "default": False
            }
        },
        "required": ["alias", "display_name"]
    }
})
async def handle_add_account(arguments: dict) -> dict:
    """Add or update account credentials."""
    result = credential_manager.add_account(
        alias=arguments["alias"],
        display_name=arguments["display_name"],
        character_id=arguments.get("jx_character_id", ""),
        session_id=arguments.get("jx_session_id", ""),
        proxy=arguments.get("proxy", "")
    )

    if arguments.get("set_default") and result.get("success"):
        credential_manager.set_default(arguments["alias"])
        result["is_default"] = True

    return result


@registry.register({
    "name": "remove_account",
    "description": "[Credentials] Remove an account from the credential store.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "alias": {
                "type": "string",
                "description": "Account alias to remove"
            }
        },
        "required": ["alias"]
    }
})
async def handle_remove_account(arguments: dict) -> dict:
    """Remove an account from the credential store."""
    return credential_manager.remove_account(arguments["alias"])


@registry.register({
    "name": "set_account_proxy",
    "description": "[Credentials] Set or remove proxy for an existing account. The proxy will be used automatically when starting this account.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "alias": {
                "type": "string",
                "description": "Account alias to update"
            },
            "proxy": {
                "type": "string",
                "description": "Proxy URL (e.g., 'socks5://user:pass@host:port'). Leave empty to remove proxy."
            }
        },
        "required": ["alias", "proxy"]
    }
})
async def handle_set_account_proxy(arguments: dict) -> dict:
    """Set or remove proxy for an existing account."""
    return credential_manager.set_proxy(arguments["alias"], arguments["proxy"])


@registry.register({
    "name": "import_credentials",
    "description": "[Credentials] Import credentials from ~/.runelite/credentials.properties. Use after logging in via Bolt launcher.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "alias": {
                "type": "string",
                "description": "Account alias to save as (e.g., 'main', 'alt1')"
            },
            "display_name": {
                "type": "string",
                "description": "In-game display name for this account"
            },
            "set_default": {
                "type": "boolean",
                "description": "Make this the default account",
                "default": False
            }
        },
        "required": ["alias", "display_name"]
    }
})
async def handle_import_credentials(arguments: dict) -> dict:
    """
    Import credentials from the current credentials.properties file.

    Workflow:
    1. Log into account via Bolt launcher
    2. Call this tool to import and save the credentials
    """
    result = credential_manager.import_from_properties(
        alias=arguments["alias"],
        display_name=arguments["display_name"]
    )

    if arguments.get("set_default") and result.get("success"):
        credential_manager.set_default(arguments["alias"])
        result["is_default"] = True

    return result


@registry.register({
    "name": "set_default_account",
    "description": "[Credentials] Set the default account used when no account_id is specified.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "alias": {
                "type": "string",
                "description": "Account alias to make default"
            }
        },
        "required": ["alias"]
    }
})
async def handle_set_default_account(arguments: dict) -> dict:
    """Set the default account."""
    return credential_manager.set_default(arguments["alias"])
