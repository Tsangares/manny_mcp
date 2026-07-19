# Tutorial attempt #3b (ifixifixit/llama) — the exact→plain revert is VALIDATED, but a RESUME-position structural gap (minimap-follower can't traverse the fenced cook-compound's doors/gates) blocks 05b before the ladder — Lessons Learned
**Date:** 2026-07-19

## The Problem

Resumed `ifixifixit` on llama after commit `070d159` reverted the attempt-#3 exact-mode
GOTO regression. Goal: escape the attempt-#3 wall-trap, re-run `00_master`, and finally
answer the campaign's key question — **does the ladder descend?** Result: the wall-trap
escape succeeded fast, the revert behaved exactly as designed, but 05b could not complete
because the freed player was on the WRONG SIDE of the fenced cooking compound and the
minimap nav-follower cannot walk through doors/gates. **The ladder question remains
UNANSWERED** — same net outcome as attempt #3, but a fully different (and now precisely
identified) root cause.

## Root Cause(s)

Three distinct issues, in order of contact:

1. **`hosts.yaml` default display `:2` on llama IS the user's physical GNOME desktop.**
   `ifixifixit` had no `account_displays` entry, so `mannyctl start` fell back to the host
   default `:2`, where `gnome-shell` (pid 1193) + `Xwayland :1` own `/tmp/.X11-unix/X2`.
   The client crashed with `AWTError: Can't connect to X11 window server using ':2'`.
   Attempt #3's journal noted ifixifixit ran on `:5` ("matches hosts.yaml this run") — the
   mapping was LOST from hosts.yaml between attempts.

2. **Resume-from-arbitrary-position is incompatible with the corpus.** The attempt-#3
   trap parked the player OUTSIDE, at the SOUTH edge of the fenced cook compound. 05b
   assumes the player starts INSIDE the cook building (fresh from the cooking step) and
   exits WEST through the cook door up the x=3072 corridor. From the exterior the player
   is separated from that route by the building wall + compound fence, whose only openings
   are doors/gates.

3. **The minimap directional nav-follower cannot traverse doors/gates.** With
   `navBackend=shadow`, stage-2 A* only logs (`NAV-SHADOW`), and the legacy directional
   follower drives. It minimap-clicks toward the target BEARING and wall-sticks; it does
   NOT issue the game-native click-through-door that OSRS uses to auto-open and path
   through a door. Symptom: `[NAV-DIRECT] smartMinimapClick failed ... Stuck ... path
   blocked by wall/obstacle`, and the game itself printed **"I can't reach that!"**.

## Key Lessons

### 1. The exact→plain revert WORKS — validated live, up to the structural wall

**What happened:** After I hand-walked the player to `(3076,3088)` — *exactly* attempt-#3's
undershoot tile — and re-launched the chain:
- 05b **step 1** `GOTO 3073 3090` (plain): the `location:3073,3090` await (3-tile Chebyshev
  tolerance) **ACCEPTED** `(3076,3088)` (Cheb dist 3). In attempt #3 the `exact` suffix
  hard-failed this same undershoot and sealed the player in. **This is the fix, proven.**
- 05b **step 2** `INTERACT_OBJECT Door Open`: **succeeded** ("Successfully performed Open").
- 05b **step 3** `GOTO 3072 3090`: failed — but honestly (see lesson 3), because the door
  is untraversable by the follower from the exterior, not because of the revert.

**Why it matters:** The revert's slop-tolerance is the correct behavior on approach legs.
It accepted the legitimate 3-tile undershoot while still rejecting the 17-tile and
4-tile-wall-blocked cases. Reserve `exact` for the live-earned ladder pins only (12d/12e).

### 2. Escaping the attempt-#3 wall-trap: go EAST through the gate, never punch WEST

**What happened:** From the park tile `(3085,3097)` a single plain `GOTO` toward the
gate-adjacent tile routed the player 5 tiles THROUGH `Gate(3089,3092)` to building-exterior
`(3090,3093)` — the "dead sink" only exists WESTWARD. Free-pathing then confirmed with a
clean 10-tile plain GOTO. **The overseer's east-detour intel was exactly right.** Escape
took ~2 min, not the feared 20.

### 3. Plain GOTO reports FAILURE honestly — no dishonest-success defect; and `strict_steps` IS set

**What happened (answers the doctrine question):**
- `05_cooking_to_quest_guide.yaml:59` has **`strict_steps: true`** — NOT a corpus gap.
- When fully blocked, plain `GOTO` returns **`status: failed` / "Navigation failed"**
  (`CommandBase: [GOTO] Command failed`), NOT a dishonest success. The restored
  await-`location` tolerance (separate mechanism) is what accepts small undershoots — and
  it correctly accepted Cheb-3 while rejecting Cheb-17/blocked. So the slop we deliberately
  restored and the honesty of the primitive are cleanly separated; neither is defective.
