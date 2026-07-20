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
