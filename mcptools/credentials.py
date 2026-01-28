"""
Secure credential storage for multi-account RuneLite management.

Stores Jagex account identity (JX_CHARACTER_ID, JX_SESSION_ID) with account aliases
in ~/.manny/credentials.yaml. This is separate from config.yaml to keep secrets out
of the project directory.

Bolt launcher handles actual authentication - we only need identity fields.

Usage:
    from mcptools.credentials import credential_manager

    # Get account credentials
    creds = credential_manager.get_account("main")

    # List all accounts
    aliases = credential_manager.list_accounts()

    # Add/update account
    credential_manager.add_account("alt1", "AltAccount", character_id="123", session_id="abc")
"""
import os
import stat
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml


class CredentialManager:
    """
    Manages secure credential storage for multiple OSRS accounts.

    Credentials are stored in ~/.manny/credentials.yaml with 600 permissions.
    """

    CREDENTIALS_DIR = Path.home() / ".manny"
    CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials.yaml"

    def __init__(self):
        self.accounts: Dict[str, Dict[str, str]] = {}
        self.default: str = "default"
        self._load()

    def _ensure_dir(self) -> None:
        """Ensure credentials directory exists with proper permissions."""
        if not self.CREDENTIALS_DIR.exists():
            self.CREDENTIALS_DIR.mkdir(mode=0o700, parents=True)

    def _load(self) -> None:
        """Load credentials from file."""
        if not self.CREDENTIALS_FILE.exists():
            self.accounts = {}
            self.default = "default"
            return

        try:
            with open(self.CREDENTIALS_FILE, 'r') as f:
                data = yaml.safe_load(f) or {}

            self.accounts = data.get("accounts", {})
            self.default = data.get("default", "default")
        except Exception as e:
            print(f"Warning: Could not load credentials: {e}")
            self.accounts = {}
            self.default = "default"

    def _save(self) -> None:
        """Save credentials to file with secure permissions (600)."""
        self._ensure_dir()

        data = {
            "accounts": self.accounts,
            "default": self.default
        }

        # Write with restricted permissions
        with open(self.CREDENTIALS_FILE, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        # Set file permissions to 600 (owner read/write only)
        os.chmod(self.CREDENTIALS_FILE, stat.S_IRUSR | stat.S_IWUSR)

    def get_account(self, alias: str = None) -> Optional[Dict[str, str]]:
        """
        Get credentials for an account alias.

        Args:
            alias: Account alias. If None, uses default.

        Returns:
            Dict with display_name, jx_character_id, jx_session_id, proxy
            or None if not found.
        """
        alias = alias or self.default
        return self.accounts.get(alias)

    def list_accounts(self) -> List[str]:
        """
        List all account aliases.

        Returns:
            List of alias strings.
        """
        return list(self.accounts.keys())

    def get_accounts_info(self) -> List[Dict[str, Any]]:
        """
        Get info about all accounts (without exposing secrets).

        Returns:
            List of dicts with alias, display_name, has_tokens, is_default, has_proxy.
        """
        result = []
        for alias, creds in self.accounts.items():
            result.append({
                "alias": alias,
                "display_name": creds.get("display_name", ""),
                "has_character_id": bool(creds.get("jx_character_id")),
                "has_session_id": bool(creds.get("jx_session_id")),
                "has_proxy": bool(creds.get("proxy")),
                "is_default": alias == self.default
            })
        return result

    def add_account(
        self,
        alias: str,
        display_name: str,
        character_id: str = "",
        session_id: str = "",
        proxy: str = ""
    ) -> Dict[str, Any]:
        """
        Add or update an account's credentials.

        Args:
            alias: Account alias (e.g., "main", "alt1", "fishing_bot")
            display_name: In-game display name
            character_id: JX_CHARACTER_ID from Bolt credentials
            session_id: JX_SESSION_ID from Bolt credentials
            proxy: Optional proxy URL (e.g., "socks5://user:pass@host:port")

        Returns:
            Result dict with success status.
        """
        is_update = alias in self.accounts

        self.accounts[alias] = {
            "display_name": display_name,
        }

        if character_id:
            self.accounts[alias]["jx_character_id"] = character_id

        if session_id:
            self.accounts[alias]["jx_session_id"] = session_id

        if proxy:
            self.accounts[alias]["proxy"] = proxy

        self._save()

        return {
            "success": True,
            "action": "updated" if is_update else "added",
            "alias": alias,
            "display_name": display_name,
            "has_proxy": bool(proxy)
        }

    def set_proxy(self, alias: str, proxy: str) -> Dict[str, Any]:
        """
        Set or update proxy for an existing account.

        Args:
            alias: Account alias
            proxy: Proxy URL (e.g., "socks5://user:pass@host:port") or empty to remove

        Returns:
            Result dict with success status.
        """
        if alias not in self.accounts:
            return {
                "success": False,
                "error": f"Account '{alias}' not found"
            }

        if proxy:
            self.accounts[alias]["proxy"] = proxy
        elif "proxy" in self.accounts[alias]:
            del self.accounts[alias]["proxy"]

        self._save()

        return {
            "success": True,
            "alias": alias,
            "proxy_set": bool(proxy)
        }

    def remove_account(self, alias: str) -> Dict[str, Any]:
        """
        Remove an account from the credential store.

        Args:
            alias: Account alias to remove.

        Returns:
            Result dict with success status.
        """
        if alias not in self.accounts:
            return {
                "success": False,
                "error": f"Account '{alias}' not found"
            }

        del self.accounts[alias]

        # If we removed the default, reset default
        if self.default == alias:
            self.default = list(self.accounts.keys())[0] if self.accounts else "default"

        self._save()

        return {
            "success": True,
            "action": "removed",
            "alias": alias
        }

    def set_default(self, alias: str) -> Dict[str, Any]:
        """
        Set the default account.

        Args:
            alias: Account alias to make default.

        Returns:
            Result dict with success status.
        """
        if alias not in self.accounts:
            return {
                "success": False,
                "error": f"Account '{alias}' not found"
            }

        self.default = alias
        self._save()

        return {
            "success": True,
            "default": alias
        }

    def import_from_properties(self, alias: str, display_name: str) -> Dict[str, Any]:
        """
        Import credentials from ~/.runelite/credentials.properties.

        Useful after running RuneLite with --insecure-write-credentials flag.

        Args:
            alias: Account alias to save as
            display_name: Display name for this account

        Returns:
            Result dict with success status.
        """
        creds_file = Path.home() / ".runelite" / "credentials.properties"

        if not creds_file.exists():
            return {
                "success": False,
                "error": "~/.runelite/credentials.properties not found"
            }

        # Parse properties file
        props = {}
        try:
            content = creds_file.read_text()
            for line in content.splitlines():
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    props[key.strip()] = value.strip()
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to read credentials.properties: {e}"
            }

        character_id = props.get("JX_CHARACTER_ID", "")
        session_id = props.get("JX_SESSION_ID", "")

        if not character_id and not session_id:
            return {
                "success": False,
                "error": "No JX_CHARACTER_ID or JX_SESSION_ID found in file. "
                        "Make sure Bolt launcher has written credentials after logging in."
            }

        return self.add_account(
            alias=alias,
            display_name=display_name,
            character_id=character_id,
            session_id=session_id
        )

    def reload(self) -> None:
        """Reload credentials from disk."""
        self._load()


# Global singleton instance
credential_manager = CredentialManager()
