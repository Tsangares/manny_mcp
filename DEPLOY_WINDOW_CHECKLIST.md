# Deploy Window Checklist

Runnable instrument-everything + lifecycle-discipline checklist, distilled from
`journals/2026-07-19_methods_retrospective.md` (shortlist items #2 and the checklist lesson under "Where
we burned time"). Run through this **before closing any deploy window** — a window is any cycle that
rebuilds/redeploys the Java jar, restarts a client, or hands live control back to an unattended run.

Linked from `journals/OVERSEER_HANDOFF.md`. Keep this file itself short; if a check needs a paragraph of
explanation, put the explanation in the handoff or a journal and link it from here.

---

## (a) Every defect gated has an unconditional diagnostic

For each `DEFECT-N` this window claims to gate (fix + live-test), confirm: **the log line that answers
the question the *next* failure will ask exists unconditionally** — not only inside the branch that
happens to execute when the fix works.

- [ ] For each defect gated this window, the diagnostic line prints on EVERY pass through that code path,
      success or failure (the DEFECT-22b lesson: a blind gate that only logs inside the branch that never
      ran teaches nothing when it fails).
- [ ] The line includes enough state to diagnose from logs alone (no re-run needed): what was checked,
      what value was found, what decision was made.
- [ ] If you're not sure whether a gate is "blind," ask: *if this defect resurfaces at 3am with nobody
      watching, does the log already contain the answer?* If no, add the line now — it costs nothing.

## (b) Harvest/bank valuable inventory before any client restart

- [ ] Before stopping or restarting a client for this window's deploy, check current inventory for
      anything valuable and unbanked (feathers, ore, bars, hides, coins, quest items).
- [ ] If anything is unbanked and reachable, walk it to a bank and deposit before the restart — or
      explicitly accept the loss and note the amount in this window's journal entry (don't just lose it
      silently; see the ~830-feather loss this rule exists to prevent).
- [ ] Note the item + quantity banked (or accepted-lost) in the window's ledger row / journal notes.

## (c) Record client start times + 8h-cap deadlines

User rule: no client/account runs longer than ~8h continuous; at 8h, stop/log out and switch to another
account/lane until ~10h from that client's start (~2h rest), then it may resume.

- [ ] For every client (re)started this window, record its start time (`ps -o lstart= -p <pid>` or the
      watchdog ledger's `started_at`).
- [ ] Compute and write down its 8h-cap deadline (start + 8h) and its resume-eligible time (start + 10h).
- [ ] If this window schedules a long unattended run (e.g. a Track-G-style proof), confirm the run's
      planned duration fits inside the client's remaining cap — don't schedule a 4h proof to start at
      hour 6 of an 8h window.

## (d) Run the metrics ledger row

- [ ] Append a `window` row to `metrics/campaign_ledger.csv` for this window: date, window_id, live_hours
      (if known), defects_gated, gates_passed, gates_failed, notes.
- [ ] For every routine that got its first live attempt this window (first-contact), append a
      `first_contact` row: date, routine, account, outcome (pass/fail/blocked), failure_class, notes.
- [ ] Leave fields blank rather than guess — an honest gap is more useful than an invented number. See
      `metrics/README.md`.

## (e) Record the scoped-file deploy vs. full provision decision

- [ ] Note which path this window used: a scoped `scp`/rsync of specific changed files (jar + touched
      YAML/scripts), or a full `mannyctl <host> provision` run.
- [ ] If scoped: list what was NOT re-synced (so a future "why is diort's copy of X stale" question has
      an answer). `scripts/remote/hosts.yaml` staging_dir/runelite_libs paths are the source of truth for
      what "in sync" means.
- [ ] If a file diverged between the repo and the live host during the window (e.g. a hand-patch applied
      directly on the run host to unblock something live), reconcile it back into the repo before closing
      the window, or explicitly note in the ledger/handoff that it's still diverged and why.

## (f) Post-window: verify no orphaned processes/watchers on the host

- [ ] `ps aux | grep -i java` (or the account-scoped equivalent) — every client process still running is
      one you intend to be running, with a known owner and a known 8h-cap deadline.
- [ ] Check `/tmp/manny_runs/*.json` for any ledger whose `status` is `unmanaged_loop`, `stale`, or
      `crash` that hasn't been accounted for in this window's notes.
- [ ] Confirm no stray watcher/watchdog scripts (`ps aux | grep -i watch`) are still polling for an
      account/run that no longer exists — a "quiet" background process is not a dead one (the dual-driver
      ghost lesson).
- [ ] Confirm any `scripts/tree_lock.sh` claims this window's agents took have been released, or are
      still legitimately held by a still-running agent.
