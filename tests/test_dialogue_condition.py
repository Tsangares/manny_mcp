"""Tests for the NARROW `dialogue` / `no_dialogue` predicate.

This is the only new condition atom added for the tutorial routines. It reads
the top-level `dialogue` object ({open, type, options}) in the state file:
- `dialogue`    -> dialogue.open is True
- `no_dialogue` -> dialogue.open is False

It also fixes `await_condition: "dialogue"`, which previously raised ValueError
in _parse_condition (before the command was ever sent). It is deliberately
minimal -- NOT the proposed general condition dialect.
"""
import json
from unittest.mock import MagicMock

import pytest

from mcptools.tools import monitoring


class TestParseDialogueCondition:
    def test_dialogue_parses_to_want_open(self):
        assert monitoring._parse_condition("dialogue") == ("dialogue", True, None)

    def test_no_dialogue_parses_to_want_closed(self):
        assert monitoring._parse_condition("no_dialogue") == ("dialogue", False, None)

    def test_idle_still_parses(self):
        assert monitoring._parse_condition("idle") == ("idle", None, None)

    def test_unknown_bare_word_still_raises(self):
        with pytest.raises(ValueError):
            monitoring._parse_condition("gibberish")


class TestCheckDialogueCondition:
    def test_dialogue_open_matches_dialogue(self):
        state = {"dialogue": {"open": True, "type": "npc", "options": []}}
        assert monitoring._check_condition(state, ("dialogue", True, None)) is True
        assert monitoring._check_condition(state, ("dialogue", False, None)) is False

    def test_dialogue_closed_matches_no_dialogue(self):
        state = {"dialogue": {"open": False, "type": "none", "options": []}}
        assert monitoring._check_condition(state, ("dialogue", False, None)) is True
        assert monitoring._check_condition(state, ("dialogue", True, None)) is False

    def test_missing_dialogue_key_treated_as_closed(self):
        state = {"player": {}}
        assert monitoring._check_condition(state, ("dialogue", False, None)) is True
        assert monitoring._check_condition(state, ("dialogue", True, None)) is False

    def test_null_dialogue_treated_as_closed(self):
        state = {"dialogue": None}
        assert monitoring._check_condition(state, ("dialogue", False, None)) is True


@pytest.mark.asyncio
class TestAwaitDialogueNoLongerFailsFast:
    """`await_condition: "dialogue"` used to return Invalid condition without ever
    polling. It now routes through the narrow predicate and actually waits."""

    async def _run(self, monkeypatch, tmp_path, dialogue_open, condition):
        state = {"player": {"location": {"x": 1, "y": 2, "plane": 0}},
                 "dialogue": {"open": dialogue_open, "type": "npc", "options": []}}
        state_file = tmp_path / "manny_state.json"
        state_file.write_text(json.dumps(state))

        fake_config = MagicMock()
        fake_config.get_state_file.return_value = str(state_file)
        monkeypatch.setattr(monitoring, "config", fake_config)

        return await monitoring.handle_await_state_change({
            "condition": condition,
            "timeout_ms": 500,
            "poll_interval_ms": 50,
        })

    async def test_dialogue_open_condition_met(self, monkeypatch, tmp_path):
        result = await self._run(monkeypatch, tmp_path, True, "dialogue")
        assert result["success"] is True
        assert result["condition_met"] is True

    async def test_no_dialogue_condition_met(self, monkeypatch, tmp_path):
        result = await self._run(monkeypatch, tmp_path, False, "no_dialogue")
        assert result["success"] is True
        assert result["condition_met"] is True

    async def test_dialogue_condition_is_not_invalid(self, monkeypatch, tmp_path):
        # Dialogue closed but we await "dialogue" -> times out (NOT "Invalid condition").
        result = await self._run(monkeypatch, tmp_path, False, "dialogue")
        assert result["success"] is False
        assert "invalid" not in (result.get("error", "").lower())
