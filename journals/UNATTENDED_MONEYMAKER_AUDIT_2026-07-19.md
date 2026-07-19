# Unattended Money-Maker Audit (Cowhide Banking / Chicken Feathers)

Read-only desk audit, 2026-07-19. Scope: `routines/money_making/cowhide_banking.yaml`,
`routines/money_making/chicken_feathers.yaml`, `run_routine.py`,
`mcptools/tools/routine.py`, cross-checked against `ROUTINE_SCHEMA.md` and
`manny_tools.py`'s `validate_routine_deep`. Humanization/anti-detection code
(`mcptools/humanize.py` etc.) explicitly excluded per instructions.
DEFECT-30 (STOP an owned loop on step timeout) is already fixed/committed and
is not re-reported below; several findings are explicitly noted as *adjacent*
to it.

No files were edited, no commands run, no client contacted. This file is the
one permitted write.

---

## HIGH — non-inner-loop step failures "log-and-continue" instead of
retrying or aborting (`mcptools/tools/routine.py:1401-1429`, `1498`)

**The bug:** When a step fails, `handle_execute_routine` only has special
recovery logic if that step's index falls inside an **inner-loop range**
(`inner_start_idx <= current_step_idx <= inner_end_idx`, routine.py:1407-1429
— restart from `inner.start_step`, or exit via `on_exit` after 3 consecutive
failures). For every step **outside** that range, a failure just appends a
string to `results["errors"]` (routine.py:1402-1404) and falls straight
through to `current_step_idx += 1` (routine.py:1498) — the runner proceeds to
the *next scripted step* exactly as if the failed step had succeeded. There
is no "abort this pass," no "retry from a known-good checkpoint," no location
re-verification.

