# Routine YAML Schema (Authoritative)

This is the single source of truth for the `steps:`/`loop:`-based routine YAML
format executed by `./run_routine.py` (which calls
`mcptools/tools/routine.py:handle_execute_routine`). If you are an LLM authoring
a routine, read this document fully before writing YAML — do not infer the
schema from example files alone, because several example files contain keys
that parse cleanly but are **silently ignored by the engine** (see section (f)).

Every claim below cites the exact source line(s) that back it, in the engine
(`mcptools/tools/routine.py`, `mcptools/tools/monitoring.py`) or the plugin
(`manny_src/utility/commands/*.java`, symlinked to
`/home/wil/Desktop/manny/utility/commands/`). Re-verify line numbers with
`grep -n` if this file drifts from the code — the doc is a snapshot, the
source is truth.

**Out of scope:** `execute_combat_routine` (`mcptools/tools/commands.py:585-710`)
is a *completely different* YAML dialect (`npc:`, `kills:`, `loot:`, `eating:`,
no `steps:` at all) consumed by a separate MCP tool, not by
`run_routine.py`/`handle_execute_routine`. If you see `loot:`/`eating:`/
`threshold_percent:` used validly somewhere, it's in that other dialect — see
section (f) for why those same keys are dead in *this* schema.

---

## (a) File anatomy — top-level keys

The engine only ever reads these top-level keys from the parsed YAML dict
(`mcptools/tools/routine.py:1088-1093`, plus the `name` read at line 1120):

| Key | Read by engine? | Purpose |
|---|---|---|
| `name` | Yes (routine.py:1120, display only) | Shown in results as `routine_name` |
| `type` | **No** | Documentation only (e.g. `quest`, `skilling`, `combat`) |
| `description` | **No** | Documentation only |
| `skill` | **No** | Documentation only |
| `config:` | Yes (routine.py:1093) | Variables for `${var}` / `${var\|underscore}` interpolation — see below |
| `locations:` | **No** | Documentation only. Steps reference coordinates directly in `args`, not by `locations:` key lookup |
| `requirements:` | **No** | Documentation only |
| `npcs:` / `widgets:` | **No** | Documentation only |
| `steps:` | Yes (routine.py:1091) | **Required.** A list of step dicts (see (b)). Missing this key → `{"success": False, "error": "Routine has no steps"}` (routine.py:1088-1089) |
| `loop:` | Yes (routine.py:1092) | Flat or nested loop config — see (d) |

`config:` values are substituted into step `args` and `await_condition`
strings via `interpolate_variables()` (routine.py:1028-1067):
- `${variable}` → direct substitution
- `${variable|underscore}` → substitution with spaces replaced by `_`
  (useful for command args that require underscores, e.g. object names)
- Unresolved variables (not present in `config:`) are left as literal
  `${...}` text (routine.py:1052-1054) — no error is raised, so a typo in a
  variable name silently ships a broken command string.

`locations:`, `requirements:`, `npcs:`, `widgets:` are **never read** by
`handle_execute_routine` — confirmed by grepping every `routine.get(...)` /
`routine[...]` access in routine.py (only `steps`, `loop`, `config`, `name`
appear, routine.py:1091-1120). Put coordinates in `args` on the step itself.

---

## (b) Step reference

A step is one entry in the `steps:` list. Fields read by the engine
(confirmed via every `step.get(...)` call across routine.py):

