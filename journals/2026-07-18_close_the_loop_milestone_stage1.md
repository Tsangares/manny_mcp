# 2026-07-18 — "Close the Loop" milestone, stage 1: both halves of the prime directive attacked at once

**Author:** overseer (Fable session, orchestration-only; all execution delegated to Opus/Sonnet scoped agents).
**Plan file:** `~/.claude/plans/kind-snuggling-turtle.md`. **Read-first state doc:** `journals/OVERSEER_HANDOFF.md`.

## One-line story
The prime directive is *an LLM that RUNS routines and MAKES routines easily*. A 3-agent audit found exactly
two load-bearing gaps — no structured tool surface against the remote run host (RUN half), and no schema /
no trustworthy validator / zero money-making routines (MAKE half). In one parallel stage we closed both
gaps on the laptop side (7 pushed manny_mcp commits, 3 manny commits), survived an account ban mid-stage,
and are now mid-way through the live lane: tutorial completion → feather stat-training grind → cowhide
banking loop → a 4-hour unattended proof.

## Decisions (user-locked)
- **Milestone = close the full loop:** an LLM authors a NEW money-maker and runs it unattended on diort.
- **First money-maker = cowhides** (deliberately forces the DEFECT-21 bridge fix + banking robustness);
  feathers-at-chickens promoted to a stat-training sub-milestone on the way.
- **The Claude session IS the canonical driver** (manny_driver/ and discord_bot/ non-canonical, untouched).
- After the ban (below): **run on `newbakshesh`, accept ban risk on expendable accounts, iterate.**

## What landed (all pushed)

