# Navigation Stage-2 Plan — Precomputed Collision + Transition Graph (the "Shortest Path" core)

**Date:** 2026-07-18
**Author:** Stage-2 navigation design worker (Opus)
**Status:** Implementation plan — decisive, ready to schedule into work packages
**Scope:** Design only. READ-ONLY on all code. No Java touched by this document.
**Companion:** `journals/NAV_ARCHITECTURE_REPORT_2026-07-18.md` (the pipeline map + patch-vs-replace verdict). Read that first; this plan executes its **Stage 2** ("replace the collision/graph core").

> **One-paragraph thesis.** Stage 1 shipped (DEFECT-19/19b/20/21/7 patches; the DEFECT-21 live-collision follower guard landed in `manny@b40838a`). Stage 2 replaces the *map and the router*, not the walker. We **vendor the open-source Shortest Path plugin's packed collision map (1.2 MB) and its transport TSVs, and port its A\*+transport-graph core** into a new `pathfinder` package, behind a `navBackend` feature flag. `gotoPositionSafe` becomes the cutover point: it asks the graph for a path whose steps are either WALK-tiles (handed to the *existing* minimap follower, our stealth asset) or TRANSPORT-actions (doors/gates/stairs/ladders the follower now *opens/climbs* instead of stalling). This fixes DEFECT-19 (no more "uncached = blocked"), removes the DEFECT-21 class at the map level, folds the manual Indoor Navigation Protocol into GOTO, gives GOTO real cross-plane travel, and lets us **delete `osrspathfinder.com` and the `world_map.png` walkability tier**. The DEFECT-21 surgical guard stays as a belt-and-suspenders net the whole way.

---

## 1. What we are replacing (recap, source-cited)

From the architecture report, the current GOTO stack is a four-layer hybrid with three "maps" that disagree:

- **External API** `PathfinderApiClient.findPath` (`manny/utility/PathfinderApiClient.java:56`) → `POST osrspathfinder.com/find-path` (`:32`), and it **discards LINK steps** (`:161`, `// Skip LINK steps`) so doors/stairs computed server-side are thrown away.
- **Local A\*** over either the live `CollisionMapCache` (uncached = blocked, `CollisionMapCache.java:163-166` → DEFECT-19) or **`world_map.png` pixel colours** (`WorldMapData.java`, loaded via `getResourceAsStream("/world_map.png")` at `:56`).
- **Dormant precise tier** `CollisionDataLoader` (`manny/utility/CollisionDataLoader.java`) reads `data/collision/region_<id>.dat` (`:396`); **zero files ship** — `data/collision/` holds only a README pointing at a 2–3 GB cache download (`data/collision/README.md`) and the never-run `scripts/download_cache.sh` + `scripts/extract_collision.sh`.
- **Follower** minimap walker (`NavigationHelpers.java:1565`, `findFurthestVisibleWaypoint :3103`, `clickMinimapPoint`), now with the DEFECT-21 live-collision guard wired in (`validateAgainstLocalCollision :289`, called at `:2774` and `:3182`).

**Router entry point** is `NavigationHelpers.gotoPositionSafe(ClientThread, WorldPoint, int)` (`:1354`). That single method is the Stage-2 cutover seam.

---

## 2. The Shortest Path model, in the detail we need to port it

Source: **Skretzo/shortest-path** (`github.com/Skretzo/shortest-path`), **BSD-2-Clause**. Building on Explv's map work; cache dumpers live in the sibling `osrs-pathfinding/shortest-path-tooling` repo.

### 2.1 Collision data — `collision-map.zip`, the `SplitFlagMap` format