| Field | Type | Read at | Semantics |
|---|---|---|---|
| `id` | int or string | routine.py:1098, 1178, 1446, 1517 | Step identifier. Supports non-sequential/string IDs like `"6b"` for `goto_step:`/`start_step`/`end_step` targeting (`_resolve_step_idx`, routine.py:1326-1335). Defaults to list index+1 if omitted. |
| `phase` | string | routine.py:1473, 1545, 1621 | Carried into step results only; not used for control flow. |
| `action` | string | routine.py:1518 | A plugin command name (e.g. `GOTO`, `MINE_ORE`). Mutually exclusive with `mcp_tool` in practice — if both present, `action` wins (routine.py:1541 builds `command` from `action`; `mcp_tool` dispatch happens first at 1536-1538 and returns early, so `mcp_tool` actually wins if both are set). |
| `mcp_tool` | string | routine.py:1536, 1610 | Dispatches to an MCP tool handler instead of a plugin command — see (g) for the whitelist. |
| `args` | string (for `action`) or dict (for `mcp_tool`) | routine.py:1523, 1613 | For `action`: appended to the command as `"{action} {args}"` (routine.py:1541). For `mcp_tool`: passed as kwargs — **must be a dict**, a bare string silently becomes `{}` (routine.py:1614-1615, see (g)). |
| `await_condition` | string | routine.py:1377, 1527 | One of the **step-level condition atoms** — see (c). Interpolated via `config:` first (routine.py:1528-1529). |
| `timeout_ms` | int | routine.py:1520 | Per-attempt timeout for the command/await. **Default 30000 (30s)** if omitted. This is the number that blocking commands blow through — see (e). |
| `delay_before_ms` | int | routine.py:1519, 1532-1533 | `asyncio.sleep()` before sending the command. |
| `delay_after_ms` | int | routine.py:1603-1605 | `asyncio.sleep()` after the command completes. Note the `_ms` suffix is required — see (f). |
| `repeat` | int | routine.py:1373 | Blind fixed-count repeat of the step's action (min 1). If `await_condition` is also set, a successful check short-circuits remaining repeats (routine.py:1382-1384). |
| `repeat_until` | string | routine.py:1369, 1447 | A **step-level condition atom** (same vocabulary as `await_condition`, parsed via `monitoring._parse_condition`). Runs the action in a `while not satisfied` loop — check-first semantics, so if already satisfied the action runs zero times (routine.py:1428-1442). Mutually exclusive with `repeat`/`await_condition` handling — routed to `_execute_repeat_until` before the normal repeat/await path even looks at the step (routine.py:1369-1370). |
| `max_iterations` | int | routine.py:1459-1462 | **Only meaningful together with `repeat_until`.** Safety cap on `repeat_until` iterations. Default 25 (`DEFAULT_REPEAT_UNTIL_MAX_ITERATIONS`, routine.py:1397). Overridable per-step or via `config.repeat_until_max_iterations`. **This is a different key from `loop.max_iterations`, which is dead — see (d) and (f).** |
| `repeat_until_timeout_ms` | int | routine.py:1463-1466 | Per-iteration wait for the predicate to become true after acting, for `repeat_until`. Default 2000ms (routine.py:1398). |
| `poll_interval_ms` | int | routine.py:1467-1469 | Poll interval while waiting on `repeat_until`'s predicate. Default 250ms (routine.py:1399). |

**Documentation-only step fields** (never read by the engine, but harmless —
include them for humans/future maintainers): `description`, `notes`.

**A genuinely dead step field not previously documented:** `location:` — some
routines (e.g. `routines/combat/chicken_killer_loop.yaml:26`) set a
per-step `location: some_key` pointing at a top-level `locations:` entry.
This is **never read** by `_execute_step_once` or anywhere else in
routine.py (confirmed: `location` does not appear in the `step.get(...)`
list above). The step still works correctly because the actual coordinates
live in `args`, but the `location:` key itself does nothing — see (f).

---

## ⚠️ (c) THE TWO CONDITION VOCABULARIES — READ THIS BEFORE WRITING ANY CONDITION

There are **two entirely disjoint condition grammars** in this codebase, and
nothing else documents that they don't overlap. Using one grammar's atom in
the other's slot fails, sometimes silently.

> **Grammar 1 — step-level `await_condition` / `repeat_until`.**
> Parsed by `monitoring._parse_condition()` (`mcptools/tools/monitoring.py:521-546`),
> checked by `monitoring._check_condition()` (`monitoring.py:576-642`).
>
> | Atom | Example | Semantics (monitoring.py) |
> |---|---|---|
> | `plane:N` | `plane:2` | `player.location.plane == N` (line 552-553, 582-585) |
> | `has_item:X` | `has_item:Pot of flour` | item `X` present in inventory, case-insensitive (554-555, 587-594) |
> | `no_item:X` | `no_item:Grain` | item `X` absent from inventory (556-557, 596-603) |
> | `inventory_count:<op>N` | `inventory_count:<=5` | slot count vs `N`; ops `<=`, `>=`, `<`, `>`, or bare `==` (558-568, 605-619) |
> | `location:X,Y` | `location:3208,3216` | within 3 tiles of `(X,Y)`, Chebyshev distance (569-571, 621-627) |
> | `idle` | `idle` | `not player.isMoving` (535-536, 629-632) |
> | `dialogue` / `no_dialogue` | `dialogue` | top-level `dialogue.open` is True/False (542-545, 634-640) — **NARROW, tutorial-only**, reads a different state-file key (`dialogue`, not `player.dialogue`) |
>
> Any other string raises `ValueError: Unknown condition type` (monitoring.py:573)
> or `Invalid condition format` (546) — for `repeat_until` this is caught and
> surfaces as a step failure (`Invalid repeat_until condition: ...`,
> routine.py:1483-1487); for `await_condition` it propagates from
> `_handle_send_and_await`/`_handle_await_state_change`.
>
> **Grammar 2 — loop `stop_conditions:` (flat) / `exit_conditions:` (inner/outer).**
> Checked by `routine.check_stop_condition()` (`routine.py:1654-1731`), called
> from `_check_conditions()` (routine.py:1338-1346, used by inner/outer
> `exit_conditions`) and directly from the flat-loop path (routine.py:1310-1317).
>
> | Atom | Example | Semantics (routine.py) |
> |---|---|---|
> | `inventory_full` | `inventory_full` | `used >= 28` slots (1661-1669) |
> | `has_item:X` | `has_item:Coins` | inverse of `no_item:X` (1695-1698) |
> | `no_item:X` | `no_item:Raw lobster` | item `X` absent, own implementation (NOT the monitoring.py one) (1672-1692) |
> | `<skill>_level:N` | `mining_level:60` | `skills[skill].level >= N` — note the `_level:` suffix pattern, not a `skill:` prefix (1723-1729) |
> | `no_item_in_bank:X` | `no_item_in_bank:Coal` | **raises `NotImplementedError`** — bank contents aren't in the state snapshot; this deliberately fails loudly rather than silently returning `False` forever (1700-1720) |
>
> Anything else falls through to `return False` at the end of
> `check_stop_condition` (routine.py:1731) — i.e. an unrecognized loop
> condition just **never triggers**, with no error. This is more dangerous
> than Grammar 1's `ValueError` because a typo here fails silently and the
> loop just runs to its iteration cap (if any — see (d)) instead of stopping.
>
> **The overlap is a trap, not a convenience.** `has_item:X`/`no_item:X`
> exist in *both* grammars with the same string syntax but *different,
> independently-maintained implementations* reading slightly different
> inventory shapes. `plane:N`/`inventory_count:N`/`location:X,Y`/`idle`/
> `dialogue` exist **only** in Grammar 1 and will silently no-op if used in
> `stop_conditions:`/`exit_conditions:`. `inventory_full`/`<skill>_level:N`/
> `no_item_in_bank:X` exist **only** in Grammar 2 and will raise
> `ValueError` if used in `await_condition:`.
>
> **Rule of thumb:** step-level fields (`await_condition`, `repeat_until`) →
> Grammar 1. Loop-level fields (`stop_conditions`, `exit_conditions`) →
> Grammar 2. Never mix.

