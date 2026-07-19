# 2026-07-19 — `newbakshesh` banned, all grinding halted, humanization promoted to prerequisite

**Author:** methods-adoption agent (post-incident writeup; no live client contact — the banned client
was read-only inspected over SSH for evidence). **Account:** `newbakshesh` (lane 1, display `:2` on
diort). **Second behavioral ban in two days** — see "the pattern" below.

## What happened

`newbakshesh` was running the `chicken_feathers.yaml` defence-training grind (Block stance, `KILL_LOOP`
on Chickens) as a **managed run** with a watchdog attached. That run (`20260719T065401Z_newbakshesh`,
started `06:54:03Z`) hit its `KILL_LOOP_CONFIG` step's `timeout_ms` (3,600,000 — one hour) at kill count
177 of a 1000-kill batch. The step timeout expired and `run_routine.py` exited — but the Java-side
`KILL_LOOP` it had launched **kept running on the client**, unsupervised. The watchdog correctly flagged
this: ledger status `unmanaged_loop` at `07:55:05Z`, "run pid 2402732 gone but active_loop still
present ... kills: 177". This is logged as a **DEFECT-30 candidate**: `run_routine.py` must *stop* the
loop it owns when its own await times out, not exit and abandon it running.

A relaunch followed immediately: run `20260719T075743Z_newbakshesh` started `07:57:45Z`, kill 1 of a
fresh 1000-kill batch — i.e. the account's **178th scripted chicken kill of the morning**, on an
unbroken, metronomic `KILL_LOOP` cadence going back through the orphaned first run.

**32 seconds later, `07:58:17Z`, the account was banned.**

It was not presented as a ban at first — the client threw five consecutive `[DISCONNECT-DETECT]` "Menu
shows only 'Cancel'" warnings, `CombatSystem` aborted combat to avoid an infinite retry, and `KillLoopCommand`
self-stopped ("killed 1/1000") — a clean, correct disconnect-handling response by the plugin. Only once
the ghost login-session cleared and the client returned to a real screen did the actual cause show:

![Ban screen — "Your account has been involved in serious rule breaking."](images/2026-07-19_newbakshesh_ban_screen.jpg)

**"Your account has been involved in serious rule breaking."** Jagex's standard behavioral-ban dialogue,
World 380, with "View Appeal Options" the only path forward. The screenshot above is the ban screen
itself — safe to keep (no account credentials, no session tokens, nothing personal). Local copy at
`journals/images/2026-07-19_newbakshesh_ban_screen.jpg`, originally captured to
`manny_mcp_lane1_scratch/frame.jpg`.

