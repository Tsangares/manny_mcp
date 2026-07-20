# Tutorial Island Attempt #7 — judeaislam / llama — 2026-07-20

## TL;DR

The rebuilt Section 8 (`08_combat.yaml` + `08_combat_sword_ranged.yaml`, commit
`6214d0e`) worked end to end on first live contact: equipment-stats gate,
already-worn dagger equip, sword/shield handover (410→420), melee cage
(440→450), and bow/ranged (470→480) all passed clean, taking progress from
400 to 500 in under 3 minutes of live time. This is the first time this
account has ever cleared combat.

The run then reached **Section 9: Banking** for the first time ever (any
account, any attempt) and hit a genuine first-contact defect: the `Poll_booth`
object's right-click menu does not actually contain a `Use` option, despite
the routine's own comment claiming this was "LIVE-VALIDATED 2026-07-19."
`strict_steps: true` correctly flagged the section failed, but non-abort step
semantics let steps 7-10 keep running anyway, so the chain reached the exit
door and got an honest in-game block ("You need to visit the poll booth
before you can proceed through this door") instead of a silent false pass.
Progress stalled at **520** (gate is 550). No ban signals. Account parked
clean, healthy (10/10 HP), zero processes left running.

## Launch (mannyctl window — first real-mode use)

`scripts/remote/mannyctl llama window judeaislam routines/tutorial_island/00_master.yaml`

All 6 gates passed clean, no fallback needed:

```
WINDOW_GATE 1 predecessor-dead PASS
WINDOW_GATE 2 credentials      PASS: alias 'judeaislam' present, default='punitpun' (not banned)
WINDOW_GATE 3 display          PASS: 'judeaislam' -> display :8
WINDOW_GATE 4 provision        PASS: jar_sha=d0668f589e9af018 routine.py=clean
WINDOW_GATE 5 launch           PASS: LOGGED_IN at location=3107,9508,0 (login_index=10)
WINDOW_GATE 6 run              PASS: run_routine.py + watchdog detached on llama
WINDOW_RESULT overall=OK
```

Run id: `20260720T014033Z_judeaislam`. Login location (3107,9508) matched the
parked location from attempt #6, confirming clean resume.

One non-issue during launch: the watchdog ledger flagged a "crash" event
immediately (`java.lang.NullPointerException: Cannot read field "am" because
"xz.ch" is null`). Traced to `net.runelite.client.plugins.manny.ui.UITools$
WidgetInspectorTool$Panel.lambda$refreshWidgetTree$8` firing once during
`game_state: STARTING` — a debug widget-inspector panel refreshing before the
game state was ready, unrelated to login or gameplay. Login succeeded
normally 20s later. Treated as benign; not a ban signal.

## Section 8 (combat) — FIRST-CONTACT PASS

Chain correctly skipped sections 1-7 (progress 400, all gates already met)
and entered `08a: Combat (equipment interface + dagger)` within ~2 minutes of
run start, as predicted. From there, ground-truth `tutorial.progress` polling
showed:

| Time (poll) | progress | notes |
|---|---|---|
| run start | 400 | skip-gates confirmed |
| ~+1 min | 470 | equipment stats gate, dagger equip, sword/shield handover (410→420, already-worn fix), melee cage (440-450) all passed; player equipped Bronze sword + Wooden shield, HP 8/10 (combat damage, normal) |
| ~+2 min | 480 | bow/ranged section under way |
| ~+2.5 min | 500 | ranged phase complete; player back near start-of-combat-area position (3107,9508); HP 9/10 |

Client log confirms real interaction, e.g. a verified `Attack` click on
`Giant rat` (id 3313) via the menu-search/verify pipeline (`[MENU-VERIFY] ✓
Click verified: 'Attack' on attempt 1`). No manual intervention was needed —
the sword/shield already-worn `equip_item` fix and the door-crossing fix
(`f5fc911`) were not directly exercised as failure points in this section
(no doors in this stretch), but the section overall validates the `6214d0e`
rebuild.

By final state snapshot, equipped weapon was a **Shortbow** with 47 Bronze
arrows (post-ranged-phase gear), inventory contained the Bronze dagger and
Bronze sword unequipped (stowed after their respective phases) — consistent
with a normal tutorial combat teardown sequence.

**Verdict: Section 8 (both 8a and 8b) — PASS, first contact.** This retires
the failure class that blocked attempts #5 and #6 (DEFECT-29, the
sword/shield handover wedge at varp 400).

## Section 9 (banking) — FIRST-CONTACT FAIL (honest)

Progress moved 500 → 520 (ladder up/down to bank floor, bank booth used)
before stalling. Chain summary:

```
[chain 11/12] Section 9: Banking
  ! section failed, stopping chain: Section 9: Banking
...
  [FAIL] 11. Tutorial Island - Banking  - 1 step error(s)
Status: FAILED
Sections run: 11/12
```

### Root cause (client log, exact)

