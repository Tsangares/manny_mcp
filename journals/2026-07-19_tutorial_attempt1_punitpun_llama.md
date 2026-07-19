# 2026-07-19 — Tutorial Island attempt #1: `punitpun` on llama — s01-05 clean, one desync poisons everything after

**Author:** live supervisor agent (overseer-tutorial umbrella). **Account:** `punitpun` (fresh),
display auto-allocated `:4` on llama (brabra, direct residential egress per user decision).
**Chain:** `routines/tutorial_island/00_master.yaml`, run `20260719T181857Z_punitpun`,
T0 18:18:57Z, declared exhausted 19:42Z (~83 live minutes of a 4h window).
**Outcome:** mainland NOT reached. Sections 01-05 passed first-contact in ~23 minutes — the best
clean streak the tutorial chain has ever produced. Section 06 false-passed (game did not advance),
and every subsequent section failed as a cascade of that single desync. No ban signals at any point.

## The headline lesson

**The chain's failure mode is not "a section fails" — it is "a section false-passes and the chain
keeps going."** s07 and s08 burned 42 blind minutes clicking at rocks that weren't there because
s06 never completed *in the game*, only *in the runner*. The runner's per-step error signals
(`repeat_until` caps, `Item not found`, MENU-VERIFY mismatches) fired dozens of times and none of
them stopped or even flagged the section. Everything below follows from this.

## Root causes found (in causal order)

### 1. Provisioning gap: `mannyctl run` reads `config.yaml`, which ships laptop paths
Launch 1 (`...181258Z`) died in seconds: `java_path: /usr/lib/jvm/java-21-openjdk/bin/java` does
not exist on llama (system OpenJDK 26 at `/usr/bin/java`). Launch 2 (`...181631Z`) booted java but
with the **stale untrusted jar** `/home/wil/runelite.jar` (sha `0a2556ab…`), because the Gradle
auto-detect path (`runelite_root/runelite-client/build/libs`) is empty on llama and the fallback
`runelite_jar` in config.yaml pointed at the stale artifact — NOT the smoke-tested
`~/Desktop/runelite-client-libs/client-1.12.34-SNAPSHOT-shaded.jar` (sha `054d6298…`).
`hosts.yaml` has the correct `jdk:` and `runelite_libs:` for llama, but **only `mannyctl start`
uses hosts.yaml; `mannyctl run` → `run_routine.py` → `ServerConfig.load()` → `config.yaml`**,
which `provision.sh` ships as-is (its own comment admits this). The smoke test used `start`, so
the gap was invisible until the first real `run`. Fixed live on llama only (java_path →
`/usr/bin/java`, runelite_jar → the shaded jar; backup at `/tmp/config.yaml.bak-*`).

### 2. s06 false-pass: dialogue-desync with no in-game completion gate
The chain's s06 issued its Quest Guide steps, the runner marked the section passed, and the game
overlay still read "speak to the Quest Guide" (screenshot evidence). Likely ordering gate: the
routine opened the quest journal tab out of the order the tutorial's varbit progression expects.
The section has no await on the tutorial-progress varbit/overlay, so the chain marched into s07.

### 3. `GOTO` cannot traverse cross-plane transports (ladder), and fails SILENTLY
With the game later genuinely at the "climb down the ladder" stage (gate open), a fresh s07 run
issued `GOTO 3080 9504 0` (underground) for 8.5 minutes and the player did not move one tile from
(3088,3118). The walker has no ladder/transport knowledge and does not report failure — the
routine's steps blind-advance on their timeouts. Every underground section (07-10) is unreachable
by routine unless the preceding section's explicit ladder INTERACT succeeds.

### 4. Ladder INTERACT fails on reachability, and the section still reports SUCCESS
Both s06 resume runs ended runner-status SUCCESS while logging "Step 9 (CLICK_WIDGET): Could not
click widget" and the game showing "I can't reach that!" on the ladder click (player stood outside
the house wall; interact-by-name with no position pin — the exact bug class the 07 routine's own
authoring note warns about). **A routine that logs a failed step and exits SUCCESS is the same
defect as #2 wearing different clothes: step errors don't propagate to section status.**

