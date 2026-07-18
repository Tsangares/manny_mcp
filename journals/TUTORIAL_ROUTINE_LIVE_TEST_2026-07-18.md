# Tutorial Island — Upgraded Routine Engine LIVE UNATTENDED Test (2026-07-18)

**Account:** `newbakshesh` (NewBakshesh), display `:2`, jar client-1.12.34-SNAPSHOT-shaded.
**Engine:** post-upgrade `run_routine.py` (commit 1c63c42 — repeat_until, no_dialogue/dialogue
predicate, click_text wiring, chain support).
**Method:** OBSERVE + DIAGNOSE only. Each section launched via `run_routine.py
routines/tutorial_island/NN_*.yaml --account newbakshesh`; progress verified by XP deltas,
inventory, `/tmp/manny_newbakshesh_state.json`, screenshots of `:2`, and the tutorial
instruction overlay (widget group **263**). No routine/engine edits. No manual tutorial-driving
(only read-only queries + connection recovery).

---

## HEADLINE

The engine drove **Sections 01, 02, 03 fully unattended (clean SUCCESS)** and **Section 04
through woodcutting + firemaking**, then got **genuinely stuck at 04's cook-shrimp-on-fire
step** — reproduced twice, identical failure. Sections 05 and 06 were **not reachable this run**
because cooking the shrimp is a hard tutorial gate. The stuck point is a **routine-content
timing gap, not an engine bug or a plugin defect** — the cook command fires ~5s after the
fire is *started*, before the fire GameObject has spawned.

**Correction to the task premise:** the account was NOT at Section 03. On arrival it was
**disconnected** ("You were disconnected from the server" login screen), and its last live
state (which the stale state-file / cached widget tree reflected) was **Section 01, character
creation, appearance not yet set** — i.e. the very start. I recovered the connection
(`CLICK_AT 383 301` to dismiss the Ok dialog, then `LOGIN`) and drove from Section 01 forward.

---

## Per-section results

| # | Routine | Engine result | Evidence |
|---|---------|---------------|----------|
| 01 | `01_character_creation.yaml` | **COMPLETED unattended** (2nd attempt; 1st hit the disconnect) | Char-creator closed (group 679 gone); instruction advanced to "Getting started — click the Gielinor Guide" |
| 02 | `02_gielinor_guide.yaml` | **COMPLETED unattended** | Settings tab opened; **exit door opened via INTERACT_OBJECT** (DEFECT-1 fix holds); player outside at (3098,3107); instruction "Follow the path to find the Survival Instructor" |
| 03 | `03_survival_expert.yaml` | **COMPLETED unattended** | fishing XP **+10**; inventory = Small fishing net + Raw shrimps; skills tab opened; instruction "Skills and Experience… speak to continue" |
| 04 | `04_woodcutting_firemaking.yaml` | **PARTIAL — stuck at step 10** | woodcutting **+25**, firemaking **+40** (tree chopped, fire lit); **step 10 `USE_ITEM_ON_OBJECT shrimps fire` → "Object not found: fire"**; shrimp still raw; tutorial gate blocked passage |
| 05 | `05_cooking*.yaml` | **NOT REACHED** — gated behind 04 cook | — |
| 06 | `06_quest_guide.yaml` | **NOT REACHED** — gated behind 05 | — |
| 07–10 | — | Not attempted (known Wave-6-gated; out of scope for this run) | — |

---

## Root-cause: Section 04 cook-shrimp failure (the first real stuck point)

**Reproduced twice, identical.** Log timing (run 2):
```
11:45:31  USE_ITEM_ON_ITEM Tinderbox Logs   (sent)
11:45:33  USE_ITEM_ON_ITEM ... executed successfully   (tinderbox-on-logs DISPATCHED — only starts the light animation)
11:45:38  USE_ITEM_ON_OBJECT shrimps fire   (sent, ~5s later)
11:45:38  ERROR UseItemOnObjectCommand - Object not found or not clickable: fire
```
Run 1 was byte-identical (11:42:33 → 11:42:38). Both runs still gained firemaking **+40**,
proving the fire *did* light — just **after** the cook query ran.

**Diagnosis: routine-content timing gap (NOT engine, NOT plugin defect).**
- `USE_ITEM_ON_ITEM Tinderbox Logs` returning "success" only means the *use-on* interaction was
  dispatched. Lighting a fire in OSRS then plays a multi-tick animation (and can take several
  attempts) before the **Fire GameObject spawns**. The routine's step 9 (`KEY_PRESS Space`,
  `delay_before_ms: 3000`) + step 10 (`delay_before_ms: 1000`) give only ~4–5s, which fired
  the cook **before the fire existed**.
- Secondary aggravator: after a fire lights the player **auto-steps one tile back (west)**, so
  even once "Fire" exists the cook may need a re-path to an adjacent tile ("...or not clickable").
