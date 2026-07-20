# routines/mainland/ — first post-tutorial mainland progression

The early-combat progression for a **fresh account at Lumbridge spawn** (the
first live target is `judeaislam`, parked at Lumbridge spawn, tutorial varp
1000). Design goal, in the user's words: *"kill chickens until 10 att, def, str,
then start working on cows."*

## Progression design

```
Lumbridge spawn (fresh mainland account)
   │  arrival_ritual_bank_gear.yaml   (ENTRY STEP — user's design: "bank all
   │  your items ... before killing chickens", a natural traveling movement)
   ▼
equip bronze sword + wooden shield ── cross-country walk to Draynor bank
(3093,3243) ── deposit the whole starter kit ── walk to the chicken coop
   │
   │  combat_chickens_to_10s.yaml   (pure combat, rotating stances)
   ▼
chicken coop (3235,3295) ── rotate accurate→aggressive→defensive every pass
   │                        stop when defence_level:10 (⇒ all three ≥ 10)
   ▼
combat_cows_hides.yaml     (combat + money)
   │
   ▼
cow pen (3178,3327) ── kill cows, loot Cowhide until inventory full ──► Lumbridge
                        Castle bank (3208,3220,p2) ── deposit ── back to pen ── loop
```

**Master chain:** `00_fresh_account.yaml` runs *ritual → chickens* as one
command (tutorial-island `00_master.yaml` style). It deliberately stops at the
chicken milestone; cows and the skilling activities below are separate
per-session invocations. Because a `00_*` master with a `chain:` key is
authoritative for directory runs, `./run_routine.py routines/mainland/` runs
ritual→chickens instead of alphabetically grinding every file in the directory.

