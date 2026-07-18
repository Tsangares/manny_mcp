# Routine Corpus Audit — 2026-07-18 (Track D)

Read-only audit during the parallel diort-bringup stage. No YAML edited (fixes below all need a live
Tutorial-Island pass on a FRESH account to validate — diort's `new` account is tutorial-done, so these
are deferred to a later tutorial gate, not this bring-up).

## Tutorial 05/06 double-run — REAL overlap (fix pending one live pass)
`00_master.yaml` chains `05_cooking` → `05_cooking_to_quest_guide` → `06_quest_guide`.
- `05_cooking_to_quest_guide.yaml` does the ENTIRE Quest Guide section (walk, talk, open Quest Journal
  widget `35913794`, re-talk+Space, then **climbs ladder to mining area at step 19**).
- `06_quest_guide.yaml` then repeats the SAME section from the SURFACE — but the player is already
  UNDERGROUND (~3088,9520) after 05's ladder descent, so its surface GOTOs (3086,3110 / 3086,3126)
  can't arrive → wasted timeouts / mis-walk.
- CATCH: `06` step 9 does `CLICK_WIDGET 15138820` (select "Quest Guide" dialogue option), flagged
  CRITICAL — "only after this dialogue does the ladder become usable." `05_cooking_to_quest_guide`
  LACKS this click (relies on re-talk+Space). So 05's ladder-down may silently fail and 06 is an
  accidental belt-and-suspenders.

**Fix (apply after ONE live tutorial pass confirms the 15138820 dependency):**
1. Port `CLICK_WIDGET 15138820` into `05_cooking_to_quest_guide.yaml` between its step 12
   (`CLICK_WIDGET 35913794`) and step 13 (re-talk), mirroring `06` steps 8→9.
2. Remove the `06_quest_guide.yaml` entry from `00_master.yaml` (lines ~59-61).
If the live pass shows 05 already descends on its own, skip step 1 and only remove 06's chain-entry.

## GOTO await audit — 6 genuine fire-and-forget (next step is an INTERACT)
Runner default `timeout_ms=30000` (`mcptools/tools/routine.py:1520`). A GOTO with `await_condition`
arrival-polls; a GOTO WITHOUT one is fire-and-forget (`{sent:true}` returns immediately, next step
runs before arrival). Genuine hazards — add `await_condition: "location:X,Y"` + explicit `timeout_ms`
(matching the ~60 already-fixed steps), but validate against DEFECT-7 (GOTO can stop 1 tile short →
exact-coord await could false-timeout; use a tolerant await or confirm timeout-aborts-vs-continues):
- `tutorial_island/02_gielinor_guide.yaml` step 11 (→3097,3107)
- `tutorial_island/03_survival_expert.yaml` step 7 (→3101,3093)
- `tutorial_island/10_prayer_magic.yaml` steps 1 (→3124,3124) and 11 (→3130,3107)
- `quests/romeo_and_juliet.yaml` steps 6 and 22 (→3158,3425 plane 1)
- `quests/sheep_shearer.yaml` step 9 (→3209,3212 plane 1)

Lower severity (await present, `timeout_ms` omitted → 30s×2 cap, marginal for long walks):
`skilling/superheat_mining_guild.yaml` step 1; `tutorial_island/08_combat.yaml` 16/18;
`09_banking.yaml` step 9; `10_prayer_magic.yaml` steps 10/19.

## Parse/lint: ALL CLEAN — 43/43 routines `yaml.safe_load` without error.