---

## (d) Loop schemas — flat vs. nested, and the missing iteration cap

`loop:` supports **two mutually-exclusive shapes**. Mixing them silently
no-ops the one that loses.

### Flat loop (backwards-compatible form)

```yaml
loop:
  enabled: true
  repeat_from_step: 1        # step id/index to jump back to
  stop_conditions:           # Grammar 2 atoms (see (c)), ANY match stops the loop
    - "inventory_full"
```

Parsed at routine.py:1106-1107 (`loop_config.get('enabled', False)`,
`loop_config.get('repeat_from_step', 1)`); driven at routine.py:1301-1319.
On completing all steps once, if `flat_loop_enabled`, the engine jumps back
to `repeat_from_step` and re-runs, checking `stop_conditions` (via
`check_stop_condition`, Grammar 2) after each full pass.

**⚠️ NO ITERATION CAP.** The flat-loop branch (routine.py:1301-1319) never
reads a `loop.max_iterations` key — the only bound on `outer_count` is the
`max_loops` parameter passed into `handle_execute_routine` from outside
(default 10000, routine.py:1076; `run_routine.py`'s `--loops` CLI flag sets
this, `run_routine.py:307`). **If you write `loop.max_iterations: 50` inside
the YAML expecting it to cap the loop at 50 passes, it does nothing — the
real cap is `run_routine.py --loops N` on the command line.** See (f).

Also note: `start_step` (not `repeat_from_step`) is used by several existing
routines under a flat `loop:` block (e.g.
`routines/skilling/fishing_karamja_harpoon.yaml:51-54`) — this is **also
dead** for flat loops; only `repeat_from_step` is read (routine.py:1107).
It happens to be harmless in those files only because they all want
`start_step: 1`, which matches the default anyway.

### Nested inner/outer loop

```yaml
loop:
  inner:
    enabled: true
    start_step: 9             # step id to jump back to while inner loop continues
    end_step: 10               # step id whose completion triggers the exit check
    exit_conditions:           # Grammar 2 atoms, ANY match exits the inner loop
      - "inventory_full"
    on_exit: "goto_step:11"    # where to jump when the inner loop exits
  outer:
    enabled: true
    start_step: 1
    end_step: 13
    exit_conditions: []        # empty = never exits on condition (runs to max_loops)
```

Real example: `routines/skilling/superheat_mining_guild.yaml:203-229` (mine +
superheat until inventory full, banking loop wraps around it).

Parsed at routine.py:1102-1116; driven at routine.py:1254-1299. `has_inner_outer`
(routine.py:1110) is true if *either* `inner.enabled` or `outer.enabled` is
true. When the engine reaches the step whose `id` matches `inner.end_step`,
it checks `inner.exit_conditions` (Grammar 2, via `_check_conditions`); if
none match, it jumps back to `inner.start_step` (routine.py:1274-1279); if one
matches, it jumps to the `goto_step:` target in `on_exit` (routine.py:1266-1272).
The outer loop works the same way at the very end of the step list.

**Inner-loop step failures don't just propagate** — 3 consecutive failures
inside the `inner.start_step..end_step` range restart the inner loop from
`start_step` (routine.py:1189-1212); after `max_inner_consecutive_failures`
(hardcoded 3, routine.py:1136), it exits via `on_exit` instead of retrying
forever (routine.py:1198-1209).

