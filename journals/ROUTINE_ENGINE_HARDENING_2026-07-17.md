# Routine Engine Hardening — conditions, failure signals, recovery

*2026-07-17. Design proposal, follow-up to `ROUTINE_STRATEGY_2026-07-17.md` (accepted: YAML
routines are the ONLY execution format). Written from a read-only audit of
`mcptools/tools/routine.py`, `run_routine.py`, `mcptools/tools/monitoring.py`,
`mcptools/tools/commands.py`, `manny_tools.py:validate_routine_deep`, and 8 routines across
categories. No code was changed. Every "exists today" claim below has a file:line cite.*

**Driving gap:** the old `EAT_FOOD` took an HP threshold; the new atomic `EAT`
(`manny_src/utility/commands/EatCommand.java:37-62`) unconditionally eats the best food.
`routines/combat/hill_giants_loot.yaml:70-79` now eats every loop iteration and says so in
its own notes. YAML has no way to express "do X only when HP < N", and the engine has no
per-step failure policy and no mid-run signal an LLM monitor can consume.

**Design stance (matches the philosophy doc):** routines stay linear command lists. We add
*guards* (skip a step) and *await atoms* (wait for a state), not branching, not expressions,
not a DSL. Anything needing real branching is either an inner/outer loop (already exists) or
a Java command's job (`KILL_LOOP` already stops at 50% HP per `manny_src/CLAUDE.md`). Combat
is explicitly not a priority; the EAT gate is sustain plumbing, not a combat system.

---

## 0. Audit: what the engine actually has today

Worth stating precisely, because half of what one might propose already exists.

**Condition checking exists TWICE, with different vocabularies:**

| | `monitoring.py:521-624` (`_parse_condition`/`_check_condition`) | `routine.py:1485-1545` (`check_stop_condition`) |
|---|---|---|
| Used by | `await_condition` on steps (via `send_and_await`, `await_state_change`) | loop `exit_conditions` / `stop_conditions` (via `_check_conditions`, routine.py:1302) |
| Atoms | `plane:N`, `has_item:`, `no_item:`, `inventory_count:<op>N`, `location:X,Y` (±3 tiles), `idle` | `inventory_full`, `has_item:`, `no_item:`, `no_item_in_bank:` (**stub — always False**, routine.py:1531-1534), `<skill>_level:N` (routine.py:1537-1543) |

So `attack_level:30` works as a loop exit but is a parse error as an `await_condition`, and
`inventory_full` vs `inventory_count:>=28` mean the same thing in different dialects. This is
the click-tool-sprawl pattern in miniature and is the first thing to fix.

**Failure/recovery machinery already present:**
- Crash detection via state-file staleness + auto-restart, 3 attempts, at outer-loop start
  and every 5 steps (routine.py:1138-1155, 1196-1215; `_auto_restart_client` routine.py:1604-1642).
- Await-condition steps automatically retry ONCE with 2x timeout (routine.py:1417-1428).
- `repeat: N` with await short-circuit (routine.py:1313-1348, just added).
- Inner-loop failure → restart iteration from `start_step`, capped at 3 consecutive failures,
  then exit via `on_exit: goto_step:` (routine.py:1170-1194).
- `send_and_await` pre-flight frozen-plugin detection (commands.py:375-397).
- Outside an inner loop, a failed step is **recorded and execution falls through to the next
  step** (routine.py:1167-1169, then 1245). That silent-continue default is why loot pickups
  work — and why a failed `GOTO` cheerfully proceeds to fish on the wrong island.

**State available for conditions** (all already written by the plugin, ~600ms cadence):
- `player.health.{current,max}` — `manny_src/utility/GameEngine.java:5468-5471`
- `combat.state` + `combat.threat.{name,level,distance}` — GameEngine.java:5558-5588
- `dialogue.{open,type,options}` — GameEngine.java:5503-5513
- `player.equipment`, `player.skills.{skill}.{level,xp}` — exposed via `get_game_state`
  field filters (monitoring.py:237-253)

