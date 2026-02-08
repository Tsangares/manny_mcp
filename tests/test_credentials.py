"""Tests for mcptools.credentials - CredentialManager CRUD operations."""
import os
import stat
import pytest
import yaml
from pathlib import Path
from unittest.mock import patch

from mcptools.credentials import CredentialManager


@pytest.fixture
def cred_manager(tmp_dir):
    """Create a CredentialManager with a temp credentials directory."""
    mgr = CredentialManager.__new__(CredentialManager)
    mgr.CREDENTIALS_DIR = tmp_dir / ".manny"
    mgr.CREDENTIALS_FILE = mgr.CREDENTIALS_DIR / "credentials.yaml"
    mgr.accounts = {}
    mgr.default = "default"
    return mgr


class TestCredentialManagerCRUD:
    def test_add_account(self, cred_manager):
        result = cred_manager.add_account("main", "TestPlayer", character_id="c1", session_id="s1")
        assert result["success"] is True
        assert result["action"] == "added"
        assert "main" in cred_manager.accounts
        assert cred_manager.accounts["main"]["display_name"] == "TestPlayer"

    def test_add_account_with_proxy(self, cred_manager):
        result = cred_manager.add_account("alt", "AltPlayer", proxy="socks5://x:y@h:1080")
        assert result["success"] is True
        assert result["has_proxy"] is True
        assert cred_manager.accounts["alt"]["proxy"] == "socks5://x:y@h:1080"

    def test_update_existing_account(self, cred_manager):
        cred_manager.add_account("main", "Player1")
        result = cred_manager.add_account("main", "Player1Updated")
        assert result["action"] == "updated"
        assert cred_manager.accounts["main"]["display_name"] == "Player1Updated"

    def test_get_account(self, cred_manager):
        cred_manager.add_account("main", "TestPlayer", character_id="c1")
        account = cred_manager.get_account("main")
        assert account["display_name"] == "TestPlayer"
        assert account["jx_character_id"] == "c1"

    def test_get_account_nonexistent(self, cred_manager):
        assert cred_manager.get_account("missing") is None

    def test_get_account_default(self, cred_manager):
        cred_manager.add_account("main", "TestPlayer")
        cred_manager.default = "main"
        account = cred_manager.get_account()  # Uses default
        assert account["display_name"] == "TestPlayer"

    def test_remove_account(self, cred_manager):
        cred_manager.add_account("main", "Player")
        result = cred_manager.remove_account("main")
        assert result["success"] is True
        assert "main" not in cred_manager.accounts

    def test_remove_nonexistent(self, cred_manager):
        result = cred_manager.remove_account("ghost")
        assert result["success"] is False

    def test_remove_default_resets(self, cred_manager):
        cred_manager.add_account("main", "Player1")
        cred_manager.add_account("alt", "Player2")
        cred_manager.default = "main"
        cred_manager.remove_account("main")
        assert cred_manager.default == "alt"

    def test_list_accounts(self, cred_manager):
        cred_manager.add_account("main", "P1")
        cred_manager.add_account("alt1", "P2")
        aliases = cred_manager.list_accounts()
        assert set(aliases) == {"main", "alt1"}

    def test_set_default(self, cred_manager):
        cred_manager.add_account("main", "P1")
        result = cred_manager.set_default("main")
        assert result["success"] is True
        assert cred_manager.default == "main"

    def test_set_default_nonexistent(self, cred_manager):
        result = cred_manager.set_default("ghost")
        assert result["success"] is False


class TestCredentialManagerProxy:
    def test_set_proxy(self, cred_manager):
        cred_manager.add_account("main", "Player")
        result = cred_manager.set_proxy("main", "socks5://a:b@h:1080")
        assert result["success"] is True
        assert cred_manager.accounts["main"]["proxy"] == "socks5://a:b@h:1080"

    def test_remove_proxy(self, cred_manager):
        cred_manager.add_account("main", "Player", proxy="socks5://x:y@h:1080")
        result = cred_manager.set_proxy("main", "")
        assert result["success"] is True
        assert "proxy" not in cred_manager.accounts["main"]

    def test_set_proxy_nonexistent(self, cred_manager):
        result = cred_manager.set_proxy("ghost", "socks5://x")
        assert result["success"] is False


class TestCredentialManagerInfo:
    def test_get_accounts_info(self, cred_manager):
        cred_manager.add_account("main", "P1", character_id="c1", session_id="s1")
        cred_manager.add_account("alt", "P2", proxy="socks5://x")
        cred_manager.default = "main"

        info = cred_manager.get_accounts_info()
        assert len(info) == 2

        main_info = next(i for i in info if i["alias"] == "main")
        assert main_info["display_name"] == "P1"
        assert main_info["has_character_id"] is True
        assert main_info["has_session_id"] is True
        assert main_info["is_default"] is True

        alt_info = next(i for i in info if i["alias"] == "alt")
        assert alt_info["has_proxy"] is True
        assert alt_info["is_default"] is False


class TestCredentialManagerPersistence:
    def test_save_creates_file_with_600_perms(self, cred_manager):
        cred_manager.add_account("main", "Player")
        assert cred_manager.CREDENTIALS_FILE.exists()
        mode = stat.S_IMODE(os.stat(cred_manager.CREDENTIALS_FILE).st_mode)
        assert mode == 0o600

    def test_save_and_reload(self, cred_manager):
        cred_manager.add_account("main", "Player", character_id="c1")
        cred_manager.set_default("main")

        # Reload from disk
        cred_manager._load()
        assert "main" in cred_manager.accounts
        assert cred_manager.accounts["main"]["jx_character_id"] == "c1"
        assert cred_manager.default == "main"

    def test_load_empty_file(self, cred_manager):
        cred_manager.CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
        cred_manager.CREDENTIALS_FILE.write_text("")
        cred_manager._load()
        assert cred_manager.accounts == {}
        assert cred_manager.default == "default"

    def test_load_missing_file(self, cred_manager):
        cred_manager._load()
        assert cred_manager.accounts == {}