**Exclusivity note:** if both a flat `loop.enabled: true` block *and* an
`inner`/`outer` block with `enabled: true` are present in the same YAML,
`has_inner_outer` wins (checked first, routine.py:1284, before the
`elif flat_loop_enabled:` branch at 1301) — the flat block's
`repeat_from_step`/`stop_conditions` are silently never consulted. Pick one
shape per routine.

---

## (e) Blocking-command table — timeout_ms and await_condition guidance

**The default step timeout is 30000ms (30s)** (`step.get('timeout_ms', 30000)`,
routine.py:1520). Several plugin commands run **synchronously inside the
plugin's command handler** for minutes and only write a response at the very
end — if your step's `timeout_ms` is smaller than the command's real runtime,
`run_routine.py` gives up waiting and reports a step timeout/failure *while
the client is still executing the command unsupervised*. Separately, `idle`
as an `await_condition` on any of these **fires almost instantly** (before
the blocking command's internal loop has done anything, because the player
was already idle the moment the command was sent and `isMoving` doesn't
reflect "a Java command is running") — never pair a blocking command with
`await_condition: idle`.

| Command | Source | Blocks until | Typical real duration | `timeout_ms` guidance | `await_condition`? |
|---|---|---|---|---|---|
| `KILL_LOOP <npc> <food\|none> [max_kills]` | `KillLoopCommand.java` executeCommand loop, 165-763 | `max_kills` kills (default 100, line 97), HP safety stop, or interrupt | Highly variable — each kill involves NPC search/LOS/attack (up to 60s attack timeout per attempt, line 474) + ~1-3s of fixed post-kill delays (loot/bury/cook sleeps, lines 610-762). A 100-kill default run realistically spans **many minutes to over an hour**. | Set generously, e.g. `3600000` (1hr) as already done in `routines/combat/chicken_killer_loop.yaml:34` for a 100-kill batch. Never rely on the 30s default. | **No.** Let the runner block on the plugin's own response. |
| `KILL_LOOP_CONFIG <json_path>` | `KillLoopConfigCommand.java:98-102` delegates to `KillLoopCommand` with food forced to `"none"` | Same as `KILL_LOOP` above, but food management is **always disabled** (line 101: `config.npc + " none " + config.kills`) → HP safety-stop threshold is 50%, not the food-managed 30% floor (KillLoopCommand.java:239-250 vs 228-237) | Same order of magnitude as `KILL_LOOP` | Same as `KILL_LOOP` | No |
| `MINE_ORE <ore> [count]` | `MineOreCommand.java` loop, 172-324 | inventory full or `count` reached | Per-ore poll up to 5s (line 283), plus rock-search/camera-scan retries (2-5s backoff, lines 215-230); a full-inventory run (~27 ores) is commonly **several minutes**. | ≥ `300000` (5 min) for a full-inventory run; scale with expected ore count. | No |
| `CHOP_TREE <tree>` | `ChopTreeCommand.java` loop, 70-151 | inventory full | Per-tree wait capped at 60s (`maxWait = 60000`, line 126); a full-inventory run is commonly **several minutes to 10+ minutes** depending on tree respawn/competition. | ≥ `600000` (10 min) | No |
| `FISH <fish>` | `FishCommand.java` loop, 97-169 | inventory full | Per-spot session capped at 60s (`maxWait = 60000`, line 125); full-inventory run commonly **several minutes**. | ≥ `300000`-`600000` | No |
| `FISH_DROP <fish>` | Same family as `FISH`/`POWER_MINE`/`POWER_CHOP` (drop instead of bank) | Effectively unbounded (drops instead of stopping at full inventory) | **Unbounded** — designed to run indefinitely for XP training | Very large, or rely on the plugin's own `KILL_LOOP`-style interrupt instead of a step timeout | No |
| `FISH_DRAYNOR_LOOP <target_level>` | `FishDraynorLoopCommand.java:113` — literal `while (true)` | target skill level reached, or interrupt | **Unbounded by design** — no internal iteration/time cap at all | Do not use a per-step `timeout_ms` to bound this; it will always "time out" before finishing unless set absurdly high. Prefer running it via a dedicated background invocation and polling `get_game_state`, not as one routine step. | No |
| `COOK_ALL <raw_food>` | `CookAllCommand.java` loop, 556-581 | all of `raw_food` cooked, or timeout | Capped by the command itself: `maxWaitTime = initialCount * 2000L` ms (line 560) — e.g. 28 raw fish → up to 56s internal cap. | Set `timeout_ms` comfortably above `initialCount * 2000 + setup overhead`, e.g. `90000` for a full inventory. | No |
| `SMELT_BAR <bar> <cycles> [oreCount]` / `SMELT_BRONZE_BARS <cycles> ...` | `SmeltBarsCommand.java` loop, 194-373 | `cycles` completed | Each cycle: ~7-8s of fixed banking/smelting sleeps (lines 262-369) plus animation time not captured in `Thread.sleep` alone — multi-cycle runs (`cycles` > 1) commonly run **minutes**. | Scale with `cycles`, e.g. `cycles * 30000` as a floor. | No |

