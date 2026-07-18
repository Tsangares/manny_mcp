# Tutorial Island Routine Readiness — 2026-07-18

*Read-only assessment. No files edited, no client touched, no writes to the live
defect log (`TUTORIAL_TEST_DEFECTS_2026-07-17.md`, Driver #5 in flight) or to
`/tmp/manny_new_*`. Cross-references: `routines/tutorial_island/*.yaml`, the routine
engine `mcptools/tools/routine.py`, condition parser `mcptools/tools/monitoring.py`,
and the journals `TUTORIAL_TEST_DEFECTS_2026-07-17.md` (Driver #1-#4 durable log) and
`ROUTINE_CORPUS_STUDY_2026-07-18.md`.*

---

## Verdict

**NO — we cannot one-command replay Tutorial Island today. Honest readiness ≈ 20%.**

Two independent walls, either of which alone is fatal:

1. **There is no runnable target.** `run_routine.py` takes exactly one YAML file
   (`run_routine.py:24,64,139`); `handle_execute_routine` has no directory/glob/chain
   support. There is **no `00_master` / `run_all` tutorial routine** — the 01→10
   sections are ten separate files, each requiring the *exact* tutorial stage as start
   state (corpus study §1, "require the exact tutorial stage as start state"). So
   `run_routine.py tutorial_island` is not even a valid invocation. One-command replay
   requires a chaining wrapper that does not exist.

2. **The three most dialogue-heavy sections (08/09/10) are pre-adopted against engine
   features that were never built.** They will not run clean through the executor even
   though they carry `status: VALIDATED` — because they were validated *agent-driven*,
   never through `run_routine.py`'s await/repeat path (corpus study §5.2).

Critically, **tonight's manual drive produced ZERO routine improvements.** The defect
log states repeatedly: "no routine YAML edits were made (git clean at termination)"
(defects log:56), "No YAML edits committed yet" (:106), "will annotate rather than
rewrite" (:106). Every hard-won coordinate, gate location, hover-sweep pixel offset,
and modal-dismissal trick from Drivers #1-#4 lives **only as prose in the journal** —
none of it is in the YAMLs. The manual knowledge and the runnable artifact are still
completely disjoint.

---

## Per-section readiness table

| Sec | File | Executable? | Blocking gaps | Effort → runnable |
|---|---|---|---|---|
| 1 | `01_character_creation.yaml` | Yes (widget + WAIT only) | Fixed `WAIT 16000` timing; no NPC/door. Lowest risk. | **Low** — likely runs as-is |
| 1b | `01_experience_selection.yaml` | Yes (1 step) | Overlaps sec 1; ambiguous run order (two `01_*`). | Low |
| 2 | `02_gielinor_guide.yaml` | Partial | Fixed 4×/3× `KEY_PRESS Space` (blind count, no dialogue check); `INTERACT_OBJECT Door Open` (DEFECT-1 path — fix holds on new jar, defects:191). | **Med** — timing fragility |
| 3 | `03_survival_expert.yaml` | Partial | GOTO range + blind space counts; INTERACT_NPC fine. | Med |
| 4 | `04_woodcutting_firemaking.yaml` | Partial | `INTERACT_OBJECT tree/Gate`, `USE_ITEM_ON_OBJECT` — DEFECT-1 path; blind space. | Med |
| 5 | `05_cooking.yaml` | Partial | `INTERACT_OBJECT Door Open` ×2; wrong-door hazard noted in prose only. | Med |
| 5b | `05_cooking_to_quest_guide.yaml` | Partial (data gap) | 5 `locations`/`waypoints` **missing `plane`** (corpus §3); lowercase `door` vs `Door`; DEFECT-11 door-action filtering risk. | Med |
| 6 | `06_quest_guide.yaml` | Partial | Doors + ladder (DEFECT-1 path); dialogue-option widget `15138820`; blind space. | Med |
| 7 | `07_mining_smithing.yaml` | Partial | **Dead steps**: prospect steps 7,12 — Driver #2 confirmed this variant skips Prospect (defects:126-129); rock/furnace/anvil are estimated coords; DEFECT-1 path. | **Med-High** — remove dead steps + re-verify coords |
| 8 | `08_combat.yaml` | **NO** | `await_condition:"dialogue"` ×3 (:64,97,148) — parser raises `ValueError`, command never sent (monitoring.py:533-536); `repeat_until:"no_dialogue"` ×3 — **unimplemented, presses space once**; DEFECT-7 GOTO no-op, DEFECT-8 modal-block (the 40-min combat saga, defects:142-184). | **High** |
| 9 | `09_banking.yaml` | **NO** | `repeat_until:"poll_interface_open"` / `"no_dialogue"` — unimplemented; `await_condition:plane:N` OK; doors auto-close (defects:241). | High |
| 10 | `10_prayer_magic.yaml` | **NO** | `await_condition:"dialogue"` ×7 (:62,85,120,142,170,194,242); `mcp_tool:"click_text"` ×6 (:175,199,247,263,271...) — **not in dispatch, returns "Unknown mcp_tool"**; `repeat_until` ×6 — unimplemented. Worst-off section. | **High** |
| — | `widget_reference.yaml` | Reference (no steps) | Doc only. | n/a |

Summary: sections **1-6 are directionally runnable** with engine tolerance/timing
work; **7 has dead/unverified steps**; **8/9/10 are structurally broken** against the
executor and are the sections whose "VALIDATED" stamp is misleading.

---

## The conversion gap — what stands between "manual drive tonight" and "runnable routine"

### A. Engine changes (Python, doable NOW — not blocked by the deployment freeze)

The routine engine lives entirely in Python; none of these touch the frozen plugin jar.

1. **`repeat_until` is completely unimplemented.** `grep repeat_until mcptools/tools/routine.py`
   returns **zero matches.** The step executor (`_execute_step`, routine.py:1329-1348)
   reads only a numeric `repeat` with an optional `await_condition` short-circuit — it
   never looks at `repeat_until`. So every `repeat_until:"no_dialogue"` step (08/09/10,
   ~15 steps total) executes **exactly once**: a single space press through a multi-screen
   tutorial dialogue. This is the **single biggest structural gap** — bigger than the
   `dialogue` atom — because tutorial dialogues run 3-12 screens and vary in length.
   Fix: implement `repeat_until: <condition>` as a loop-until-condition-or-max, reusing
   `_parse_condition`; add a `no_dialogue` / `dialogue` predicate reading `handle_get_dialogue`'s
   `dialogue_open` (routine.py:297-414 already computes exactly this).

2. **`await_condition:"dialogue"` fails fast.** `_parse_condition` (monitoring.py:527-536)
   raises `ValueError` for any bare word except `idle`; `handle_send_and_await` parses the
   condition *before* writing the command (corpus §5.2), so the step returns
   `Invalid condition` **without ever issuing the INTERACT_NPC** — then the one retry
   (routine.py:1417-1428) fails identically. 10 steps affected (08:64,97,148 +
   10:62,85,120,142,170,194,242). Fix: add a `dialogue` case to `_parse_condition` (poll
   `dialogue_open == true`). Same predicate as #1.

3. **`mcp_tool:"click_text"` is not wired.** `_execute_mcp_tool_step` (routine.py:1463-1471)
   dispatches only `equip_item`, `click_widget`, `find_and_click_widget`; anything else
   returns `Unknown mcp_tool`. Section 10 uses `click_text` in **6 steps** (all its final
   dialogue/Ironman-decline advances) → all fail. Fix is trivial: map `click_text` →
   `handle_click_widget({dialogue_option / text})` — `handle_click_widget` already supports
   `dialogue_option` and `continue_dialogue` (routine.py:605-627).

### B. Deploy-frozen plugin defects (BLOCKED until the Wave 6 relaunch)

These are Java-side and cannot be fixed under the current freeze (defects log:42):

- **DEFECT-7 (GOTO arrival tolerance no-ops)** — GOTO to a tile ≤2-3 away returns
  "Already at" *without moving* (defects:136-140,222). Tutorial routines are packed with
  short precision GOTOs (e.g. `GOTO 3097 3107 0` before a door). **This silently breaks
  door-approach and NPC-approach positioning across nearly every section.** Highest-impact
  plugin defect for tutorial driving. Needs an `exact:true` / tolerance-0 mode.
- **DEFECT-8 ("I can't reach that!" modal blocks all movement; CLICK_CONTINUE fails on it,
  KEY_PRESS space dismisses)** (defects:154,183,223). No routine step handles this.
- **DEFECT-11 (INTERACT_OBJECT has no action-aware candidate filtering — locks onto the
  wrong/closer door)** (defects:229-232). Directly hits the many `INTERACT_OBJECT Door Open`
  steps where an open and a closed door coexist.
- **DEFECT-1/3/12, CAMERA_STABILIZE off-thread** — DEFECT-1 (INTERACT_OBJECT camera-orient)
  is *fixed and holds on new jar 2fcb602* (defects:191), but **DEFECT-3 (SCAN_TILEOBJECTS)
  is confirmed NOT covered by that fix** (defects:193-209) and DEFECT-12 (TILE NPE) is a new
  regression. Routines avoid SCAN_TILEOBJECTS, so DEFECT-3 is low-impact for them.

Priority order the drivers themselves converged on (defects:183-184):
**DEFECT-8 > DEFECT-7 > DEFECT-1** for tutorial driving.

### C. Coordinate / knowledge transcription (Python-side YAML edits, doable NOW)

None of Drivers #1-#4's findings are in the YAMLs. To transcribe:
- Add `plane` to the 5 locations in `05_cooking_to_quest_guide.yaml` (corpus §3).
- Delete/guard the dead Prospect steps in `07_mining_smithing.yaml:83-95,114-119`.
- Encode the validated exact gate/door/ladder tiles the drivers found (e.g. combat exit
  gate reachable from `3109,9515`, defects:169-173; bank ladder up→down immediately,
  09:47-61) so GOTO targets are ≥4 tiles out (DEFECT-7 workaround) rather than the current
  1-3-tile approaches.
- The hover-sweep pixel primitive (defects:246-250) is an **agent** technique, not a
  routine step type — it cannot be transcribed into YAML and is a sign the linear model is
  fighting the client (see Design note).

---

## Minimal path to a runnable, unattended `tutorial_island`

Shortest ordered task list. **[NOW]** = pure-Python, not blocked by the freeze;
**[BLOCKED]** = needs the Wave 6 plugin relaunch.

1. **[NOW]** Implement `repeat_until` + a `dialogue`/`no_dialogue` predicate in
   `routine.py` (`_execute_step` loop + `_parse_condition`). Unblocks the dialogue spine of
   08/09/10 and lets 01-07 drop their brittle blind space-press counts. *Highest ROI.*
2. **[NOW]** Wire `mcp_tool:"click_text"` into `_execute_mcp_tool_step` (~3 lines). Unblocks
   section 10's 6 failing steps.
3. **[NOW]** Fix the `05_cooking_to_quest_guide` plane gap and remove `07`'s dead Prospect
   steps.
4. **[NOW]** Write the missing orchestrator: a `00_tutorial_master.yaml` (or a
   `--chain` flag / directory mode in `run_routine.py`) that runs 01→10 in order. Without
   this there is no single command regardless of section quality. Gate each section on the
   tutorial-progress hint (widget group 263, defects:129) rather than assuming the prior
   section left the player in the exact spot.
5. **[BLOCKED]** DEFECT-8 (modal dismissal) and DEFECT-7 (GOTO exact mode) plugin fixes,
   then re-drive 07-10 through the executor to re-stamp them *executor-validated* (today's
   "VALIDATED" means agent-validated only).
6. **[BLOCKED]** DEFECT-11 (door action filtering) to make `INTERACT_OBJECT Door Open`
   reliable where multiple doors coexist.

Realistically: steps 1-4 (all **doable now in Python**) get sections **01-06 to a plausible
unattended run** and make the command *exist*. Sections **07-10 stay gated on the Wave 6
deploy** (DEFECT-7/8/11) before they're trustworthy hands-off. So the honest near-term
ceiling without a deploy is **"unattended through the Quest Guide (sec 6), agent-assisted
thereafter."**

---

## Design note — fixed step-list vs dialogue-state-driven loop

**A fixed step-list is the wrong structure for the tutorial, and the corpus already shows
the seam.** Sections 01-07 hardcode N separate `KEY_PRESS Space` steps with `delay_before_ms`
timers — a *blind, timing-based* count. This is fragile in both directions: if a dialogue has
one more screen than coded, the routine desyncs and every later step targets the wrong UI
state; if it has fewer, the extra space presses can dismiss the *next* interaction or open an
unintended dialogue. Tutorial dialogue length genuinely varies (experienced-vs-new account
paths, and the "stale instruction" wrinkles the drivers hit, defects:52).

Sections 08/09/10 already tried to fix this by switching to `repeat_until:"no_dialogue"` — i.e.
**"keep advancing while a dialogue is open."** That is exactly the right instinct; the only
problem is the engine never implemented it. **Recommendation:**

- **Replace every blind space-count with a `repeat_until: no_dialogue` continue-loop** once
  the predicate exists (task 1). This makes dialogue advancement self-terminating and
  timing-independent — the biggest single reliability win for the whole tutorial.
- **Keep a thin linear skeleton for the irreversible *actions*** (fish, chop, mine, equip,
  cast, climb) — those are genuinely sequential and gated by the game.
- **Gate section transitions on the tutorial progress hint** (widget group 263), not on
  assumed player position, so the master routine is a **stage-driven state machine** ("read
  current stage → run the handler for that stage → advance"), not a fixed 250-step list. This
  is also the only structure that survives the disconnect/relaunch recovery the drivers kept
  needing (defects:60-66).

Net: the tutorial wants a **dialogue-state-driven loop wrapped in a stage state machine**, not
a fixed step list. The current YAMLs are ~80% linear-action skeleton (reusable) and ~20% blind
dialogue counting (should be replaced by the `repeat_until` loop). The engine work in tasks 1-2
is what converts the drivers' prose knowledge into that reliable structure.
