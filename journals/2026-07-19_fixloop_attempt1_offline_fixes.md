# 2026-07-19 — FIX-LOOP after tutorial attempt #1: engine honesty, ladder pins, kill-then-spawn, provisioning, creds guard

**Author:** FIX-LOOP agent (overseer-tutorial umbrella), offline pass between attempt #1
(punitpun @ llama, journal `2026-07-19_tutorial_attempt1_punitpun_llama.md`) and attempt #2.
All fixes verified offline only: full pytest suite green (380 passed, incl. 10 new tests),
`validate_routine_deep` clean on every touched routine, full-corpus `--dry-run` sweep green
(39 executable routines, 0 failures), master-chain dry-run PASS on all 11 sections.

## Fix 1a — step-failure propagation: `config.strict_steps` (false-pass class)

Attempt #1's root defect class: a section logged failed steps (`repeat_until` caps, widget
miss, ladder "I can't reach that!") and still exited runner-status SUCCESS, so the chain
marched on against a desynced game (42 blind minutes in s07/s08).

Engine (`mcptools/tools/routine.py`): new `config: {strict_steps: true}` gate. Any step that
fails under the default `on_failure: continue` policy now flips the SECTION result to
`success: False` at completion (`strict_failure`, `first_failed_step`, `failed_steps`
recorded) — control flow unchanged (not an abort; retry/abort policies unaffected). The
chain runner (`run_routine.py run_chain`) already stops on a failed section, so this closes
the loop end-to-end. Off by default: legacy grind routines that tolerate transient step
failures behave exactly as before. All 12 `routines/tutorial_island/*.yaml` sections opt in.

## Fix 1b — game-progress gating: Python/YAML design + REQUIRED JAVA EXPORT (user gate)

Checked the live state export (`/tmp/manny_punitpun_state.json`): the top-level `scenario`
field is the plugin's own scenario-playback progress (`running/looping/currentTask`), NOT
the game's tutorial progression. **No field in the state export carries the OSRS
tutorial-progress signal**, so a true "game says this section is done" gate cannot be built
from Python today. Per the no-Java-edits rule, the Java half is specified here and NOT
implemented:

- **Java export needed:** `StateExporter` should add a top-level `tutorial` object, e.g.
  `"tutorial": {"progress": <int varbit 281>, "hint_visible": <bool widget group 263 visible>}`.
  Varbit 281 (`VarbitID.TUTORIAL_PROGRESS`, "Tutorial Island progress") increments through
  the island's stages and hits 1000 on completion; it is THE authoritative signal the game
  itself uses to gate each instructor. One `client.getVarbitValue(281)` per GameTick export —
  negligible cost, read-only, no new command surface.