**Stats and loot lost with the account:** attack 8, strength 15, defence 14, hitpoints 16, and 2,720
Feathers banked from the grind. All of it now inaccessible pending appeal (not expected to succeed —
this campaign does not contest bans, per the user's "expendable accounts, iterate" posture).

## The pattern: this is the second behavioral ban in two days

- **`GrimmsFairly` (account alias `new`), banned 2026-07-18** — "serious rule breaking," on this same
  residential IP (diort, no proxy), no world-hopping/farming detected at the network layer.
- **`newbakshesh`, banned 2026-07-19** (this incident) — same ban text, same IP, same undisguised
  scripted cadence: a fresh F2P account running a sustained, metronomic `KILL_LOOP` for its entire
  played lifetime.

Two data points is not statistics, but the shape is identical both times: **fresh F2P account + hours of
uninterrupted, uniform-timing kill-loop + the same source IP as a prior ban.** The residential IP —
which the diort migration was explicitly banking on as a ban-risk mitigation — did not prevent either
ban. Detection here is behavioral, not IP-based.

## The infrastructure worked; the behavior didn't

The genuinely useful finding in this incident is what *didn't* go wrong. The managed-run/watchdog
machinery — built earlier in this campaign specifically to catch exactly this class of problem — worked
exactly as designed straight through the incident:

- It detected the first run's step-timeout abandonment (`unmanaged_loop`, `07:55:05Z`) instead of
  silently losing track of the loop.
- It correctly attributed the orphaned loop's kill count (177) and let us compute the "178th kill"
  figure precisely after the fact.
- The relaunch, the ban, and the ghost-disconnect sequence are all reconstructable second-by-second from
  the ledger (`/tmp/manny_runs/20260719T075743Z_newbakshesh.json`) and the client log
  (`/tmp/runelite_newbakshesh.log`) — nothing was lost, nothing had to be guessed.
- The banned client was left exactly where it died — up, logged into the ban screen, untouched — as
  appeal evidence, per standing incident doctrine (never touch a client mid-incident).

In other words: the supervisor detected, diagnosed, preserved evidence, and stood down cleanly. **The
infrastructure passed. The behavioral signature — the thing the infrastructure was never built to
address — failed.** That distinction is the actual lesson of this incident, and it's why the response
below is a behavioral pivot, not an infrastructure fix.

## The pivot

Effective immediately:

1. **All grinding is halted.** No unattended or attended `KILL_LOOP`-class routines run on any live
   account until humanization lands. This includes Track G (the milestone's 4-hour unattended proof),
   which is explicitly deferred, not cancelled.
2. **Humanization is promoted from "post-milestone nice-to-have" to prerequisite.** The methods
   retrospective (`journals/2026-07-19_methods_retrospective.md`, written a few hours before this ban)
   had already flagged this as risk item #5, sequenced "post-Track-G, before scaling." That sequencing
   is now inverted: humanization comes *before* any further unattended or sustained-grind live contact.
   Scope (unchanged from the retrospective, now just re-prioritized): inter-action timing jitter from
   sampled distributions (not fixed delays), click-point variance within hulls (not always the hull
   centroid), reaction-delay modeling, occasional camera drift, and scheduled micro-breaks integrated
   with the watchdog. This is being built in the Java tree now (`manny` repo — out of scope for this
   agent's git tree, tracked via the handoff).
3. **IP diversity is planned as a second-layer mitigation**, not a replacement for humanization: routing
   future accounts through mat + a proxy, so a ban on one account doesn't share fate with the ones
   still running. Not yet implemented.
4. **`blast` (lane 2) becomes the humanization guinea pig** once the Java work lands — it's mid-tutorial,
   not yet grinding, and was already parked cleanly at (3111,9525) with a dagger equipped, blocked on
   DEFECT-29 (see `OVERSEER_HANDOFF.md`). It resumes under humanized primitives, not the old ones.
5. **`punitpun` stays clean.** A fresh spare credential was added specifically to have an unburned
   account once humanization is ready to prove itself; it is not to be used for anything before then.
6. **Track G is deferred, not cancelled**, until the primitives it would exercise unattended are
   humanized. Running the milestone's flagship unattended proof on robotic timing would be the single
   worst place to find this out.

## Evidence index

- Ban screenshot: `journals/images/2026-07-19_newbakshesh_ban_screen.jpg`
- Watchdog ledgers (diort, `/tmp/manny_runs/`): `20260719T065401Z_newbakshesh.json` (orphaned run,
  `unmanaged_loop` at kill 177 / iteration 191, `07:55:05Z`) and `20260719T075743Z_newbakshesh.json`
  (relaunch, `unmanaged_loop` again at `08:03:45Z` after the ban had already landed)
- Client log (diort, `/tmp/runelite_newbakshesh.log`): `[DISCONNECT-DETECT]` sequence and
  `KillLoopCommand` self-stop at `07:58:28Z` PDT-adjacent timestamps
- Last known player state (diort, `/tmp/manny_newbakshesh_state.json`, timestamp `07:58:17Z`): attack 8,
  strength 15, defence 14, hitpoints 16, Feather ×2,720
- The banned client (pid 2391595, display `:2`) is left running at the ban screen — do not restart it.

## Open items

- DEFECT-30 (candidate, unfiled as a Java/Python change yet): `run_routine.py`'s step-timeout path must
  actively `STOP` the loop it owns before exiting, not abandon it. This is unrelated to the ban itself
  (the ban would very likely have happened on schedule regardless) but is a real correctness gap the
  incident surfaced.
- Humanization implementation — in flight, Java tree, tracked in `OVERSEER_HANDOFF.md`.
- Appeal filed on `newbakshesh`'s behalf: not planned; treat as a write-off per standing posture.
