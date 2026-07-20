# Mainland session #1 (task #22) — judeaislam/diort — GATE 3 (display) blocked launch, zero live minutes

**Verdict: no live client was ever launched — the session terminated at the mannyctl `window`
ceremony's GATE 3 (display), before GATE 4 (provision), GATE 5 (launch), or GATE 6 (run).** This is
an honest, designed-for abort, not an improvisation target: `hosts.yaml` has an explicit
`account_displays` mapping for `judeaislam` only under the **llama** host block (`judeaislam: ":8"`,
line 109), not under **diort** (lines 64–87: only `newbakshesh`, `blast`, `new`, `punitpun` are
mapped there). The brief specified diort as host (llama is busy driving a different account's
tutorial run). GATE 3 exists precisely to refuse an unmapped account rather than let it fall back to
diort's physical `:2` desktop (the #3b/#4 hijack lesson in MANNY_OVERSEER.md) — it did its job. Per
the brief's own launch-sequence instruction ("If ANY gate fails, capture the exact error, stop,
report as terminal. Do not improvise around a gate"), no attempt was made to patch `hosts.yaml`,
retry on llama, or otherwise route around the failure. Zero hand-driven game actions (target was 0;
actual 0/0) — no game client process ever started, so no client log, no screenshot, no run ledger,
no watchdog attach exist for this session.

## Preflight (all passed)

1. `git log --oneline -2` — HEAD = `f604757` (one commit ahead of the expected `1f91a80`; `f604757`
   is `1f91a80`'s immediate child, "tutorial attempt 15" journal/CSV commit — no code/routine
   drift, so preflight proceeded).
2. `./run_routine.py --dry-run routines/mainland/00_fresh_account.yaml --account judeaislam` —
   **PASS**. Both chain members simulated clean:
   - `arrival_ritual_bank_gear.yaml`: 7/7 steps, simulated wall-clock 7.7s, ends at
     `(3235,3295,0)` — equip sword, equip shield, GOTO Draynor (3093,3243), BANK_OPEN,
     BANK_DEPOSIT_ALL (`inventory_count:<=0` await satisfied), BANK_CLOSE, GOTO coop.
   - `combat_chickens_to_10s.yaml`: 11/11 steps, one rotation (`--loops` unset → 1 pass),
     simulated wall-clock 7.6m, stop reason `reached max_loops (1)` (the dry-run fixture doesn't
     model XP accrual to a real `defence_level:10`, so this stop reason is expected/benign for a
     single-pass dry-run).
   - Dry-run's own caveat stands: sequencing/awaits/loops only, no coordinate-reachability,
     collision, or NPC/widget-availability check — "necessary, not sufficient."

## Launch attempt (terminal)

```
$ scripts/remote/mannyctl diort window judeaislam routines/mainland/00_fresh_account.yaml
=== mannyctl window: judeaislam -> routines/mainland/00_fresh_account.yaml on diort (nav=shadow) ===
WINDOW_GATE 1 predecessor-dead PASS: no java client / run_routine.py / watchdog.py driving 'judeaislam' on diort
WINDOW_GATE 2 credentials      PASS: alias 'judeaislam' present, default='punitpun' (not banned); creds synced to diort (600)
WINDOW_GATE 3 display          FAIL: 'judeaislam' has NO account_displays mapping for 'diort' in hosts.yaml — refusing (an unmapped account would hijack the host's physical ::2 desktop). Add 'judeaislam: ":N"' under hosts.diort.account_displays.
=== WINDOW SUMMARY (host=diort account=judeaislam routine=routines/mainland/00_fresh_account.yaml nav=shadow dry=0) ===
WINDOW_RESULT gate1=PASS gate2=PASS gate3=FAIL gate4=SKIP gate5=SKIP gate6=SKIP
WINDOW_RESULT overall=FAIL
```

