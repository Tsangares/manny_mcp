"""Offline regression tests for three confirmed bug fixes (2026-07-18).

1. `no_item_in_bank:` stop condition no longer silently returns False -- bank
   contents are absent from the state snapshot, so it now FAILS LOUDLY.
   (mcptools/tools/routine.py:check_stop_condition)

2. `handle_send_and_await` now dispatches through the rid-correlated transport
   (`send_command_with_response`) instead of writing the raw command straight to
   the command file. (mcptools/tools/commands.py)

3. `validate_routine_deep` recognizes `mcp_tool:` steps and exempts
   reference/library/catalog/config-sidecar/manual-runbook files from the
   `steps`-required check, without suppressing genuine defects.
   (manny_tools.py)

All tests are pure/offline -- no live client, no writes to /tmp/manny_new_*.
"""
import json

import pytest
import yaml
from unittest.mock import AsyncMock, MagicMock

import manny_tools
from mcptools.tools import commands as commands_mod
from mcptools.tools import routine as routine_mod


# ---------------------------------------------------------------------------
# Bug 1: no_item_in_bank fails loudly instead of silently returning False
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestNoItemInBankFailsLoud:
    async def test_raises_not_implemented(self, monkeypatch):
        # State exists (non-empty) so evaluation reaches the condition branch.
        monkeypatch.setattr(
            routine_mod, "get_game_state",
            AsyncMock(return_value={"inventory": {"used": 1, "items": ["Coal x1"]}}),
        )
        with pytest.raises(NotImplementedError) as exc:
            await routine_mod.check_stop_condition("no_item_in_bank:Coal")
        # Message must name the condition and explain why (loud, not silent).
        assert "no_item_in_bank:Coal" in str(exc.value)
        assert "bank" in str(exc.value).lower()

    async def test_does_not_shadow_no_item(self, monkeypatch):
        # "no_item_in_bank:" must NOT be matched by the "no_item:" branch, which
        # would silently return a bool instead of raising.
        monkeypatch.setattr(
            routine_mod, "get_game_state",
            AsyncMock(return_value={"inventory": {"used": 1, "items": ["Coal x1"]}}),
        )
        with pytest.raises(NotImplementedError):
            await routine_mod.check_stop_condition("no_item_in_bank:Coal")

    async def test_plain_no_item_still_returns_bool(self, monkeypatch):
        # Regression guard: the ordinary inventory condition is unaffected.
        monkeypatch.setattr(
            routine_mod, "get_game_state",
            AsyncMock(return_value={"inventory": {"used": 1, "items": ["Coal x1"]}}),
        )
        assert await routine_mod.check_stop_condition("no_item:Coal") is False
        assert await routine_mod.check_stop_condition("no_item:Gold") is True


# ---------------------------------------------------------------------------
# Bug 2: handle_send_and_await routes through the rid transport
# ---------------------------------------------------------------------------
def _wire_send_and_await(monkeypatch, tmp_path, send_response, check_result):
    """Wire up commands module deps with a fresh (non-stale) state file."""
    state_file = tmp_path / "manny_state.json"
    state_file.write_text(json.dumps({"location": {"x": 1, "y": 2, "plane": 0}}))

    cfg = MagicMock()
    cfg.get_state_file.return_value = str(state_file)
    # get_command_file must NOT be needed anymore; make it explode if used.
    cfg.get_command_file.side_effect = AssertionError(
        "handle_send_and_await must not write the command file directly"
    )
    monkeypatch.setattr(commands_mod, "config", cfg)

    send_mock = AsyncMock(return_value=send_response)
    monkeypatch.setattr(commands_mod, "send_command_with_response", send_mock)

    monkeypatch.setattr(commands_mod, "_parse_condition", lambda c: c)
    monkeypatch.setattr(commands_mod, "_check_condition", lambda state, cond: check_result)
    monkeypatch.setattr(commands_mod, "_extract_relevant_state", lambda s: s)
    return send_mock, cfg