So every condition proposed below is a **pure Python read of fields the state file already
has**. Zero Java work.

**Bugs/holes found during audit (fix alongside, cheap):**
1. `no_item_in_bank:` silently never fires (routine.py:1531-1534) — a routine relying on it
   loops forever.
2. `handle_send_and_await` writes the command file **raw** (commands.py:402-411), bypassing
   the rid-correlated `transport.send_command` that Wave 2 made canonical (compare
   `execute_simple_command`, routine.py:58-66). Every step with an `await_condition` loses
   rid correlation; the stale-response class of bug is still alive on that path.
3. `routines/quests/restless_ghost.yaml:154-160` uses `action: MCP_TOOL` + `tool:
   equip_item` — the executor only recognizes the `mcp_tool:` key (routine.py:1371-1374), so
   this step sends the literal game command `MCP_TOOL Ghostspeak amulet` and fails.
   `validate_routine_deep` would catch the unknown action, but nobody ran it.
4. `validate_routine_deep` (manny_tools.py:2492-2678) validates actions, GOTO args, and
   locations — but does **not** parse `await_condition` strings, `mcp_tool` steps, `repeat`,
   or `loop:` step references. Bad conditions fail at runtime, mid-grind.

---

## 1. Condition system

### 1a. One grammar, one evaluator

Merge the two dialects into a single module, e.g. `mcptools/conditions.py`, exposing
`parse(condition_str)` and `check(state, parsed)`. `monitoring._parse_condition`,
`monitoring._check_condition`, and `routine.check_stop_condition` become thin calls into it
(keep the old names as shims so nothing else moves). Loop exits, await conditions, and the
new guards all speak the same language; the validator imports the same parser.

### 1b. The full atom vocabulary (existing + new)

Existing, unchanged: `plane:N`, `has_item:Name`, `no_item:Name`, `inventory_count:<op>N`,
`location:X,Y`, `idle`, `inventory_full` (promoted from the loop dialect, defined as
`inventory_count:>=28`).

New atoms — each is ~5 lines in `check()`:

