"""
Shared fixtures for manny-mcp tests.
"""
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml


@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a temporary directory for test files."""
    return tmp_path


@pytest.fixture
def mock_config_data():
    """Minimal valid config.yaml data."""
    return {
        "runelite_root": "/tmp/test_runelite",
        "plugin_directory": "/tmp/test_plugin",
        "runelite_jar": None,
        "log_file": "/tmp/test_manny.log",
        "session_file": "/tmp/test_session.json",
        "display": ":2",
    }


@pytest.fixture
def config_file(tmp_dir, mock_config_data):
    """Write a temporary config.yaml and return its path."""
    # Create the directories so validation doesn't warn
    Path(mock_config_data["runelite_root"]).mkdir(parents=True, exist_ok=True)
    Path(mock_config_data["plugin_directory"]).mkdir(parents=True, exist_ok=True)

    config_path = tmp_dir / "config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(mock_config_data, f)
    return config_path


@pytest.fixture
def mock_state_file(tmp_dir):
    """Create a mock game state JSON file."""
    state = {
        "location": {"x": 3222, "y": 3218, "plane": 0},
        "inventory": {
            "used": 3,
            "items": ["Lobster x5", "Coins x1000", "Bronze axe"]
        },
        "skills": {"mining": {"level": 45, "xp": 61512}},
        "health": {"current": 30, "max": 40},
    }
    state_path = tmp_dir / "manny_state.json"
    with open(state_path, "w") as f:
        json.dump(state, f)
    return state_path


@pytest.fixture
def credentials_dir(tmp_dir):
    """Create a temporary credentials directory."""
    creds_dir = tmp_dir / ".manny"
    creds_dir.mkdir()
    return creds_dir


@pytest.fixture
def sample_credentials():
    """Sample credentials data."""
    return {
        "accounts": {
            "main": {
                "display_name": "TestMain",
                "jx_character_id": "char123",
                "jx_session_id": "sess456",
            },
            "alt1": {
                "display_name": "TestAlt",
                "jx_character_id": "char789",
                "jx_session_id": "sessabc",
                "proxy": "socks5://user:pass@proxy:1080",
            },
        },
        "default": "main",
    }
