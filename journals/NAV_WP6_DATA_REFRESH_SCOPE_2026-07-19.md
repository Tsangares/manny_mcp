# NAV WP6 — Collision/Transport Data-Refresh Tooling: Scope & Design

**Date:** 2026-07-19
**Author:** WP6 scoping worker (Opus, read-only investigation)
**Scope:** Design/scoping only. READ-ONLY on all code. No client launch, no live game, no git commits, no code edits.
**Companions:** `journals/NAV_STAGE2_PLAN_2026-07-18.md` (WP1–WP6 plan), `journals/NAV_ARCHITECTURE_REPORT_2026-07-18.md`.

> **Headline correction to the task framing.** The task brief states "WP6 … is NOT STARTED — that is what you scope." **That is out of date.** WP6 was implemented and committed to the manny repo as `81bd912` ("nav-stage2 WP6: vendored-data refresh tooling for pathfinder package"). The provenance pin, the refresh script, and a 90-assertion offline harness already exist and are in-tree. This document therefore does two things: (1) **audits what shipped** against the four WP6 questions, and (2) **designs the genuinely-open gaps** — chiefly a *runtime* format/version safeguard, which is absent, plus harness hardening and pipeline wiring. Everything below cites concrete files/methods.

---

## 0. Inventory — what already exists (audited, in-tree)

All under `/home/wil/Desktop/manny/pathfinder/` unless noted:

| Artifact | Role | State |
|---|---|---|
| `DATA_MANIFEST` | Machine-readable vendored-data pin (shell-sourceable `KEY=VALUE`): upstream repo, ref, dates, byte counts, **sha256** for both files. | Present, pinned. |
| `THIRD_PARTY.md` | Human-readable provenance + BSD-2 attribution + refresh runbook + live-gate checklist. | Present. |
| `LICENSE-shortest-path` | BSD-2-Clause text (Skretzo). | Present. |
| `collision-map.zip` | Vendored packed `SplitFlagMap` (1,197,109 bytes). | Present. |
| `transports/transports.tsv` | Vendored transport TSV (301,844 bytes, 5,634 lines). | Present. |
| `scripts/refresh_pathfinder_data.sh` (in `manny/scripts/`) | **The WP6 refresh tool.** Re-pulls both files from a ref, verifies size+sha256+zip-integrity, diffs, dry-run by default, `--apply` re-pins. | Present. |
| `scripts/install_pathfinder_resources.sh` (in `manny/scripts/`) | Stages the two files into the RuneLite resource tree (package path) so `getResourceAsStream` finds them in the shaded jar. | Present. |
| `PathfinderVerify.java` (25 checks) | Offline harness incl. **known-route regression** (Lumbridge bridge, staircase plane-change, door parse, count bounds, heap). | Present. |
| `NavShadowVerify.java` (17 checks) | Shadow-mode log-formatter unit checks. | Present. |
| `NavGraphVerify.java` (49 checks) | Graph-mode segmentation/classification/decision-table checks. | Present. |

The three harnesses total the "90 assertions" the manifest/THIRD_PARTY.md reference (25+17+49 = 91 `check()` calls; the docs round to 90 — a trivial doc drift worth noting but not load-bearing).

---

## 1. Where does the data originate? (provenance) — **RESOLVED, documented**

Provenance is **not** undocumented. It is pinned in two mutually-consistent places:

- `pathfinder/DATA_MANIFEST` (source of truth, machine-readable):
  - `UPSTREAM_REPO=Skretzo/shortest-path`, `UPSTREAM_LICENSE=BSD-2-Clause`
  - `UPSTREAM_REF=7e7e5bf94bbb155c2454bcdf8c1036dec0fd9a79`, `UPSTREAM_REF_DATE=2026-07-16`, `FETCHED_DATE=2026-07-18`
  - `COLLISION_MAP_SHA256=3e1658cf…c40a` (1,197,109 bytes)
  - `TRANSPORTS_TSV_SHA256=802662c0…4152` (301,844 bytes)
  - Upstream paths recorded: `src/main/resources/collision-map.zip`, `src/main/resources/transports/transports.tsv`.
