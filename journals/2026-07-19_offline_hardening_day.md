# 2026-07-19 — Offline Hardening Day

**Repos:** `manny_mcp` (Python: MCP server, routine engine, driver/watchdog) and
`manny` (Java: the RuneLite plugin).
**Ranges pushed today:** `manny_mcp` `a6e6191..d91c409`, `manny` `e56ba40..21468c0`.

## Why the day looked nothing like the plan

The plan was to grind. Two fresh F2P accounts had other ideas: `new`
(GrimmsFairly) was behaviorally banned on 2026-07-18, and `newbakshesh` followed
on 2026-07-19 — banned roughly 32 seconds after a KILL_LOOP relaunch, on diort's
residential IP with no proxy. The infrastructure was fine; the *behavior* was the
tell — undisguised timing and click cadence. That put every live lane, attended
and unattended, on hold campaign-wide. Resumption now waits on a USER decision
(proxy/IP posture and which account), which no automated session is allowed to
make.

So the day pivoted to what could be done with zero live contact: a
parallel-subagent **offline hardening sweep** across both repos. Five threads ran:
the unattended money-maker audit, a full routine-corpus triage, the ban-detection
redesign, the nav data pipeline, and deploy prep. The test suite went from **248
to 295 passing** in `manny_mcp` over the sweep, and every commit was scoped —
never a `git add -A` — because the working tree carried parked, user-owned edits
that had to stay out of every build and every commit (more on that at the end).

---

## 1. The unattended money-maker audit → engine `on_failure` policy

The money-maker path is the milestone: `cowhide_banking.yaml` and
`chicken_feathers.yaml` grinding for hours with nobody watching. A read-only desk
audit (`journals/UNATTENDED_MONEYMAKER_AUDIT_2026-07-19.md`) went looking for the
"silently misbehaves — no crash, no hang, just quietly wrong" failure mode, and
found it.

**The core bug (audit Finding 1):** when a routine step fails, the engine only had
real recovery logic if the step sat *inside a nested inner-loop range*. Every step
outside that range — every GOTO, INTERACT_OBJECT, and BANK_* in the whole
travel-and-bank sequence — just appended a string to `results["errors"]` and fell
straight through to the next step, exactly as if it had succeeded. In
`cowhide_banking.yaml` the inner loop covers *only* the kill batch; the other 22
steps had zero handling. A single bridge-hop timeout could cascade the character
through the entire staircase-climb / bank / return leg, none of it working, before
the once-per-pass wraparound had any chance to self-correct. Worst case: a whole
field↔bank cycle silently wasted.

**The fix — `475977f`:** a backward-compatible per-step `on_failure` key in the
routine engine (`mcptools/tools/routine.py`), parsed by `_parse_on_failure`:

- `continue` (default — identical to today's behavior: log and proceed)
- `abort` — stop the run, record why
- `retry:N` / `{retry: N}` — re-send up to N times, then abort

Steps without the key parse as `continue`, so no existing routine changed
behavior. `on_failure` was registered in `LIVE_STEP_KEYS`, documented in
`ROUTINE_SCHEMA.md`'s step reference, and covered by `tests/test_on_failure.py`
plus validator tests.

**Applying it to the actual money-makers — `7a47812`:** the banking steps had the
*weakest* Python-side resilience of anything in the file (no `await_condition`
meant no retry-at-2x path at all), which is a bad property for the three steps that
are the entire economic point of the routine. `cowhide_banking.yaml` now gives the
bank leg real teeth: `BANK_DEPOSIT_ALL` awaits `inventory_count:<=0` (verifies the
inventory actually emptied) with `on_failure: abort`; `BANK_OPEN` uses
`on_failure: retry:2` (no bank-open await atom exists in the engine vocabulary, so
re-send then abort); `BANK_CLOSE` gets `on_failure: abort`. The audit's other
findings were closed in the same commit: the return-leg's ~38-tile diagonal was
split back into two short hops (restoring the DEFECT-21 anti-corner-cut symmetry by
mirroring outbound waypoint `3247,3235`), the DOOR RISK header note near
`(3218,3217)` was extended to cover the identical return leg, a staircase waypoint
was reconciled `3205,3209 → 3205,3208`, and `chicken_feathers.yaml`'s step-3
timeout was resized to 6h to match the real `kills:1000` config it references
(the description had claimed 100).

The audit's low-priority validator false-positive (a non-terminal `KILL_LOOP`
warning firing on the correct nested inner/outer pattern) was fixed separately in
`71e004b` — `_is_nested_inner_loop_body` now suppresses the warning only when the
step is a single inner-loop body with real `exit_conditions` + `on_exit`; genuine
flat-loop non-terminal cases still warn.