**General rule:** any command whose Java implementation contains its own
internal `while`/`for` loop with `Thread.sleep` calls (i.e. anything in
`manny_src/utility/commands/` implementing a "do this repeatedly until X"
verb — `MINE_ORE`, `CHOP_TREE`, `FISH*`, `COOK_ALL`, `SMELT_*`, `KILL_LOOP*`,
`POWER_MINE`, `POWER_CHOP`) is a **blocking command**: give it a large
`timeout_ms` and never an `await_condition` (especially not `idle`). Commands
that just fire one client-thread action and return immediately (`GOTO`,
`INTERACT_OBJECT`, `INTERACT_NPC`, `CLICK_DIALOGUE`, `BANK_*`, `PICK_UP_ITEM`,
...) are the ones `await_condition` (Grammar 1, section (c)) is for.

---

## (f) Dead-key blacklist — these parse clean and do NOTHING

All of the following are valid YAML, load without error, and are silently
ignored by `handle_execute_routine`. Confirmed by grepping every
`step.get(...)` / `loop_config.get(...)` / `routine.get(...)` call in
`mcptools/tools/routine.py` — none of these strings appear as a dict-get key
anywhere in the execution path.

| Dead key | Where it's tempting to use it | Why it's dead | Seen in real routines? |
|---|---|---|---|
| `loop.max_iterations` | Top-level `loop:` block, to cap a flat loop | Flat-loop branch only reads `enabled` and `repeat_from_step` (routine.py:1106-1107); no `max_iterations` read anywhere in the flat-loop path (1301-1319). The real cap is `run_routine.py --loops N` (default `max_loops=10000`, routine.py:1076). | Yes — `routines/combat/chicken_killer_loop.yaml:47`, `routines/combat/hill_giants_loot.yaml:21`, `routines/skilling/fishing_karamja_harpoon.yaml:53`, `routines/skilling/fishing_karamja_lobster.yaml:50` all set this expecting it to cap loop count. It does not. |
| `loop.start_step` (flat form) | Alternative spelling of where to resume the loop | Only `repeat_from_step` is read for flat loops (routine.py:1107). `start_step` is only meaningful inside `inner:`/`outer:` blocks (routine.py:1115-1116, 1298). | Yes — same four files above set `start_step: 1` under a flat `loop:`; harmless only because the (also-unused) default happens to equal 1. |
| `loop.delay_between_loops_ms` | Pace flat-loop iterations | Never read anywhere in routine.py. No delay is applied between flat-loop passes at all. | Yes — `routines/combat/chicken_killer_loop.yaml:48`. |
| `skip_if` (step-level) | Conditionally skip a step | Not read by `_execute_step_once`/`_execute_single_step`. | Referenced only in generator prose (`mcptools/tools/routine_generator.py:425,539`), not implemented in the executor. |
| `delay_after` (step-level, no `_ms` suffix) | Delay after a step | Only `delay_after_ms` is read (routine.py:1603). A bare `delay_after:` is a silent no-op typo. | Not currently present in `routines/`, but a plausible authoring mistake given `delay_before_ms`/`delay_after_ms` naming. |
| `location:` (step-level) | Point a step at a named `locations:` entry | Never read — see (b). Coordinates must live in `args` directly. | Yes — `routines/combat/chicken_killer_loop.yaml:26`. |
| `threshold_percent`, `eating:`, `loot:` blocks | Combat food/loot tuning, by analogy with `execute_combat_routine`'s YAML | **This schema's engine (`handle_execute_routine`) never reads `routine.get('loot')`/`routine.get('eating')` — only `steps`, `loop`, `config`, `name` are read (routine.py:1091-1120).** These keys are real and functional, but only in the *separate* `execute_combat_routine` MCP tool's YAML dialect (`mcptools/tools/commands.py:659-676`), which is not what `run_routine.py` executes. In a `steps:`-based routine they are inert. | Yes — `routines/combat/cow_killer_no_bones.yaml` and `routines/combat/hill_giants.yaml` use exactly this shape, which is also *why* both files have no `steps:` key and are non-runnable stubs (see ROUTINE_CATALOG.md) — deleted as part of this cleanup. |
| `no_item_in_bank:X` (as a Grammar 1 `await_condition`) | "wait until the bank has no more X" | It's a Grammar 2 atom (loop conditions only) and even there it deliberately `raise`s `NotImplementedError` rather than silently no-op (routine.py:1700-1720) — bank contents aren't in the state snapshot. Not usable in either grammar today. | No current routine uses it. |

**Correction to a prior claim:** the earlier audit asserted one existing
routine uses a bare `mcp_tool: key` shorthand that isn't wired up. Grepping
every `mcp_tool:` occurrence under `routines/` today
(`grep -rn "mcp_tool:" routines/`) turns up only `equip_item` and
`click_widget` — both of which **are** wired (see (g)). Either this was
already fixed by a prior cleanup pass, or the audit reference was imprecise;
no reproduction found as of this writing.

---

## (g) `mcp_tool:` whitelist and the dict-args rule