- **Python half (designed, parked):** a `tutorial_stage:>=N` Grammar-1 atom in
  `monitoring._parse_condition/_check_condition` reading `state["tutorial"]["progress"]`,
  plus per-section `await_condition` gates (the master chain's `progress_hint` values are
  already positioned to become the gate thresholds). NOT implemented now because (a) it is
  dead code until the export exists, and (b) `_parse_condition` carries an explicit parked
  design note ("the general condition dialect is pending the user's design decision — do
  NOT generalize it here"). When the user green-lights the Java export, the atom is a
  ~15-line addition and the YAML gates a mechanical edit.
- **Interim mitigation (live now):** strict_steps + location awaits give a de-facto
  game-truth gate at every section boundary — e.g. if s05b's ladder gate did not open, the
  player stays on the surface, s07 step 1's `await_condition: location:3080,9504`
  (underground) times out, strict_steps fails s07, chain stops. Honest failure instead of
  false-pass, just one section later than a varbit gate would catch it.

## Fix 2 — ladder / cross-plane honesty

- **YAML (2a):** the ladder lives in `05_cooking_to_quest_guide.yaml` (NOT 06 — 06 is
  deprecated out of the chain). Added step **12d**: `GOTO 3088 3119 0 exact` +
  `await_condition: location:3088,3119` seating the player ON the ladder's surface tile
  before step 13's `INTERACT_OBJECT Ladder Climb-down` — the attempt-#1 resume clicks came
  from outside the house wall ("I can't reach that!"). Object name stays `Ladder` (single
  word, no underscore needed; live-verified name from attempt-#1 logs). Same pin added to
  the deprecated 06 reference file (step 15b) for parity. NOTE: descent lands at
  (3088,9520) still plane 0 — underground here is a Y-offset, not a plane change, so the
  await on the NEXT section's location gate (see 1b interim) verifies the descent; do not
  gate on `plane:`.
- **Engine (2b):** no-await `GOTO` steps now take a position snapshot before sending and
  verify progress after: if the player has not moved one tile within ~4s (6 polls x 0.7s)
  and is not already within 2 tiles of the target, the step FAILS with an explicit
  "path likely blocked or requires a transport" error (`_verify_goto_progress`). The s07
  cross-plane silent march (0 tiles in 8.5 min) is now an immediate honest step failure,
  which strict_steps escalates to a section failure. GOTOs WITH a `location:` await are
  untouched (their await already polices arrival and timeouts to failure).

## Fix 3 — auto-restart kill-then-spawn (double-client)

`_auto_restart_client` previously called `runelite_manager.stop_instance()` — a no-op when
the client was launched by a DIFFERENT process (`mannyctl start`), since the CLI run path
builds a fresh `MultiRuneLiteManager` with empty `instances`. That is exactly how attempt
#1 got two JVMs on display :4 sharing the account's IPC. Now:

- `_reap_account_client`: reaps the tracked instance AND any session-ledger PID for the
  account (`session_manager.get_active_sessions()` + `pid_is_runelite` verification —
  cross-process, so it finds the mannyctl-launched client), SIGTERM -> verify -> SIGKILL ->
  verify. If any predecessor cannot be confirmed dead, **refuse to spawn** (fail loud).
- Restart cap: `_MAX_AUTO_RESTARTS = 2` per account per process. The disconnect->relogin
  escalation path does not spend the crash `restart_attempts` budget, so pre-fix it could
  relaunch forever; now the 3rd escalation fails loud and the run exits with
  `disconnect_detected` for the watchdog/supervisor to see.

## Fix 4 — provisioning: host-correct config render + jar sha256 gate + unbuffered runner

- `provision.sh` step 4b (new): after venv setup, renders the HOST's `config.yaml` in
  place — `java_path` <- hosts.yaml `jdk`, `runelite_jar` <- staged
  `<runelite_libs>/<shaded jar>`, `runelite_root` <- staging dir (so the laptop gradle
  auto-detect can never resolve a stale jar on a host with no source tree), and stamps
  `runelite_jar_sha256` with the orchestrator-side sha of the jar it just rsynced.
  Idempotent; values passed as argv (no YAML-literal quoting through ssh).
- `ServerConfig` gained optional `runelite_jar_sha256`; `RuneLiteInstance.start()` verifies
  the RESOLVED jar against it before launching and refuses on mismatch (loud error naming
  both hashes) — the attempt-#1 stale `~/runelite.jar` silent fallback is now impossible on
  a provisioned host. Laptop behavior unchanged (field absent -> no check).
- `mannyctl run` (both detached and `--attach`) now exports `PYTHONUNBUFFERED=1` so
  section-transition prints stream to the host log live (attempt #1's runner log was
  useless until process exit).

## Fix 5 — credentials fix script + push-creds wiring

New `scripts/fix_credentials_defaults.sh` (idempotent, tested on a copy of the live file):
sets `default:` to a safe automation alias (`punitpun` default, `--default <alias>` flag;
refuses aliases not present in the file), inserts the BANNED guard comment above `new:` and
`newbakshesh:` when absent (awk prev-line guard — re-runs never duplicate), preserves 600
perms, never prints tokens. `mannyctl push-creds` now runs it on the LOCAL file before the
scp, so a Bolt-reset `default: new` can never be propagated to a host again (the reset has
struck 5+ times; the live file indeed had `default: new` when this was written).

## NOT addressed (from the attempt-#1 journal), and why

- **Cause of the 19:19Z disconnect at ~60 min:** unestablished; nothing to fix offline.
  Attempt #2 should watch for a recurrence at similar session age.
- **Premature "Client crash detected (attempt 1/3)" on first boot** (health check fires
  before the client finishes booting): mitigated indirectly (restart is now harmless-safe
  and capped) but the premature-fire itself is untouched — it needs a boot-grace window in
  `check_client_health` and a live client to tune it against; deferred to avoid changing
  crash detection semantics blind.
- **Ladder transport knowledge in the walker (GOTO traversing ladders):** the honest-failure
  half is done (2b); actual transport-aware pathing is Java (`pathfinder/transports`) and
  out of scope under the no-Java rule.
- **Tutorial varbit gate:** Java half specified above, user-gated.
- **Moving attempt-#1 screenshots into journals/images/:** left in the supervisor
  scratchpad; a supervisor housekeeping task, not a repo fix.

## Attempt #2 resume recipe (for the supervisor)

punitpun is parked mid-island on the SURFACE at the "climb down the ladder" stage (state
file loc (3094,3107) — quest-guide area; ladder gate believed OPEN from attempt #1's 06
resume runs having exhausted the post-journal monologue, but NOT verified). Resume with:

    mannyctl llama run routines/tutorial_island/05_cooking_to_quest_guide.yaml \
        --account punitpun --start-step 12b

i.e. section file `05_cooking_to_quest_guide.yaml`, start step **12b** (re-talk -> 12c
monologue exhaust -> 12d NEW ladder-tile pin -> 13 climb-down). Starting at 12b rather than
12d deliberately re-runs the gate-opener: if the gate is already open the re-talk is a
cheap no-op dialogue, and if attempt #1's desync left it closed this is the only sequence
that opens it. Then continue with 07 -> 10 (07's step 1 location await now verifies the
descent under strict_steps). Prerequisite: re-provision llama first (`mannyctl llama
provision`) so the 4b config render + jar sha gate land there — the live-edited
`/tmp`-backed config fix from attempt #1 predates the sha256 field.