Exit code 1. Gates 4–6 (provision, launch, run) never ran — no jar deploy, no client process, no
IPC files, no run_id was assigned. Nothing to stop (`mannyctl diort stop judeaislam` was not
applicable — nothing was started; not run, per the safety rails' scoped-stop instruction which only
applies to a live process).

## Per-question findings (task #22 brief)

1. **Arrival ritual survival, DEFECT-33 blast radius, chicken combat, mainland nav quality** — **not
   measured this session.** No client reached Lumbridge, so none of the live-contact questions
   (equip steps, the ~130-tile Lumbridge→Draynor leg, Draynor bank deposit-all / DEFECT-33 false-negative
   exposure, chicken re-engage/level-up/stance-rotation behavior, door/gate handling) could be
   exercised. This is the headline gap for the mission's stated purpose.
2. **NAV_BACKEND / shadow-mode availability** — confirmed trivially available without any code
   change: `mannyctl <host> window` defaults `nav="shadow"` (`scripts/remote/mannyctl:546`), and the
   GATE 5 dry-preview line explicitly names it (`client_remote.sh start ... (NAV_BACKEND=shadow)`,
   line 702). Had the launch reached GATE 5, shadow-mode nav logging would have been active for both
   travel legs by default — no flag needed. This part of the brief is answered even though the run
   never got there: the infrastructure question has a clean "yes, on by default" answer.

## Defect harvested

**Host/account mapping gap: `judeaislam` has an `account_displays` entry only on `llama`
(`:8`, `hosts.yaml:109`), not on `diort`.** The task brief assigned diort specifically because llama
was occupied by a different account's tutorial lane — but the routing data needed to actually honor
that host choice for this account was never populated. This is a coordination/provisioning gap
between campaign task assignment and `hosts.yaml`, not a code defect in GATE 3 itself (GATE 3 is
working exactly as designed — MANNY_OVERSEER.md's #3b/#4 hijack lesson is precisely why it refuses
rather than falls back). Fix is a one-line addition to `hosts.yaml` under `hosts.diort.account_displays`
(e.g. `judeaislam: ":N"` for an unused diort display number — `:2` is diort's physical desktop and
`:3`,`:4`,`:5` are already claimed by `blast`/`new`/`punitpun`, so `:6` or higher is free) — deliberately
NOT made in this session per "do not improvise around a gate."

## Hand-driven action count

**0 / target 0.** No gameplay commands, clicks, walks, interactions, or dialogue were sent — no
client process ever existed to send them to.

## Timeline / state

No varp, skill, or position data to report — judeaislam's state is unchanged from the prior
checkpoint (Lumbridge spawn ~3221,3218, varp-281 = 1000, per `OVERSEER_HANDOFF.md`). Total elapsed
wall-clock for this session: preflight + one launch attempt, well under a minute of actual command
time; no live client minutes accrued.

## Recommendation for the next attempt

Add `judeaislam: ":<free-number>"` under `hosts.diort.account_displays` in `scripts/remote/hosts.yaml`
(a desk fix, zero live risk), or reissue task #22 against `llama` once its current tutorial lane
frees up (llama already has `judeaislam: ":8"` mapped and ready). Either unblocks GATE 3 with no
further changes — GATE 1 (predecessor-dead) and GATE 2 (credentials) both already PASS for
judeaislam on diort, so once GATE 3 is satisfied the ceremony should proceed straight to
provision/launch.

---

# Session 1b (relaunch) — gate-3 config fixed, first LIVE mainland contact — honest abort at BANK_OPEN (new defect class)

**Verdict: the first live mainland routine contact ever. The arrival ritual survived its first
three steps — both equips passed, and the ~128-tile Lumbridge→Draynor navigation leg (the longest
nav ever attempted in this campaign) completed with one self-healed follower bail — then aborted
honestly at step 4: `BANK_OPEN` crashed all 3 attempts with
`java.lang.IllegalStateException: must be called on client thread`, a NEW defect class
(candidate DEFECT-34), NOT the anticipated DEFECT-33 `isBankOpen()` false negative (which was never
reached — the crash is upstream of any oracle check). Zero hand-driven game actions. Chain stopped
at section 1/2; chickens never reached. ~4.5 live routine minutes.**

