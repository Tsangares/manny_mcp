# Task #26 — Generic varp/varbit quest-state export + `varp:`/`varbit:` await atoms

**Status:** Java side DONE + compile-verified (this task). Python side = SPEC ONLY
(the Python tree is in use by a live run; do NOT implement until that run ends).

**Motivation.** Quests gate on arbitrary game vars, not on item facts. Cook's
Assistant is VarPlayer 29 (`0` not-started → `1` started → `2` complete); today a
quest routine can only proxy on inventory contents, which is fragile (false-pass
class). The tutorial chain already proved the pattern: gate on the game's own
counter (VarPlayer 281) via the `tutorial_progress:` step atom. This task
generalizes that to an allowlisted set of varps/varbits and a matching pair of
step-level await atoms.

---

## (a) New state-file JSON keys (Java side — ALREADY SHIPPED IN SOURCE)

`GameEngine.StateExporter.buildVarState()` adds a top-level `"vars"` object to the
exported state, alongside the existing `"tutorial"` object (which is unchanged):

```json
"vars": {
  "varps":   { "281": 1000, "29": 1 },
  "varbits": { }
}
```

- Keys are the **decimal id as a String** (Gson emits a stable JSON object; an
  int-keyed map would serialize oddly).
- Values are the raw `int` var values.
- Both sub-maps are emitted **empty when logged out** (`GameState != LOGGED_IN`)
  and on any read exception (fail-safe). An id absent from the export = **unknown**.