### manny_mcp
| Commit | What |
|---|---|
| `3a5556f` | **manny-diort MCP endpoint** — the MCP server runs ON diort over SSH stdio (`scripts/remote/mcp_stdio.sh` + `config.diort.yaml` + `.mcp.json` entry). Full 39-tool parity against the remote host; verified with a live initialize/tools-list/check_health handshake. The RUN-half gap, closed at the transport layer with ~40 lines of config. |
| `396f27f` | **ROUTINE_SCHEMA.md** (~600 lines, every claim source-cited) — the LLM authoring on-ramp: both condition vocabularies side-by-side, loop-schema exclusivity, blocking-command table, dead-key blacklist, worked examples. Catalog split Existing/Planned. |
| `88bd59b` | **Validator upgrades** — 7 new mechanical checks encoding every bug class previously only found live; 25 tests; corpus sweep found 7 true-positive error files with zero false positives. |
| `e909085` | **watchdog.py + run ledger** — every `mannyctl run` gets a sidecar watchdog (thermal 2-strike SIGTERM, stale/crash detection) writing `/tmp/manny_runs/<run_id>.json`; `mannyctl <host> runs` reads the ledger. All 5 gates passed live against dummy processes. |
| `23abe99` | **NAV_ARCHITECTURE_REPORT** — the patch-vs-replace answer: map data is a pixel screenshot, the follower clicks blind, a precise collision tier exists but ships no data, the API discards door steps. Verdict: surgical patches now, Shortest-Path-style precomputed transition graph next milestone. |
| `0d600ee` | 7 corpus routines fixed (the KILL_LOOP numeric-food-arg class ×4, illegal awaits on blocking FISH ×2, missing POWER_MINE timeout). |
| `c501d06` | Corpus-coupled test decoupled to an inline fixture. |
| `0cb6c9e` | Tutorial pre-flight: 05 plane fields fixed; master chain verified (11 sections, 06 correctly excluded); stale chain test corrected. |
| `1b4b016` | mannyctl watchdog cwd bug (live agent's catch — detached watchdogs launched from $HOME → no ledger; `cd X && … &` backgrounds the whole group). |
| `b0e08f8` | **E1: chicken_feathers routine** (KILL_LOOP_CONFIG + loot_items, style-parameterized combat training, defence_level:20 stop) — validated 0/0. |
| `ab020dd` | Tutorial 05 repair v1 (door nav + dialogue — superseded in part by the live ladder-gate recipe, second edit pass pending). |
| `2a06c31` | Chain glob-mode guard — bare-directory resolution defers to `00_master`'s explicit chain; the 06 double-run footgun is structurally impossible. |
| `5f9a08a` | **E2 DRAFT: cowhide_banking routine** — 24 steps, nested inner/outer loop, explicit bridge waypoints + staircase plane-awaits; validated 0/0; 5 named open questions for the live gate. |
| `55c7495` | OVERSEER_HANDOFF refreshed to this milestone. |

### manny (plugin, Java)
| Commit | What |
|---|---|
| `b40838a` | **DEFECT-21 fix** — wired the existing-but-never-called `validateAgainstLocalCollision` (live client collision maps, water flag 0x200000) into the blind greedy follower: no more clicking known-blocked tiles, no more corner-cutting off the bridge. Compile-green; live gate pending (rides the cowhide run). |
| `6566fe9` | **DEFECT-22** — LoginHandlers ban fail-fast (terminal-failure classification before the world-hop retry path). Live gate showed the widget-text source doesn't see the rasterized ban dialogue → **DEFECT-22b filed**: classify via the login response index instead. |

## The ban (the stage's plot twist)
Account `new` (GrimmsFairly) — the account that proved the diort thermal fix yesterday — is **banned for
"serious rule breaking."** Detected behaviorally despite the residential IP. Consequences handled:
- `newbakshesh` promoted to the live account (it was mid-tutorial, not fresh — a prior session had advanced it).
- `main` is the user's real account and is never used for bot work.
- The ban screen exposed DEFECT-22's blind spot (rasterized dialogue, not widgets) — and gave us a free,
  zero-risk live gate for the eventual DEFECT-22b fix.
- User posture: expendable accounts are R&D cost; keep iterating.

## Live-lane findings (tutorial, in progress at time of writing)
1. **DEFECT-23 (filed):** GOTO lands ~1 tile short (DEFECT-7 tolerance), the next INTERACT fires before
   settle → "not found" → a closed door then blocks re-pathing with no retry. Manual-clear recipe proven
   (settle adjacent → open → step ONTO the door tile → ≤10-tile hops). Fix direction: the nav report's
   `exact` arrival mode + a one-shot INTERACT retry after settle.
2. **Quest-guide ladder gate cracked** — the validated recipe: `INTERACT_NPC Quest_Guide Talk-to` →
   `CLICK_CONTINUE` until `no_dialogue` (multi-page monologue must be EXHAUSTED) → `TAB_OPEN quests` →
   `INTERACT_OBJECT Ladder Climb-down`. Widget 15138820 (the routine's old click target) turned out to be
   the dialogue *speaker-name header* — never a real gate at all.
3. **DEFECT-24 (filed):** the plugin's dialogue state writer misreports NPC monologues as
   `type:"options"` and hints `CLICK_DIALOGUE "<speaker>"` — a trap for any LLM driver reading state
   hints (clicking the speaker name no-ops). Also: TabOpenCommand's javadoc claims F-keys; it actually
   widget-clicks — stale doc.
4. **Tutorial 07 ambiguous-rocks bug (live-diagnosed):** the mining step repeats `INTERACT_OBJECT Rocks
   Mine` with no position-pinning GOTO first — tin and copper outcrops are both named "Rocks", so the
   interaction farms the nearest (tin) forever; 13 tin, zero copper, cascade failure through
   bar → dagger → gate. **Generalizable lesson: interact-by-name needs a position-pinning GOTO whenever
   object names are ambiguous** (same class as the door bug). Corpus fix + rerun in progress.
5. Watchdog ledgers confirmed working on every post-fix run (status/temp/events); the pre-fix run
   produced none — which is precisely how the cwd bug was caught.

## Orchestration notes (what worked)
- **Fable as pure overseer** (~23% context after a full day) + Opus/Sonnet scoped general-purpose agents —
  never forks — with explicit file-ownership boundaries per agent. ~15 agents dispatched; zero rogue.
- **Peer messaging as the mesh:** Track B's corrections were forwarded mid-flight into Track C's prompt
  window; the nav report's root-cause intel reached the live DEFECT-21 agent mid-diagnosis; the live
  agent's discoveries flowed back as filed defects. The overseer carried conclusions, not file dumps.
- **Concurrent-commit discipline:** every agent stages only its own files, pulls --rebase before push,
  retries on index.lock; the overseer pushes stragglers with `git pull --rebase --autostash`.
- **One session owns the live account** — enforced all day; the only ambiguity is a mystery run
  (`20260719T014238Z`) launched by neither this session nor its agents (user asked, see open items).
- **The live agent pauses at NEW failure classes instead of improvising** — this turned three would-be
  disasters into filed, evidence-backed defects.

## Open items (stage 2, in order)
1. Tutorial 07 (fixed) rerun → 08 → 09 → 10 → mainland verification. [live lane, in progress]
2. E1 feather smoke ≥30 min → bounded stat-training grind (att/str/def → ~20). [live lane]
3. **Java window** (while stats train; one rebuild + provision): DEFECT-22b (ban detection via login
   response index — free gate on the banned account), DEFECT-23 (exact-arrival mode), DEFECT-24
   (dialogue state writer). MannyPlugin.java remains LOCKED.
4. E2 cowhide live gate — validates the DEFECT-21 bridge fix + the 5 draft open questions
   (coords, staircase geometry, booth reachability, batch size 30→~27, clean starting inventory).
5. **Track G: the 4-hour unattended proof** — a fresh LLM session, given only ROUTINE_SCHEMA.md + the
   validator + the manny-diort endpoint, authors a variant and runs unattended with ledger evidence.
6. Mystery run `20260719T014238Z` (07 retry, pid 2295350, ~18:42 local): launched by whom? Not this
   session. If the user launched it manually — say so; otherwise its parentage gets checked before
   anything else drives the account.
7. Next milestone (pre-scoped by the nav report): Shortest-Path-style precomputed collision + transition
   graph — fixes doors/gates at the root, deletes the osrspathfinder.com dependency.

## Environment / versions
diort: Arch, 2011 iMac 4-core i5, jdk21 pinned, Python 3.14.4, Xvfb :2, fish login shell, temps 51-74°C
all day (refuse 88°C). Jar: client-1.12.34-SNAPSHOT-shaded.jar @ manny `6566fe9`. Laptop builds only —
never runs the client (thermal). MCP: local server `runelite-debug`, remote `manny-diort` over SSH stdio.
