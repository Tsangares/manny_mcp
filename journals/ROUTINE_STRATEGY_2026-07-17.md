# Routine Strategy — how should we handle the game?

*2026-07-17. Discussion document, not a plan. Written from a read-only audit of `routines/`,
the executor, and every recording pipeline in both repos, mid-refactor-campaign (post Wave 4c,
`f8ac79f`). Nothing here has been changed yet.*

---

## 1. What exists today

### The routine library (`routines/`, 44 files)

| Category | Files | State |
|---|---|---|
| `tutorial_island/` | 12 (steps 01–10 + widget_reference) | Validated Jan 2026, command-compatible today |
| `skilling/` | 11 (fishing, mining, superheat, cooking, …) | Command-compatible |
| `combat/` | 9 (cows, chickens, hill giants chain) | 1 broken (`hill_giants_loot` uses removed `EAT_FOOD`) |
| `quests/` | 5 | **3 broken** — `imp_catcher`, `sheep_shearer`, `restless_ghost` use `DIALOGUE_CONTINUE`/`DIALOGUE_SELECT`, which no longer exist anywhere in the plugin (0 grep hits) |
| `utility/`, `test/`, `generated/` | 5 | Misc; one auto-generated sample |

Concrete staleness check: I extracted every `action:` across all 44 YAMLs (45 distinct commands)
and diffed against the live client's LIST_COMMANDS (133 commands, post-Wave-4c). **Only 3 are
dead** (`DIALOGUE_CONTINUE`, `DIALOGUE_SELECT`, `EAT_FOOD`) — the library aged far better than
expected. The dialogue commands were presumably replaced by `CLICK_CONTINUE`/`CLICK_DIALOGUE`,
so the 4 broken routines are a rename-fix, not a rewrite.