- CAVEAT: in the FIRST (pre-reposition) run I saw steps execute while the player sat frozen
  17-18 tiles from every target — a possible silent-march signature — but I killed the
  runner+watchdog before either run terminated naturally (their ledgers are stuck
  `running`), so I cannot confirm whether `strict_steps` failed to enforce or was mid-retry.
  **A dedicated offline dry-run/replay is needed to settle this; do not conclude a defect.**

### 4. Plain-GOTO's 3-tile short-circuit BLOCKS close-range manual positioning

**What happened:** To hand-walk the player onto a door-adjacent tile, every
`GOTO <tile within 3>` returned `"Already at ... distance N tiles"` and moved the player
ZERO tiles. With `exact` forbidden during shepherding, there is **no non-exact lever to
nudge a player a precise 1-3 tiles.** The workaround (target a tile BEYOND tolerance to
force movement, e.g. `GOTO 3069 3090` west-of-door) still failed here because the follower
can't cross the door — but the technique is the right one when no door is in the way.

### 5. Xvfb framebuffer screenshot = the fastest geometry oracle

Two `import -window root` captures on `DISPLAY=:5` instantly revealed what 15 minutes of
coordinate-probing could not: the player was OUTSIDE the building at the compound's SW
corner, boxed by fences, with the Quest Guide flag across an unreachable fence line. When
nav "can't reach", **screenshot before theorizing.**

## Anti-Patterns

1. **Don't** let an automation account fall back to a host's default display without
   verifying that display isn't a real desktop session — you'll hijack (or crash against)
   the user's GNOME/Xwayland.
2. **Don't** expect the shadow-mode minimap follower to open or path through doors/gates —
   it walks toward a bearing and wall-sticks. This is the load-bearing case for stage-2
   transports.
3. **Don't** hand-navigate tile-by-tile around a structural obstacle the overseer already
   classified as "known gap, no fix expected" — it's the click-tool-sprawl anti-pattern and
   burns live budget for nothing. Classify, screenshot, report, stop.
4. **Don't** trust a GOTO's own verdict — "timeout"/"failed" frequently coincides with 5+
   tiles of real movement; always re-read `location` from the state file after.

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `import -window root /tmp/x.png` (DISPLAY=:5), scp, Read | Ground-truth geometry when nav "can't reach" |
| `mannyctl <host> cmd <acct> SCAN_TILEOBJECTS <name>` | Door/gate positions + open/closed state |
| `mannyctl <host> cmd <acct> QUERY_TRANSITIONS` | Summary of nearby doors/gates + states |
| `python3 state.py` on `/tmp/manny_<acct>_state.json` | LOC + tutorial.progress + login + state age (freeze check) |
| `ss -lxp \| grep X<n>` on host | Who really owns a display (Xvfb vs gnome-shell/Xwayland) |
| `grep NAV-DIRECT/NAV-SHADOW <clientlog>` | Distinguish follower wall-stick from A* path-not-found |

## Interface Gaps Identified

- [ ] **hosts.yaml (orchestration):** llama default display `:2` = physical GNOME desktop.
      Every automation account needs an explicit `account_displays` entry, or the default
      must point at a non-physical display. (Worked around locally: restored
      `ifixifixit: ":5"`; left UNCOMMITTED for the user to ratify.)
- [ ] **Plugin/nav (the real blocker):** the shadow-mode minimap follower cannot traverse
      doors/gates. Until stage-2 transport-aware nav drives (not just shadows), any routine
      that must pass a door/gate is unrunnable from a non-corpus start position. This is the
      resume-from-arbitrary-position gap; stage-2 transports are the intended fix.
- [ ] **Doctrine:** confirm `strict_steps` enforcement vs. silent-march via offline replay
      (see lesson 3 caveat).
- [ ] **Campaign:** the LADDER descent and the s08 sword/shield/bow DEFECT-29 equips remain
      UNMEASURED. Both need a run that reaches 05b/07/08 from an IN-CORPUS position — i.e. a
      FRESH account run (which now, post-revert, should clear 5b's cook-exit from inside),
      NOT another resume of this exterior-trapped account.

## Files Modified (working tree only — NOT committed by this run)

| File | Change |
|------|--------|
| `scripts/remote/hosts.yaml` | Restored `account_displays.ifixifixit: ":5"` on llama + comment that default `:2` is the physical desktop. Local orchestration config; left uncommitted for user review. |
| `journals/2026-07-19_tutorial_attempt3b_ifixifixit_llama.md` | This journal (committed). |
| `journals/metrics_first_contact.csv` | 3b rows (committed). |