@pytest.mark.asyncio
class TestSendAndAwaitRidTransport:
    async def test_dispatches_through_transport(self, monkeypatch, tmp_path):
        send_mock, cfg = _wire_send_and_await(
            monkeypatch, tmp_path,
            send_response={"request_id": "abc123", "status": "ok",
                           "result": {"done": True}},
            check_result=True,
        )
        result = await commands_mod.handle_send_and_await({
            "command": "INTERACT_OBJECT Ladder Climb-up",
            "await_condition": "plane:1",
            "timeout_ms": 500,
            "poll_interval_ms": 10,
        })
        # Routed through the rid transport exactly once with the raw command.
        send_mock.assert_awaited_once()
        args = send_mock.await_args.args
        assert args[0] == "INTERACT_OBJECT Ladder Climb-up"
        assert args[1] == 500  # timeout_ms passed through
        # Never wrote the command file directly (the old bypass).
        cfg.get_command_file.assert_not_called()
        # Condition met -> success, and the correlated response is surfaced.
        assert result["success"] is True
        assert result["condition_met"] is True
        assert result["command_response"]["request_id"] == "abc123"

    async def test_timeout_still_reports_response(self, monkeypatch, tmp_path):
        send_mock, cfg = _wire_send_and_await(
            monkeypatch, tmp_path,
            send_response={"request_id": "z9", "status": "ok", "result": {}},
            check_result=False,  # condition never met -> timeout
        )
        result = await commands_mod.handle_send_and_await({
            "command": "GOTO 1 2 0",
            "await_condition": "location:1,2",
            "timeout_ms": 30,
            "poll_interval_ms": 5,
        })
        send_mock.assert_awaited_once()
        assert result["success"] is False
        assert result["condition_met"] is False
        assert result["command_response"]["request_id"] == "z9"
        assert result["checks"] >= 1  # do-while: at least one state check ran

    async def test_undelivered_fails_fast(self, monkeypatch, tmp_path):
        send_mock, cfg = _wire_send_and_await(
            monkeypatch, tmp_path,
            send_response={"delivered": False, "status": "error",
                           "error": "command not consumed"},
            check_result=True,  # would pass if we polled -- but we must not
        )
        result = await commands_mod.handle_send_and_await({
            "command": "BANK_OPEN",
            "await_condition": "idle",
            "timeout_ms": 100,
            "poll_interval_ms": 10,
        })
        send_mock.assert_awaited_once()
        assert result["success"] is False
        assert "not consumed" in result["error"]
        assert result["command_response"]["delivered"] is False

    async def test_stale_state_preflight_short_circuits(self, monkeypatch, tmp_path):
        # A stale state file should fail BEFORE dispatching (transport untouched).
        import os
        import time
        state_file = tmp_path / "manny_state.json"
        state_file.write_text(json.dumps({"location": {}}))
        old = time.time() - 120
        os.utime(state_file, (old, old))

        cfg = MagicMock()
        cfg.get_state_file.return_value = str(state_file)
        monkeypatch.setattr(commands_mod, "config", cfg)
        send_mock = AsyncMock()
        monkeypatch.setattr(commands_mod, "send_command_with_response", send_mock)
        monkeypatch.setattr(commands_mod, "_parse_condition", lambda c: c)

        result = await commands_mod.handle_send_and_await({
            "command": "GOTO 1 2 0",
            "await_condition": "idle",
        })
        assert result["success"] is False
        assert result["diagnosis"] == "PLUGIN_FROZEN"
        send_mock.assert_not_awaited()


# ---------------------------------------------------------------------------
# Bug 3: validator recognizes mcp_tool steps + exempts reference files
# ---------------------------------------------------------------------------
def _write_yaml(tmp_path, name, data):
    p = tmp_path / name
    p.write_text(yaml.safe_dump(data))
    return str(p)


def _validate(path):
    # check_commands=False -> no dependency on a live PlugerHelpers.java parse.
    return manny_tools.validate_routine_deep(path, plugin_dir="/nonexistent",
                                             check_commands=False)


