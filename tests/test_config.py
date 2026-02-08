"""Tests for mcptools.config - ServerConfig loading, validation, and defaults."""
import pytest
import yaml
from pathlib import Path

from mcptools.config import ServerConfig, AccountConfig


class TestAccountConfig:
    def test_from_dict_with_all_fields(self):
        data = {
            "display": ":3",
            "jx_character_id": "char1",
            "jx_display_name": "Player1",
            "jx_session_id": "sess1",
        }
        config = AccountConfig.from_dict(data)
        assert config.display == ":3"
        assert config.jx_character_id == "char1"
        assert config.jx_display_name == "Player1"
        assert config.jx_session_id == "sess1"

    def test_from_dict_with_defaults(self):
        config = AccountConfig.from_dict({})
        assert config.display == ":2"
        assert config.jx_character_id == ""
        assert config.jx_display_name == ""
        assert config.jx_session_id == ""


class TestServerConfigLoad:
    def test_load_minimal_config(self, config_file):
        config = ServerConfig.load(config_file)
        assert config.display == ":2"
        assert config.use_exec_java is False
        assert config.java_path == "java"
        assert config.log_buffer_size == 10000

    def test_load_sets_defaults(self, config_file):
        config = ServerConfig.load(config_file)
        assert config.command_file == "/tmp/manny_command.txt"
        assert config.state_file == "/tmp/manny_state.json"
        assert config.use_virtualgl is False
        assert config.vgl_display == ":0"
        assert config.runelite_args == []

    def test_load_missing_file_raises(self, tmp_dir):
        with pytest.raises(FileNotFoundError):
            ServerConfig.load(tmp_dir / "nonexistent.yaml")

    def test_load_with_accounts(self, tmp_dir):
        data = {
            "runelite_root": "/tmp/test_rl",
            "plugin_directory": "/tmp/test_plugin",
            "runelite_jar": None,
            "log_file": "/tmp/test.log",
            "session_file": "/tmp/test_sess.json",
            "display": ":2",
            "accounts": {
                "main": {"display": ":3"},
                "alt1": {"display": ":4", "jx_character_id": "abc"},
            },
        }
        Path("/tmp/test_rl").mkdir(exist_ok=True)
        Path("/tmp/test_plugin").mkdir(exist_ok=True)
        config_path = tmp_dir / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(data, f)

        config = ServerConfig.load(config_path)
        assert "main" in config.accounts
        assert "alt1" in config.accounts
        assert config.accounts["main"].display == ":3"
        assert config.accounts["alt1"].jx_character_id == "abc"


class TestServerConfigValidation:
    def test_invalid_display_format_raises(self, tmp_dir):
        data = {
            "runelite_root": "/tmp/test_rl",
            "plugin_directory": "/tmp/test_plugin",
            "runelite_jar": None,
            "log_file": "/tmp/test.log",
            "session_file": "/tmp/test_sess.json",
            "display": "invalid",
        }
        Path("/tmp/test_rl").mkdir(exist_ok=True)
        Path("/tmp/test_plugin").mkdir(exist_ok=True)
        config_path = tmp_dir / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(data, f)

        with pytest.raises(ValueError, match="Invalid display format"):
            ServerConfig.load(config_path)

    def test_small_log_buffer_corrected(self, tmp_dir):
        data = {
            "runelite_root": "/tmp/test_rl",
            "plugin_directory": "/tmp/test_plugin",
            "runelite_jar": None,
            "log_file": "/tmp/test.log",
            "session_file": "/tmp/test_sess.json",
            "display": ":2",
            "log_buffer_size": 10,
        }
        Path("/tmp/test_rl").mkdir(exist_ok=True)
        Path("/tmp/test_plugin").mkdir(exist_ok=True)
        config_path = tmp_dir / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(data, f)

        config = ServerConfig.load(config_path)
        assert config.log_buffer_size == 10000  # Corrected to default


class TestServerConfigHelpers:
    def test_get_command_file_default(self, config_file):
        config = ServerConfig.load(config_file)
        assert config.get_command_file() == "/tmp/manny_command.txt"

    def test_get_command_file_account(self, config_file):
        config = ServerConfig.load(config_file)
        assert config.get_command_file("alt1") == "/tmp/manny_alt1_command.txt"

    def test_get_state_file_default(self, config_file):
        config = ServerConfig.load(config_file)
        assert config.get_state_file() == "/tmp/manny_state.json"

    def test_get_state_file_account(self, config_file):
        config = ServerConfig.load(config_file)
        assert config.get_state_file("ape") == "/tmp/manny_ape_state.json"

    def test_get_response_file_default(self, config_file):
        config = ServerConfig.load(config_file)
        assert config.get_response_file().endswith("response.json")

    def test_get_response_file_account(self, config_file):
        config = ServerConfig.load(config_file)
        assert config.get_response_file("alt1") == "/tmp/manny_alt1_response.json"

    def test_get_display_default(self, config_file):
        config = ServerConfig.load(config_file)
        assert config.get_display() == ":2"

    def test_get_display_for_account(self, tmp_dir):
        data = {
            "runelite_root": "/tmp/test_rl",
            "plugin_directory": "/tmp/test_plugin",
            "runelite_jar": None,
            "log_file": "/tmp/test.log",
            "session_file": "/tmp/test_sess.json",
            "display": ":2",
            "accounts": {"main": {"display": ":5"}},
        }
        Path("/tmp/test_rl").mkdir(exist_ok=True)
        Path("/tmp/test_plugin").mkdir(exist_ok=True)
        config_path = tmp_dir / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(data, f)

        config = ServerConfig.load(config_path)
        assert config.get_display("main") == ":5"

    def test_to_dict(self, config_file):
        config = ServerConfig.load(config_file)
        d = config.to_dict()
        assert "runelite_root" in d
        assert "display" in d
        assert d["display"] == ":2"