`mcp_tool` steps are dispatched by `_execute_mcp_tool_step`
(routine.py:1610-1651), **not** the plugin command path. Only these values
are recognized at runtime:

| `mcp_tool` value | Dispatches to | routine.py line |
|---|---|---|
| `equip_item` | `_handle_equip_item` | 1627-1628 |
| `click_widget` | `handle_click_widget` | 1629-1631 |
| `find_and_click_widget` | `handle_click_widget` (legacy alias — same handler as `click_widget`) | 1629-1631 |
| `click_text` | `handle_click_text` → `handle_click_widget(dialogue_option=...)` | 1632-1636 |

Anything else → `{"success": False, "error": f"Unknown mcp_tool: {mcp_tool}"}`
(routine.py:1637-1640).

**⚠️ Validator/engine mismatch — a genuine discrepancy, not a doc error.**
`validate_routine_deep` (`manny_tools.py:2557`, `_KNOWN_MCP_TOOLS` at line
2495) only recognizes **three** of these four:
`{"equip_item", "click_widget", "find_and_click_widget"}` — it does **not**
include `click_text`. A routine using `mcp_tool: click_text` would run
correctly at execution time but be falsely flagged as
`"Unknown mcp_tool 'click_text'"` by the validator. If you hit this, trust
the runtime whitelist above (routine.py:1610-1651), not the validator's
error — or fix `manny_tools.py:2495` (out of scope for this document; owned
by the Python-code track).

**`args` for `mcp_tool` steps must be a dict**, not a string:

```python
# routine.py:1613-1615
mcp_args = step.get('args', {})
if isinstance(mcp_args, str):
    mcp_args = {}   # bare string silently becomes an empty dict!
```

```yaml
# WRONG — args is a bare string, silently becomes {} at runtime,
# so equip_item receives no item_name and will fail with a vague error.
- mcp_tool: equip_item
  args: "Bronze sword"

# RIGHT — args is a dict matching the handler's kwargs.
- mcp_tool: equip_item
  args:
    item_name: "Bronze sword"
```

Real validated example: `routines/tutorial_island/08_combat.yaml:109`
(`mcp_tool: equip_item` with a dict `args:`).

`account_id` is auto-injected into `mcp_args` if not already present
(routine.py:1616-1617), so you don't need to set it yourself.

---

## (h) `KILL_LOOP` / `KILL_LOOP_CONFIG` — the food-arg trap and loot config

### `KILL_LOOP <npc_name> <food_name|none> [max_kills] [minX,minY,maxX,maxY]`

Argument parsing is strictly positional (`KillLoopCommand.java:83-97`):

```
parts[0] = npc_name    (underscores → spaces)
parts[1] = food_name    (underscores → spaces; "none" disables food mgmt)
parts[2] = max_kills    (optional, default 100)
parts[3] = area bounds  (optional, "minX,minY,maxX,maxY")
```

**⚠️ The #1 authoring mistake:** `KILL_LOOP Chicken 100` does **not** mean
"kill 100 chickens." Position 1 is the food name, so this parses as
`npc=Chicken, food="100", max_kills=<default 100>` — the plugin will try to
eat an item literally named `"100"` when HP drops, which doesn't exist, and
food management silently never succeeds. The correct form is
`KILL_LOOP Chicken none 100` (no food management, kill 100) or
`KILL_LOOP Chicken Bread 100` (eat Bread, kill 100).

**Default loot (bare `KILL_LOOP`, no config file):** only
`["Law rune", "Nature rune", "Fire rune", "Water rune"]`
(`KillLoopCommand.java:674-676`) — **dropped items are not looted** unless
you use `KILL_LOOP_CONFIG` with `loot_items` (below). Bones are *always*
picked up ("smart detection", line 715-721) and *always* buried
(line 723-732) regardless of config — there is no way to keep bones via
either command.

### `KILL_LOOP_CONFIG <config_json_path>`

Reads a JSON file (not YAML) with this shape
(`KillLoopConfigCommand.java:52-88`):

```json
{
  "npc": "Hill Giant",
  "kills": 500,
  "loot_items": ["Law rune", "Nature rune", "Fire rune", "Water rune"],
  "bones": ["Big bones"],
  "ignore_items": ["Limpwurt root"],
  "eat_threshold_percent": 50,
  "escape_food_count": 3
}
```

`loot_items` is the only way to loot non-default drops (e.g. armor, herbs,
seeds) — it's read into `activeCombatConfig.lootItems` and consulted by
`KillLoopCommand`'s loot-pickup step in preference to the hardcoded rune list
(`KillLoopCommand.java:665-676`).

**⚠️ `KILL_LOOP_CONFIG` always forces food off.** Line 101 of
`KillLoopConfigCommand.java` builds the delegated call as
`config.npc + " none " + config.kills` — food name is hardcoded to `"none"`
no matter what you put in the JSON (there is no `food` key read from the
config at all). This means the *no-food-management* HP safety branch
(`KillLoopCommand.java:239-250`) always applies: the loop stops for safety
at **50% HP**, not the food-managed 30% floor
(`KillLoopCommand.java:228-237`) that a bare `KILL_LOOP <npc> <food> ...`
call would get. If you need both custom loot **and** food management, there
is currently no single command that does both — you'd need a routine that
alternates `KILL_LOOP_CONFIG` batches with manual food restocking steps.