**Concrete failure scenario — `cowhide_banking.yaml`:** the inner loop covers
*only* step 2 (`start_step: 2, end_step: 2`, the kill batch). All 22 other
steps (1, 3-24 — every GOTO/INTERACT_OBJECT/BANK_* in the whole travel+bank
sequence) get zero special handling. If any single bridge-hop GOTO times out
(step 5 e.g., `location:3244,3227` — one of the three UNVERIFIED bridge
tiles the file's own header flags as untested), the routine does not stop or
back up: it proceeds to step 6's GOTO from wherever the character actually
is, then step 7, 8, the staircase climbs (steps 9/11, `INTERACT_OBJECT
Staircase Climb-up` awaiting `plane:N` — resolved by nearest-name-match
within 15 tiles per `ROUTINE_SCHEMA.md` (i), so a mispositioned character
risks interacting with the wrong staircase instance or none at all),
`BANK_OPEN`, `BANK_DEPOSIT_ALL`, all the way through the return leg — each
possibly also failing, each logged and skipped. The only real checkpoint in
the entire file is the outer-loop wraparound back to step 1 (`GOTO` to the
cow field), which happens once per full pass. Worst case: **one entire
field↔bank cycle (up to ~1h kill batch + ~10min of travel) silently
misbehaves** — cowhides never get banked, the character ends up who-knows-where
— before the next pass's step 1 has a chance to self-correct. Over a
multi-hour unattended run this is exactly the "silently misbehave" failure
mode the audit is looking for: no crash, no hang, just quietly wrong.

**Suggested fix (do not apply):** either (a) extend the
"restart-on-consecutive-failure" mechanism to non-inner-loop steps too (e.g.
N consecutive step failures anywhere aborts the pass and jumps to a safe
recovery point — for `cowhide_banking.yaml` that would be back to step 1),
or (b) make travel/banking steps `await_condition`-gated with an explicit
`repeat_until`/max-iterations retry loop instead of a bare single step, or
(c) at minimum have `handle_execute_routine` treat certain step failures
(BANK_OPEN, BANK_DEPOSIT_ALL) as pass-aborting even outside a formal inner
loop.

---

## HIGH — the three banking steps have the *least* retry protection of any
step class in the file (`cowhide_banking.yaml:279-299`, `routine.py:1784-1811`)

**The bug:** `_execute_step_once` only has a Python-level retry (resend the
command once at 2x `timeout_ms`, routine.py:1797-1809) for steps that carry
an `await_condition`. `BANK_OPEN` (step 13), `BANK_DEPOSIT_ALL` (step 14) and
`BANK_CLOSE` (step 15) have **no** `await_condition` at all (they only set
`delay_after_ms`), so they fall into the plain `execute_simple_command` path
(routine.py:1811-1836) with **zero** Python-side retry — one shot only.
`BankOpenCommand.executeCommand`/`BankDepositAllCommand.executeCommand`
(manny/utility/commands/BankOpenCommand.java:30-46,
BankDepositAllCommand.java:25-41) do return an honest `false` on failure (not
a false-positive "sent:true"), so a genuine failure to find/open the bank
*is* correctly surfaced as `step_result["success"] = False" — but per the
HIGH finding above, that failure is then just logged and ignored, and the
routine proceeds straight to `BANK_CLOSE` and the return-to-field leg with
the inventory still full of unbanked cowhides.

Put together with the first finding: the single most consequence-bearing
3-step sequence in the "milestone" money-maker (the actual banking — the
entire economic point of the routine) is also the sequence with the weakest
Python-side resilience of anything in the file. A transient bank-booth click
miss, or a booth-out-of-render-distance hiccup, silently no-ops the entire
cycle's payoff.

**Suggested fix:** add a Grammar-1 `await_condition` atom for "bank is open"
(none currently exists — `plane:N`/`has_item:X`/`no_item:X`/
`inventory_count:<op>N`/`location:X,Y`/`idle`/`dialogue` are the full set per
`ROUTINE_SCHEMA.md` (c)) so `BANK_OPEN` can be retried like every other
gated step, and/or verify `BANK_DEPOSIT_ALL` succeeded via
`await_condition: "inventory_count:<=0"` before proceeding to `BANK_CLOSE`.

---

## MED-HIGH — return-trip GOTO hop granularity is asymmetric with the
outbound leg, reintroducing the DEFECT-21 corner-cutting risk the short-hop
design exists to avoid (`cowhide_banking.yaml:181-236` vs `:342-372`)

The file's own header explains the outbound field→bank leg was deliberately
split into short hops (steps 3-7: field → `3247,3235` → `3247,3228` →
`3244,3227` → `3239,3228` → courtyard) specifically because "DEFECT-21
(NAV-DIRECT corner-cutting / long cross-bridge GOTOs) has a fix landed but
NOT live-validated." But the **return** leg (steps 20-24) drops the
intermediate `3247,3235` waypoint entirely: step 23 goes straight from
`3247,3228` (bridge east end) to step 24's `3253,3266` (field) in one GOTO —
collapsing what was two outbound hops (~31 + ~7 tiles) into a single ~38-tile
diagonal GOTO on the way back, precisely the kind of long-distance GOTO the
short-hop strategy exists to avoid. If NAV-DIRECT corner-cuts on that hop,
the character could land against a fence/wrong side of the cow pen with no
intermediate location check to catch it (steps 20-23 all check locations up
to the bridge, but there is nothing checking progress between the bridge and
the field on the way back).

**Suggested fix:** add the missing return-leg waypoint (mirror of step 3,
e.g. `3247 3235 0` before the final `3253 3266 0` hop) so both directions use
identical hop granularity.

---

## MED — DOOR RISK flagged for the outbound courtyard→stair leg is silently
unaddressed on the identical return leg (`cowhide_banking.yaml:63-78` vs
`:326-340`)

The header's "STILL LIVE-GATED" section explicitly flags a possible door
near `(3218,3217)` sitting almost exactly on the straight-line path between
courtyard `(3221,3218)` and the south staircase `(3205,3208)` for **steps
7→8** (outbound), citing `journals/navigation/indoor_navigation_lessons_2025-01-04.md`.
The return leg, **steps 19→20**, walks the exact same line in reverse
(stair `3205,3208` → courtyard `3221,3218`) and carries the identical
unaddressed risk, but the header never mentions it, and there's no
door-scan/handling step on either leg. This isn't a new risk, just an
incompletely-scoped writeup of an already-known one — worth closing out
together rather than only gating the outbound direction before this leaves
DRAFT.

**Suggested fix:** the header already prescribes the right live-validation
step ("a live run MUST `get_transitions()`/`scan_tile_objects("door")` near
`(3218,3217)` before trusting steps 7→8 unattended") — extend that
instruction to cover 19→20 as well, and pre-emptively author a conditional
`INTERACT_OBJECT <Door_name> Open` step usable on both legs once the door's
exact name/coordinate is confirmed live.

---

## MED — top-floor staircase waypoint contradicts the file's own corrected
source pin (`cowhide_banking.yaml:29-44` vs `:302-308`)

The header's STAIRCASE GEOMETRY research (lines 29-34) states the wiki pin
is `(3205,3208)` on **all three** floors of the south staircase (same
stacked column, confirmed by the wiki's raw wikitext) and explicitly
corrects the ground- and 1st-floor waypoints from `3205,3209` → `3205,3208`
to match (lines 37-39, reflected in steps 8/10/18). But step 16 ("Reposition
at the 2nd-floor staircase") still targets `3205,3209` — the *uncorrected*
value — justified only as "kept as-is... matches the wiki's top pin
(3205,3208, within 1 tile)" (lines 41-44). That's inconsistent with the
methodology applied to the other two floors in the same desk pass. Given
`location:X,Y` await tolerates a 3-tile Chebyshev radius (`ROUTINE_SCHEMA.md`
(c)), this is very likely functionally harmless, but it's a real
inconsistency in the desk-verification's own reasoning and should be
reconciled (either correct it to `3205,3208` for consistency with the other
two floors, or explicitly document *why* the top floor alone should stay at
`3209` — right now it reads as an overlooked correction).

**Suggested fix:** change step 16's args/await to `3205 3208 2` to match
steps 8/10/18's corrected coordinate, or add a one-line justification if
`3209` is intentional.

---

## MED — `chicken_feathers.json` config (`kills: 1000`) contradicts the
routine's own description and the timeout tuning history
(`chicken_feathers.yaml:71-78` vs `configs/chicken_feathers.json`)

Step 3's description says "Kill 100 chickens, loot Feathers" and the
adjacent comment explains the `timeout_ms` was raised `3600000 → 14400000`
(1h → 4h) after the 1h ceiling orphaned a live run as an `unmanaged_loop`.
But the actual config file the step references,
`routines/money_making/configs/chicken_feathers.json`, sets `"kills": 1000`
— **10x** the number the description and (implicitly) the timeout-tuning
incident were reasoning about. Per `ROUTINE_SCHEMA.md`'s own blocking-command
table, a 100-kill `KILL_LOOP*` batch already "realistically spans many
minutes to over an hour"; nothing in the file shows the 4h ceiling was
re-derived for a 1000-kill batch. If a 1000-kill batch regularly runs long
on a contested/slow world, the step will hit the (already-fixed) DEFECT-30
stop-loop path routinely, silently truncating every batch well short of
1000 kills and paying the TAB_OPEN/SWITCH_COMBAT_STYLE setup overhead again
each restart — not unsafe, but a real efficiency/correctness-of-intent gap
that's invisible unless someone reads the JSON config next to the YAML.

**Suggested fix:** either update the step-3 description to say 1000 (and
re-derive/re-verify the 4h timeout floor against a 1000-kill worst case), or
drop the config back to a number the tuning history actually covers.

---

## MED — no live GOTO-fallback for the chicken coop coordinate despite the
routine's own header flagging the need for one
(`chicken_feathers.yaml:23-26`)

The header states: "COOP COORDINATE: 3235,3295 is the proven-grind pen NE of
Lumbridge... Old template used 3180,3288; if the GOTO cannot settle at
3235,3295 on the live world, fall back to 3180,3288 and update step 1 + the
await. VERIFY LIVE at smoke time." No such fallback exists in the YAML —
step 1 is a single GOTO/await pair (with the standard one retry-at-2x-timeout
from routine.py:1797-1809, ~4 min total). If that coordinate doesn't settle
live, step 1 fails, and per the first HIGH finding above the routine
log-and-continues into TAB_OPEN → SWITCH_COMBAT_STYLE → a 1000-kill,
up-to-4-hour `KILL_LOOP_CONFIG` batch run from wherever the character
actually ended up — potentially finding no chickens at all and burning the
entire unattended window every single flat-loop pass (since `repeat_from_step: 1`
always retries the same coordinate).

**Suggested fix:** either confirm `3235,3295` live before shipping this
unattended, or encode the documented fallback as a second GOTO attempt at
`3180,3288` gated on step 1's failure (not currently expressible cleanly in
this schema — worth a note back to the schema/engine owner if a
conditional-fallback step type doesn't exist yet).

---

## MED — health-check machinery is blind for the entire duration of a
blocking KILL_LOOP* step; adjacent to DEFECT-30 (`routine.py:1128-1187,
1433-1468`)

Not re-reporting DEFECT-30 (STOP-on-timeout is fixed). But note the coverage
gap it lives inside: the periodic mid-pass health check
(`steps_since_health_check >= health_check_interval(5)`, routine.py:1433) can
only fire **between** step executions — and a `KILL_LOOP`/`KILL_LOOP_CONFIG`
step is, from the outer loop's perspective, a *single* step that blocks
inside `_await_active_loop_finish` for its entire real-world duration (up to
`timeout_ms`, e.g. 4h for chicken_feathers). During that whole window the
*only* liveness signal is `_await_active_loop_finish`'s own stall detector
(`stall_ms=300000` — 5 minutes of no kill/iteration progress,
routine.py:1183-1187), not the general crash/disconnect
health-check→auto-restart→relogin path. For `chicken_feathers.yaml`
specifically, the routine has only 4 steps per pass (fewer than
`health_check_interval=5`), so the in-pass health check can never fire even
in principle for this routine — the only other checkpoint is the
once-per-pass check at the top of the outer loop (routine.py:1358), which
for a 4h pass means at most one health check every ~4 hours outside of the
kill-loop's own stall detector. A crash/freeze whose symptom is a frozen (not
absent) `active_loop.kills`/`iteration` pair is caught within 5 minutes by
the stall detector; anything that manages to keep those two numbers moving
without genuine progress would not be caught until the full step timeout.

**Suggested fix (informational, not urgent given the stall detector already
covers the common case):** consider having `_await_active_loop_finish` also
cross-check `check_client_health`'s disconnect/crash discriminator on the
same poll cadence, not just kill-progress staleness, so a genuine
client-level crash is caught by the same signal regardless of what
`active_loop`'s counters happen to be doing.

---

## LOW — `validate_routine_deep`'s non-terminal-KILL_LOOP warning is a
false positive for the correctly-structured nested-loop pattern
(`manny_tools.py:3038-3047`)

The check fires whenever a `KILL_LOOP`/`KILL_LOOP_CONFIG` step isn't the
literal last step of the file (`i < len(routine_steps)`). `cowhide_banking.yaml`
step 2 is intentionally not terminal — it uses the nested inner/outer loop
pattern (`ROUTINE_SCHEMA.md` (d)'s own worked example,
`superheat_mining_guild.yaml`) where the kill loop is `inner.start_step ==
inner.end_step` and `on_exit` jumps to the banking leg — a different, equally
valid shape from the flat-loop "kill loop must be the last step" pattern the
check is really guarding against. This will always warn on this routine even
though it's structured correctly, and could mislead a live-gating reviewer
into "fixing" something that isn't broken.

**Suggested fix:** scope the check to flat-loop routines only, or exempt
`KILL_LOOP*` steps that are both `inner.start_step` and `inner.end_step` of
a nested loop.

---

## LOW — `BANK_CLOSE` (step 15) shares the same no-retry gap as
`BANK_OPEN`/`BANK_DEPOSIT_ALL` but is lower-risk

Same mechanism as the HIGH finding above (no `await_condition`, single
attempt), but a failed `BANK_CLOSE` is lower-consequence in practice since
walking away to start the return-to-field GOTO typically closes the bank
interface as a side effect in OSRS. Noted for completeness, not worth fixing
in isolation.

---

## LOW — `ROUTINE_SCHEMA.md` section (g) appears stale re: `click_text`
(`manny_tools.py:2498`)

Not relevant to either money-maker routine (neither uses `mcp_tool:` steps),
flagged only because the schema doc explicitly says "re-verify... the source
is truth." The doc claims `_KNOWN_MCP_TOOLS` is missing `click_text`
(`{"equip_item", "click_widget", "find_and_click_widget"}`), but the live
code at `manny_tools.py:2498` is
`{"equip_item", "click_widget", "find_and_click_widget", "click_text"}` —
four entries, `click_text` included. The doc's own "Correction to a prior
claim" paragraph (section (f) tail) suggests this class of drift has
happened before; this looks like the same thing recurring on `click_text`
itself, the doc's own worked example.

---

## Checked and found clean (no new findings)

- Neither file uses the already-documented dead keys (`loop.max_iterations`,
  `loop.start_step` under a flat block, `loop.delay_between_loops_ms`,
  `skip_if`, bare `delay_after`, step-level `location:`) — both appear to
  have already been audited against `ROUTINE_SCHEMA.md`.
- No Grammar 1/Grammar 2 condition-vocabulary crossovers in either file's
  `await_condition`/`exit_conditions`/`stop_conditions`.
- No flat-vs-nested loop-shape conflicts (`cowhide_banking.yaml` uses
  inner/outer only; `chicken_feathers.yaml` uses flat only).
- `KILL_LOOP_CONFIG` timeout floors (`cowhide`: 3.6M ms for 35 kills;
  `chicken`: 14.4M ms, see MED finding above re: the kills=1000 mismatch)
  both clear `validate_routine_deep`'s `BLOCKING_COMMANDS` floor
  (`manny_tools.py:2601-2602`, 3,600,000ms) and neither carries a forbidden
  `await_condition`.
- Bridge-hop and courtyard coordinates are already correctly flagged
  UNVERIFIED by the file's own header — not re-litigated here beyond the
  asymmetric-hop and door-risk-scope findings above.
- Inventory-full-mid-kill behavior (`KILL_LOOP_CONFIG` doesn't stop early on
  a full inventory, keeps attacking to `kills` regardless) is already
  correctly documented in `cowhide_banking.yaml`'s own header math — not a
  new finding, just confirmed accurate against `KillLoopCommand.java`'s
  documented `for (int i = 0; i < maxKills; i++)` semantics.
