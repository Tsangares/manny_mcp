# Navigation Architecture Report — GOTO Pipeline, Failure Modes, and the Patch-vs-Replace Decision

**Date:** 2026-07-18
**Scope:** Source analysis only (read-only). Java plugin at `/home/wil/Desktop/manny`, Python/MCP layer at `/home/wil/Desktop/manny_mcp`.
**Author:** Navigation architecture review (Opus research agent)

> A note on how to read this. GOTO is the single most load-bearing primitive in the whole
> project — every routine moves the character with it. This report traces GOTO from the Python
> routine layer all the way down to the individual minimap clicks, explains where each known
> failure comes from, and answers the owner's direct question: **do we patch the pathfinder, or
> replace it?** Short version of the answer: **patch to survive this milestone, then replace the
> collision/graph *core* next milestone — but keep the human-like minimap walker, which is an
> anti-detection asset, and delete the external `osrspathfinder.com` dependency along the way.**

---

## 1. Executive Summary (plain language)

- **GOTO is a four-layer hybrid, and the layers disagree about the map.** A route is fetched
  either from an *external* web service (`osrspathfinder.com`) or from a *local* A\* search, and is
  then "walked" by a minimap-clicking follower. The web service and the local search use
  completely different, and differently-wrong, ideas of what tiles are walkable. Most navigation
  pain traces to that mismatch.

- **The local map is a screenshot, not real collision data.** Long-range local pathfinding decides
  walkability by reading pixel colors out of a bundled image (`world_map.png`) — blue means water,
  bright-white means fence, red means gate. This is inherently fuzzy and is the root cause of
  **DEFECT-21** (routes across the Lumbridge river veer off the narrow bridge into the water). A
  precise, precomputed collision dataset is *scaffolded in the code but empty* — no data files ship.

- **The follower is "blind" — it never checks whether a tile is walkable before clicking it.** The
  minimap walker greedily clicks the farthest visible waypoint and only notices trouble *after* the
  character fails to move. Between sparse waypoints it clicks in straight lines, which is exactly how
  a character ends up walking off a bridge into a river.

- **GOTO cannot open a door in its path, by design.** The web service actually computes door/stair
  crossings but the client *throws those steps away* (it skips "LINK" steps). The result is that
  routines can't trust GOTO indoors, so they fall back to a manual, tool-driven "Indoor Navigation
  Protocol" — scan for doors, open them one at a time, walk one step, repeat. That works but it is
  slow and lives entirely in prompt/routine logic, not in the navigator.

- **The recommended direction is patch-now / replace-core-next.** This milestone: three surgical,
  low-risk patches (make the follower reject known-blocked clicks; tighten waypoint spacing near
  water; fix the GOTO "already there" tolerance bug). Next milestone: adopt the well-known
  open-source *Shortest Path* plugin's data model — a precomputed full-map collision grid plus a
  *transport graph* where doors, gates, stairs, and teleports are graph edges. That fixes DEFECT-19,
  DEFECT-21, and door-handling at the root, folds the Indoor Protocol into GOTO itself, and lets us
  remove the `osrspathfinder.com` network dependency entirely.

---

## 2. The GOTO Pipeline, End to End

Below, "tile" = one OSRS world square; a `WorldPoint` is `(x, y, plane)` where *plane* is the floor
(0 = ground). "Collision flags" = a bitmask the game keeps per tile saying which directions are
blocked by walls/objects/water. "Waypoint" = one point in a path the follower steers toward.

### 2.1 Layer diagram

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│ LAYER 0 — ROUTINE / MCP                                                              │
│   YAML/JSON routine step:  action: GOTO  args: "3235 3295 0"                         │
│   (background thread, replies ONLY on arrival, SAME PLANE only)                      │
│   MCP writes command → plugin command file                                          │
└───────────────────────────────┬──────────────────────────────────────────────────┘
                                 ▼
┌────────────────────────────────────────────────────────────────────────────────────┐
│ LAYER 1 — COMMAND ENTRY   GotoCommand.java:56                                        │
│   parse coords/name → plane guard (:119) → "already there ≤3 tiles" (:131)           │
│   close menus, cancel prior nav, zoom camera out → gotoPositionSafe(target, 1) :159 │
└───────────────────────────────┬──────────────────────────────────────────────────┘
                                 ▼