| Atom | Reads | Semantics |
|---|---|---|
| `hp:<N` (also `<=`, `>`, `>=`) | `player.health.current` | absolute HP compare |
| `hp_pct:<N` (same ops) | `player.health.current/max` | percentage compare |
| `skill:attack:>=30` | `player.skills.attack.level` | boosted level compare (subsumes the loop dialect's `attack_level:30`, which stays as an accepted alias) |
| `equipped:Ghostspeak amulet` / `not_equipped:...` | `player.equipment` | item worn (case-insensitive, same matching as `has_item`) |
| `dialogue_open` / `no_dialogue` | `dialogue.open` | dialogue widget up |
| `in_combat` / `not_in_combat` | `combat.state` | anything but the idle/none combat state |

Fix `no_item_in_bank:` while in there: either implement (bank contents ARE in state? they are
not — GameEngine doesn't export bank outside the bank-open snapshot) or make it a **parse
error** instead of a silent False. Recommend parse error + validator warning; a condition
that can't be evaluated should refuse to load, not refuse to fire.

That's the whole grammar. **Explicitly rejected:** `and`/`or`/`not` expressions, comparisons
between two state values, arithmetic, regex on chat. One string, one atom, one operator. If
a routine seems to need boolean algebra, it actually needs an inner loop, a second step with
its own guard, or a smarter Java command. (Escape valve if we're ever wrong: a YAML list
under a guard meaning AND — noted in Open Questions, not proposed now.)

### 1c. Step guards: `only_if` / `skip_if`

New optional step keys, taking exactly one condition string:

```yaml
# The EAT threshold case — hill_giants_loot.yaml step 7 becomes:
- id: 7
  phase: "sustain"
  action: EAT
  only_if: "hp_pct:<50"          # skip entirely when healthy
  description: "Eat when below half HP"
```

```yaml
# "await HP recovered": eat repeatedly until recovered, using existing repeat short-circuit
- id: 7b
  action: EAT
  only_if: "hp_pct:<50"
  repeat: 5                       # existing semantics, routine.py:1339-1343
  await_condition: "hp_pct:>=70"  # short-circuits remaining repeats once recovered
  delay_after_ms: 1800
```

```yaml
# Other repaired-routine cases fall out for free:
- id: 9                           # restless_ghost — don't re-equip if already worn
  mcp_tool: equip_item
  args: {item_name: "Ghostspeak amulet"}
  skip_if: "equipped:Ghostspeak amulet"

- id: 4                           # dialogue steps — skip when no dialogue is up
  action: CLICK_CONTINUE
  repeat: 5
  skip_if: "no_dialogue"
```

Semantics (small and exact):
- `skip_if: C` — evaluate C once against the current state file, *before* `delay_before_ms`;
  if true, do not execute; result is `{success: true, skipped: true, skip_reason: C}`.
- `only_if: C` — sugar for skip-unless; identical machinery, reads better for the EAT case.
- Both present: error at validation time (ambiguous, refuse).
- With `repeat: N`: guard is re-evaluated before **each** iteration (so `EAT only_if
  hp_pct:<50 repeat:3` stops eating mid-repeat once recovered — this is the natural reading
  and costs nothing since we already loop in `_execute_single_step`).
- A skipped step counts as success for inner-loop failure accounting (it is not a failure).

Implementation sketch (no code here, just location):
- `mcptools/tools/routine.py:_execute_single_step` (line 1313): resolve
  `skip_if`/`only_if` (with `interpolate_variables`, same as `await_condition` at 1363-1365),
  read state via existing `get_game_state()` (routine.py:1548), call `conditions.check`,
  return the skipped result or fall through. Guard re-check goes inside the existing
  repeat loop (1339-1343).
- `manny_tools.py:validate_routine_deep`: parse every `await_condition`, `skip_if`,
  `only_if`, and loop `exit_conditions` with `conditions.parse`; error on failure; error on
  both guards present; also validate `mcp_tool` steps and the known-broken `action: MCP_TOOL`
  shape (audit finding 3).

---

## 2. Failure detection an LLM monitor can react to

Today the runner is a black box while running: `results` accumulates in memory and
`run_routine.py:100-134` prints once at exit. A monitoring agent's only live signals are the
state file and `get_logs`. Per CLAUDE.md the monitor's contract is "poll every 30-60s,
intervene if idle >60s / 3+ errors / stuck" — but nothing tells it the error count or which
step it's on.

### 2a. Structured run events (JSONL) + status snapshot

Two files, matching the repo's existing file-based IPC idiom (state file, command file,
`/tmp/manny_sessions/` command log — session.py already does daily YAML logs):

1. **Event stream** `logs/routines/<run_id>.jsonl` — the runner appends one line per
   step result and per loop transition. A step event is essentially the `step_result` dict
   that `_execute_single_step` already builds (routine.py:1379-1384 has step_id, action,
   command; plus success/elapsed_ms/attempts/await_result/error) plus `{ts, run_id,
   routine, outer_loop, inner_loop, skipped}` and a 5-field state stamp (hp, hp_max,
   inventory_used, x, y — all one state-file read we're already doing for guards). Loop
   events record `inner_exit`, `outer_exit`, `auto_restart`, `crash_detected`.
2. **Status snapshot** `/tmp/manny_routine_status_<account>.json` — atomically rewritten
   after every step: current step id/action, loop counters, consecutive-failure counters,
   last 3 errors, run start time, event-file path. One read = whole picture; this is what a
   polling monitor actually wants (tailing JSONL is for post-mortems and dashboards —
   `dashboard.py` can consume it later).

Emission points: end of `_execute_single_step` (one place catches every step, including
repeats), the inner/outer loop bookkeeping blocks (routine.py:1218-1263), and the
crash/restart branches (1141-1155, 1200-1215). Plus a tiny `get_routine_status` MCP tool in
monitoring.py that reads the snapshot file — that's the "missing get_game_state hook"; the
game-state side needs nothing new (health/combat/dialogue already filterable,
monitoring.py:243-253).

### 2b. Stuck heuristics beyond idle-timeout

Cheap and high-value, in priority order:

1. **Per-step consecutive-failure counter, global.** The 3-strikes rule exists only inside
   inner loops (routine.py:1174-1194). Track `fail_count[step_id]` everywhere; at 3, emit a
   `stuck` event with the step and last error. Don't auto-abort by default (see §3) — the
   point is the monitor gets a signal it can act on.
2. **Progress delta per outer loop.** `run_routine.py:54-91` already computes XP gains, but
   only start-vs-end. Move the sample into the outer-loop boundary: if a full outer
   iteration of a `type: skilling` routine produced zero XP delta and zero inventory delta,
   emit `no_progress`. This catches the classic "fishing spot moved, FISH is clicking
   nothing" failure that per-step success never sees.
3. **Loop-iteration duration anomaly.** Record per-outer-loop elapsed; if an iteration takes
   >3x the median of previous iterations, emit `slow_loop`. (Catches contention/world-hop
   degradation, e.g. the coal-competition case documented in
   `routines/skilling/superheat_steel_bars.yaml:314-317`.)

Explicitly not proposing: chat-message scraping heuristics, screenshot diffing, or a
watchdog process. The monitor is an LLM; give it clean events and let it decide.

### 2c. Transport honesty (bug fix, not feature)

Route `handle_send_and_await`'s send through `transport.send_command`
(commands.py:402-411 → the pattern in routine.py:58-66). Until then, "step failed" on an
await step can mean "response correlation raced", which poisons every failure count above.
This should land before or with the event stream.

---

## 3. Recovery primitives: `on_fail`

What exists already (§0) covers crashes (auto-restart), transients (await retry once,
`repeat`), and inner-loop hiccups (restart-iteration + 3-strikes). The missing piece is a
**per-step policy** for the fall-through default at routine.py:1167-1169. Proposal — one
key, four verbs, no nesting:

```yaml
on_fail: continue        # today's behavior, now explicit (loot pickups, optional steps)
on_fail: retry:3         # rerun this step up to 3 times before applying the default
on_fail: goto:11         # jump to step id (reuses _resolve_step_idx, routine.py:1290)
on_fail: abort:"out of position - needs human/agent"   # stop routine, reason in results+events
```

- Default when absent: `continue` (unchanged behavior, zero migration).
- `retry:N` is distinct from `repeat:N`: repeat is "do it N times as part of the plan";
  retry is "it failed, try again". Retry exhausted → falls back to `continue` unless
  combined form `retry:3,abort` (the only allowed combination — a verb after the retry).
- `goto:` enables the pattern the inner-loop `on_exit` already uses (routine.py:1186-1191),
  e.g. "GOTO failed → jump back to the bank phase".
- `abort:` sets `success: false`, `stop_reason`, emits a final event; `run_routine.py`
  already exits non-zero on failure (run_routine.py:162), so a driving agent notices.

**Evaluated and deferred: `run:<sub-routine>`.** It's the tempting one (death →
`utility/death_escape.yaml`) but it drags in recursion limits, loop-state save/restore,
account plumbing, and event-stream nesting — a multi-day feature with one known use case.
The same need is served today by `abort:"died - run death_escape"` + the monitoring LLM
launching `run_routine.py routines/utility/death_escape.yaml` — which is exactly the
philosophy: the LLM driver runs and monitors routines; rare orchestration belongs to it,
not to a YAML interpreter growing a call stack.

Implementation: a small wrapper around the `_execute_single_step` call site in
`handle_execute_routine` (routine.py:1163-1169) — evaluate policy, loop for retry, mutate
`current_step_idx` for goto, return early for abort. Validator checks the verb grammar and
that `goto:` targets exist.

---

## 4. Cost/complexity ranking and first slice

| Piece | Where | Size |
|---|---|---|
| A. `conditions.py` consolidation + new atoms (hp, hp_pct, skill, equipped, dialogue, combat) + `no_item_in_bank` parse error | new module + 3 shim call sites | one afternoon |
| B. `skip_if`/`only_if` in `_execute_single_step` + repeat interaction | routine.py | half a day (rides on A) |
| C. Validator: parse all condition strings, guard conflicts, `mcp_tool`/`MCP_TOOL` shape, `on_fail` grammar, loop step refs | manny_tools.py | half a day |
| D. Event JSONL + status snapshot + `get_routine_status` tool | routine.py emission points + monitoring.py | one afternoon |
| E. `on_fail` continue/retry/goto/abort | routine.py step loop | half a day |
| F. send_and_await → transport (bug fix) | commands.py | 1-2 hours, but touches every await step — needs a live-client verify pass |
| G. Stuck heuristics 2-3 (progress delta, duration anomaly) | routine.py loop boundaries | one day |
| H. `run:` sub-routines, composite conditions | — | multi-day, **deferred** |

**Recommended first slice: A + B + C** (roughly one focused day). It directly repairs the
four flagged routines (hill_giants_loot EAT gate; restless_ghost/sheep_shearer/imp_catcher
dialogue guards + the MCP_TOOL step), kills the two-dialect sprawl, and makes bad routines
fail at validation instead of at 3am mid-grind. **Second slice: D + F** — the monitor
contract in CLAUDE.md becomes actually satisfiable, on honest transport. E and G follow on
demand; nothing in the library blocks on them today.

---

## 5. Open questions for you

1. **hp vs hp_pct default for the EAT gate.** The old EAT_FOOD threshold was absolute
   ("below 25"); `hill_giants.yaml:23` / `cow_killer_no_bones.yaml:14` carry (currently
   unread) `threshold_percent` config keys. I'd standardize routines on `hp_pct` — portable
   across accounts/levels. OK to treat those stale config keys as dead and delete them
   during repair?
2. **Guard lists.** If a step ever genuinely needs two conditions, is a YAML list under
   `only_if` meaning AND acceptable as the one extension — or do you want a hard "one
   condition per guard, forever" rule so nobody ever writes boolean YAML?
3. **3-strikes global default.** With the per-step failure counter (§2b), should 3
   consecutive failures of the *same step* outside inner loops auto-abort (safer for
   unattended overnight runs) or only emit `stuck` and continue (today's behavior, monitor
   decides)? I lean auto-abort with `on_fail: continue` as the per-step opt-out.
4. **Event retention.** `logs/routines/<run_id>.jsonl` accumulates; is a "keep last 50 runs"
   cleanup in run_routine.py enough, or do you want events under `/tmp` (lost on reboot,
   zero maintenance)?
5. **Java-side thresholds.** `HealthBelowCondition` already exists in the ScenarioEngine-era
   condition framework (`PlayerHelpers.java:8360-8415`) and `KILL_LOOP` has its own 50%-HP
   stop. This proposal puts all *routine-level* conditions in Python and leaves Java
   commands' internal logic alone. Confirm you don't want an `EAT <threshold>` arg re-added
   Java-side instead — it would solve only the EAT case, add a second condition location,
   and conflict with the Wave 6 plan to gut the ScenarioEngine layer.
6. **Fix-now bug list.** Findings §0.1-0.3 (dead `no_item_in_bank`, raw-write
   send_and_await, restless_ghost MCP_TOOL step) are independent of this design — want them
   ticketed/fixed ahead of the first slice?