The Tutorial Island set is the best-documented code in the repo: every step carries validated widget
IDs, discovered pitfalls ("fishing spot action is `Net` not `Small Net`", "skills tab is
35913793, not the two IDs that don't work"), and range-limit notes. That knowledge is real and
expensive to re-derive. **But** the routines are open-loop: dialogue is advanced by blind
`KEY_PRESS Space` with fixed `delay_before_ms`, almost no `await_condition` usage — they work
when the game cooperates and drift silently when it doesn't.

### The executor (`run_routine.py` → `mcptools/tools/routine.py:951`)

Better than its reputation: inner/outer loops, string step IDs, variable interpolation,
`await_condition` support (`plane:`, `has_item:`, `location:`, `idle`, …), `mcp_tool` steps,
health checks every 5 steps, **crash detection with auto-restart (3 attempts)**, consecutive-
failure limits, XP accounting. Post-Wave-2 it uses `transport.py` (rid-correlated sends — the
stale-response bug is gone). This layer is solid and worth keeping.

## 2. The recording story — what you half-remember

You remembered correctly, and then some. There are **four** overlapping recording pipelines,
which is the click-tool sprawl pattern again, one layer up:

1. **Always-on command log** (`session.py`) → `/tmp/manny_sessions/commands_YYYY-MM-DD.yaml`.
   Works — today's file exists. Logs every command the MCP layer sends. No state, no timing
   semantics, no manual-play capture.
2. **Explicit session recording** (`start_session_recording` / `stop_session_recording` /
   `session_to_routine`, session.py) — records commands + state deltas + markers + dialogue.
   `session_to_routine` exists but is **naive**: commands → steps verbatim, drops all timing,
   infers no await conditions. Aspirational-quality output.
3. **`generate_routine`** (`routine_generator.py`) — builds a routine from the plugin's
   **location history** (`/tmp/manny_<acct>_location_history.json`, live now): collapses
   movements, extracts interaction/plane/dialogue events, **infers await_conditions**, detects
   phases. This is the smartest converter — and it captures *manual play too*, because location
   history records what the character does regardless of who's driving. One sample output exists
   (`routines/generated/`).
4. **Java-side recorder** (`DialogueTracker` + sidebar "Action Recorder" panel) — this is the
   one you used while playing. Two modes; **COMMANDS mode is the default** and translates your
   raw clicks into high-level commands (`WALK_TO`, `TALK_NPC`, …), exportable to .cmdlog/YAML;
   its tooltip literally says "Best for Tutorial Island automation!". Replay goes through
   `ScenarioEngine` via the registered `LOAD_SCENARIO` command, with a scenario library at
   `~/.osrs_scenarios/` — **which does not exist on this machine**. Any recordings you made
   live on the old laptop (backup at juno:/mnt/backup/old_laptop_260330, worth a look).

So: recording→routine is real, not imagined — but it's four half-finished paths where one
finished one should be, and the two replay engines (YAML routines vs ScenarioEngine scenarios)
duplicate each other. Wave 6 already plans to gut ScenarioEngine's Actions layer; this doc's
question is which *strategy* the survivors should serve.

## 3. The strategic options

**a. YAML routines as the workhorse (status quo, repaired).**
Cheap to run (zero tokens once written), debuggable (declarative steps, validated widget IDs),
integrates with the interrupt system through normal commands. But brittle to game state
(open-loop dialogue stepping), and authoring is expensive — someone has to know the widget IDs.
Fine for grind loops; poor for anything dialogue-heavy or novel.

**b. Record-then-replay as the primary path.**
Lowest authoring cost — you just play. But recordings are the *most* brittle artifact: they
bake in one specific world state (your position, camera, spawn RNG, dialogue order). Verbatim
replay of Tutorial Island would fail the first time an NPC pathing differs. Recording is a great
*authoring input*, a bad *execution format*.

**c. Live agent-driven play, no routines.**
Most robust to surprises — the agent reads state, adapts, recovers; it's how we'll debug the
refactored stack anyway. But it's the most expensive per hour by orders of magnitude (tokens),
slow (~seconds per decision), and non-reproducible: a failed run doesn't leave behind an
artifact you can fix. Using it for grinding 100 lobsters is burning money to imitate a cron job.

**d. Hybrid layering.**
Each mode where it's strong: agent for novel/one-off content, routines for repetition,
recording as an authoring aid that produces routine drafts.

## 4. My recommendation

**Hybrid (d), with a hard consolidation of the recording sprawl — expressed as three rules:**

1. **One execution format: YAML routines run by `run_routine.py`.** It's the layer with loops,
   health checks, auto-restart, and await conditions. Retire ScenarioEngine *replay* as a
   parallel execution engine in Wave 6 (its recorder half stays, see rule 3) — two replay
   engines is the same disease as five widget-click tools.
2. **Agent drives anything novel; routines run anything repeated.** For the upcoming Tutorial
   Island acceptance test specifically: drive it agent-first, using the existing 01–10 routines
   as a *validated map* (widget IDs, pitfalls, order) rather than executing them blind. As each
   section passes, repair/refresh the routine so the artifact of the test is a working routine
   set. That converts test effort into durable automation instead of spending it twice.
3. **One authoring pipeline: play (or agent-run) → capture → `generate_routine` draft → human/
   agent edits in await conditions → validate.** `generate_routine` from location history is the
   keeper (it infers awaits and captures manual play); the COMMANDS-mode recorder is a
   reasonable Java-side source feeding the same funnel. Deprecate `session_to_routine` (naive)
   rather than improving it — don't maintain two converters.

Near-term repairs regardless of decision (small): fix the 3 dead commands in 4 routines
(rename to `CLICK_CONTINUE`/`CLICK_DIALOGUE`, re-add or substitute `EAT_FOOD`), and check the
old-laptop backup for `~/.osrs_scenarios/` recordings before assuming there's nothing to salvage.

## 5. Decision questions for you

1. Agree that YAML routines stay the single execution format and ScenarioEngine replay retires
   in Wave 6? (Its recorder can still feed routine drafts.)
2. Tutorial Island test: agent-first-with-routine-repair (my rec), or routines-first-with-agent-
   rescue? The latter is cheaper if the Jan routines mostly still work; riskier at the character
   creator where widgets differ.
3. Do you want the recording funnel wired up as part of Wave 6 (capture → generate_routine →
   validate as one command/tool), or parked until after the acceptance test?
4. Should I dig the old laptop backup on juno for your past recordings, or is nothing there
   worth keeping?
5. Grind economics: is token cost a real constraint for long grinds (favors routines hard), or
   is robustness worth paying agent-time for? This sets how much await-condition hardening the
   routine library deserves.