---

## 2. The full corpus triage → 21 routines fixed + a validator that lied

With the money-makers hardened, the same treatment went to everything else: a
read-only triage of all 41 routines outside `money_making/`
(`journals/CORPUS_VALIDATION_TRIAGE_2026-07-19.md`), reviewed by six parallel
streams against `ROUTINE_SCHEMA.md`. The method was to run the validator as a
baseline, then hunt the *silent* stuff the validator misses — the 48 findings
graded HIGH/MED/LOW plus 4 validator (tool) bugs.

**The validator itself had to be fixed first (`8a8d3e9`)**, because a lying
validator distorts every other judgment:

- **V-1:** `validate_routine_deep` rejected the legal optional trailing `exact`
  token on GOTO — which `GotoCommand.java` explicitly parses and strips — making
  the one and only "failing" file in the corpus
  (`05_cooking_to_quest_guide.yaml`, a live-validated routine) a false positive.
  Now accepts both `x y plane` and `x y plane exact`.
- **V-2:** `_routine_is_non_executable` returned true for *any* file containing a
  `manual_steps:` block, mislabeling `utility/death_escape.yaml` (12 real steps +
  a doc block) as non-executable. Now it only exempts `manual_steps`-only files.

Then the routine fixes landed in two commits. **`86ac7b4`** took the HIGH findings:
`woodcutting_lumbridge.yaml` had no `loop:` block at all despite a comment claiming
"continuous" grinding — it ran exactly once; added the flat loop.
`superheat_mining_guild.yaml` targeted a members-only/unreachable iron-rock cluster
`(3030,9720)` that a sibling file already documented as broken — retargeted to
`(3029,9739)` and added a `no_item:Iron ore` await on the superheat cast.
`mining_falador_iron.yaml` and `hill_giants_restock.yaml` had always-true `plane:0`
staircase awaits that pass on the first poll whether or not the click worked —
replaced with awaits that verify the underground landing.
`hill_giants_loot.yaml` looted a giant that was still alive (a 1s attack action
followed immediately by pickup steps) — replaced the whole manual loop with
`KILL_LOOP_CONFIG` + a loot-config JSON.

**The dialogue-drain lesson.** Five quest files (`romeo_and_juliet`,
`sheep_shearer`, `imp_catcher`, `restless_ghost`, `cooks_assistant`) each drained
multi-page dialogue with a single unconditional `CLICK_CONTINUE`, guaranteeing
either a hang-to-timeout or a no-op that silently skips the quest-start option.
The important subtlety, learned from a live-validated correction (DEFECT-24): the
monologue drains use a **BLIND fixed-count repeat + `await:dialogue`**, *not*
`repeat_until:no_dialogue` — because the `no_dialogue` check-first pattern
false-closes mid-monologue when the state file misreports dialogue as closed
between pages. Stable item predicates (e.g. `Cadava potion`) keep `repeat_until`.
`sheep_shearer` also had an off-by-one: `inventory_count:>=20` went true at 19 wool
+ 1 shears (shears occupy a slot), one wool short of the quest requirement — fixed
to `>=21`.

**`a113495`** swept the MED/LOW tail: `chicken_killer_training` timeout raised
1h→2h for its 200-kill batch; the six `hill_giants_restock` withdraw delays bumped
300ms→4000ms (Withdraw-X quantities cannot round-trip in 300ms and were silently
producing a wrong loadout); a `BANK_DEPOSIT_ALL` added before the
`hill_giants_resupply` restock so a part-full inventory can't corrupt the loadout;
`flour_milling`'s instant-pass `idle` await on a stationary Operate replaced with a
calibrated delay; and a handful of comment corrections that had recommended the
exact patterns the files' own fixes forbid.

**One routine was honestly marked non-executable, not "fixed":**
`utility/gravestone_retrieval.yaml` has no `steps:` key — only `manual_steps:`
prose — so `run_routine.py` returns "Routine has no steps" immediately. Rather than
fake a `steps:` block against placeholders that no state predicate can yet resolve,
it was left documented as a manual runbook. Honest beats broken.

`ROUTINE_CATALOG.md` and `TRACK_G_PROTOCOL.md` were updated (`57afd25`) to reflect
the pass and to annotate the now-banned account line.

---

## 3. Ban-detection redesign — after two dead approaches