**Alternate-session variety (the user's "mix up the activities"):** two starter
skilling routines sit alongside the combat track. The intended usage pattern
**alternates these routines across sessions rather than grinding one** —
activity variety at the routine-selection level only (NOT humanization, which
is out of scope):

- `fishing_lumbridge_swamp_to_10.yaml` — net-fish shrimp at the Lumbridge Swamp
  coast (net acquired honestly from the permanent ground spawn by the Fishing
  tutor — live receipt 2026-01-24), **drop** policy documented in-file, stops
  at `fishing_level:10`.
- `woodcutting_lumbridge_to_10.yaml` — withdraw the bronze axe at Draynor
  (idempotent has_item-await pattern), chop normal trees at 3163,3301 (corpus
  receipt), **burn** the logs with the starter tinderbox (`LIGHT_FIRE`
  repeat-until loop, Firemaking XP; `DROP_ALL Logs` cleanup fallback), stops
  at `woodcutting_level:10`.

**The ban-risk mechanism is activity progression + variety, nothing else.**
Humanization is explicitly out of scope. Long single-activity grinds are the
risk profile (MANNY_OVERSEER.md §5), so:

- The arrival ritual makes the first session open with a natural traveling
  movement (the user's explicit design) instead of an instant grind.
- `combat_chickens_to_10s.yaml` rotates all three melee stances **every pass**
  (15 kills/stance) rather than grinding one style for hundreds of kills.
- The account then **graduates** from chickens to cows — a different NPC,
  location, and a field↔bank travel cycle for variety.
- Sessions alternate combat and skilling routines from this directory.

### Bank choice for the arrival ritual (user suggested Port Sarim)

Evaluated three options; **picked Draynor Village bank (3093,3243)**:

| Option | Receipts | Verdict |
|---|---|---|
| Port Sarim deposit box (3029,3210) | corpus receipt, live-tested 2025-01-09 (`fishing_karamja_lobster.yaml`) | the user's suggestion, but deposit-only AND `BANK_DEPOSIT_ALL` cannot work there — its widget 786473 = (12<<16)+41 is the **bank**-interface Deposit-inventory button (`BankingSupport.java:40`); the box interface needs fragile per-item deposits with no interface await atom. Upgrade path: a deposit-box-aware DEPOSIT_ALL plugin command, then a Port Sarim variant of the ritual. |
| **Draynor Village bank (3093,3243)** | `LocationManager.java:42` (`DRAYNOR_BANK`); prior-art `KillCowGetHidesCommand` banks here | **picked** — a full bank ON the Lumbridge→Port Sarim road: keeps the natural traveling character the user asked for (~130-tile cross-country walk) with the proven `BANK_OPEN`/`BANK_DEPOSIT_ALL`/`BANK_CLOSE` set. |
| Lumbridge Castle bank (3208,3220,p2) | confirmed (6 corpus routines) | rejected — nearest, but zero traveling character, against the user's intent. |

## Are level-gated stops possible in the real grammar? YES.

**Key finding for the caller:** the loop stop-condition vocabulary (Grammar 2,
`ROUTINE_SCHEMA.md` (c)) **does** support `<skill>_level:N`
(`mcptools/tools/routine.py:2125-2132` → `skills[skill].level >= N`, read from
the plugin's own skill export). So `defence_level:10` is an **honest
ground-truth gate**, not a kill-count approximation. No runner extension is
needed to gate a grind on a skill level.

**The one real limitation** (does *not* need a runner change to ship these two
files, but is the candidate next task if we want cleaner multi-phase gating): a
single flat loop has exactly **one** `repeat_from_step` + **one** ANY-match
`stop_conditions` set, so three *independent* sequentially-gated style phases
are not expressible in one file. `combat_chickens_to_10s.yaml` works around this
honestly by training the three stances with **equal batches every pass** and
gating on the **last-trained** skill (`defence_level:10`): when defence hits 10,
attack and strength — trained earlier in the same pass at equal XP rates — are
already ≥ 10. A future runner feature (sequential multi-phase loops, each phase
with its own Grammar-2 exit) would let each phase gate on its own skill
independently and drop the "train defence last" trick; until then, the
equal-batch/last-skill design is the honest single-file realisation.

## Intended invocation

Offline validation first (always — both already PASS, see below):

```bash
./run_routine.py routines/mainland/combat_chickens_to_10s.yaml --dry-run --loops 2
./run_routine.py routines/mainland/combat_cows_hides.yaml     --dry-run --loops 2
```

Live (first target `judeaislam`; `--loops N` is the ONLY real pass cap —
`loop.max_iterations` is a dead key, `ROUTINE_SCHEMA.md` (d)/(f)):

```bash
# Session 1 (recommended): the master chain — arrival ritual (runs once; no
# loop block) then chickens → 10/10/10 (iterates up to --loops or until the
# honest defence_level:10 gate).
./run_routine.py routines/mainland/00_fresh_account.yaml --loops 40 --account judeaislam

# Or individually:
./run_routine.py routines/mainland/arrival_ritual_bank_gear.yaml --account judeaislam
./run_routine.py routines/mainland/combat_chickens_to_10s.yaml --loops 40 --account judeaislam

# Cows → hides → bank. Each outer pass = one full-inventory batch + bank trip.
./run_routine.py routines/mainland/combat_cows_hides.yaml --loops 20 --account judeaislam

# Alternate-session skilling (mix these across sessions — see design note):
./run_routine.py routines/mainland/fishing_lumbridge_swamp_to_10.yaml --loops 10 --account judeaislam
./run_routine.py routines/mainland/woodcutting_lumbridge_to_10.yaml --loops 10 --account judeaislam
```

Start `combat_cows_hides.yaml` with an **empty inventory** (equipped melee gear
only). `KILL_LOOP_CONFIG` forces `food="none"`, so no food is carried;
`BANK_DEPOSIT_ALL` self-heals inventory cleanliness from the 2nd cycle onward.

## Prior art mined (attic + corpus)

- **Cow pen `COW_PEN_CENTER (3178,3327,0)`** — from the surviving Java command
  `manny_src/utility/commands/KillCowGetHidesCommand.java:83` (kill → pick up
  `Cowhide` at the death tile → bank; resume-if-full logic). We reuse the
  **coordinate** but drive the loop from YAML via the active_loop-**managed**
  `KILL_LOOP_CONFIG` — `KILL_COW_GET_HIDES` itself is uncapped/unmanaged and not
  covered by the DEFECT-26 watchdog fix (`ROUTINE_SCHEMA.md` (e.1); H-7 note in
  `routines/combat/cow_killer_training.yaml`), so we do **not** call it. Attic
  map: `journals/ATTIC_INDEX.md` §4; the layered/deleted design was read but
  **not** resurrected (`git show 396f27f^:routines/combat/cow_killer_no_bones.yaml`,
  `git show c01219c^:actions/Actions.java`).
- **Chicken coop `3235,3295`, TAB_OPEN→SWITCH_COMBAT_STYLE ordering, bronze-sword
  stance labels (Stab/Slash/Block), `defence_level:N` flat-loop gate** — all
  from the **live-proven** `routines/money_making/chicken_feathers.yaml`
  (receipts dated 2026-07-19 in its header). That file also established that
  per-pass rotation isn't expressible via a single parameter — this routine
  instead unrolls the rotation into three in-pass phases.
- **Castle staircase column (`3205,3209` on planes 0/1/2; `3205,3208` is BLOCKED)
  + bank booth `3208,3220,p2` + the courtyard door-risk near `3218,3217`** —
  reused verbatim from the collision-verified desk work in
  `routines/money_making/cowhide_banking.yaml`.
- **`SWITCH_COMBAT_STYLE`** (`manny_src/utility/commands/SwitchCombatStyleCommand.java`)
  is the canonical action/text-based combat-style click (opens Combat tab, scans
  interface group 593 for the button whose action == the style name, clicks it) —
  the dedicated command is used instead of a hand-rolled `mcp_tool: click_widget`
  variant (canonical-path rule, MANNY_OVERSEER.md §2).

## Wiki facts verified (desk)

- Chicken = combat **level 1**; Cow = combat **level 2**; **Cowhide is a 100%
  cow drop** (a ground item at the death tile) — OSRS Wiki
  (`/w/Lumbridge_cow_field`, `/w/Chicken_coop`, `/w/Cow`). The chicken coop sits
  just west of the north end of the Lumbridge cow field; chickens drop Bones
  (auto-buried by KILL_LOOP → free Prayer XP).

## Validation status (offline, laptop-only — NO live run performed here)

| File | `validate_routine_deep` | `--dry-run` |
|---|---|---|
| `combat_chickens_to_10s.yaml` | `valid: True` (2 expected non-terminal-KILL_LOOP **warnings** — intentional; see below) | **PASS**, exit 0 (`--loops 2`) |
| `combat_cows_hides.yaml` | `valid: True`, 0 warnings | **PASS**, exit 0 (`--loops 2`) |
| `arrival_ritual_bank_gear.yaml` | `valid: True`, 0 warnings | **PASS**, exit 0 |
| `fishing_lumbridge_swamp_to_10.yaml` | `valid: True`, 0 warnings | **PASS**, exit 0 (`--loops 2`) |
| `woodcutting_lumbridge_to_10.yaml` | `valid: True`, 0 warnings | **PASS**, exit 0 (`--loops 2`) |
| `00_fresh_account.yaml` (chain) | `valid: True`, 0 warnings | **PASS**, exit 0 (both sections) |

The two chicken-file warnings are the *intended* consequence of unrolling the
stance rotation into three per-pass `KILL_LOOP` batches: steps 5 and 8 are
non-terminal `KILL_LOOP`s. Under the DEFECT-26 fix, `run_routine.py` blocks on
`active_loop` until each loop finishes, so the batches run **strictly
sequentially** (attack → strength → defence) — which is exactly what a
rotation needs. Documented in the file header.

## needs-live-receipt (first live run on `judeaislam` must confirm)

Everything a desk cannot verify. Mark each confirmed/failed in the run journal.

**combat_chickens_to_10s.yaml**
- [ ] **Stance button labels** for the account's *actually equipped* weapon. Defaults
      assume a **bronze sword** → `Stab`/`Slash`/`Block`. Unarmed → `Punch`/`Kick`/
      `Block`; a dagger differs again. Edit `config:` in one place if wrong. A
      wrong label is non-fatal (SWITCH_COMBAT_STYLE logs a failure, grind continues,
      but that stance's XP is misdirected — check early).
- [ ] `EQUIP_BEST_MELEE` actually wields a sword from the starting inventory
      (determines which label set applies).
- [ ] Coop `GOTO 3235,3295` settles from spawn; the fence has no gate that stalls
      the pather. If it stalls, add a door-crossing-v2 step (exact seat → INTERACT
      gate Open → plain through-walk) — but only on an observed live defect.
- [ ] Chicken XP rate → confirm ~7 rotations reach 10/10/10; retune batch size /
      `--loops` if the start level is higher/lower than assumed.

**combat_cows_hides.yaml**
- [ ] Cows actually spawn at / around `3178,3327` and `GOTO` settles there.
- [ ] Outdoor walk `cow pen ↔ courtyard (3221,3218)` settles as single GOTO hops
      (no river here); if the pather corner-cuts/stalls, break into shorter hops.
- [ ] **DOOR RISK** near `3218,3217` on the courtyard↔staircase leg (both
      directions): `get_transitions()` / `scan_tile_objects("door")` before an
      unattended run; insert `INTERACT_OBJECT <Door> Open` if a closed door is found.
- [ ] Castle staircases climb 0→1→2 and back (plane awaits) from *this* approach.
- [ ] `kills=35` batch fills the 28-slot inventory (attempt-success rate assumption);
      retune with real telemetry.
- [ ] Cowhide ground pickup via KILL_LOOP_CONFIG loot works on cows at this pen.

**arrival_ritual_bank_gear.yaml**
- [ ] **Mainland starter inventory** actually contains Bronze sword + Wooden
      shield (attempt-8 parked judeaislam clean but journaled no inventory dump —
      scan with `get_game_state(fields=["inventory"])` before the first run).
- [ ] Both `equip_item` calls verify (DEFECT-29 outcome check) on the mainland UI.
- [ ] The two long single-GOTO legs settle (spawn→Draynor ~130 tiles,
      Draynor→coop ~180 tiles); if the minimap follower stalls, split into short
      hops using tiles harvested from the stall geometry.
- [ ] `BANK_OPEN`/`BANK_DEPOSIT_ALL` work at the Draynor booth (corpus receipts
      are for Lumbridge Castle; the booth/banker names come from the shared
      BankingSupport ID tables so this is expected to hold — confirm).

**fishing_lumbridge_swamp_to_10.yaml**
- [ ] `GOTO 3246,3157` settles (live receipt exists from 2026-01-24 — re-confirm
      on the current jar) and net-fishing spots are present on that coast.
- [ ] `INTERACT_OBJECT fishing_net Take` still resolves the GameObject ground
      spawn (ID 674) — receipt is from 2026-01-24.
- [ ] `FISH Shrimp` finds the spots ("Fishing spot" NPC name match) at this coast.
- [ ] `DROP_ALL Raw_shrimps` drops the full stack of raws and nothing else.

**woodcutting_lumbridge_to_10.yaml**
- [ ] Idempotent withdraw: `BANK_WITHDRAW Bronze axe 1` + `has_item` await passes
      in BOTH states (axe banked / axe already carried).
- [ ] Trees present at `3163,3301` (corpus receipt from woodcutting_lumbridge.yaml).
- [ ] **`LIGHT_FIRE` burn loop** — NO mainland live receipt exists (tutorial used
      raw USE_ITEM_ON_ITEM, a different path). Watch the first burn closely; if it
      misbehaves, delete the LIGHT_FIRE step — the `DROP_ALL Logs` fallback alone
      is the validated-simple policy.
- [ ] Failed-light retry behavior at Firemaking 1 stays within `max_iterations: 60`.

**General:** `--dry-run` cannot verify coordinate reachability/collision,
NPC/widget availability, or timing realism. A PASS is necessary, not sufficient.
The cow routine banks at Lumbridge Castle per the task; note the prior-art
command banked cowhides at **Draynor** (`3093,3243`, closer to some cow fields)
— a possible alternative if the castle-stairs leg proves fragile live.
