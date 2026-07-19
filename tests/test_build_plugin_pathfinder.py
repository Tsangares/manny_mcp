"""Tests for build_plugin's pathfinder-resources wiring (nav WP6 backlog item 4).

install_pathfinder_resources.sh (manny/scripts/) stages the vendored pathfinder
data (collision-map.zip, transports/transports.tsv, data.fingerprint) into the
RuneLite resource tree that the client build consumes. It was previously not
invoked by any manny_mcp build path (journals/NAV_WP6_DATA_REFRESH_SCOPE_2026-07-19.md,
§5/backlog item 4), so a re-cloned RuneLite tree or a post-refresh build could
silently ship without pathfinder data, or with a stale copy the runtime
integrity guard then refuses.

`handle_build_plugin` (mcptools/tools/core.py) now runs the install script
before invoking gradle and aborts loudly if the script is missing or exits
nonzero. These tests cover both the standalone helper (`_install_pathfinder_resources`,
exercised against tiny real stand-in shell scripts -- cheap, no gradle) and the
full `handle_build_plugin` flow with subprocess mocked out entirely (no real
gradle run).
"""
import subprocess
import textwrap
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from mcptools.tools import core as core_mod

# core_mod.subprocess IS the stdlib `subprocess` module object (same import) --
# monkeypatching core_mod.subprocess.run patches it everywhere, including here.
# Grab the real one up front so fake_run() below can still shell out for real.
_real_subprocess_run = subprocess.run


def _config(tmp_path: Path) -> SimpleNamespace:
    plugin_directory = tmp_path / "manny"
    runelite_root = tmp_path / "runelite"
    plugin_directory.mkdir()
    runelite_root.mkdir()
    return SimpleNamespace(plugin_directory=plugin_directory, runelite_root=runelite_root)


def _write_script(plugin_directory: Path, body: str) -> Path:
    scripts_dir = plugin_directory / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    script = scripts_dir / "install_pathfinder_resources.sh"
    script.write_text(textwrap.dedent(body))
    script.chmod(0o755)
    return script


# ---------------------------------------------------------------------------
# _install_pathfinder_resources -- exercised against real (tiny) stand-in
# scripts, not the real install_pathfinder_resources.sh, and not gradle.
# ---------------------------------------------------------------------------
class TestInstallPathfinderResourcesHelper:
    def test_missing_script_fails_loud(self, tmp_path, monkeypatch):
        cfg = _config(tmp_path)
        monkeypatch.setattr(core_mod, "config", cfg)
        # No scripts/install_pathfinder_resources.sh created.

        result = core_mod._install_pathfinder_resources()

        assert result["success"] is False
        assert "install_pathfinder_resources.sh not found" in result["error"]
        assert str(cfg.plugin_directory) in result["error"]

    def test_script_success_reports_output(self, tmp_path, monkeypatch):
        cfg = _config(tmp_path)
        monkeypatch.setattr(core_mod, "config", cfg)
        _write_script(cfg.plugin_directory, """\
            #!/usr/bin/env bash
            echo "  up-to-date: net/runelite/client/plugins/manny/pathfinder/collision-map.zip"
            exit 0
        """)

        result = core_mod._install_pathfinder_resources()

        assert result["success"] is True
        assert "up-to-date" in result["output"]

    def test_script_nonzero_exit_fails_loud(self, tmp_path, monkeypatch):
        cfg = _config(tmp_path)
        monkeypatch.setattr(core_mod, "config", cfg)
        _write_script(cfg.plugin_directory, """\
            #!/usr/bin/env bash
            echo "ERROR: source resource missing" >&2
            exit 1
        """)

        result = core_mod._install_pathfinder_resources()

        assert result["success"] is False
        assert "exited 1" in result["error"]
        assert "ERROR: source resource missing" in result["output"]

    def test_uses_config_paths_not_hardcoded(self, tmp_path, monkeypatch):
        """MANNY_ROOT/RUNELITE_ROOT passed to the script must come from config,
        not a hardcoded absolute path (per WP6 backlog item 4 requirement)."""
        cfg = _config(tmp_path)
        monkeypatch.setattr(core_mod, "config", cfg)
        _write_script(cfg.plugin_directory, """\
            #!/usr/bin/env bash
            echo "MANNY_ROOT=$MANNY_ROOT"
            echo "RUNELITE_ROOT=$RUNELITE_ROOT"
            exit 0
        """)

        result = core_mod._install_pathfinder_resources()

        assert result["success"] is True
        assert f"MANNY_ROOT={cfg.plugin_directory}" in result["output"]
        assert f"RUNELITE_ROOT={cfg.runelite_root}" in result["output"]


# ---------------------------------------------------------------------------
# handle_build_plugin -- subprocess fully mocked, no real gradle/script run.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestHandleBuildPluginWiring:
    async def test_missing_script_aborts_before_gradle(self, tmp_path, monkeypatch):
        cfg = _config(tmp_path)
        monkeypatch.setattr(core_mod, "config", cfg)
        run_mock = MagicMock()
        monkeypatch.setattr(core_mod.subprocess, "run", run_mock)

        result = await core_mod.handle_build_plugin({})

        assert result["success"] is False
        assert result["stage"] == "install_pathfinder_resources"
        assert "not found" in result["error"]
        # Script was missing -> subprocess.run must never be invoked (no gradle call).
        run_mock.assert_not_called()

    async def test_script_failure_aborts_before_gradle(self, tmp_path, monkeypatch):
        cfg = _config(tmp_path)
        monkeypatch.setattr(core_mod, "config", cfg)
        _write_script(cfg.plugin_directory, """\
            #!/usr/bin/env bash
            exit 1
        """)

        gradle_run = MagicMock()

        def fake_run(cmd, **kwargs):
            if cmd[0] == "./gradlew":
                gradle_run(cmd, **kwargs)
                return subprocess.CompletedProcess(cmd, 0, stdout="BUILD SUCCESSFUL", stderr="")
            # Real script execution for the pathfinder-install call.
            return _real_subprocess_run(cmd, **kwargs)

        monkeypatch.setattr(core_mod.subprocess, "run", fake_run)

        result = await core_mod.handle_build_plugin({})

        assert result["success"] is False
        assert result["stage"] == "install_pathfinder_resources"
        assert "exited 1" in result["error"]
        gradle_run.assert_not_called()

    async def test_success_flows_through_to_gradle(self, tmp_path, monkeypatch):
        cfg = _config(tmp_path)
        monkeypatch.setattr(core_mod, "config", cfg)
        _write_script(cfg.plugin_directory, """\
            #!/usr/bin/env bash
            echo "  up-to-date: collision-map.zip"
            exit 0
        """)

        def fake_run(cmd, **kwargs):
            if cmd[0] == "./gradlew":
                return subprocess.CompletedProcess(cmd, 0, stdout="BUILD SUCCESSFUL", stderr="")
            return _real_subprocess_run(cmd, **kwargs)

        monkeypatch.setattr(core_mod.subprocess, "run", fake_run)

        result = await core_mod.handle_build_plugin({"clean": False})

        assert result["success"] is True
        assert result["return_code"] == 0
        assert "up-to-date" in result["pathfinder_resources"]