- `pathfinder/THIRD_PARTY.md` restates the same pin in prose + a provenance table, plus the BSD-2 attribution chain (Skretzo, building on Explv; collision map derived from Jagex's OSRS cache and redistributed by Skretzo under BSD-2).

**Origin of the bytes (traced):** The data is **vendored, not self-generated.** It is fetched verbatim from Skretzo's `shortest-path` GitHub repo at the pinned commit — `refresh_pathfinder_data.sh` pulls from `https://raw.githubusercontent.com/Skretzo/shortest-path/<ref>/…`. Skretzo in turn regenerates `collision-map.zip` from the live OSRS cache using the sibling `osrs-pathfinding/shortest-path-tooling` cache dumpers (documented as the break-glass fallback in THIRD_PARTY.md, §"If upstream ever goes dark"). manny does **not** run that dumper and does not touch a game cache — this is the decisive "vendor, don't regenerate" call from NAV_STAGE2_PLAN §3.

**Format of the vendored data (traced from the loaders):**
- `collision-map.zip`: one zip entry per region named `"<regionX>_<regionY>"`; each entry is a compressed `BitSet` of 2 flags/tile (flag0 = can-move-north, flag1 = can-move-east), 64×64 tiles/region, up to 4 planes. Parsed by `SplitFlagMap.fromStream` (`SplitFlagMap.java:109`), packed into one shared `long[]`. No version marker inside the zip.
- `transports.tsv`: tab-separated, comment/section lines start with `#`. Columns (0-based): `0 Origin | 1 Destination | 2 "menuOption menuTarget objectID" | 3 Skills | 4 Items | 5 Quests | 6 Varbits | 7 VarPlayers | 8 Duration | 9 Display info`. Origin/Dest are space-separated `"x y plane"`. Parsed by `TransportLoader.parseLine` (`TransportLoader.java:83`); col-2 action is split on spaces, trailing numeric token = objectId, tokens between = multi-word menuTarget. A row is "free" iff cols 3–7 are all empty (`:125`). First data row confirmed: `3097 3107 0 → 3098 3107 0 : Open Door 9398 : … : Duration 1`.

**Verdict on item 1:** No action needed to *establish* provenance — it exists and is pinned with cryptographic hashes. The one weakness (below, §3) is that the pin is a **build-time** record only; nothing enforces it at **runtime**.

---

## 2. The refresh workflow — **EXISTS; here it is, marked manual vs automatable**

The pipeline below is what `refresh_pathfinder_data.sh` + surrounding runbook already implement. Steps marked **[AUTO]** are done by the script today; **[MANUAL]** are documented-but-hand-run; **[GAP]** are not yet built (designed in §3–§5).

1. **Source of truth** — the pin in `DATA_MANIFEST` (`UPSTREAM_REPO` + `UPSTREAM_REF`). **[AUTO]** the script sources this file directly.
2. **Check for drift** — `scripts/refresh_pathfinder_data.sh --ref master` (dry-run): fetches upstream HEAD to a scratch `mktemp -d`, computes byte count + sha256, and diffs vs the vendored copies. Reports `CHANGED`/`unchanged` per file, with a byte delta and, for the TSV, an added/removed line-diff summary. **[AUTO]** Nothing is written in dry-run. (Confirmed by THIRD_PARTY.md: as of 2026-07-18 the pin equalled upstream HEAD — not stale.)
3. **Integrity gate on fetched bytes** — `unzip -tq` zip-integrity test on the fetched collision map; non-empty check on the TSV; both abort on failure. **[AUTO]**
4. **Regenerate (fallback only)** — if upstream is dark, run the `osrs-pathfinding/shortest-path-tooling` cache dumper to reproduce the same zip format, then treat its output as the fetch source. **[MANUAL]**, break-glass, external repo + a 2–3 GB cache. Not steady-state.
5. **Apply + re-pin** — `--apply` copies the fetched files over `pathfinder/collision-map.zip` and `pathfinder/transports/transports.tsv`, then rewrites *only* the `UPSTREAM_REF/_DATE/FETCHED_DATE/*_BYTES/*_SHA256` fields of `DATA_MANIFEST` via `sed`. **[AUTO]** (writes to the manny working tree; git commit is **[MANUAL]** and deliberately out of the script).
6. **Validate — offline harness** — re-run `PathfinderVerify` + `NavShadowVerify` + `NavGraphVerify` (all 90/91 assertions must stay green). Requires compiled classes (JDK21, `./gradlew :client:compileJava -x checkstyleMain -x pmdMain`) and `-Dmanny.pathfinder.resourceDir=<manny>/pathfinder`. **[MANUAL]** today — the script only *documents* the invocation in its header; it does not run it. → **[GAP], §4.1**.
7. **Vendor → RuneLite classpath** — `scripts/install_pathfinder_resources.sh` copies the two files into `runelite-client/src/main/resources/net/runelite/client/plugins/manny/pathfinder/` (idempotent, `cmp`-guarded). **[MANUAL]** step, but the script itself is automatable. → wiring is **[GAP], §5**.
8. **Update prose attribution** — hand-edit `THIRD_PARTY.md`'s provenance table + "Vendored revision" line to match the new pin. **[MANUAL]** by design (prose, not machine-managed).
9. **Rebuild** — `mvn compile -pl runelite-client` (or gradle) to shade the refreshed resources into the jar. **[MANUAL]**.
10. **Live gate** — shadow-mode soak first (`-Dmanny.navBackend=shadow`), then a graph-mode goto on diort per the THIRD_PARTY.md live-gate checklist (pure-walk route, staircase plane-change, indoor door). **[MANUAL]** — and correctly excluded from this WP (no live contact here).

**Automatable-but-not-yet-automated (the seam):** steps 6, 7, 9 could be chained into a single `--apply --verify --install` flow guarded by the harness exit code (fail → revert the working-tree copy + manifest). That is the highest-value remaining automation (design §4.1).

---

## 3. Format / versioning safeguards — **THE PRIMARY GAP**

**Finding:** There is **no runtime version or integrity check anywhere.** Confirmed by grep: no `version`/`format`/`sha256`/`magic`/`checksum` guard in any `pathfinder/*.java`; nothing reads `DATA_MANIFEST` at runtime. The sha256 in the manifest is a **build-time** provenance record consumed only by the refresh *script*; `ShortestPathEngine` (`ShortestPathEngine.java:44` ctor) loads the classpath resources with **zero validation** beyond "the stream exists."

**Why this is dangerous — both loaders fail *silently and soft* on bad/stale data:**
- `SplitFlagMap.get()` (`SplitFlagMap.java:150`) returns `false` (→ treated as blocked) for any region index or plane out of range. A truncated or partially-wrong zip does not throw — it just makes areas silently un-walkable.
- `TransportLoader.parseLine()` (`TransportLoader.java:83`) returns `null` (→ `continue`, row dropped) for any structurally malformed line. A format change upstream (e.g. an inserted column, a re-ordered field) would not crash — it would **silently drop or mis-parse transports**, shipping bad nav data that looks healthy.
- Neither the zip nor the TSV carries an internal format-version token (the TSV's only header is a `#`-comment column list, which the parser skips).

So the exact failure the task warns about — "a stale/incompatible file … silently shipping bad nav data" — is currently *possible*. The safeguard must be **added by manny**, because upstream ships no version field.

### 3.1 Design — a runtime integrity + format-compat guard in `ShortestPathEngine`

Two layers, both fail-loud at load:

**(A) Bundled expected-fingerprint resource (integrity).** Have `install_pathfinder_resources.sh` (or the refresh `--apply`) also emit a tiny `pathfinder/data.fingerprint` resource next to the data, containing the expected `COLLISION_MAP_SHA256`, `TRANSPORTS_TSV_SHA256`, byte counts, and `UPSTREAM_REF` copied from `DATA_MANIFEST`. `ShortestPathEngine` reads it at load and:
  - computes sha256 of each loaded resource stream; on mismatch → **log ERROR with expected-vs-actual + upstream ref, and refuse to serve** (return `null` from `getInstance()`, exactly as it already does on load failure at `:103`). This makes "the jar shipped a file that isn't the pinned one" a loud, first-request failure instead of silent bad routing.
  - Because `getInstance()` already returns `null` cleanly and the router falls back to legacy on a null engine (per the WP2/WP3 abort→legacy design), a fingerprint mismatch degrades safely to legacy nav rather than wedging.

**(B) Manny-owned FORMAT_VERSION + structural self-check (compat).** Add a `static final int FORMAT_VERSION` constant to `ShortestPathEngine` (manny's own schema version, bumped whenever the loaders' expectations change — e.g. TSV column layout). At load, run cheap structural assertions and fail loud if violated:
  - collision: `flagMap.getLoadedRegionCount()` within a sane band (see §4.2), `getWordCount() > 0`.
  - transports: `getEdgeCount()` and `getOriginTileCount()` within a band; **and a canary-row probe** — assert a hardcoded known edge still parses (e.g. Tutorial-Island `Open Door 9398` at `3097 3107 0`, or the Lumbridge `Large door 12349` the harness already uses). If the canary parses to the wrong `menuOption`/`menuTarget`/`objectId`, the TSV column layout changed → **throw at load**, don't serve.
  The canary is the cheapest possible detector of an upstream *format* change (as opposed to a *content* change): content changes move the counts a little; a format change makes the canary mis-parse.

**Load-time log line (observability):** `ShortestPathEngine` already logs a rich load summary (`:78`) — extend it to also print `formatVersion=`, `upstreamRef=` (from the fingerprint), and the fingerprint verdict (`integrity=ok|MISMATCH`). Staleness/incompatibility then shows up in the client log on every startup, satisfying the "flag staleness so it's visible in logs" intent from NAV_STAGE2_PLAN §8.

This (A)+(B) design is the concrete answer to task item 3: **a stale-but-structurally-valid file is caught by (A) sha mismatch; an incompatible-format file is caught by (B) canary mis-parse; either way it fails loudly at load and degrades to legacy, never silently ships bad nav data.**

---

## 4. Validation harness — **EXISTS; here's what it covers and what to add**

**What's already there (`PathfinderVerify.java`, the offline known-route regression the task asks for):**
- **[A] count sanity:** `>2000` regions carry data, `words>0`, `>5000` transport edges, `>4000` free edges (`:70–73`).
- **[B] walkability spot-checks:** known-walkable tiles (castle courtyard, east bank, staircase base) return not-blocked; known-water tiles in the River Lum return blocked (`:77–82`).
- **[C] Lumbridge bridge crossing (DEFECT-21 regression):** castle→cow-field path exists, **no WALK tile is water**, path spans both banks, crossing tiles stay on the land strip `y≤3226`, and run water-adjacent bridge tiles (`:85–132`). This is exactly the "Lumbridge-cowfield ⇄ castle-bank path still resolves" check the task requests — it is already implemented.
- **[D] staircase plane change:** plane-0→2 route contains ≥1 `Climb` transport that changes plane and terminates on plane 2 (`:135–161`).
- **[E] door parse:** Lumbridge `Large door 12349` edge loads with `Open`/`Large door`/dest `3212,3221,0`/free (`:165–182`).
- **[F] heap budget:** loaded static data `< 50 MB` (`:185–189`).

`NavGraphVerify` (49) additionally regression-tests route **segmentation** on the real staircase path plus a synthetic door+stairs path, classification, the retry/abort decision table, and log formatting. `NavShadowVerify` (17) covers the shadow log formatter.

**Gaps to close (task item 4 — "catch a bad refresh"):**

### 4.1 Wire the harness into the refresh (automate step 6)
Add a `--verify` mode to `refresh_pathfinder_data.sh` (or a thin `scripts/verify_pathfinder_data.sh`) that, after `--apply`, invokes the three harness `main()`s against `-Dmanny.pathfinder.resourceDir=<manny>/pathfinder` and **reverts the working-tree files + manifest if the aggregate exit code ≠ 0.** Today this is a documented manual step; a bad refresh currently only fails if a human remembers to run the harness. This is the single most valuable automation gap.

### 4.2 Add **upper** bounds, not just lower bounds
Every count check in `PathfinderVerify` is one-sided (`> min`). A refresh that *doubled* the TSV (duplicate rows) or corrupted the zip into far too many phantom regions would pass. Add sane bands, e.g. regions ∈ [2000, 6000], edges ∈ [5000, 40000], free edges ∈ [4000, edges]. Derive the current values from a first harness run and set bands at roughly ±40% so ordinary game-update growth passes but a structural blowup fails.

### 4.3 Add a transports "column-count histogram" check
Cheap detector for an upstream format change: assert that the overwhelming majority of non-comment TSV rows split into exactly the expected column count (10, tab-delimited). A spike in off-count rows means the column layout moved. Pairs with the runtime canary (§3.1B) — one guards the build, one guards the runtime.

### 4.4 Delta-report as a soft signal
`refresh_pathfinder_data.sh` already prints the TSV added/removed line counts on `--apply`. Promote that into the harness output (e.g. "transports net +37 / −4 vs previous pin") so a reviewer eyeballs whether the churn matches a known game update. Keep it advisory (a game update legitimately churns many rows), not a hard gate.

---

## 5. Pipeline wiring (the remaining automation seam)

`install_pathfinder_resources.sh` is **not invoked by any build/deploy path** — confirmed: no reference to it anywhere in `manny_mcp/` (`.py`/`.sh`/`.yaml`). THIRD_PARTY.md's own "Overseer note" flags this: `world_map.png` has no copy recipe either (it's just committed into the RuneLite tree), and WP6 deliberately did not edit `manny_mcp`. **Recommendation:** in the `manny_mcp` build layer that drives `build_plugin`/shading, add a pre-build hook that runs `install_pathfinder_resources.sh` (idempotent, `cmp`-guarded, cheap) so a fresh checkout or a post-refresh build can never ship a stale-in-classpath copy while the manny-repo copy is fresh. This is a `manny_mcp`-side change and out of scope for a code-frozen investigation, but it is the concrete next action.

---

## 6. Concrete remaining WP6 backlog (prioritized)

| # | Item | Where | Value |
|---|---|---|---|
| 1 | **Runtime integrity + format-compat guard** (fingerprint sha check + FORMAT_VERSION + canary-row probe; fail loud → null engine → legacy fallback). | `ShortestPathEngine.java` (+ emit `data.fingerprint` from refresh/install script) | **High** — closes the "silently ships bad nav data" hole (task item 3). |
| 2 | **`--verify` auto-runs the 90-assertion harness on `--apply`, reverts on failure.** | `scripts/refresh_pathfinder_data.sh` | **High** — a bad refresh currently only fails if a human runs the harness. |
| 3 | **Upper-bound count bands + column-count histogram** in the harness. | `PathfinderVerify.java` | Medium — catches bloat/duplication/format-shift a one-sided `>min` misses. |
| 4 | **Wire `install_pathfinder_resources.sh` into the `manny_mcp` build hook.** | `manny_mcp` build layer | Medium — prevents stale classpath copy. |
| 5 | **Extend load-log with `formatVersion`/`upstreamRef`/`integrity=` verdict.** | `ShortestPathEngine.java:78` | Low/easy — staleness visible in every client log. |
| 6 | Resolve the true upstream **commit date** on `--apply` (script currently stamps fetch date, noted in its own output). | refresh script (optional GitHub API call) | Low — cosmetic provenance accuracy. |
| 7 | Decide whether to vendor the **other 23 transport TSVs** (agility/boats/teleports/fairy rings…). Refresh script + `ShortestPathEngine.TRANSPORT_RESOURCES` (`:35`) handle only `transports.tsv` today. | manifest + script + engine | Deferred — per plan §5.5, only when a routine needs non-free transports. |

**Note:** items 1–5 are all offline / no-live-lane work, consistent with WP6's "no live gate" classification in NAV_STAGE2_PLAN §7. None require touching `MannyPlugin.java` (the engine is a self-init singleton; the guard lives inside its ctor).

---

## 7. One-paragraph answer to the four WP6 questions

**(1) Origin:** vendored verbatim from `Skretzo/shortest-path` @ `7e7e5bf…` under BSD-2, pinned with sha256 in `pathfinder/DATA_MANIFEST` + `THIRD_PARTY.md`; upstream regenerates the zip from the OSRS cache via `shortest-path-tooling` (manny's break-glass fallback, never run). Provenance is fully documented — no gap. **(2) Refresh:** `scripts/refresh_pathfinder_data.sh` already implements fetch→verify(size+sha+zip-integrity)→diff→dry-run/`--apply`→re-pin; the remaining manual links are harness-run, `install_pathfinder_resources.sh`, prose update, rebuild, and the live soak — of which the harness-run and install-wiring are the automatable seams. **(3) Format/versioning:** the *primary real gap* — there is **no runtime check**; both loaders fail silently-soft on bad data, so add a manny-owned fingerprint sha verification + `FORMAT_VERSION` + canary-row probe in `ShortestPathEngine` that fails loud at load and degrades to legacy. **(4) Validation:** the known-route regression the task asks for **already exists** in `PathfinderVerify` (Lumbridge bridge no-water crossing, staircase plane-change, door parse, count/heap bounds) — harden it with upper-bound bands + a column-count histogram, and auto-run all 90 assertions from the refresh script's `--apply`, reverting on failure.