The plugin has to recognize at login that an account is banned and STOP — instead
of misreading the ban dialogue as "world busy" and hammering five worlds before
giving up. Two prior approaches were already dead
(`journals/BAN_DETECTION_REDESIGN_2026-07-19.md`):

- **Widget text scan** (`getWidgetRoots`) — FAILED: the ban dialogue is
  *rasterised to the canvas*, backed by no text widget.
- **Reflection over the client's String fields** — FAILED at the live gate: the
  scan returns len=0, because the ban text lives in no scannable String field.
- **Hardcoded `loginIndex` 10→14 magic number** — BRITTLE: `loginIndex` is
  undocumented above 4 and drifted 10→14 between client revisions. A false
  terminal latch would brick a healthy login.

Root cause: RuneLite exposes only `getLoginIndex()` (the login *screen* state,
which drifts) — no login-response byte, no login-message string, no login-error
event. The redesign's insight: the only reader immune to obfuscation, field drift,
and index drift is one that reads the *pixels* — which manny already has.

**Java half — `manny 93dae33`:** ripped out the reflection scan
(`scanClientStringFields`, `readLoginResponseViaReflection`, the `STRICT_*`
patterns) and the hardcoded 10→14 signature. In their place, a **persistence
heuristic** in `WorldSelector.switchToF2PWorld`: a non-`{2,4}` login index that
persists across ≥2 consecutive world-hop attempts without ever reaching
`LOGGED_IN` latches terminal-suspect and stops hopping. It keys only on the two
*documented, stable* form indices (2 = username form, 4 = authenticator) — no magic
number. `GameEngine.java` now exports a `login` section in the state file
(`game_state`, `login_index`, `terminal_login_failure`, `login_failure_message`)
so the driver is no longer blind between launches. The widget phrase match stays as
a tertiary helper; the bounded-hop cap stays as backstop.

**Python half — `manny_mcp 89f33ff`:** a vision-confirm-then-STOP chain. The driver
consumes the new `login` section (`get_game_state(fields=["login"])`) and, on a
suspected login-terminal signal, vision-confirms via `analyze_screenshot`
(PRIMARY — Gemini reads the rasterised text regardless of client version) and STOPs
the run cleanly — never relaunch, never world-hop, never retry.
`stuck_detector.py` gained pure, testable `classify_login_state` /
`parse_vision_verdict` / `apply_vision_verdict` plus a driver-side persistence
backstop (a non-`{2,4}` error screen held past 30s). `watchdog.py` got a
`suspected_ban` terminal path that SIGTERMs the run like a thermal kill and marks
it `needs_attention`. Crucially, a missing `login` section (a pre-22b plugin)
classifies as NORMAL — backward compatibility is mandatory, and 32 offline tests
include old-plugin fixtures to prove it. The full suite was at 288 passing after
this commit.

Both halves are offline-complete; only a **zero-risk live login gate** remains
(one login attempt on an already-banned alias, capture the signals, stop — a banned
account cannot log in, so risk is genuinely zero).

---

## 4. Nav data pipeline — a refresh that could brick itself

The vendored pathfinder data (Skretzo's collision map + transports TSV, pinned by
sha256 in `DATA_MANIFEST`) carried no *runtime* integrity check. Both loaders fail
silently-soft: a truncated zip makes areas quietly un-walkable, and a re-ordered
TSV column silently drops or mis-parses transports — bad nav data that looks
healthy (`journals/NAV_WP6_DATA_REFRESH_SCOPE_2026-07-19.md`).

**Runtime guard — `manny be87b99`:** `ShortestPathEngine` now reads the resource
bytes, sha256s them, and verifies against a bundled `data.fingerprint`; a mismatch
refuses to serve and degrades to legacy nav (`getInstance()` → null). Layered on
top is a manny-owned `FORMAT_VERSION` constant, structural count bands, and a
**canary-row probe** — the Lumbridge `Large door 12349` row must still parse to the
same menuOption/menuTarget, so a moved column makes the canary mis-parse and throw
at load. A missing fingerprint is non-fatal (verdict `unverified`) so a fresh
checkout still loads.