```
INTERACT_OBJECT Poll_booth Use --rid=2c8000cf
[INTERACT-OBJECT] Finding 'Poll booth' within 15 tiles for action 'Use'
[GameEngine] Found 1 TileObjects matching 'Poll booth' within 15 tiles
[INTERACT-OBJECT] Found TileObject 'Poll booth' as fd at WorldPoint(x=3119, y=3121, plane=0)
[INTERACT-OBJECT] Distance to 'Poll booth': 3 tiles (max interaction distance: 5)
[INTERACT-OBJECT] Already within interaction range of 'Poll booth'
[INTERACT-TILEOBJECT] Attempt 1/3 to click fd 'Poll booth' with action 'Use'
[INTERACT-TILEOBJECT] Orienting camera toward 'Poll booth' at (3119, 3121)
[INTERACT-TILEOBJECT] Menu option 'Use' not found for fd 'Poll booth'
... (attempt 2/3, same result)
... (attempt 3/3, same result)
[INTERACT-OBJECT] Failed to interact with TileObject 'Poll booth' after 3 attempts
[INTERACT_OBJECT] Failed to Use Poll booth
Command failed: INTERACT_OBJECT Poll_booth Use
```

The object was found, in range, camera oriented correctly — but its actual
right-click menu simply does not contain a `Use` verb. This directly
contradicts the routine's own header comment (`routines/tutorial_island/
09_banking.yaml` objects block): `# LIVE-VALIDATED 2026-07-19: correct object
name is "Poll_booth" (Use). Earlier "poll" transcription was wrong.` — the
object *name* transcription was apparently right, but the *action* was not
(or the action differs by context/camera angle not captured in the earlier
validation).

Because `strict_steps: true` marks the section failed on any step error but
does not hard-abort execution, steps 7-10 (dialogue advance no-op, escape
no-op, GOTO to door position, door open) all still ran and all reported
individual success. Step 10 (open door, `INTERACT_OBJECT Door Open`) did
succeed mechanically (verified click, "Command succeeded") on its 2nd of 3
attempts — but the game's own state gate then produced an honest blocking
dialogue instead of letting the player pass:

```
dialogue.text = "You need to visit the poll booth before you can proceed
through this door."
hint = CLICK_CONTINUE
```

This is the doctrine's honest-failure pattern working as designed: no false
pass, no silent cascade — the chain correctly stopped at `[FAIL] 11.
Banking`. Progress never reached the section's gate (550); it stalled at 520.

### What needs fixing (not done live — routine-authoring task, not supervision)

`routines/tutorial_island/09_banking.yaml` step 6 needs its actual menu verb
re-discovered live (e.g. via `scan_tile_objects`/menu dump on `Poll_booth` at
(3119,3121)) — likely something other than `Use` (candidates worth checking:
`Read`, `Look-at`, `Search`, or a left-click default action with no explicit
right-click entry). A one-line action-string fix in the YAML, contingent on
that live discovery.

## Process/safety notes

- Java client remained healthy throughout: LOGGED_IN, 10/10 HP at the time of
  diagnosis, not in combat, idle. No ban signals (`suspected_ban`,
  `[LOGIN] TERMINAL`) anywhere in the ledger or logs.
- Python run log (`/tmp/manny_run_judeaislam.log`) was fully stdout-buffered
  under the detached/nohup launch — stayed at 30 lines showing only chain
  section headers for the whole run despite real progress underneath, only
  flushing its full summary on process exit. Ground truth was tracked via
  the state file's `tutorial.progress` field and the RuneLite client log
  (which flushes per line) instead, per doctrine (ground truth over
  inference). Worth noting for future supervisors: don't trust
  `manny_run_<account>.log` line count as a liveness signal on detached runs;
  poll the state file and `ps` directly.
- Wrap: `scripts/remote/mannyctl llama stop judeaislam` (SIGTERM, clean).
  Verified zero java/python processes for the account afterward via
  `ps -eo pid,args | grep -i judeaislam` (empty, exit code 1) and a separate
  `run_routine.py|watchdog.py` grep (also empty).

## Metrics

Appended two rows to `journals/metrics_first_contact.csv`:
- `08_combat` — P (pass), first contact, run `20260720T014033Z_judeaislam`
- `09_banking` — F (fail), first contact, same run id

## Next actions

1. Live-discover the correct `Poll_booth` interaction verb (short live probe,
   not a full tutorial run — `scan_tile_objects`/menu-scan is enough) and fix
   `09_banking.yaml` step 6.
2. Consider whether `strict_steps` should hard-abort immediately on step
   failure rather than continuing (would have saved the wasted steps 7-10,
   though the diagnostic value of seeing the door's honest block was itself
   useful this time).
3. Resume attempt #8 once the Poll_booth fix is validated offline
   (`--dry-run` + `validate_routine_deep`) — chain gates will skip straight
   back to Section 9 at progress 520/gate ~500-510, so the cost of a retry is
   cheap.
