"""Tests for chain / directory support in run_routine.py.

`run_routine.py` can now execute an ordered sequence of routines:
- a chain YAML (`type: chain` with a `chain:` list), or
- a directory (all *.yaml in sorted order, skipping the 00_ master + reference docs).

Chain runs stop at the first failed section by default (later tutorial sections
assume the prior one positioned the player), unless --continue-on-error.
"""
import os
from unittest.mock import AsyncMock

import pytest
import yaml

import run_routine


def _write(path, data):
    with open(path, "w") as f:
        f.write(data)


class TestResolveChain:
    def test_single_file_is_one_entry(self, tmp_path):
        f = tmp_path / "solo.yaml"
        _write(f, "name: solo\nsteps:\n  - id: 1\n    action: PING\n")
        entries, base = run_routine.resolve_chain(str(f))
        assert len(entries) == 1
        assert entries[0]["routine"] == str(f)

    def test_chain_yaml_resolves_in_order(self, tmp_path):
        (tmp_path / "a.yaml").write_text("name: a\nsteps: []\n")
        (tmp_path / "b.yaml").write_text("name: b\nsteps: []\n")
        chain = tmp_path / "master.yaml"
        _write(chain, yaml.dump({
            "name": "m", "type": "chain",
            "chain": [
                {"routine": "a.yaml", "progress_hint": 1},
                {"routine": "b.yaml", "progress_hint": 2},
            ],
        }))
        entries, base = run_routine.resolve_chain(str(chain))
        assert [os.path.basename(e["routine"]) for e in entries] == ["a.yaml", "b.yaml"]
        # Relative section paths resolve against the chain file's directory.
        assert entries[0]["routine"] == str(tmp_path / "a.yaml")
        assert entries[0]["progress_hint"] == 1

    def test_chain_entries_can_be_bare_strings(self, tmp_path):
        chain = tmp_path / "m.yaml"
        _write(chain, yaml.dump({"type": "chain", "chain": ["x.yaml", "y.yaml"]}))
        entries, _ = run_routine.resolve_chain(str(chain))
        assert [os.path.basename(e["routine"]) for e in entries] == ["x.yaml", "y.yaml"]

    def test_directory_sorted_and_skips_master_and_reference(self, tmp_path):
        for name in ["02_b.yaml", "01_a.yaml", "00_master.yaml", "widget_reference.yaml"]:
            (tmp_path / name).write_text("name: n\nsteps: []\n")
        entries, base = run_routine.resolve_chain(str(tmp_path))
        names = [os.path.basename(e["routine"]) for e in entries]
        assert names == ["01_a.yaml", "02_b.yaml"]


class TestIsChain:
    def test_directory_is_chain(self, tmp_path):
        assert run_routine.is_chain(str(tmp_path)) is True

    def test_chain_yaml_is_chain(self, tmp_path):
        f = tmp_path / "m.yaml"
        _write(f, yaml.dump({"type": "chain", "chain": ["a.yaml"]}))
        assert run_routine.is_chain(str(f)) is True

    def test_plain_routine_is_not_chain(self, tmp_path):
        f = tmp_path / "solo.yaml"
        _write(f, "name: solo\nsteps:\n  - id: 1\n    action: PING\n")
        assert run_routine.is_chain(str(f)) is False


@pytest.mark.asyncio
class TestRunChain:
    async def _make_chain(self, tmp_path, n=3):
        names = [f"0{i}_sec.yaml" for i in range(1, n + 1)]
        for name in names:
            (tmp_path / name).write_text("name: n\nsteps: []\n")
        chain = tmp_path / "master.yaml"
        chain.write_text(yaml.dump({
            "type": "chain",
            "chain": [{"routine": name} for name in names],
        }))
        return str(chain), names

    async def test_runs_all_sections_in_order(self, tmp_path, monkeypatch):
        chain, names = await self._make_chain(tmp_path, 3)
        calls = []

        async def fake_run(path, max_loops, start_step, account_id):
            calls.append(os.path.basename(path))
            return {"success": True, "routine_name": os.path.basename(path)}

        monkeypatch.setattr(run_routine, "run_routine", fake_run)
        result = await run_routine.run_chain(chain, account_id="main")

        assert result["success"] is True
        assert calls == names
        assert result["sections_run"] == 3

    async def test_stops_on_first_failure(self, tmp_path, monkeypatch):
        chain, names = await self._make_chain(tmp_path, 3)
        calls = []

        async def fake_run(path, max_loops, start_step, account_id):
            calls.append(os.path.basename(path))
            # Second section fails.
            ok = len(calls) != 2
            return {"success": ok, "routine_name": os.path.basename(path)}

        monkeypatch.setattr(run_routine, "run_routine", fake_run)
        result = await run_routine.run_chain(chain)

        assert result["success"] is False
        assert calls == names[:2]  # stopped after the failing 2nd section
        assert result["sections_run"] == 2

    async def test_continue_on_error_runs_all(self, tmp_path, monkeypatch):
        chain, names = await self._make_chain(tmp_path, 3)
        calls = []

        async def fake_run(path, max_loops, start_step, account_id):
            calls.append(os.path.basename(path))
            ok = len(calls) != 2
            return {"success": ok, "routine_name": os.path.basename(path)}

        monkeypatch.setattr(run_routine, "run_routine", fake_run)
        result = await run_routine.run_chain(chain, continue_on_error=True)

        assert result["success"] is False       # overall still failed
        assert calls == names                    # but every section ran
        assert result["sections_run"] == 3

    async def test_missing_section_file_stops_chain(self, tmp_path, monkeypatch):
        chain = tmp_path / "m.yaml"
        chain.write_text(yaml.dump({"type": "chain", "chain": ["nope.yaml"]}))

        fake_run = AsyncMock(return_value={"success": True})
        monkeypatch.setattr(run_routine, "run_routine", fake_run)
        result = await run_routine.run_chain(str(chain))

        assert result["success"] is False
        assert fake_run.await_count == 0
        assert "not found" in result["sections"][0]["error"].lower()


class TestMasterChainFile:
    def test_master_resolves_all_ten_sections(self):
        master = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "routines", "tutorial_island", "00_master.yaml")
        entries, base = run_routine.resolve_chain(master)
        names = [os.path.basename(e["routine"]) for e in entries]
        # 11 section files (two 01_* and two 05_*), in tutorial order.
        #
        # NOT 12: as of the DOUBLE-RUN FIX (2026-07-18, Track D, commit
        # e17123a), 06_quest_guide.yaml is deliberately NOT chained.
        # 05_cooking_to_quest_guide.yaml is the merged bridge that now performs
        # the entire Quest Guide segment itself (it ported 06's "Quest Guide"
        # dialogue option CLICK_WIDGET 15138820 step -- see 00_master.yaml's
        # DOUBLE-RUN FIX comment). Chaining 06 after it re-ran the whole
        # segment on an already-underground player and desynced the
        # Tutorial-progress gate. 06 stays on disk only as a standalone
        # reference; it is intentionally excluded from 00_master.yaml's
        # `chain:` list (an explicit list, not a directory glob, so the
        # duplicate 01_*/05_* numeric prefixes are non-ambiguous here).
        assert names[0] == "01_character_creation.yaml"
        assert names[-1] == "10_prayer_magic.yaml"
        assert "06_quest_guide.yaml" not in names
        assert len(entries) == 11
        # Every referenced section actually exists on disk.
        for e in entries:
            assert os.path.exists(e["routine"]), e["routine"]