┌────────────────────────────────────────────────────────────────────────────────────┐
│ LAYER 2 — ROUTER   NavigationHelpers.gotoPositionSafe :1354                          │
│   compute initialDistance (:1377) and hasLineOfSight (:1381)                         │
│                                                                                      │
│   distance < 15 & LOS clear ──────────────► simpleDirectionalNavigation (LOCAL)      │
│   distance < 15 & LOS blocked ────────────► try open door, else API                 │
│   distance ≥ 15 (or blocked, no door) ────► PATHFINDER API (default path)           │
└───────────────┬──────────────────────────────────────────────┬─────────────────────┘
                ▼ (API branch)                                  ▼ (local branch)
┌───────────────────────────────────────┐   ┌────────────────────────────────────────┐
│ LAYER 3a — EXTERNAL API                │   │ LAYER 3b — LOCAL A*                     │
│ PathfinderApiClient.findPath :56       │   │ PathfindingHelpers.findPathGlobalAStar  │
│ POST osrspathfinder.com/find-path      │   │   :834                                  │
│ 5s timeout, 2 retries                  │   │  ≤20 tiles → live RuneLite collision   │
│ returns ~20 coarse waypoints           │   │            (findPathAStar :210)         │
│ DOORS/STAIRS COMPUTED SERVER-SIDE      │   │  >20 tiles → CollisionMapCache.canMove  │
│ BUT "LINK" steps are SKIPPED (:161)    │   │            OR world_map.png (PNG)       │
│ densify to ≤6-tile spacing (:1526)     │   │  thin + insertGateWaypoints             │
└───────────────┬───────────────────────┘   └───────────────┬────────────────────────┘
                └───────────────┬───────────────────────────┘
                                ▼
┌────────────────────────────────────────────────────────────────────────────────────┐
│ LAYER 4 — WAYPOINT FOLLOWER (minimap walker w/ lookahead)  :1565                     │
│   findFurthestVisibleWaypoint (:3103): pick FARTHEST waypoint within 12 tiles AND    │
│     inside the minimap circle (radius 60px) → clickMinimapPoint (:1712)              │
│   NO pre-click walkability check. Detects trouble only AFTER: distMoved ≤ 1 (:1686) │
│   reactive: on stuck, detectNearbyObstacle + attemptOpenGate (:1777)                 │
│                                                                                      │
│   Timeout layer (DEFECT-19b): simpleDirectionalNavigationMultiClick :1082           │
│     PROGRESS-AWARE — fail only after NO_PROGRESS_TIMEOUT 20s (:1096); 180s ceiling;  │
│     oscillation guard (≤3 unique tiles / 10 moves); 200-iteration cap                │
└────────────────────────────────────────────────────────────────────────────────────┘

  COLLISION DATA (feeds Layer 3b)
   • Live scan: GameEngine.scanAndCacheCollisionData :3204 — radius ~50 tiles, every 10 ticks,
     only when entering a NEW 64×64 region → CollisionMapCache (write-once, no eviction).
     canMove() is CONSERVATIVE: uncached tile ⇒ treated as BLOCKED.
   • Precomputed disk tier: CollisionDataLoader reads region_<id>.dat — DORMANT (zero files ship).
   • world_map.png (WorldMapData): pixel-color walkability — blue=water, white≥220=fence, red=gate.
```

### 2.2 The handoffs, in words

1. **Routine → command (Layers 0–1).** A routine emits `GOTO x y plane`. The MCP tool relays it to
   the plugin, where `GotoCommand` (`GotoCommand.java:56`) validates it. Two important early exits
   live here: a hard refusal if the target is on a different plane (`:119` — GOTO *cannot change
   floors*), and an "already at destination" success if within **3 tiles** (`:131`). It then calls
   `gotoPositionSafe(target, targetDistance=1)` (`:159`).

2. **Router decides API vs local (Layer 2).** `gotoPositionSafe`
   (`NavigationHelpers.java:1354`) computes the straight-line distance and a *line-of-sight (LOS)*
   check — "is the direct line from here to the target free of barriers, per the pixel map?"
   (`:1381`). The routing is a **distance-plus-LOS ladder**, not the simple "30-tile split" the docs
   claim. The real cutover constant is **15 tiles** (`:1385`, `:1394`, `:1442`). *Documentation
   drift worth fixing:* `README.md:405` and `CLAUDE.md` still describe `navigateToLocal()` /
   `navigateToGlobal()` with a 30-tile split — **those method names do not exist in the code**; the
   behavior is realized inline in `gotoPositionSafe`.

3. **Path acquisition (Layer 3).** For anything ≥15 tiles the *default* is the external API
   (`PathfinderApiClient.findPath`, `PathfinderApiClient.java:56`): an HTTPS `POST` to
   `osrspathfinder.com/find-path`, 5-second timeout, up to 2 retries, returning a coarse waypoint
   list (~20 points). The API *does* resolve doors, stairs, ships, and teleports server-side — **but
   the client deliberately discards the "LINK" steps that represent those crossings**
   (`PathfinderApiClient.java:161`, `// Skip LINK steps`). Only WALK points and TELEPORT endpoints
   survive. On success the path is densified so no two waypoints are more than ~6 tiles apart
   (`insertIntermediateWaypoints(path, 6)`, `NavigationHelpers.java:1526`).