This JSON config file is produced by the *separate* `execute_combat_routine`
MCP tool from its own `npc:`/`kills:`/`loot:`/`eating:` YAML dialect
(`mcptools/tools/commands.py:658-687`) — see the note at the top of this
document and in (f). You can also hand-write the JSON directly and call
`KILL_LOOP_CONFIG <path>` from a `steps:`-based routine's `action:` field.

---

## ⚠️ (i) Two live-validated authoring traps: ambiguous names and unexhausted dialogue

Both found live on 2026-07-18, both silent — no error, no validator hit (k).

### Position-pin before `INTERACT_OBJECT`/`INTERACT_NPC` when the name is ambiguous

Both commands resolve purely by name to the **closest match to the player**
— 15-tile default radius, closest-first (`manny_src/utility/InteractionSystem.java:547-550,596-610`
for objects; `:1916-1979` for NPCs). No ID/uniqueness check: if two distinct
instances share a display name, the nearer one always wins.

**Live failure:** the tutorial mining area has two "Rocks" outcrops — tin
and copper. `INTERACT_OBJECT Rocks Mine` with no repositioning between ore
types farmed the nearer one (tin) forever: 13 tin, 0 copper, cascading into
smelting/smithing. Fixed in `routines/tutorial_island/07_mining_smithing.yaml:93-140`;
validated coords: tin `3076,9504`, copper `3085,9502`.

**Rule:** when the target name is ambiguous in the area (check
`scan_tile_objects`/`query_nearby` first), precede the INTERACT with a
`GOTO` + `location:` await pinning the player next to the intended instance.

```yaml
# WRONG — "Rocks" matches both outcrops; always resolves to the nearer (tin).
- id: 8
  action: INTERACT_OBJECT
  args: "Rocks Mine"
  description: "Mine copper ore"

# RIGHT — pin next to the copper instance first.
- id: 7
  action: GOTO
  args: "3085 9502 0"
  await_condition: "location:3085,9502"
  timeout_ms: 20000
- id: 8
  action: INTERACT_OBJECT
  args: "Rocks Mine"
  description: "Mine copper — nearest 'Rocks' is now the copper outcrop"
  timeout_ms: 30000
```

### The `CLICK_DIALOGUE "<speaker name>"` no-op trap

**DEFECT-24 (filed, fix pending):** the dialogue state writer can misreport
a multi-page NPC monologue as `type:"options"` and hint
`CLICK_DIALOGUE "<speaker name>"`. That's a no-op: widget group 231 child 4
(`15138820`, `NPC_NAME_ID`, `routine.py:346`) is the speaker-name **header**,
not an option; child 5 (`15138821`) is the continue button
(`journals/romeo_quest_widget193_death_2026-02-09.md:78`); child 6
(`15138822`, `NPC_TEXT_ID`, `routine.py:347`) is body text.

**Correct pattern** (live-validated,
`routines/tutorial_island/05_cooking_to_quest_guide.yaml:110-135`):
`INTERACT_NPC` to start, then `CLICK_CONTINUE` in a
`repeat_until: "no_dialogue"` loop (Grammar 1, section (c)) until the
monologue is fully **exhausted** — an unexhausted monologue silently blocks
whatever comes next (tabs, gated objects).

```yaml
- id: 10
  action: INTERACT_NPC
  args: "Quest_Guide Talk-to"
- id: 11
  action: CLICK_CONTINUE
  repeat_until: "no_dialogue"   # NOT CLICK_DIALOGUE "<speaker name>" — DEFECT-24
  repeat_until_timeout_ms: 3000
  max_iterations: 15
- id: 12
  action: TAB_OPEN
  args: "quests"
- id: 13
  action: INTERACT_OBJECT
  args: "Ladder Climb-down"
```

---

## (j) Three worked examples

### 1. Linear quest (adapted from `routines/quests/cooks_assistant.yaml`)

No `loop:` block at all — a straight-line step sequence, each gated by a
Grammar 1 `await_condition` so the runner doesn't race ahead of movement/
animation.

```yaml
name: "Cook's Assistant (excerpt)"
type: quest

steps:
  - id: 1
    phase: "travel"
    action: GOTO
    args: "3253 3270 0"
    description: "Walk to the cow pen east of Lumbridge"
    await_condition: "location:3253,3270"
    timeout_ms: 20000

  - id: 2
    phase: "gather"
    action: INTERACT_NPC
    args: "Cow Bucket-from-cow"          # underscores would be needed for
    description: "Milk a cow"             # multi-word action text
    await_condition: "has_item:Bucket of milk"
    timeout_ms: 15000

  - id: 3
    phase: "travel"
    action: GOTO
    args: "3208 3216 0"
    description: "Return to Lumbridge Castle kitchen"
    await_condition: "location:3208,3216"
    timeout_ms: 20000
```