- The allowlists live at the top of `StateExporter`:
  - `VARP_ALLOWLIST` — read with `client.getVarpValue(id)` (VarPlayer namespace).
    Seeded with `281` (tutorial) and `29` (Cook's Assistant).
  - `VARBIT_ALLOWLIST` — read with `client.getVarbitValue(id)` (Varbit namespace).
    Empty (no quest varbits gated yet).
  - **The two sets are namespace-disjoint by contract** — a varbit id placed in
    `VARP_ALLOWLIST` reads a wrong, usually-permanent-`0` slot (attempt #2's
    `getVarbitValue(281)` bug; see `buildTutorialState()` docstring and
    MANNY_OVERSEER.md §2). To add a quest gate: append the id + a one-line
    value-meaning comment to the matching set. No other Java change is needed.
- Cadence: exported **every tick** from `buildState()` (called on `onGameTick`),
  identical cadence to `tutorial.progress`.
- Backward-compat: `tutorial.progress` (varp 281) is retained verbatim; `vars` is
  purely additive. Old-jar state files simply lack `"vars"` → Python must treat an
  absent section as "all ids unknown", never crash.

Java prior art / pattern followed (this repo, `manny`):
- `2f641d9`, `cf22ed5` — added `tutorial.progress` (the varp-281 export + the
  varp-vs-varbit namespace lesson). `buildVarState()` mirrors `buildTutorialState()`
  exactly (LOGGED_IN guard, try/catch fail-safe, string keys, `@Data` field on
  `MannyState` with a Gson-verbatim comment).

---

## (b) Proposed Grammar-1 await atoms `varp:<id>:<op>N` and `varbit:<id>:<op>N`

**Grammar-1 = step-level `await_condition` / `repeat_until` only** (NOT loop
stop/exit conditions — see (d)). Two atoms, one per namespace, because the export
keeps them separate and they must not be conflated:

| Atom | Example | Meaning |
|---|---|---|
| `varp:<id>:<op>N` | `varp:29:>=1` | VarPlayer `<id>` value `<op>` `N` |
| `varbit:<id>:<op>N` | `varbit:3550:==1` | Varbit `<id>` value `<op>` `N` |

- Ops: `>=`, `<=`, `>`, `<`, or **bare `==`** — identical operator set and
  parsing to `inventory_count:` / `tutorial_progress:` / `skill_diff:`.
- `<id>` is the decimal var id; it is looked up as `str(id)` in the export map.

**Semantics (must mirror `tutorial_progress` exactly):**
- Read `state["vars"]["varps"]` (or `["varbits"]`) → `.get(str(id))`.
- **Missing id / absent `vars` section / null value → condition NOT met, return
  `False`, NEVER raise.** This is the same old-jar-safe, unknown-is-not-satisfied
  rule that keeps a `tutorial_progress` gate a no-op against an old jar rather than
  a crash (`monitoring._check_condition`, tutorial_progress branch). A quest gate on
  an un-allowlisted id therefore silently never fires — acceptable and safe (the
  fix is to allowlist the id in Java + redeploy, not to crash the routine).

---

## (c) Exact Python edits required (DO NOT IMPLEMENT YET — spec only)

Mirror precisely how `tutorial_progress` was added. Reference commits in `manny_mcp`:
`fcdada5` (atom parse+check), `c186adf` (dry-run model). Line numbers below are
current as of this spec; re-grep before editing.

### 1. `mcptools/tools/monitoring.py` — parser + evaluator (the core)

**`_parse_condition()`** (currently ~lines 529–602). The `tutorial_progress`
branch at **lines 581–600** is the template. Add two analogous branches. Because
these atoms carry an embedded id (`varp:<id>:<op>N`), the split differs slightly —
`condition.split(":", 1)` yields `cond_type="varp"`, `value="<id>:<op>N"`, so the
branch must split `value` again on the first `:` into id and comparison:

```python
elif cond_type in ("varp", "varbit"):
    # value == "<id>:<op>N"; split off the id, reuse the inventory_count/
    # tutorial_progress operator parse for the "<op>N" tail.
    id_str, comp = value.split(":", 1)
    var_id = int(id_str)
    if comp.startswith("<="):   op, n = "<=", int(comp[2:])
    elif comp.startswith(">="): op, n = ">=", int(comp[2:])
    elif comp.startswith("<"):  op, n = "<",  int(comp[1:])
    elif comp.startswith(">"):  op, n = ">",  int(comp[1:])
    else:                        op, n = "==", int(comp)
    return (cond_type, (var_id, n), op)   # cond_type carries the namespace
```

(Choose whatever tuple shape is cleanest — the existing atoms use
`(type, value, operator)`; packing `(var_id, n)` into the value slot keeps that
shape. Match the surrounding style.)

**`_check_condition()`** (currently ~lines 605–692). The `tutorial_progress`
branch at **lines 671–690** is the template. Add:

```python
elif cond_type in ("varp", "varbit"):
    var_id, n = value
    section = "varps" if cond_type == "varp" else "varbits"
    vars_map = (state.get("vars") or {}).get(section) or {}
    raw = vars_map.get(str(var_id))          # keys are string ids
    if raw is None:
        return False                          # unknown -> not satisfied, never raise
    if operator == "<=": return raw <= n
    if operator == ">=": return raw >= n
    if operator == "<":  return raw <  n
    if operator == ">":  return raw >  n
    return raw == n
```

Also extend the `_parse_condition` and `await_state_change` **docstrings**
(the "Supported conditions" lists at ~lines 533–541 and ~lines 699–707) with the
two new atoms, exactly as `tutorial_progress` was documented there.

### 2. `mcptools/manny_tools.py` — `validate_routine_deep` static validation

- **`AWAIT_CONDITION_ATOMS`** frozenset (**lines 2571–2575**): add `"varp"` and
  `"varbit"` to the prefixed group (next to `"tutorial_progress"`). This frozenset
  is documented as "EXHAUSTIVE per `monitoring._parse_condition`", so it MUST be
  kept in lockstep with edit #1.
- **`_AWAIT_VOCAB_HELP`** (**lines ~2705–2706**): append `varp:<id>:<op>N,
  varbit:<id>:<op>N` to the help string so validation-error messages list them.
- Optional but recommended, mirroring `_skill_diff_error`: a small
  `_var_atom_error(cond)` that flags a malformed `varp:`/`varbit:` atom (non-integer
  id, missing comparison) as an ERROR pre-run instead of letting
  `monitoring._parse_condition` raise `ValueError` only at runtime. `skill_diff`'s
  `_skill_diff_error` (**lines ~2711–2740**) is the exact template; wire the call in
  next to where `_skill_diff_error` is invoked in the await-atom validation path.
  (If skipped, an out-of-format atom still fails loudly at runtime via
  `_parse_condition` — acceptable, just later.)

### 3. `mcptools/dryrun.py` — offline effect model

- **`StateModel.__init__`** (~line 169): add `varps=None, varbits=None` params and
  store `self.varps = varps or {}`, `self.varbits = varbits or {}` (mirroring the
  `tutorial_progress=None` field at lines 169/185).
- **`StateModel.to_state()`** (~line 225, where `"tutorial": {"progress": ...}` is
  built): add `"vars": {"varps": self.varps, "varbits": self.varbits}` so dry-run's
  fixture state has the same shape the live plugin exports.
- **Effect table** — the `elif ctype == "tutorial_progress":` block at
  **lines 455–466** is the template. Add `elif ctype in ("varp", "varbit"):` that
  applies the same optimistic arming assumption: an `await`/`repeat_until` on a
  `varp:`/`varbit:` atom is game-truth that no simulated command sets, so on reaching
  such a gate, set the modeled var to a value that satisfies the op (`> N` → `N+1`,
  `< N` → `max(0, N-1)`, else `N`) in the matching `self.varps`/`self.varbits` dict.
  This lets a var-gated step be *exercised* offline (same rationale as the
  tutorial_progress arming comment at lines 456–460).

### 4. `ROUTINE_SCHEMA.md` — authoring reference

- **Grammar-1 atom table** (**lines 151–159**): add two rows after the
  `inventory_count`/`location` rows:

  | `varp:<id>:<op>N` | `varp:29:>=1` | VarPlayer `<id>` value `<op>` `N`; ops `<=` `>=` `<` `>` or bare `==`. Reads `vars.varps["<id>"]`; **unknown id → not satisfied, never raises**. Requires the id be allowlisted in the plugin's `VARP_ALLOWLIST`. |
  | `varbit:<id>:<op>N` | `varbit:3550:==1` | as `varp:` but reads `vars.varbits["<id>"]` via `client.getVarbitValue`. Namespace is NOT interchangeable with `varp:`. |

  (Note: the Grammar-1 table in `ROUTINE_SCHEMA.md` does not currently list
  `tutorial_progress` — a pre-existing doc gap. Consider adding a `tutorial_progress`
  row in the same edit for completeness, since the new rows will invite the question.)
- Add a short note that both atoms are **Grammar-1 only** (step `await_condition` /
  `repeat_until`); they are NOT in the loop `stop_conditions`/`exit_conditions`
  vocabulary (`STOP_CONDITION_ATOMS`) and will `ValueError` if used there — same
  trap already documented for `plane:`/`location:`/`tutorial_progress:`.

---

## (d) Grammar-2 (loop stop/exit conditions) — deferred, same pattern as `skill_diff`

If a quest routine later needs to gate a *loop* (e.g. "keep talking until
`varp:29:==2`"), the loop vocabulary can gain `varp:`/`varbit:` the same way
`skill_diff` was added:
- `mcptools/tools/routine.py` `check_stop_condition()` — add a branch reading the
  same `state["vars"]` section (commit `13aec22` is the `skill_diff` template).
- `mcptools/manny_tools.py` `STOP_CONDITION_ATOMS` frozenset (**lines 2580–2584**) —
  add the atoms there.
- Keep the two grammars' implementations independent (the schema explicitly warns
  the overlap is "a trap, not a convenience", `ROUTINE_SCHEMA.md` lines 204–211).

Not needed for the initial quest work — Cook's Assistant and most F2P quests gate
fine at the step level. Ship Grammar-1 first; add Grammar-2 only when an actual
loop needs it (doctrine: strictness/features earned by a real need, not prophylactic).

---

## Validation checklist (when the Python side is implemented)

1. `validate_routine_deep` on a routine using `varp:29:>=1` → no unknown-atom error.
2. `./run_routine.py <routine> --dry-run` → the var-gated step is reached/satisfied
   via the effect model, not a guaranteed timeout.
3. Live: with the new jar deployed, `get_game_state(fields=[...])` shows
   `vars.varps["29"]` tracking Cook's Assistant progress; a `varp:29:==2` await
   fires exactly on quest completion.
4. Old-jar safety: against a state file with no `vars` section, a `varp:` await
   evaluates `False` and never raises.