4. **Local fallback (Layer 3b).** If the API returns nothing, the router first tries a **fast
   line-of-sight shortcut** (the DEFECT-19 fix — see §3), and only if LOS is blocked does it call
   the local **Global A\*** (`PathfindingHelpers.findPathGlobalAStar`, `:834`). Global A\* itself
   branches: ≤20 tiles uses the *live* RuneLite collision API for accuracy (`findPathAStar`,
   `:210`); >20 tiles uses either the runtime `CollisionMapCache` (if `config.useCollisionData()`)
   or the `world_map.png` pixel data. It then thins redundant waypoints and inserts approach/at/exit
   waypoints around any red-pixel "gates" (`insertGateWaypoints`, `:585`).

5. **The follower walks it (Layer 4).** `NavigationHelpers.java:1565` onward. This is a **lookahead
   minimap walker**: `findFurthestVisibleWaypoint` (`:3103`) scans forward and returns the *farthest*
   waypoint that is both within 12 tiles and geometrically inside the minimap circle (radius 60px),
   and clicks it (`clickMinimapPoint`, `:1712`). This "click the farthest visible point" behavior is
   what makes movement look human and efficient. **Crucially, it performs no walkability check before
   clicking** (confirmed: `validateAgainstLocalCollision` exists at `:289` but is *not called* in the
   click path). It detects a bad click only reactively — if the character fails to move
   (`distMoved ≤ 1`, `:1686`) — and then tries to open a nearby gate/door.

6. **Arrival & timeouts.** Arrival tolerance is the caller's `targetDistance` (GOTO passes 1, but the
   "already there" guard in `GotoCommand` uses 3). The anti-hang timeout layer is
   `simpleDirectionalNavigationMultiClick` (`:1082`), which after DEFECT-19b is **progress-aware**:
   it fails only after 20s of *no forward progress* (`NO_PROGRESS_TIMEOUT_MS`, `:1096`), with a 3-minute
   absolute ceiling (`:1097`), plus oscillation and speed guards and a 200-iteration cap.

### 2.3 Collision data — what the local layers actually know

This is the crux of most defects, so it deserves its own summary (source: GameEngine, CollisionMapCache,
CollisionDataLoader, WorldMapData):

- **Live scan** (`GameEngine.scanAndCacheCollisionData`, `:3204`): reads the game's own collision
  flags for tiles within ~**50 tiles** of the player, fired every 10 game ticks (~6s) and **only when
  the player crosses into a new 64×64 region** (`MannyPlugin.java:1338-1354`). Results go into
  `CollisionMapCache`, which is **write-once and never evicted** (no TTL, no size cap). Tiles the
  player has never walked near are simply **unknown**.