- The `USE_ITEM_ON_OBJECT` command itself is fine — it correctly reported the object was absent.
- Consequence chain: uncooked shrimp → step 13 `INTERACT_OBJECT Gate Open` correctly refused by
  the game with the modal *"You need to talk to the Survival Guide and complete her tasks before
  you are allowed to proceed through this gate."* (a **DEFECT-8** plain-message modal; `KEY_PRESS
  Space` dismisses it, `CLICK_CONTINUE` would not).

**This is exactly the class of gap the upgraded engine's `repeat_until` / await predicates were
built to close** — but `04_woodcutting_firemaking.yaml` does not yet use them for the cook step.

---

## What WORKED well (positive signals)

- **INTERACT_OBJECT on doors/gates is solid** — the Gielinor-Guide exit door (02) and the tree
  chop (04) all succeeded with no client-thread crash. DEFECT-1 remains fixed on this jar. This
  is the single most important precondition for 05/06 (which are door/gate/range-heavy).
- **INTERACT_NPC + KEY_PRESS Space dialogue chains** drove every talk in 01–04 cleanly.
- **CLICK_WIDGET with the IDs baked into the routines is correct** — the char-creator Confirm
  button really is `44499018` (verified live via widget scan); the earlier "not found/hidden"
  failures were **caused by the disconnect** (torn-down widget tree), not stale IDs.
- **Skilling actions with real state change** — fishing (+10), woodcutting (+25), firemaking
  (+40) all registered, so the atomic interactions land; only the *sequencing/await* around the
  ephemeral fire object is wrong.

## Engine observations / minor findings

- **False-positive crash detection.** During Section 01's first (disconnected) run the engine
  logged `Client crash at step 5 … No runelite_manager available, cannot restart`. The trigger
  was the stale state file — on the character-creation screen (and while disconnected) the
  periodic state-writer legitimately stops updating, so age >30s looks like a freeze even though
  the command processor was answering. Worth making crash-detection distinguish "state stale but
  command channel alive" from a true freeze; and wiring an auto-restart/relogin path
  (`No runelite_manager available` means unattended recovery from a disconnect is currently
  impossible from inside the engine).
- **`--start-step` works** (re-ran 04 from step 6 cleanly).
- **State file has no tutorial-progress field and no nearby-NPC list** — determining "current
  section" unattended currently requires either `QUERY_NPCS` + inventory heuristics or reading
  instruction widget group 263. A `tutorial_progress` varbit in the state file would make the
  chain's `progress_hint` gating (still not wired) trivial.

---

## Assessment: how close are 03–06 to reliable hands-off?

- **03 (Survival Expert): reliable NOW.** Ran clean end-to-end unattended.
- **04 (Woodcutting/Firemaking): one fix away.** Everything works except the cook step's timing.
  It is deterministically broken today (0/2), but the failure is a missing await, not a missing
  capability.
- **05–06: unverified this run** (blocked by 04). Their historically-risky parts are the
  door/gate/ladder INTERACT_OBJECTs and NPC-range GOTOs — all of which behaved well in 02/04 on
  this jar, so the outlook is cautiously positive *provided* they get the same await treatment
  the cook step needs. Real hands-off validation must wait until 04 passes.

**Bottom line:** the upgraded engine drove 3.5 tutorial sections with zero manual intervention
(only connection recovery). It is genuinely close for 03–06; the gating issue is await-condition
discipline in the routine YAMLs, plus environment stability (the account disconnected before the
run even began).

---

## Concrete fixes (priority order) to make 03–06 reliably unattended

1. **[ROUTINE — 04, top priority] Make the cook step wait for the fire to exist and retry.**
   Replace step 9/10's fixed `delay`s with the upgraded engine's `repeat_until` around
   `USE_ITEM_ON_OBJECT shrimps fire`, gated on something like `no_item:Raw shrimps` (or a
   fire-present predicate), with a per-attempt wait ≥6–8s and the player re-adjacent. This alone
   should unblock 04→05→06. Optionally `await_condition` the tinderbox step on the Fire object
   before cooking.
2. **[ROUTINE — 04] Add a short `KEY_PRESS Space` after the gate-refusal modal** (DEFECT-8) so a
   mistimed run self-recovers instead of stalling behind the modal; and consider a `GOTO` to the
   Survival Expert at the top of 04 so re-entry from a wandered position still finds him
   (INTERACT_NPC range ~10 tiles).
3. **[ENGINE] Fix crash-detection + add relogin recovery.** Distinguish "state stale but IPC
   alive" from a true freeze, and give the runner a `runelite_manager`/`LOGIN` recovery path so a
   mid-run disconnect (which happened here before the run started) is auto-handled unattended.
   Also add `--start-step`-style resume-from-section on chain failure.
4. **[ROUTINE/STATE] Expose tutorial-progress** (varbit) in the state file and turn on the
   master-chain `progress_hint` gating, so a section already completed is skipped and the chain
   can be started mid-tutorial.

*(Sections 07–10 remain gated on the previously-documented Wave-6 items — DEFECT-7 GOTO-exact,
DEFECT-8 modal dismissal, DEFECT-11 door filtering, DEFECT-13 home-teleport widget — unchanged
by this run.)*