### 2. Flat-loop grind (adapted from `routines/combat/chicken_killer_loop.yaml`)

```yaml
name: "Chicken Killer Auto-Loop (excerpt)"
type: combat

steps:
  - id: 1
    phase: "travel"
    action: GOTO
    args: "3180 3288 0"
    description: "Walk to chicken coop"
    await_condition: "location:3180,3288"
    timeout_ms: 20000

  - id: 2
    phase: "combat"
    action: KILL_LOOP
    args: "Chicken none 100"              # food="none" per (h); 100 kills
    description: "Kill 100 chickens"
    timeout_ms: 3600000                   # 1hr ceiling — see (e), no await_condition

# Flat loop: re-run from step 1 after each full pass, until a Grammar 2
# stop_condition matches. NOT a nested inner/outer block — see (d).
loop:
  enabled: true
  repeat_from_step: 1
  stop_conditions:
    - "inventory_full"
# NOTE: no cap on the number of passes lives in this file — bound it with
# `./run_routine.py <this file> --loops 50`, NOT a `loop.max_iterations` key
# (dead, see (f)).
```

### 3. Nested inner/outer banking loop (adapted from
`routines/skilling/superheat_mining_guild.yaml`)

```yaml
name: "Superheat Mining Guild (excerpt)"
type: skilling

steps:
  - id: 1
    phase: "travel"
    action: GOTO
    args: "3062 9812 0"
    description: "Walk into Mining Guild"
    await_condition: "location:3062,9812"
    timeout_ms: 20000

  # ... steps 2-8: withdraw runes, walk to iron rocks ...

  - id: 9
    phase: "gather"
    action: MINE_ORE
    args: "Iron 1"
    description: "Mine one iron ore"
    timeout_ms: 300000                    # blocking command, see (e)

  - id: 10
    phase: "process"
    action: CAST_SPELL_NPC
    args: "Superheat_Item Iron_ore"
    description: "Superheat the ore into a bar"
    await_condition: "no_item:Iron ore"
    timeout_ms: 15000

  # ... step 11: GOTO bank, step 12-13: deposit + withdraw more runes ...

loop:
  inner:
    enabled: true
    start_step: 9                         # jump back here each pass
    end_step: 10                          # check exit_conditions after this step runs
    exit_conditions:
      - "inventory_full"                  # Grammar 2 — stop mining/smelting
    on_exit: "goto_step:11"               # jump to the banking steps
  outer:
    enabled: true
    start_step: 1
    end_step: 13
    exit_conditions: []                   # runs until `--loops N` is exhausted
```

---

## (k) Validation workflow

Before running a new/edited routine:

```python
validate_routine_deep(
    routine_path="routines/skilling/your_routine.yaml",
    plugin_dir="manny_src",     # or config.plugin_directory
    check_commands=True,        # verifies action: names exist in PlayerHelpers.java
    suggest_fixes=True          # fuzzy-matches unknown command names
)
```

(`manny_tools.py:2557-2789`.) It checks: YAML syntax, `steps:` presence
(non-executable/config-sidecar files are exempted via
`_routine_is_non_executable`, `manny_tools.py:~2609`), that each step has
either `action` or a **known** `mcp_tool` (remember the validator's
`_KNOWN_MCP_TOOLS` set is missing `click_text` — see (g)), `action` names
against the live command list, `GOTO` arg-count, and more. **It does not
check Grammar 1 vs. Grammar 2 condition placement, `timeout_ms` sufficiency
for blocking commands, or any of the dead keys in (f)** — those are exactly
the classes of bug this document exists to prevent by construction, since
the validator won't catch them.

Then dry-run with a small step/loop count before a long unattended run:

```bash
# Single pass, from the top
./run_routine.py routines/skilling/your_routine.yaml --account main

# Resume from a specific step (useful after a partial failure)
./run_routine.py routines/skilling/your_routine.yaml --start-step 9 --account main

# Bound a loop explicitly — this is the ONLY real iteration cap, see (d)/(f)
./run_routine.py routines/skilling/your_routine.yaml --loops 3 --account main

# Raw JSON output for programmatic inspection
./run_routine.py routines/skilling/your_routine.yaml --loops 1 --json --account main
```

`run_routine.py` also accepts a directory or a chain YAML
(`type: chain` / top-level `chain:` list) to run multiple routine files in
order (`run_routine.py:30-97`); each section still follows everything in
this document individually.

Watch the run with `get_game_state(fields=["location","inventory"])` and
`get_logs(level="ALL", grep="<COMMAND>")` — the routine runner logs a health
check every 5 steps (`health_check_interval = 5`, routine.py:1129) and
auto-restarts/re-logs-in on detected crashes or disconnects
(routine.py:1141-1173, 1218-1251); you generally don't need to babysit
individual steps, but a routine that's silently stuck on a dead-key loop
condition (section (f)) won't trip any of that — it'll just run to
`--loops N` doing nothing useful, which is why validating against this
document *before* a long run matters more than watching it *during* one.