class TestValidatorMcpToolSteps:
    def test_mcp_tool_step_is_valid(self, tmp_path):
        path = _write_yaml(tmp_path, "equip_routine.yaml", {
            "name": "Equip test",
            "steps": [
                {"id": 1, "action": "BANK_OPEN", "description": "open"},
                {"id": 2, "mcp_tool": "equip_item",
                 "args": {"item_name": "Ghostspeak amulet"},
                 "description": "equip"},
            ],
        })
        res = _validate(path)
        joined = " ".join(res["errors"])
        assert "Missing required field 'action'" not in joined
        assert res["valid"] is True

    def test_unknown_mcp_tool_errors(self, tmp_path):
        path = _write_yaml(tmp_path, "bad_mcp.yaml", {
            "name": "Bad mcp",
            "steps": [{"id": 1, "mcp_tool": "teleport_home", "description": "x"}],
        })
        res = _validate(path)
        assert any("Unknown mcp_tool 'teleport_home'" in e for e in res["errors"])

    def test_step_missing_both_action_and_mcp_tool_errors(self, tmp_path):
        path = _write_yaml(tmp_path, "no_action.yaml", {
            "name": "No action",
            "steps": [{"id": 1, "description": "does nothing"}],
        })
        res = _validate(path)
        assert any("Missing required field 'action'" in e for e in res["errors"])


class TestValidatorReferenceExemption:
    def test_reference_filename_exempt(self, tmp_path):
        path = _write_yaml(tmp_path, "widget_reference.yaml", {
            "tabs": {"combat_tab": 123}, "banking": {"deposit": 456},
        })
        res = _validate(path)
        assert "Missing required field: 'steps'" not in res["errors"]
        assert res["non_executable"] is True

    def test_common_actions_nested_steps_exempt(self, tmp_path):
        path = _write_yaml(tmp_path, "common_actions.yaml", {
            "stairs": {"lumbridge": {"up": {"steps": [{"action": "GOTO"}]}}},
        })
        res = _validate(path)
        assert "Missing required field: 'steps'" not in res["errors"]
        assert res["non_executable"] is True

    def test_manual_steps_exempt(self, tmp_path):
        path = _write_yaml(tmp_path, "gravestone_retrieval.yaml", {
            "name": "Gravestone Retrieval", "type": "utility",
            "manual_steps": ["do a thing", "do another"],
        })
        res = _validate(path)
        assert "Missing required field: 'steps'" not in res["errors"]
        assert res["non_executable"] is True

    def test_config_sidecar_exempt(self, tmp_path):
        path = _write_yaml(tmp_path, "hill_giants.yaml", {
            "name": "Hill Giants", "type": "combat", "npc": "Hill Giant",
            "loot": {"items": ["Law rune"]}, "eating": {"food": "Tuna"},
        })
        res = _validate(path)
        assert "Missing required field: 'steps'" not in res["errors"]
        assert res["non_executable"] is True

    def test_explicit_type_reference_exempt(self, tmp_path):
        path = _write_yaml(tmp_path, "some_doc.yaml", {
            "name": "A doc", "type": "reference", "notes": "stuff",
        })
        res = _validate(path)
        assert "Missing required field: 'steps'" not in res["errors"]
        assert res["non_executable"] is True

    def test_genuine_missing_steps_still_errors(self, tmp_path):
        # A real routine that simply forgot its steps must STILL be flagged --
        # no marker, no nested steps, no config sidecar sections.
        path = _write_yaml(tmp_path, "broken_routine.yaml", {
            "name": "Broken", "type": "skilling", "author": "someone",
        })
        res = _validate(path)
        assert "Missing required field: 'steps'" in res["errors"]
        assert res["non_executable"] is False
        assert res["valid"] is False

    def test_normal_routine_not_flagged_non_executable(self, tmp_path):
        path = _write_yaml(tmp_path, "real.yaml", {
            "name": "Real", "type": "skilling",
            "steps": [{"id": 1, "action": "MINE_ORE", "description": "mine"}],
        })
        res = _validate(path)
        assert res["non_executable"] is False
        assert "Missing required field: 'steps'" not in res["errors"]