- **Conservative unknowns:** `CollisionMapCache.canMove()` returns **false** (blocked) if either tile
  is uncached (`CollisionMapCache.java:163-166`, "prevents A\* from finding paths through unknown
  areas"). This is safe but it means **a fresh long route is mostly "blocked" to local A\*** — the
  direct cause of DEFECT-19.
- **Precomputed tier is empty:** `CollisionDataLoader` is built to load precise per-region collision
  from `data/collision/region_<id>.dat` files (`:396`), but **none ship** — the directory contains
  only a README telling the user to download a ~2–3 GB game cache and generate them with
  `scripts/extract_collision.sh`. Confirmed: `find … -name "region_*.dat"` returns nothing. So this
  "collision-complete" tier is fully scaffolded but dormant.
- **The pixel map:** `world_map.png` (`WorldMapData.java`) is a static image where each pixel ≈ one
  tile; walkability is inferred from color — water if blue-dominant (`blue>100, red<120, green<150`),
  fence if brightness ≥ 220, gate if red. A 3×3 majority vote smooths noise (`:120-158`). This is the
  *only* dense, always-available "map" the bot has today, and it is fundamentally approximate.

---

## 3. Failure-Mode Analysis

| Defect / class | Symptom | Where in pipeline | Root cause | Status |
|---|---|---|---|---|
| **DEFECT-7** — arrival tolerance no-op | `GOTO 3104 9509` returns *"Already at — distance 2/3 tiles"* without moving; then `INTERACT` fails "can't reach" | Layer 1 (`GotoCommand.java:131`, ≤3 tiles) + `waitForArrival` tolerance | Arrival tolerance is too loose for precision moves; a target 2–3 tiles away (even behind a fence) counts as "arrived", so no real pathing runs | **OPEN** (documented worse than first thought; needs an `exact`/tolerance-0 mode) |
| **DEFECT-19** — long-route stall | 76-tile GOTO never moves for ~45s; log ends at "falling back to Global A\*"; LOS was *clear* | Layer 3 handoff: API fails → local A\* | In the sandbox the external API is unreachable, so every call fails and falls back. Local A\* then treats the mostly-**uncached** route as fully blocked (`canMove`=false for unknown tiles) and returns null → router gives up without walking, *even though LOS was clear* | **FIXED** (`a5069a0`): take the LOS directional shortcut **before** the slow A\* (`NavigationHelpers.java:1467-1479`) |
| **DEFECT-19 v1 regression** — hot A\* churn | First fix put the shortcut *after* A\*; A\* churned the blocked grid up to 50 000 iterations, hung >51s, CPU hit 90 °C | Layer 3b (`findPathGlobalAStar` maxIterations 50 000, `PathfindingHelpers.java:971`) | A\* over an all-"blocked" grid does not fail fast | **FIXED** (superseded by v2 ordering) |
| **DEFECT-19b** — walk aborts mid-progress | After the shortcut fired and the character walked 35 of 76 tiles (distance steadily dropping), it aborted at a flat 30s timeout | Layer 4 timeout (`simpleDirectionalNavigationMultiClick`) | The old timeout was an **absolute** 30s wall-clock; a legitimate long walk simply takes longer, so "slow" was misread as "stuck" | **FIXED** (`1403107`): progress-aware timeout (`:1096-1099`); anti-hang live-validated on diort, full happy-path gate still pending |
| **DEFECT-20** — off-thread collision reads | "must be called on client thread" crashes from mining/cooking callers | Collision reads in GameEngine | Collision/tile lookups executed on background threads | **FIXED in source** (`a6da377`); live re-verification pending |
| **DEFECT-21** — river/bridge mis-route | Route crossing the Lumbridge river **veers west off the bridge into the water and stalls at the bank**. North-side grinds are fine. Reproduced on diort where the API *is* reachable (7ms) | Layers 3b + 4 together | See dedicated analysis below | **OPEN** (not yet fixed in plugin HEAD `a6da377`) |
| **Infinite pathfinding loop** (2026-01-27) | Bot clicks "Cancel" once/second forever on an unreachable target; oscillates between two tiles | Layer 4 | No global timeout/iteration cap; oscillation not caught (mean-speed stays high when bouncing 2 tiles); "Cancel-only" menu not treated as failure | **FIXED**: oscillation + 30s + 200-iter + Cancel-menu guards added (the 30s absolute limit that DEFECT-19b later had to make progress-aware) |
| **Phase-1 naive clicking** (2026-02-10) | GOTO fell to naive minimap clicking and walked Falador→(2979,3520), hundreds of tiles the wrong way, no abort | Layer 4 fallback path | The oldest fallback had **no** time/iteration limit; speed-based stuck detection never fires during a full-speed walk in the wrong direction | **FIXED**: 60s + 200-iter cap added; lesson: *fallbacks need stricter limits than the primary path, not looser* |

### 3.1 DEFECT-21 in depth — is it the API, the follower, or the collision data?

The owner asked precisely this. Reasoning from the code, **it is not the API, and it is a
compounding of the follower and the collision data — the two "blind" halves of the system reinforcing
each other:**

- **Not the API path.** DEFECT-21 reproduces on diort where `osrspathfinder.com` responds in 7ms, so
  the coarse API waypoints are presumably geometrically sane (they cross via the bridge). The failure
  happens *while walking them*, not in acquiring them.

- **The follower cuts corners between sparse waypoints.** The API returns ~20 coarse points; densify
  brings spacing to ~6 tiles (`NavigationHelpers.java:1526`), and the interpolation is **straight-line
  linear** (`PathfindingHelpers.insertIntermediateWaypoints:552-562`). The Lumbridge bridge is a
  narrow, not-perfectly-axis-aligned strip. A straight segment between two on-bridge waypoints — or
  the follower's own lookahead, which clicks the *farthest* visible waypoint up to 12 tiles away
  (`:3103`) — can pass through a tile that is *off* the bridge and *in* the water. Because the follower
  does **no pre-click walkability check** (`validateAgainstLocalCollision` exists but is unused,
  `:289`), it happily clicks a water tile; the character walks to the bank, can't continue, and the
  progress timeout eventually fails it. This is the "veered west off the bridge line and stalled at
  the bank" signature exactly.

- **The collision data can't save it, and may cause it.** If the walk ever drops to local A\*, the
  only dense map is `world_map.png`, whose water test is a blue-dominant pixel check with a 3×3
  majority vote (`WorldMapData.java:120-158, 228-232`). A one-tile-wide bridge over blue water is a
  worst case for 3×3 majority sampling: the neighborhood around a genuine bridge tile is mostly water
  pixels, so the vote can flip the bridge tile to "unwalkable", making A\* refuse the bridge and route
  around — into the bank. Either way, **there is no authoritative "the bridge is walkable, the river
  is not" signal** anywhere in the local stack.

**Verdict:** DEFECT-21 is a *route-quality/execution* bug born of (1) a follower that trusts geometry
over collision and (2) an approximate pixel map with no reliable notion of a narrow walkable corridor
over water. A targeted fix (follower legality gate + tighter near-water spacing) will stop the
immediate bleeding; only real per-tile collision data removes the class of bug.

---

## 4. Doors and Gates — Today's Reality and Why GOTO Can't Open Them

### 4.1 What exists today

- **Observability tool — `QUERY_TRANSITIONS`** (MCP: `scan_environment(transitions_only=True)`,
  `mcptools/tools/spatial.py:362-424`; plugin: `GameEngine.findNavigableTransitions:2304`). It
  categorizes nearby objects into **doors, gates, stairs, ladders, trapdoors, portals**, each with
  `state` (open/closed — inferred from whether the object offers an "Open" vs "Close" action,
  `GameEngine.java:2488-2496`), `direction`, `distance`, `actions`, and `objectId`. This exists
  precisely because the ordinary "scan nearby objects" call *excludes WallObjects* — so closed doors
  and gates were previously **invisible** to the bot (`indoor_navigation_transitions_2025-01-16.md`).

- **Manual opener — `INTERACT_OBJECT <name> Open`.** The routine layer opens a specific door/gate by
  name and action.

- **The "Indoor Navigation Protocol"** (`CLAUDE.md:184-197`; origin
  `journals/navigation/indoor_navigation_lessons_2025-01-04.md`). Because *"naively GOTO-ing through
  buildings"* traps the character, routines follow a manual loop: **scan transitions → plan a route
  through the doors → for each door: walk to it, `INTERACT_OBJECT … Open`, verify, walk one step
  through, repeat.** This is reliable but entirely hand-driven at the routine/LLM layer — it is a
  workaround for GOTO's inability to path through transitions.

- **Inside the Java walker:** two partial mechanisms exist. (1) *Reactive* gate opening — when the
  follower detects it's stuck, it calls `detectNearbyObstacle` + `attemptOpenGate`
  (`NavigationHelpers.java:1777`). (2) *Proactive* gate waypoints — local A\* paths get
  approach/at/exit waypoints inserted around any red-pixel gate (`insertGateWaypoints`,
  `PathfindingHelpers.java:585`). Neither covers doors on API paths.

### 4.2 Why GOTO cannot open a closed door in its path

Three independent reasons, all in the code:

1. **The API's door steps are discarded.** `osrspathfinder.com` *does* return the crossing as a
   "LINK" step, but `PathfinderApiClient.java:161` explicitly **skips LINK steps**. So the waypoint
   list handed to the follower contains no "open this door" instruction — just WALK points on both
   sides of a door that is currently shut.

2. **Closed doors aren't "collision" the follower checks.** The pixel map has no per-object door
   state, and the follower does no pre-click legality check anyway. So the walker clicks a waypoint
   on the far side of a closed door, the character bumps the door and stops, and only the *reactive*
   `attemptOpenGate` might rescue it — if the obstacle is recognized as an openable gate within range.

3. **There is no transition-aware graph.** Nothing in the navigator represents "to get from tile A to
   tile B you must perform action *Open* on object *Large door* at tile C." Doors/stairs/gates are not
   edges in any graph the pathfinder searches.

### 4.3 What "path through doors" would require

A **transition-aware graph**: nodes are tiles (or regions), and *some* edges are not plain steps but
*actions* — `Open(Large door)`, `Climb-up(Staircase)`, `Cross(Gate)`, `Teleport(...)`. The follower
would then execute an edge either as a walk *or* as an `INTERACT_OBJECT`. This is exactly the model
the open-source Shortest Path plugin uses (§5), and it is the clean way to fold today's manual Indoor
Protocol into GOTO itself.

---

## 5. The Obvious Alternative — the RuneLite "Shortest Path" Plugin Approach

The well-known open-source **Shortest Path** RuneLite plugin (Skretzo, building on Explv's map work)
takes the opposite architecture to Manny's current hybrid:

- **Precomputed, client-side, offline.** It ships a **full-map collision grid** — packed per-region
  walkability/wall bit-flags extracted from the OSRS game cache — and does **all pathfinding locally**
  with BFS/A\*-style search. No network call, ever.
- **Transports as graph edges.** It ships a `transports` dataset (a plain TSV) listing doors, gates,
  staircases, ladders, ships, spirit trees, agility shortcuts, and teleports as **edges** connecting
  tile A to tile B with an associated action/requirement. Its search treats "open this door" or "climb
  these stairs" as a first-class move — so it paths *through* buildings and *between floors*
  natively. This is precisely the "transition-aware graph" §4.3 calls for.
- **Licensing.** The plugin is **BSD-2-Clause** — permissive and compatible with vendoring its data
  files and/or porting its algorithm into this project, provided the copyright notice is retained.
  (The collision data is derived from Jagex's cache, so it's regenerated locally rather than
  redistributed wholesale — the same posture Manny's own dormant `.dat` pipeline already assumes.)

**How close is Manny to this already?** Surprisingly close in *intent*: `CollisionDataLoader` +
`scripts/download_cache.sh` + `scripts/extract_collision.sh` are a home-grown version of exactly this
data pipeline (per-region collision `.dat` files). It's just **never been populated**, and there is
**no transport/transition graph** to go with it. Adopting the Shortest Path model is therefore less a
rewrite than a *completion plus extension* of infrastructure that's already sketched in.

**Trade-off vs today's API+follower hybrid:** the API gives high-quality routes with zero data-shipping
cost, but it is a **network dependency inside a timing-sensitive control loop** — unreachable in the
sandbox (the entire trigger for DEFECT-19), and a general reliability/liability concern. The Shortest
Path approach front-loads a data-generation cost (a few MB of collision + a TSV, regenerated when the
game updates) in exchange for deterministic, offline, transition-aware routing.

---

## 6. Options Matrix

Effort: **S** ≈ hours–day, **M** ≈ few days, **L** ≈ a week+. "Removes API?" = does it let us delete the
`osrspathfinder.com` dependency.

| # | Option | What it fixes | Effort | Risk | Removes API? |
|---|---|---|---|---|---|
| **(a)** | **Targeted patches.** (1) Wire the *existing* `validateAgainstLocalCollision` (`NavigationHelpers.java:289`) into the follower so it never minimap-clicks a tile known to be blocked. (2) Tighten densification spacing near water and make interpolation reject water tiles. (3) Add a bridge-corridor constraint (hard-coded walkable strip, mirroring the existing `INTERIOR_AREAS` mechanism in `WorldMapData.java:352`). | **DEFECT-21** (the water-click half), robustness of every walk. Not gates, not 19 root. | **S–M** | **Low–Med** | No |
| **(b)** | **Make local pathfinding collision-complete.** Populate/bundle the precomputed per-region `.dat` collision (the `CollisionDataLoader` pipeline already exists) and enable `useCollisionData`. Global A\* then has *real* per-tile flags everywhere, not pixels or "unknown = blocked." | **DEFECT-19** at root (no more uncached-blocked), **DEFECT-21** (real bridge collision), long-route quality. Not gates/doors (collision alone). | **M** | **Med** (data staleness on game updates; generation needs the game cache) | **Yes** (for correctness — API becomes optional) |
| **(c)** | **Adopt the Shortest Path graph wholesale (the "replace" option).** Precomputed collision **plus a transport/transition graph** (doors, gates, stairs, ladders, teleports as edges); purely client-side search; follower executes walk-edges and action-edges. | **DEFECT-19, DEFECT-21, door/gate blockage, cross-plane GOTO** — and folds the Indoor Protocol into GOTO. | **L** | **Med–High** (integration + port + data pipeline + keeping transports current) | **Yes** (fully) |
| **(d)** | **Keep API primary + robust local validation layer.** API stays the fast path, but add the follower legality gate from (a) and a collision-complete validation net from (b) so the API is *no longer load-bearing*. | **DEFECT-21** (validation catches water clicks), partial gates, de-risks API outages. Not door-pathing. | **M** | **Low** | No (but demotes it from critical to optional) |

---

## 7. Recommendation & Staged Plan

**Answer to "patch or replace?": both, in sequence — patch the *follower/tolerance* now, replace the
*collision/graph core* next — and along the way delete the external API and keep the minimap walker.**

The single most important framing: **the minimap-click follower is not the problem — it's an asset.**
Its human-like, lookahead clicking is the bot's anti-detection movement layer. The problem is that it's
*fed a bad map and given no veto*. So we do **not** rewrite the follower; we give it a trustworthy map
and a legality gate, and we replace what sits *above* it.

### Stage 1 — Lands THIS milestone (Options a + the DEFECT-7 fix) — S/M, low risk

1. **Follower legality gate.** Wire `validateAgainstLocalCollision` into the click path so the walker
   refuses to minimap-click a tile that live collision says is blocked, re-selecting the nearest legal
   waypoint instead. *Directly attacks the water-click half of DEFECT-21 with code that already
   exists.*
2. **Near-water waypoint hardening.** Reduce densification spacing and reject interpolated points that
   land on water; optionally add the Lumbridge bridge as a hard-coded walkable corridor using the
   existing `INTERIOR_AREAS` pattern. *Stops DEFECT-21 from stranding grinds that must cross the
   river.*
3. **DEFECT-7 exact-arrival mode.** Add an `exact`/tolerance-≤1 option to GOTO so short precision moves
   actually path instead of no-op'ing at 2–3 tiles. *Cheap, removes a recurring quest/tutorial
   blocker.*

These are surgical, touch only the follower and command entry, keep the API untouched, and can ship
without any data pipeline.

### Stage 2 — Next milestone (Options b → c) — M then L, strategic

4. **Collision-complete local map (b).** Populate the `.dat` region collision (bundle a compressed
   subset, or run the existing extract scripts) and switch Global A\* onto it. This *permanently*
   retires DEFECT-19's "uncached = blocked" failure and makes DEFECT-21 impossible at the map level,
   and it lets us **flip the external API from mandatory to optional accelerator, then remove it** —
   eliminating the network/sandbox liability that started this whole saga.
5. **Transition graph (c).** Layer a transport/transition graph (Shortest Path's model) on top of the
   collision grid so doors, gates, stairs, and teleports become path edges the search can traverse.
   The follower gains one new move type — "execute `INTERACT_OBJECT` for an action-edge" — reusing the
   `QUERY_TRANSITIONS` machinery that already detects and states these objects. This **folds the manual
   Indoor Navigation Protocol into GOTO itself** and delivers reliable cross-plane, through-building
   navigation.

### What we explicitly do NOT do

- **Do not rewrite the minimap follower** — it's the stealth layer; keep it and feed it better input.
- **Do not keep `osrspathfinder.com` as load-bearing** — every diagnosis flags it as a liability
  ("keep it, but it should not be load-bearing"). Demote in Stage 2b, remove after 2c proves out.
- **Do not deepen the pixel map** — `world_map.png` is a stopgap; invest in real collision (b), not
  better pixel heuristics.

**One-line answer for the owner:** *Patch the follower and tolerance this milestone to stop DEFECT-21
and DEFECT-7 bleeding; next milestone replace the pathfinding core with a precomputed collision grid +
transition graph (the Shortest Path model your `CollisionDataLoader` already half-builds), which fixes
19/21/doors at the root and lets us delete the external API — while keeping the human-like minimap
walker exactly as-is.*

---

## 8. Appendix — Code Citations

**Command entry**
- `utility/commands/GotoCommand.java:56` — `executeCommand`; `:119` plane guard; `:131` "already there ≤3 tiles"; `:159` calls `gotoPositionSafe(target, 1)`.

**Router / follower (`utility/NavigationHelpers.java`)**
- `:1354` `gotoPositionSafe`; `:1377` initialDistance; `:1381` `hasLineOfSight`.
- Routing ladder: `:1385` (<15 & LOS → local), `:1394` (<15 & blocked → door/API), `:1442` (≥15 → API).
- `:1462` API call; `:1467-1479` DEFECT-19 LOS shortcut *before* A\*; `:1482` local A\* fallback; `:1514` door-open + A\* retry; `:1526` `insertIntermediateWaypoints(path, 6)`.
- Follower: `:1565` lookahead loop; `:3103` `findFurthestVisibleWaypoint` (12-tile / 60px minimap circle); `:1712` `clickMinimapPoint`; `:1686` post-click `distMoved ≤ 1` blocked check; `:1777` reactive `attemptOpenGate`.
- Timeout: `:1082` `simpleDirectionalNavigationMultiClick`; `:1096` `NO_PROGRESS_TIMEOUT_MS=20_000`; `:1097` `MAX_NAV_TIME_MS=180_000`; oscillation guard `:1147-1159`.
- `:289` `validateAgainstLocalCollision` (defined, **unused** in click path).

**Local A\* (`utility/PathfindingHelpers.java`)**
- `:210` `findPathAStar` (local, ≤ live scene); `:834` `findPathGlobalAStar` (≤20 local API vs >20 cache/PNG); `:971` `maxIterations=50000`; `:360` `thinWaypoints`; `:474` `thinWaypointsByDistance`; `:524` `insertIntermediateWaypoints` (linear interp `:552-562`); `:585` `insertGateWaypoints`; `:1299` `hasLineOfSight`; `:804` `isWalkableHybrid` (cache → PNG → optimistic true).

**External API (`utility/PathfinderApiClient.java`)**
- `:32` endpoint `osrspathfinder.com/find-path`; `:56` `findPath`; 5s timeout / 2 retries; `:151-160` TELEPORT handled; `:161` **LINK steps skipped**.

**Collision data**
- Live scan: `utility/GameEngine.java:3204` `scanAndCacheCollisionData` (radius ~50/52 `:3257`); trigger `MannyPlugin.java:1320,1338-1354` (every 10 ticks, new region only, radius 50).
- `utility/CollisionMapCache.java:163-166` `canMove` conservative (uncached = blocked); write-once, no eviction (`:233-241` only manual clear).
- `utility/CollisionDataLoader.java:44` `COLLISION_DATA_DIR`; `:396` reads `region_<id>.dat`; `:82-97` warns when no `.dat` files exist. **Confirmed empty** — `data/collision/` holds only README; `find … region_*.dat` returns nothing.
- `utility/WorldMapData.java` — `world_map.png`; water `:228-232`; fence `≥220`; gate red `:273-289`; 3×3 majority `:120-158`; `INTERIOR_AREAS` `:352`; interior penalty `:385`.

**Door/gate at routine layer**
- `CLAUDE.md:184-197` Indoor Navigation Protocol; `journals/navigation/indoor_navigation_lessons_2025-01-04.md` origin; `journals/navigation/indoor_navigation_transitions_2025-01-16.md` (WallObjects invisible).
- Transitions tool: `mcptools/tools/spatial.py:362-424` (`_query_transitions`); plugin `GameEngine.findNavigableTransitions:2304`, state detection `:2488-2496`.

**Prior diagnoses**
- `manny/journals/DEFECT19_NAVIGATION_DIAGNOSIS.md` (DEFECT-19/19b; "API is a nice-to-have accelerator; keep it, but it should not be load-bearing").
- `manny_mcp/journals/infinite_pathfinding_loop_2026-01-27.md`; `phase1_nav_infinite_clicking_2026-02-10.md`; `TUTORIAL_TEST_DEFECTS_2026-07-17.md` (DEFECT-7); `2026-07-18_parallel_stage_and_orchestration_lessons.md` (DEFECT-19b live-validated, DEFECT-21 discovered); `OVERSEER_HANDOFF.md`.

**Plugin git state at analysis time**
- `manny` HEAD = `a6da377` (DEFECT-20). DEFECT-21 fix **not yet landed** in source; no working-tree changes observed. If the concurrent debugging agent lands a targeted DEFECT-21 fix, re-check `git log` and reconcile §3.1 against it.

**Documentation drift to correct**
- `README.md:405` / `CLAUDE.md` describe `navigateToLocal()` / `navigateToGlobal()` with a 30-tile split; these methods **do not exist** — routing is inline in `gotoPositionSafe` with a **15-tile + LOS** cutover.