**The self-brick bug — fixed in `manny 21468c0`:** here's the one that would have
bitten quietly. `refresh_pathfinder_data.sh --apply` copied new data but *left the
fingerprint stale* — so the `be87b99` guard would then refuse to serve the very
data the refresh just applied, silently falling back to legacy until someone
hand-regenerated the fingerprint. The `--apply` path now regenerates
`data.fingerprint` (sha256 + byte counts + upstream ref, preserving the
hand-maintained `FORMAT_VERSION`). A new `--verify` flag runs the ~95-assertion
offline harness (PathfinderVerify + NavShadowVerify + NavGraphVerify) against the
freshly applied data and, on any failure, reverts all four files (collision map,
TSV, manifest, fingerprint) and exits non-zero. A latent `set -euo pipefail` bug
surfaced during this work too: `diff` exits 1 when it finds differences (the normal
case for a real refresh), which aborted the script before it ever reached the apply
block — it had never bitten only because the pin had stayed current. Verified in an
isolated `/tmp` sandbox (a bogus RUNELITE_ROOT correctly reverts; the real
compiled classes pass all 95 assertions); the tracked `pathfinder/` tree was
confirmed `git status` clean before and after.

**Build wiring — `manny_mcp d91c409`:** `install_pathfinder_resources.sh` was
invoked by no build path, so a re-cloned tree could ship without pathfinder data
(which the new runtime guard would then refuse). `handle_build_plugin` in
`mcptools/tools/core.py` — the single chokepoint every build flow passes through —
now runs the staging script before gradle, using `MANNY_ROOT` and `RUNELITE_ROOT`
from config (no hardcoded paths); a missing script or nonzero exit aborts the build
and surfaces the error. This commit's `tests/test_build_plugin_pathfinder.py`
carried the suite to its final **295 passing**.

---

## 5. Deploy prep — jar built, provisioning deliberately not done

diort's live jar predates the current manny HEAD, so a clean shaded jar was built
from `21468c0` for whenever the user greenlights a deploy
(`journals/TRACK_G_PREFLIGHT_RUNBOOK_2026-07-19.md` B4). The build followed the
stash-around-parked-edits procedure exactly (see below), then:

```bash
cd /home/wil/Desktop/runelite && ./gradlew :client:compileJava :client:shadowJar \
  -x checkstyleMain -x pmdMain --console=plain    # JDK21 pinned
```

Result:
`/home/wil/Desktop/runelite/runelite-client/build/libs/client-1.12.34-SNAPSHOT-shaded.jar`,
40,085,984 bytes, sha256
`29bc3607d3068973e8ae9218a4fad2d4b26cb4a823f394e0a003374554868c2a`. Spot-checked:
434 manny plugin classes present; pathfinder resources (`collision-map.zip`,
`transports/transports.tsv`, `data.fingerprint`) present; and — the check that
matters — the parked experimental `CameraDrift` class **confirmed absent**, so the
parked code did not leak into the artifact. Provisioning to diort was **not** done:
that awaits user approval, and no automated session makes that call.

---

## The recurring discipline: parked edits, stash-around-build, scoped commits

Both working trees carried half-written, **user-owned** edits that must never be
committed and never be built against. The `manny` tree literally does not compile
with them applied (a prior agent was killed mid-file, leaving `CameraDrift` missing
helpers that `KillLoopCommand` already calls). So every Java build today wrapped
the parked paths in a stash:

```bash
cd /home/wil/Desktop/manny
git stash push -u -m "parked edits" \
  utility/CameraDrift.java utility/commands/KillLoopCommand.java utility/HumanizeVerify.java
# ... build / commit the real change ...
git stash pop    # restore the parked edits
```

On the Python side the equivalent discipline was **scoped commits only** — every
`git add` named explicit paths, never `git add -A` — so the parked
`mcptools/humanize.py`, `tests/test_humanize.py`, an uncommitted
`mcptools/tools/routine.py` hunk, and several in-flight journals stayed unstaged
across the whole sweep. The rule these edits live under is a deliberate scope
boundary, not an oversight, and this journal follows it too.

---

## Where it stands

- **Landed and pushed:** `manny_mcp` `a6e6191..d91c409` (engine `on_failure`,
  money-maker + corpus fixes, validator fixes, ban-detection Python half, nav build
  wiring); `manny` `e56ba40..21468c0` (ban-detection Java half, nav runtime guard +
  `--verify` refresh flow). Tests 248→295 in `manny_mcp`.
- **Ready, not deployed:** the clean `21468c0` shaded jar — verify its sha256 and
  provision it *once the user approves*.
- **Standing blocker (USER):** the proxy/IP posture and account decision for
  resuming any live/unattended grind. Nothing in the Track G sequence unblocks
  until then. `main` stays hard off-limits; `new`/`newbakshesh` are banned and exist
  only for the zero-risk ban-detection login gate.
- **Next offline-safe step:** the zero-risk live login gate to close out DEFECT-22b
  B3 (one attempt on an already-banned alias, capture, stop).
