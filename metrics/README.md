# Campaign metrics ledger

`campaign_ledger.csv` — one CSV, two record types discriminated by the `type` column. Per the methods
retrospective (`journals/2026-07-19_methods_retrospective.md`, "Are we measuring the right things?"): we
tracked defects and gates well but never the campaign's economics, and specifically never the single most
decision-relevant number — **first-contact survival rate of desk-verified routines**. This ledger exists
to start recording that, plus enough window-level data to eventually see cost-per-defect and deploy
cadence.

## Columns

All columns live in one header row; a given row only populates the columns relevant to its `type`, the
rest blank.

| Column | Used by | Meaning |
|---|---|---|
| `type` | both | `window` or `first_contact` — discriminates the row shape |
| `date` | both | ISO date (UTC) the row's event happened |
| `window_id` | window | short slug identifying the deploy/live window (e.g. `window-3`, `lane-2-window`) |
| `live_hours` | window | hours of live-client time the window consumed, if known. **Mostly blank historically** — this wasn't tracked before this ledger existed (see Known gaps). |
| `defects_gated` | window | semicolon-separated list of `DEFECT-N` identifiers this window attempted to gate |
| `gates_passed` | window | count of gate checks that passed live this window |
| `gates_failed` | window | count of gate checks that definitively failed live this window (a gate that was merely untested/blocked-upstream is NOT counted here — say so in notes instead) |
| `routine` | first_contact | path to the routine YAML (repo-relative), or blank if not identifiable |
| `account` | first_contact | account alias that made the attempt |
| `outcome` | first_contact | `pass`, `fail`, or `blocked` (blocked = didn't fail on its own merits, something upstream stopped it — e.g. an account ban, a missing dependency) |
| `failure_class` | first_contact | short machine-greppable tag for the failure category (e.g. `nav_short_circuit`, `item_matcher_substring`, `account_ban`, `engine_defect`, `DEFECT-29_click_bug`). Blank on `pass`. |
| `notes` | both | free text — what happened, evidence pointers, commit hashes, follow-up |

## Conventions

- **Blank means unknown, not zero and not "didn't happen."** If a value wasn't recorded at the time and
  can't be reconstructed from journals/ledgers, leave it blank. Do not backfill a plausible-looking guess
  — a `first_contact` row with `outcome` populated but `live_hours` blank on the corresponding window is
  the expected, honest shape for most of this campaign's history so far.
- **`first_contact`** means the routine's (or a materially-changed version's) *first* live attempt after
  being desk-verified — not every subsequent run. Re-runs of an already-passing routine don't get new
  rows. A routine that failed first contact, got fixed, and then passed gets **two rows**: the original
  fail and the later pass (both are real data — the goal is a survival curve, not a single boolean per
  routine).
- **`window` rows are deploy/live-window level, not per-defect.** One window can gate several defects;
  list them all in `defects_gated`, and put per-defect nuance (partial, deprioritized, blind-then-fixed)
  in `notes` rather than trying to force it into `gates_passed`/`gates_failed`.
- Account bans, orphaned-loop incidents, and other non-defect operational events get a `window` row (see
  `ban-incident` in the current data) so the live-hours ledger stays complete even when nothing was being
  *gated* that day.

## Updating this ledger

Per `DEPLOY_WINDOW_CHECKLIST.md` (d): append a `window` row before closing any deploy window, and a
`first_contact` row for every routine that got its first live attempt during that window. Append, don't
edit history — if a fact turns out to be wrong, add a corrected row and note the correction rather than
silently rewriting the old one (the CSV is also an audit trail).

## Known gaps (as of the 2026-07-19 backfill)

- **`live_hours` is blank for windows 1-3, lane-2-window, and lane-2b-window.** These windows happened
  before this ledger existed; journals record *what* happened and rough timestamps ("~03:00Z", "~04:30Z")
  but not a clean start/end duration per window. Only the `ban-incident` row has a computed `live_hours`
  (derived precisely from `/tmp/manny_runs/*.json` ledger timestamps on diort). Going forward,
  `DEPLOY_WINDOW_CHECKLIST.md`
  (c) asks for client start times to be recorded, which makes this computable.
- **The `new` (GrimmsFairly) ban's active routine/context is not identified** in any journal found during
  this backfill — the `first_contact` row for it has `routine` blank rather than a guess.
- **`cowhide_banking.yaml` (E2) has no row yet** — it's desk-verified (`9f6b6e8`) but has not had a first
  live attempt as of this backfill, so there's nothing to record.
- This is a manual backfill from `journals/` prose, not a machine-generated report — treat it as
  best-effort reconstruction, cross-check against the cited journal/commit if precision matters.