### 5. Auto-restart spawned a second client without killing the first
At 19:19Z (60 min in) the client disconnected mid-s08-churn (cause unknown; relogin by the
original client eventually succeeded). The runner's recovery escalated to "full restart" and
launched a **second** java client while the first was still alive — two clients then shared
display `:4` and the account's state/command IPC, and the runner sat in an infinite
"Client disconnected (status=LOGGING_IN), attempting relogin..." loop. New defect class:
`auto-restart-double-client`. (Kin to DEFECT-30's orphaned-loop lesson: recovery paths must own
and reap the process they replace.)

### 6. Supervision friction worth fixing (harness-side, not manny-side)
`run_routine.py`'s stdout is block-buffered when detached — section-transition lines only flush at
process exit, so the "runner log" is useless for live section tracking. Live truth had to come
from the state file, client log, and screenshots. A `flush=True` on the chain's prints (or
`PYTHONUNBUFFERED=1` in mannyctl's detach line) makes the ledger/log actually supervisable.
Also: the first-boot "Client crash detected (attempt 1/3)" is a premature health-check firing
before the client finishes booting — it cried wolf on every launch and then masked the real
double-client event when it mattered.

## What went RIGHT (do not lose this)

- **s01-05 first-contact clean at ~23 min** on a fresh account: character creation, experience
  selection, Gielinor Guide, survival expert, woodcutting/firemaking, cooking — inventory evidence
  (net/shrimps/axe/tinderbox/bread/pot/bucket) confirms real in-game completion, not false-passes.
- Thermal: llama never warmed (loadavg ~0.3, no temp warnings across 83 min). The 6C/12T box is
  massively over-provisioned for one client — good lane-2 headroom.
- No ban signals across the whole window (terminal_login_failure false throughout; the one
  disconnect recovered by normal relogin). Session ran ~60 min before the disconnect.
- The account-scoped stop path (`mannyctl llama stop punitpun`) correctly reaped BOTH duplicate
  clients by account.

## Recommended offline fixes, ranked by leverage

1. **Propagate step failures to section status, and gate tutorial sections on the game's own
   progress signal** (overlay text / tutorial varbit / hint arrow) rather than step completion.
   One await-condition primitive (`tutorial_stage:N` or `overlay_contains:`) kills root causes
   #2 and #4 and prevents every future cascade. This is the single highest-leverage change.
2. **Make cross-plane GOTO either work (ladder transport in the walker) or fail loudly.** A GOTO
   whose target plane/region differs from the player's and whose position hasn't changed in N
   ticks must return failure, not let the step timeout absorb it (#3).
3. **Fix auto-restart to kill-then-spawn** (reap the old client PID, verify it is gone, then
   start one replacement, once) (#5). Cheap fix, prevents IPC poisoning of every future long run.
4. Provisioning: make `provision.sh` render a host-correct `config.yaml` (java_path, runelite_jar
   from hosts.yaml fields) instead of shipping the laptop file (#1) — or make `run_routine.py`
   accept the same host overrides mannyctl already knows.

## Open items

- punitpun is parked mid-island at the "climb down the ladder" stage — a resumed attempt #2 can
  start at s06's ladder step (with a position pin) and get first-contact data on 07-10 including
  the DEFECT-29 equip retest that this attempt never legitimately reached.
- Why the 19:19Z disconnect happened is unestablished (60 min mark; no ban screen; relogin
  succeeded). Watch whether attempt #2 disconnects at a similar session age.
- Artifacts (ledgers for all 6 runs, runner/client logs, location histories, 5 screenshots,
  command session yaml) preserved in the supervisor scratchpad `attempt1/`; screenshots worth
  keeping long-term should move to `journals/images/`.