- **Ships as one resource:** `src/main/resources/collision-map.zip` = **1,197,109 bytes (~1.2 MB)** for the *entire* OSRS overworld + dungeons. (By comparison, manny's own `.dat` format is 4 planes × 64×64 × 4-byte int = **256 KB *per region* uncompressed**, i.e. ~40× larger per region and thousands of regions — a non-starter. We do not use it.)
- **Format** (`pathfinder/SplitFlagMap.java`, `pathfinder/CollisionMap.java`): the zip contains one entry per region named `"<x>_<y>"` (region coords, parsed by `split("_")`). Each region's bits are stored compressed → `BitSet` → packed into a single shared `long[]`. Region packed id = `(x & 0xFFFF) | ((y & 0xFFFF) << 16)`.
- **Two flags per tile** (`FLAG_COUNT = 2`): flag 0 = "can move **north**", flag 1 = "can move **east**". West/south are derived by querying the *adjacent* tile's north/east flag. This is the compact trick that makes the whole map 1.2 MB. (Manny's `CollisionDataLoader` instead stores the full 32-bit `CollisionDataFlag` per tile — richer but bulky; we abandon it in favour of the 2-flag model.)
- **Bit index within a region:** `(z*REGION_SIZE*REGION_SIZE + (y & MASK)*REGION_SIZE + (x & MASK)) * FLAG_COUNT + flag`, extracted with `word = offset + (localBit >> 6)`, `bit = localBit & 63`. `REGION_SIZE = 64`.
- **Loading:** `SplitFlagMap.fromResources()` scans all zip entries, computes `minX/minY/maxX/maxY`, allocates one consolidated `long[]`. Whole-map load (not lazy per-region).

### 2.2 Transports — the transition graph (24 TSV files)

- **Location:** `src/main/resources/transports/` — 24 tab-separated files. The one we care about first is **`transports.tsv`** (doors, gates, stairs, ladders, trapdoors). Others: `agility_shortcuts.tsv`, `boats.tsv`, `ships.tsv`, `canoes.tsv`, `fairy_rings.tsv`, `spirit_trees.tsv`, `gnome_gliders.tsv`, `teleportation_spells.tsv`, `teleportation_items.tsv`, `teleportation_levers.tsv`, `teleportation_portals.tsv`, `wilderness_obelisks.tsv`, `minecarts.tsv`, `magic_carpets.tsv`, `charter_ships.tsv`, `quetzals.tsv`, etc.
- **Column format** (tab-separated): `Origin | Destination | "menuOption menuTarget objectID" | Skills | Items | Quests | Varbits | VarPlayers | Duration | Display info`. `Origin`/`Destination` are `"x y plane"`.
- **Worked examples** (real rows from `transports.tsv`, Tutorial Island):
  - `3097 3107 0` → `3098 3107 0` : `Open Door 9398` : (no reqs) : Duration `1`  — a **door edge**, bidirectional (the reverse row also exists).
  - `3090 3092 0` → `3089 3092 0` : `Open Gate 9470` — a **gate edge**.
  - `3084 3125 0` → `3084 3124 1` : `Climb-up Staircase 16671` — a **plane-change edge** (plane 0 → 1). This is exactly the cross-floor capability GOTO lacks today.
- Each edge encodes precisely the "to get from tile A to tile B, perform *menuOption* on *menuTarget* (object *objectID*)" model §4.3 of the arch report asked for. `Skills/Items/Quests/Varbits/VarPlayers` are traversal **requirements**; `Duration` is edge cost in ticks.

### 2.3 Pathfinding algorithm

- `pathfinder/Pathfinder.java`: **A\*** (priority queue `IntMinHeap pending` for transport frontier + a `boundary` deque for plain tile neighbours). `CollisionMap.getNeighbors(node, ...)` yields both walkable tile neighbours *and* the transport edges leaving that tile; transports enter the heap with their `Duration` cost (delayed-visit so shared destinations resolve correctly). It runs on a **worker thread**; the render thread reads partial results via volatile `getPath()`. Older revisions were BFS/Dijkstra — current is cost-ordered A\*.
- Net: a **single offline computation per GOTO** over an in-memory graph. This is *not* the hot, self-heating A\* that caused DEFECT-19-v1 (that churned a 50 000-iteration all-blocked grid, `PathfindingHelpers.java:971`); a fully-populated graph converges fast.