## The gate-3 → config-fix → relaunch sequence (this session's first harvested-and-fixed defect)

Session 1a (above) ended at the `window` ceremony's GATE 3: `judeaislam` had no
`account_displays` mapping for diort. The coordinator landed `7409b4e` ("hosts: map judeaislam to
diort :6") and the relaunch preflight re-verified: HEAD `7409b4e`, dry-run of the chain still PASS
(7 + 11 steps). The relaunch ceremony then passed **all six gates**: predecessor-dead, credentials
(default=punitpun, not banned), display (`:6` explicit), provision (jar `421c03e91ff9e82b`,
routine.py clean, parked files stashed/popped/verified), launch (login 25s, DEFECT-32 gate PASS,
LOGGED_IN at 3221,3218,0), run (detached + watchdog). Harvest #0 for the session: the task-assignment
→ hosts.yaml routing gap, found by the gate exactly as designed, fixed at the desk in one line, and
retired for every future diort session of this account.

- Run ID `20260720T053755Z_judeaislam`, ledger `/tmp/manny_runs/20260720T053755Z_judeaislam.json`
  (on diort), client pid 2765180 on display :6, nav backend **shadow** (window default).

## Timeline (UTC, receipts from /tmp/runelite_judeaislam.log + run log + ledger)

| Time | Event |
|---|---|
| 05:37:30 | Client launch (`-Dmanny.navBackend=shadow` confirmed in JVM args line) |
| 05:37:55 | LOGGED_IN at (3221,3218,0) — Lumbridge spawn, varp-1000 graduate parked there |
| 05:37:58 | run_routine + watchdog up; one boot NPE logged (known benign mcptools crash signature, same as tutorial attempts 13–15; client stayed alive) |
| 05:37:59–05:38:03 | Steps 1–2: `equip_item` Bronze sword, then Wooden shield — SCAN_WIDGETS found both with "Wield" actions; both equipped (outcome-verified path, DEFECT-29); run proceeded |
| 05:38:04 | Step 3 GOTO 3093,3243 — start (3221,3218), distance 128 tiles |
| 05:38:07 | **NAV-SHADOW**: `graph=FOUND steps=147 walk=145 transport=2(doors=2,stairs=0) legacy=api/globalAStar firstDiverge=@0 graphUs=55995` |
| 05:38:10–05:38:54 | Minimap hops ~1/s, clean westward progress (~123 tiles in ~50s) |
| 05:38:55 | GOTO bailed: "stuck or timeout: ended at (3098,3244,0), 5 tile(s) from target" — 5 tiles short of the bank after covering 96% of the leg |
| 05:38:55–05:42:04 | Position pinned at (3098,3244); watchdog `stall_detected` at 05:41:58 ("zero progress for 180s") |
| 05:42:04 | Engine re-sent GOTO (new rid, exactly at the step's 240s await boundary); NAV-SHADOW: `steps=13 legacy=directional graphUs=400` |
| 05:42:11 | GOTO succeeded (within 1 tile) — step 3 PASS, self-healed at the cost of ~3.2 idle minutes |
| 05:42:11 | Step 4 BANK_OPEN #1: CACHE-FIND found 'Bank' (object 10355) at (3091,3242), 2 tiles away — then `IllegalStateException: must be called on client thread` |
| 05:42:13–14 | Retries 1/2 and 2/2: byte-identical failure |
| 05:42:14 | `strict_steps` abort: "Step 4 (BANK_OPEN) failed after 2 retries"; chain FAILED honestly at section 1/2 |
| 05:42:58 | Watchdog: run pid exited, status=dead (clean, not forced) |
| 05:44 | Screenshot at Draynor (below); 05:47 `mannyctl diort stop judeaislam` (SIGTERM, PID-scoped) |

Screenshot: `journals/images/2026-07-20_judeaislam_mainland_s1b_draynor_bankopen_fail.png`
(residential-IP overlay redacted with a black bar before commit). Shows the player at the Draynor
bank plaza, starter kit in inventory minus the equipped sword+shield, session clock 00:06:11.

## Per-question findings

### 1. Arrival ritual first-contact survival: 3 of 7 steps proven
- **Equips (steps 1–2): PASS.** `equip_item` handled both items in ~4s total, no manual tab work.
- **Lumbridge→Draynor leg (step 3): PASS with one harvested nav defect.** See §4.
- **Deposit-all (steps 4–6): NOT REACHED as designed** — BANK_OPEN crashed before any bank UI
  existed. **Return leg (step 7): NOT REACHED.**

### 2. DEFECT-33 blast radius: NOT MEASURED — a deeper defect sits in front of it
The known `isBankOpen()` false negative never got the chance to fire: `BANK_OPEN` dies before
opening anything. New defect, **candidate DEFECT-34**:

```
[BANK_OPEN] Opening nearest bank
[CACHE-FIND] ✓ Found 'Bank' at (3091, 3242) - 2 tiles away (cached for next time)
Found bank object: 10355 at (3091, 3242)
java.lang.IllegalStateException: must be called on client thread
    at du.getWorldLocation(du.java:36862)
    at net.runelite.client.plugins.manny.utility.BankingSupport.openNearestBank(BankingSupport.java:110)
    at net.runelite.client.plugins.manny.utility.commands.BankOpenCommand.executeCommand(BankOpenCommand.java:34)
```

Desk analysis (receipts, no fix attempted tonight): `BankingSupport.java:110` calls
`bank.getWorldLocation()` on the `manny-background-N` executor thread; RuneLite's TileObject
world-location accessor demands the client thread. **Why the tutorial never caught it: tutorial
section 09a never used `BANK_OPEN`** — grep of `routines/tutorial_island/09_banking.yaml` shows only
`BANK_CLOSE` (the tutorial bank opens via the section's own object-interaction steps). This was the
first live execution of `BANK_OPEN` in campaign history — a genuine first-contact truth about a
never-exercised primitive, exactly what this session was for. Repro cost: the bank-find cache path
succeeded (object located, 2 tiles), so the crash is deterministic at step 2 of the command, all 3
attempts identical. Fix shape (for the desk lane): wrap the world-location read (and any other
client-state reads in `openNearestBank`) in `clientThread.invoke`/`callOnClientThread`, same pattern
the other commands use.

### 3. Chicken combat / level-ups / stance rotation: NOT REACHED (section 2/2 never started).

### 4. Mainland navigation quality (first data ever off the island)
- **The 128-tile cross-country leg is 96% healthy at speed:** ~123 tiles in ~50s of continuous
  ~1/s minimap hops, no wrong turns, no door/gate/stile interactions needed on the executed
  (legacy `api/globalAStar`) route, no player-collision incidents (other real players visible in
  Draynor; routine correctly ignored them, as did the supervisor).
- **Harvested nav defect (known follower class, first mainland instance):** the greedy minimap
  follower bailed "stuck or timeout" 5 tiles short of the target at the Draynor bank approach
  (3098,3244 → 3093,3243) — inside the village, where building geometry crowds the minimap. The
  step then burned its remaining ~3.2-minute await window pinned in place before the engine's
  await-boundary re-send issued a fresh GOTO that cleared the last 5 tiles in 7s. Net: honest
  self-heal, no false pass, but ~70% of the leg's wall-clock was recovery latency. Candidate
  desk follow-ups: (a) find why the follower declared stuck at 5 tiles (the 3-tile plain-GOTO
  success slop nearly covers it — a 5-tile shortfall is the worst spot: too far to pass, too close
  for a vigorous re-path); (b) consider the engine re-send firing earlier than the full await
  timeout.
- **Second GOTO (5 tiles): clean**, `legacy=directional`, done in 7s.

### 5. Shadow-nav (graph backend) mainland data: CAPTURED — the mission's free payload
`--nav-backend` defaults to `shadow` in the window ceremony, so no config work was needed. Two
NAV-SHADOW receipts (first mainland graph-vs-legacy comparisons ever):
- 128-tile leg: `graph=FOUND steps=147 walk=145 transport=2(doors=2,stairs=0)
  legacy=api/globalAStar firstDiverge=@0 graphUs=55995` — the graph engine found a complete
  147-step mainland route in **56ms**, proposing a 2-door route where legacy walked around;
  divergence from the straight-line comparator started immediately (@0), consistent with a
  road-following path.
- 5-tile leg: `graph=FOUND steps=13 walk=13 transport=0 legacy=directional graphUs=400` — 0.4ms.
Graph-nav found paths on mainland collision data both times. That is the stage-2 shadow trial's
first mainland evidence: FOUND, fast, and plausible; door-transport preference vs legacy's
around-route is the thing to compare when shadow data accumulates.

## Anomaly log (not a defect verdict, needs desk follow-up)
Public chat shows **`judeaislam: *`** (visible in the screenshot chatbox) — the account said "*"
in public chat at some point this session, yet the driver sent NO TYPE/chat command (receipts: the
only keyboard activity in the client log is the login-phase camera-rotation KEY_PRESSED bursts from
LoginHandlers, and doctrine says KEY_PRESSED cannot enter chat, which consumes KEY_TYPED). Origin
unknown; a stray "*" in public chat is a (minor) detection surface and an unexplained input-path
leak. Desk task: find what emitted it (login handler? welcome-screen clicker keystroke? an AWT
synthetic event surviving as KEY_TYPED?).

## Bookkeeping
- **Hand-driven game actions: 0 (target 0).** Supervisor actions were: launch ceremony, read-only
  state/log polls, one screenshot capture, and the terminal `mannyctl diort stop judeaislam`.
  No relog needed, no stall-protocol restart used (the one stall self-healed inside the routine's
  own budget, per doctrine).
- No ban signals; ledger events: benign boot NPE, one stall_detected (the GOTO pin), clean exit.
- Varp/skills: varp-281 stayed 1000 (mainland); no combat, so no skill changes to report.
- Position trace: (3221,3218) 05:37 → (3155,3228) 05:38:34 → (3098,3244) 05:38:55–05:42:04 →
  (3093,3243) 05:42:11 → stopped there.

## Defect harvest list (session 1a + 1b)
1. **[FIXED]** hosts.yaml routing gap: judeaislam unmapped on diort → GATE 3 refusal → `7409b4e`.
2. **[NEW, open — candidate DEFECT-34]** `BANK_OPEN` thread-context crash:
   `BankingSupport.openNearestBank` (line 110) reads `TileObject.getWorldLocation()` off the client
   thread → deterministic IllegalStateException. First-ever live exercise of this primitive.
   Blocks ALL mainland banking via BANK_OPEN until fixed; DEFECT-33's blast radius remains
   unmeasured behind it.
3. **[NEW, open — nav-follower class]** 128-tile leg bail at 5 tiles short in Draynor Village;
   honest self-heal via await-boundary re-send but ~3.2 min recovery latency.
4. **[ANOMALY, open]** unexplained `judeaislam: *` public-chat line with zero TYPE commands issued.

## Next session unblock
Fix DEFECT-34 at the desk (client-thread wrap in `openNearestBank`), redeploy jar, rerun the same
chain — the ritual is proven up to step 4, so next contact should reach the deposit (and finally
measure DEFECT-33's blast radius on the same step).
