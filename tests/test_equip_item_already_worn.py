"""Offline regression test for handle_equip_item's ALREADY-WORN honest success.

Attempt #6 (judeaislam, 2026-07-20): a chain restart of tutorial section 08 at
progress 400 re-ran the dagger-equip step, but the dagger was already WORN -- it
lives in the EQUIPMENT container (not the inventory), so the widget scan found
nothing and equip_item false-failed "not found in inventory", aborting the run.
The fix: before failing, check the live equipment state; if the named item is
already equipped, return an honest success with `already_equipped: true`. A
genuine not-found (neither in inventory nor equipped) still fails.

Pure/offline -- no live client. Mocks the rid-correlated transport and the state
file the driver reads.
"""
import json

import pytest
from unittest.mock import AsyncMock, MagicMock

from mcptools.tools import commands as commands_mod


def _wire(monkeypatch, tmp_path, *, equipment, inventory_items, scan_widgets):
    """Point commands_mod at a temp state file + a scripted transport.

    ``equipment`` -> player.equipment dict; ``inventory_items`` -> player.inventory
    items list; ``scan_widgets`` -> the widgets list SCAN_WIDGETS returns.
    """
    state_file = tmp_path / "manny_state.json"
    state_file.write_text(json.dumps({
        "player": {
            "inventory": {"items": inventory_items},
            "equipment": equipment,
        }
    }))

    cfg = MagicMock()
    cfg.get_state_file.return_value = str(state_file)
    monkeypatch.setattr(commands_mod, "config", cfg)

    async def fake_send(command, timeout_ms=None, account_id=None):
        if command.startswith("TAB_OPEN"):
            return {"status": "success"}
        if command.startswith("SCAN_WIDGETS"):
            return {"status": "success", "result": {"widgets": scan_widgets}}
        return {"status": "success"}

    monkeypatch.setattr(commands_mod, "send_command_with_response",
                        AsyncMock(side_effect=fake_send))


@pytest.mark.asyncio
async def test_already_worn_item_returns_honest_success(monkeypatch, tmp_path):
    # Dagger is WORN (equipment slot), NOT in inventory; scan finds no equip-able
    # widget. equip_item must report an honest already-equipped success.
    _wire(
        monkeypatch, tmp_path,
        equipment={"weapon": {"name": "Bronze dagger", "id": 1205}},
        inventory_items=[],
        scan_widgets=[],
    )
    result = await commands_mod.handle_equip_item(
        {"item_name": "Bronze dagger", "account_id": "test"})

    assert result["success"] is True
    assert result.get("already_equipped") is True
    assert "already equipped" in result.get("note", "").lower()


@pytest.mark.asyncio
async def test_genuinely_missing_item_still_fails(monkeypatch, tmp_path):
    # Item is neither in inventory nor equipped -> must still be an honest failure
    # (do not swallow a real not-found).
    _wire(
        monkeypatch, tmp_path,
        equipment={"weapon": {"name": "Bronze dagger", "id": 1205}},
        inventory_items=[],
        scan_widgets=[],
    )
    result = await commands_mod.handle_equip_item(
        {"item_name": "Rune platebody", "account_id": "test"})

    assert result["success"] is False
    assert result.get("already_equipped") is not True
    assert "not found" in result.get("error", "").lower()


@pytest.mark.asyncio
async def test_equipped_names_helper_extracts_slot_names():
    names = commands_mod._equipped_names({
        "weapon": {"name": "Bronze dagger", "id": 1205},
        "shield": {"name": "Wooden shield"},
        "empty": None,
        "bad": "not-a-dict",
    })
    assert "bronze dagger" in names
    assert "wooden shield" in names
    assert len(names) == 2
    assert commands_mod._equipped_names(None) == []
    assert commands_mod._equipped_names({}) == []