---

## 3. Decision 1 — Data pipeline: **vendor Skretzo's published files; do NOT regenerate from cache**

**Recommendation (decisive):** Bundle Skretzo's `collision-map.zip` + the `transports/*.tsv` files directly into manny's resources, pinned to a specific upstream commit. Do **not** run the 2–3 GB cache download / extract path.

**Why:**
1. **Size is trivial** — 1.2 MB collision + a few hundred KB of TSV. Bundling is the same mechanic as the already-shipped `world_map.png` (`getResourceAsStream("/world_map.png")`, `WorldMapData.java:56`).
2. **License permits it.** BSD-2-Clause allows redistribution of source *and* binary with the copyright notice retained. Skretzo already publicly redistributes the packed `collision-map.zip` (itself derived from Jagex's cache) under BSD-2; us re-bundling that packed artifact is the identical legal posture. **Compliance action:** copy Skretzo's `LICENSE` into `manny/pathfinder/LICENSE-shortest-path`, retain a BSD-2 header on every ported `.java`, and add a one-line NOTICE crediting Skretzo + Explv.
3. **The self-generate path is dead weight.** `download_cache.sh`/`extract_collision.sh` have never been run in the project's lifetime; maintaining a bespoke cache extractor is strictly more work than `git`-pulling a 1.2 MB file that Skretzo already keeps current per game update.
4. **We keep the regenerate option as a documented fallback** (WP6): if Skretzo ever goes stale or dark, `shortest-path-tooling`'s cache dumper regenerates the *same* zip format — but that is a break-glass procedure, not the steady state.

**File placement (concrete):**
- Collision + transports become **classpath resources**, loaded exactly like `world_map.png`. In the manny plugin resource root (whatever ships alongside `/world_map.png`), add `/collision-map.zip` and `/transports/*.tsv`. Loader reads via `getClass().getResourceAsStream("/collision-map.zip")`.
- **Retire** the filesystem `data/collision/*.dat` tier: `MannyPaths.collisionDataDir()` (`MannyPaths.java:189`, returns `HOME_BASE + "/data/collision/"`) is no longer read for pathing. Delete `download_cache.sh`, `extract_collision.sh`, and the `.dat` `RegionCollisionData` (de)serializer in `CollisionDataLoader` (see Decision 2).
- **Expected footprint:** 1.2 MB zip on disk; decompressed into one shared `long[]`, estimated **~30–50 MB heap** for the full map (all regions loaded). Budget-checked against diort in the Risks section.

**Data-model consequence:** we adopt Skretzo's **2-flag (N/E) model**, not manny's 32-bit `CollisionDataFlag` model. The two are self-consistent within their own loaders; mixing them is pointless. The live `CollisionMapCache` (boolean walkable/water) survives only as a runtime *override* layer (§4).

---

## 4. Decision 2 — Integration architecture: what replaces what

New package: **`net.runelite.client.plugins.manny.pathfinder`** (vendored + adapted from Skretzo). Vendored classes: `SplitFlagMap`, `CollisionMap`, `Transport`, `TransportType`, `Pathfinder`, and the small primitives it needs (`PrimitiveIntHashMap`/`IntMinHeap` or equivalents). One new manny-owned facade: **`ShortestPathEngine`** (singleton, `getInstance()` — same self-init pattern as `CollisionDataLoader.getInstance()`, so **MannyPlugin.java stays untouched** — see Risks).

`ShortestPathEngine.findPath(WorldPoint start, WorldPoint target)` returns an ordered `List<PathStep>` where a step is one of:
- `WALK(WorldPoint tile)` — a plain tile.
- `TRANSPORT(WorldPoint origin, WorldPoint dest, String menuOption, String menuTarget, int objectId)` — an action edge (door/gate/stairs/ladder).

| Component today | Stage-2 disposition |
|---|---|
| `gotoPositionSafe` router (`NavigationHelpers.java:1354`) | **Cutover seam.** Behind `config.navBackend()==GRAPH`, call `ShortestPathEngine.findPath`; segment the result at TRANSPORT boundaries (§5); hand each WALK-run to the existing follower and execute each TRANSPORT as an object interaction. `LEGACY` keeps today's API/local/PNG ladder verbatim. |
| Minimap follower (`:1565`, `:3103`, `clickMinimapPoint`) | **Kept as-is** — the anti-detection asset. Now fed a graph-derived, collision-true waypoint list. |
| `PathfinderApiClient` (`osrspathfinder.com`) | **Deleted** after GRAPH proves out (phase D). No network in the control loop. |
| `world_map.png` walkability (`WorldMapData` walkable/water/gate methods) | **Removed from the nav decision path.** Keep the PNG only for the `VIZ_PATH`/`VIZ_REGION` visualisers; nav no longer reads pixel colours. |
| `CollisionDataLoader` `.dat` region format | **Replaced.** Repurpose the class (or fold into `ShortestPathEngine`) to front the `SplitFlagMap` static data with the live cache as an override. Drop the `0xC0111510` `.dat` reader/writer. |
| `CollisionMapCache` (live scan, boolean walk/water) | **Demoted to a runtime override.** Consulted *first* for tiles the player has scanned (captures dynamic state — an open door, a placed object); static `SplitFlagMap` answers everything else. Also still backs the DEFECT-21 follower guard. |
| Manual **Indoor Navigation Protocol** (routine/LLM layer, `manny_mcp/CLAUDE.md`) | **Folded into GOTO.** Doors/gates/stairs are now graph edges GOTO opens/climbs itself; routines stop hand-driving scan→open→step. |

**Doors/gates as first-class steps (the payoff).** A TRANSPORT step's `menuOption`+`menuTarget`+`objectId` map straight onto the existing `interactWithGameObject`/`INTERACT_OBJECT <name> <action>` machinery and the `QUERY_TRANSITIONS` state detection (`GameEngine.findNavigableTransitions:2304`, open/closed inference `:2488-2496`). The follower reaches the transport origin, fires `Open Door`/`Climb-up Staircase`, verifies the crossing, and continues — no stall, no LINK-step discard.

**Tie-ins:**
- **DEFECT-23 exact-arrival mode:** transport execution requires the character to stand on the *origin threshold tile* before interacting (a door edge is only valid from its origin tile). The follower's arrival for a WALK-run that ends at a transport origin must be tolerance-0, not the loose ≤3-tile "already there" (`GotoCommand.java:131`).
- **DEFECT-7 tolerance:** the same exact-arrival capability fixes the `GOTO` no-op-at-2-tiles bug. One mechanism (`exact`/tolerance-0 arrival) serves both. Implement once (WP4), consume in WP3.

---

## 5. Follower changes — segmented, collision-true, cross-plane

The follower stays a greedy minimap walker **within a WALK-run**, but the run is now bounded and the map underneath it is real.

1. **Segment the path at transports.** Split the `List<PathStep>` into alternating WALK-runs and TRANSPORT actions. Walk a run → arrive **exactly** at its final tile (transport origin) → execute the TRANSPORT → verify → next run.
2. **Real collision under the greedy scan.** `findFurthestVisibleWaypoint` (`:3103`) already refuses to skip past a blocked tile (DEFECT-21, `:3182`). Under GRAPH that guard is now backed by *static* `SplitFlagMap` data for *every* tile, not just live-scanned ones — so the "corner-cut across water" is impossible at the map level, and the guard becomes a redundancy rather than the sole defence. Keep both.
3. **Transport execution.** For a TRANSPORT step: `INTERACT_OBJECT <menuTarget-with-underscores> <menuOption>` (respecting the object-naming rule, `manny_mcp/CLAUDE.md` "Object Naming Rules"), then await the state change:
   - door/gate: origin→dest tile move on the same plane;
   - stairs/ladder/trapdoor: `plane` change to dest's plane (`await_condition plane:N` semantics already exist).
   Reuse `interactWithGameObject`'s retries + camera scan; on failure, fall back to the existing reactive `attemptOpenGate` (`:1777`).
4. **Plane changes become normal.** Because a staircase is a graph edge whose dest plane differs, GOTO can now route across floors. (The command-level plane guard `GotoCommand.java:119` can be relaxed for GRAPH backend in a later step; not required for the core cutover, since same-plane indoor door routing is the first win.)
5. **Requirement filtering.** Early phases use only **free** transports (doors, gates, stairs, ladders, trapdoors) — ignore any edge with non-empty Skills/Items/Quests/Varbit requirements. The live account (`newbakshesh`) will not meet most agility/teleport reqs; enabling those without a capability check would produce unwalkable "paths." Add capability-aware filtering only when a routine needs it.

---

## 6. Decision 3 — Migration & rollback: one feature flag, four phases, guard stays

**Feature flag:** `config.navBackend()` ∈ `{LEGACY, GRAPH}`, default **LEGACY**. Single branch point in `gotoPositionSafe`. (Config lives in `MannyConfig.java`; adding a config enum does **not** touch MannyPlugin's locked control flow.)

| Phase | Flag | Change | Routines gating it | Live gate on diort |
|---|---|---|---|---|
| **A — dark launch** | LEGACY (unchanged behaviour) | Land engine + data + `ShortestPathEngine`; add a read-only `GRAPH_PATH_DEBUG x y z` command that computes and logs/vizualises a graph path but does **not** drive movement | none (no behaviour change) | Offline JUnit path tests; eyeball `GRAPH_PATH_DEBUG` vs current on Lumbridge→GE and a bridge crossing |
| **B — narrow live** | GRAPH for an allowlist | Flip GRAPH on for 2–3 hand-picked routines: a Lumbridge-bridge crossing, an indoor Lumbridge-castle move, a Tutorial-Island door sequence | Tutorial Island + one bridge-crossing skilling routine | diort: those routines complete with graph nav; no water stall; doors opened by GOTO not by hand |
| **C — default on** | GRAPH default | Flip default to GRAPH; API + PNG kept **dormant** as emergency fallback for one milestone | broad routine set (mining+banking loop that crosses regions) | diort: full regression of a long cross-region grind |
| **D — retire legacy** | GRAPH only | Delete `PathfinderApiClient`, `world_map.png` walkability, `.dat` pipeline + scripts; demote `CollisionMapCache` to override-only | — | diort: post-deletion regression smoke |

**DEFECT-21 coexistence.** The Stage-1 live-collision follower guard (`manny@b40838a`, `validateAgainstLocalCollision` at `:2774`/`:3182`) is **orthogonal to the path source** — it vetoes bad *minimap clicks* regardless of who produced the waypoints. It stays wired through **all four phases**. Under GRAPH it is the safety net for stale data (a door moved by a game update, a region Skretzo hasn't refreshed): if the static graph is wrong, the live guard still refuses to click into water. Only remove it if it ever proves to *fight* a correct graph path — no reason to expect that.

**Rollback:** any phase reverts by flipping `navBackend` back to LEGACY (until phase D deletes the legacy code). Phase D is the point of no return and must not land until C has soaked.

---

## 7. Work packages (6, agent-sized, sequenced for one diort lane)

Sized for the existing orchestration pattern (Opus workers, single live diort lane, MannyPlugin.java LOCKED). Each names its dependency and its live gate. WP1/WP6 need no live lane (offline); the diort-gated ones (WP2/3/4/5) serialise on the single lane.

- **WP1 — Foundation: vendor data + port core (no live lane).**
  Add `/collision-map.zip` and `/transports/*.tsv` to manny resources (pinned to an upstream commit + LICENSE + NOTICE). Port `SplitFlagMap`/`CollisionMap`/`Transport`/`Pathfinder` (+primitives) into `manny.pathfinder` with BSD-2 headers. Build `ShortestPathEngine` singleton emitting `List<PathStep>`.
  *Deps:* none. *Constraint:* self-init singleton — **no MannyPlugin edit**. *Gate:* JUnit offline paths (Lumbridge→GE; Lumbridge bridge crossing; indoor Lumbridge castle kitchen; a staircase edge produces a plane-change step). Assert no path routes through water; assert transport steps present indoors.

- **WP2 — Router integration behind the flag (diort gate, WALK-only).**
  Add `navBackend` config. Branch `gotoPositionSafe (:1354)`: on GRAPH, call the engine, use **WALK segments only** (skip/relax transports for now), convert to the follower's waypoint list. Add `GRAPH_PATH_DEBUG`.
  *Deps:* WP1. *Gate:* diort — GRAPH on, Lumbridge→GE walk matches/beats legacy, zero water stall on a bridge crossing.

- **WP3 — Transport execution in the follower (diort gate).**
  Segment path at transports; execute door/gate/stairs/ladder as `INTERACT_OBJECT`; verify same-plane move or plane change; reactive-gate fallback; requirement filtering (free transports only).
  *Deps:* WP2, WP4 (exact-arrival). *Gate:* diort — indoor Lumbridge-castle kitchen reached through doors by GOTO alone; Tutorial-Island door run; one staircase climbed (plane 0→1→verified).

- **WP4 — Exact-arrival / tolerance-0 mode (DEFECT-7 + DEFECT-23) (diort gate).**
  Add an `exact` arrival mode (tolerance ≤1) usable by GOTO and required for transport origins; fix the `GotoCommand.java:131` ≤3-tile no-op for precision moves.
  *Deps:* WP2. *Gate:* diort — a precision `GOTO` onto a tile just behind a fence actually paths and arrives; feeds WP3.

- **WP5 — Retire legacy (diort gate, phase C→D).**
  Default flag to GRAPH; delete `PathfinderApiClient`, `WorldMapData` walkability path, `.dat` pipeline + `download_cache.sh`/`extract_collision.sh`; demote `CollisionMapCache` to override-only.
  *Deps:* WP2+WP3 soaked on diort. *Gate:* diort — full cross-region mining+banking loop regression after deletions.

- **WP6 — Data-refresh tooling (no live lane).**
  Script to pull the latest Skretzo `collision-map.zip` + `transports/*.tsv`, stamp the upstream commit/date into a resource, log the version at load, and flag staleness. Documents the `shortest-path-tooling` regenerate fallback.
  *Deps:* WP1. *Gate:* run script, diff resources, rebuild, load logs the version stamp.

**Critical path:** WP1 → WP2 → {WP4 → WP3} → WP5. WP6 parallels after WP1.

---

## 8. Risks & mitigations

- **Cache-version drift / data staleness.** Skretzo's data lags a game update by days; a moved door or new area won't be in the graph until refreshed. *Mitigations:* (1) the DEFECT-21 live-collision guard stays as the always-on net; (2) missing transport → follower's reactive `attemptOpenGate` still fires; (3) keep API+PNG dormant through phase C; (4) WP6 refresh script + version stamp so staleness is visible in logs. Pin to a known-good upstream commit rather than tracking `master` blindly.
- **Memory footprint on the 2011 iMac (diort).** `SplitFlagMap` loads the *whole* map into one shared `long[]` (~30–50 MB heap estimated; the 1.2 MB zip is compressed). diort is RAM- and thermally-constrained (per the run-host memory). *Mitigations:* measure actual heap on diort during WP2's gate before phase C; if too high, restrict the loaded region set to a bounding box around active play (the format is per-region, so a subset loader is feasible) — but only if measurement demands it, since Skretzo ships whole-map and it works on modest hardware. CPU: A\* here is a **single offline computation per GOTO**, not a hot re-planning loop, so it will not reproduce the DEFECT-19-v1 self-heating (that was a 50 000-iteration all-blocked grid; a populated graph converges in a fraction of that).
- **MannyPlugin.java LOCKED.** No edits allowed to the main plugin control flow. *Mitigation:* `ShortestPathEngine` is a self-initialising singleton (`getInstance()`, mirroring `CollisionDataLoader`); resources load via `getResourceAsStream`; the flag is a `MannyConfig` enum; the branch lives entirely inside `NavigationHelpers.gotoPositionSafe`. Nothing requires touching MannyPlugin.
- **Transport requirements vs account capability.** Agility shortcuts, teleports, and quest-gated edges need levels/items/quests the live account may lack; blindly using them yields unwalkable "paths." *Mitigation:* free-transport-only filter in early phases (§5.5); capability-aware filtering added per-routine later, never speculatively.
- **BSD-2 attribution.** *Mitigation:* retain Skretzo's copyright notice — LICENSE file in `manny.pathfinder`, BSD-2 header on every ported source, NOTICE crediting Skretzo + Explv. The packed `collision-map.zip` (Jagex-derived, BSD-2-redistributed by Skretzo) is bundled under that same notice.
- **Behavioural regression from deleting the API.** The API sometimes produced good long routes. *Mitigation:* do not delete until phase D, after GRAPH has soaked as default (phase C) with the API dormant-but-present for one milestone.

---

## 9. Appendix — key facts & citations

**Manny code (read-only, `/home/wil/Desktop/manny`):**
- Router seam: `utility/NavigationHelpers.java:1354` `gotoPositionSafe`. Follower `:1565`, `:3103` `findFurthestVisibleWaypoint`, `clickMinimapPoint`. DEFECT-21 guard `:289` `validateAgainstLocalCollision`, called `:2774`, `:3182`; water flag `0x200000` at `:334`.
- API: `utility/PathfinderApiClient.java:32` endpoint, `:56` `findPath`, `:161` LINK-skip.
- Collision loader: `utility/CollisionDataLoader.java` — `.dat` format magic `0xC0111510` `:564`, region size 64 `:42`, LRU `:409`.
- PNG: `utility/WorldMapData.java:56` `getResourceAsStream("/world_map.png")`.
- Paths: `utility/MannyPaths.java:189` `collisionDataDir()` = `HOME_BASE + "/data/collision/"`. HOME_BASE `:57` = `/home/wil/Desktop/manny`.
- Command: `utility/commands/GotoCommand.java:131` ≤3-tile no-op (DEFECT-7), `:119` plane guard.
- Dormant pipeline: `data/collision/README.md`; `scripts/download_cache.sh`, `scripts/extract_collision.sh`.
- Stage-1 landed: `manny@b40838a` (DEFECT-21 follower guard), `a5069a0`/`1403107` (DEFECT-19/19b), `a6da377` (DEFECT-20).

**Shortest Path (external, BSD-2-Clause):**
- Repo: `https://github.com/Skretzo/shortest-path` — collision `src/main/resources/collision-map.zip` = **1,197,109 bytes**; transports `src/main/resources/transports/*.tsv` (24 files, `transports.tsv` = doors/gates/stairs).
- Format: `pathfinder/SplitFlagMap.java` (zip entries `"<x>_<y>"`, 2 flags/tile N+E, region 64, packed `long[]`), `pathfinder/CollisionMap.java`, `pathfinder/Pathfinder.java` (A\* + transport heap, worker thread).
- Transport TSV columns: `Origin | Destination | "menuOption menuTarget objectID" | Skills | Items | Quests | Varbits | VarPlayers | Duration | Display info`.
- Tooling / regenerate fallback: `osrs-pathfinding/shortest-path-tooling` (cache dumpers). License: BSD-2-Clause.

**Companion report:** `journals/NAV_ARCHITECTURE_REPORT_2026-07-18.md`.
