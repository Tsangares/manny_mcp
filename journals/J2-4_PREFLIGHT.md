# J2-4 Navigation-Extraction Pre-Flight Checklist

**Date:** 2026-07-18 (produced during DEPLOYMENT FREEZE — read-only survey, ZERO .java edits made)
**Author:** J2-4 pre-flight agent
**Purpose:** Pre-stage the B1 (`PathfindingHelpers.java`) + B2 (`NavigationHelpers.java`) + `handleGotoCommand`
extraction so it executes fast the moment the freeze lifts.
**Working file surveyed:** `/home/wil/Desktop/manny/utility/PlayerHelpers.java` — **16,075 lines** (NOT the
23,683 the plan measured; J2-1 dead-purge, J2-2 latch-conversion, and J2-3 un-nest have ALL already landed).
Every line number below was re-derived by symbol name against the current tree.

> **State-of-tree note:** The plan (`W6J2_SPLIT_PLAN.md`) and edge report (`W6J2_CALL_EDGES.md`) are measured
> against the pre-J1 23,683-line tree. Their line numbers are dead. LocationManager (A6), EquipmentSystem (A1),
> ControlSystem (A3), CommandStateManager (A4), PathfindingStateManager (A5), MiningHelper (A8) are ALREADY
> un-nested into their own `utility/*.java` files (J2-3 done). The B1/B2 regions below are latch-free
> (J2-2 converted all CountDownLatch sites — grep confirms **zero** `CountDownLatch` in lines 408-6017).

---

## 1. Exact current boundaries

All B1 + B2 methods live in **PlayerHelpers-proper** (the outer class, before `CommandProcessor` which
starts at line **6851** `public static class CommandProcessor`). `handleGotoCommand` lives INSIDE
CommandProcessor. SECTION 0 header is at 408-410; SECTION 1 (widget ops, stays in PH / future B3) at 1728.

### B1 — `PathfindingHelpers.java` (SECTION 0: A* pathfinding), lines 408-1726 (~1,319 lines)

| Symbol | Start | End (excl.) | Signature | Fields read/written |
|---|---|---|---|---|
| `PathNode` (priv static class) | 415 | ~458 | `implements Comparable<PathNode>` | — (local A* node) |
| `MinimapData` (priv static class) | 459 | ~475 | data holder | — |
| `MinimapPointData` (priv static class) | 476 | ~493 | data holder | — |
| `isWalkable` | 494 | 564 | `private boolean isWalkable(WorldPoint) throws InterruptedException` | reads `client`, `worldMapData`, `helper` |
| `findPathAStar` | 565 | 692 | `private List<WorldPoint> findPathAStar(WorldPoint,WorldPoint,int) throws InterruptedException` | calls isWalkable/reconstructPath |
| `reconstructPath` | 693 | 714 | `private List<WorldPoint> reconstructPath(PathNode)` | — |
| `thinWaypoints` | 715 | 828 | `private List<WorldPoint> thinWaypoints(List<WorldPoint>)` | calls hasLineOfSight |
| `thinWaypointsByDistance` | 829 | 878 | `private List<WorldPoint> thinWaypointsByDistance(List<WorldPoint>,int)` | — |
| `insertIntermediateWaypoints` | 879 | 939 | `private List<WorldPoint> insertIntermediateWaypoints(List<WorldPoint>,int)` | — |
| `insertGateWaypoints` | 940 | 1080 | `private List<WorldPoint> insertGateWaypoints(List<WorldPoint>)` | reads `worldMapData` |
| `findFurthestCachedWaypoint` | 1081 | 1158 | `private WorldPoint findFurthestCachedWaypoint(WorldPoint,WorldPoint,CollisionDataLoader)` | uses CollisionDataLoader |
| `isWalkableHybrid` | 1159 | 1188 | `private boolean isWalkableHybrid(WorldPoint)` | reads `CollisionMapCache` |
| `findPathGlobalAStar` (2 overloads) | 1189 / 1194 | 1516 | `private List<WorldPoint> findPathGlobalAStar(WorldPoint,WorldPoint[,int])` | `pathfinderApiClient`, CollisionDataLoader/Cache, `worldMapData` |
| `isPlayerEnclosed` | 1517 | 1555 | `private boolean isPlayerEnclosed(WorldPoint)` | reads `client` |
| `findNearestExitTile` | 1556 | 1653 | `private WorldPoint findNearestExitTile(WorldPoint,WorldPoint)` | — |
| `hasLineOfSight` | 1654 | 1726 | `private boolean hasLineOfSight(WorldPoint,WorldPoint)` | reads `worldMapData` |

**B1 state:** No mutable cross-domain instance state. All deps are final injected fields
(`client`, `clientThread`, `worldMapData` @219, `pathfinderApiClient` @222) or ephemeral CollisionDataLoader/
CollisionMapCache locals. **CLEAN verbatim move.** All 14 methods are `private`; **zero external callers**
(the `isWalkable` grep hits in CollisionDataLoader/CollisionMapCache/PathfindingVisualizer are
`collisionData.isWalkable()` / `data.isWalkable()` — different objects, NOT PH's method).

### B2 — `NavigationHelpers.java` (navigation execution engine), ~3,521 lines

**Nav-state fields (top of class):**
| Field | Line | Type |
|---|---|---|
| `shouldCancelNavigation` | 249 | `private volatile boolean` |
| `lastKnownPosition` | 253 | `private WorldPoint` |
| `stuckRecoveryAttempts` | 255 | `private int` |
| `STUCK_DETECTION_INTERVAL_MS` / `STUCK_POSITION_THRESHOLD_TILES` / `MAX_STUCK_RECOVERY_ATTEMPTS` | 256-258 | `private static final int` |
| `MINIMAP_WIDGET_ID` / `MINIMAP_WIDGET_ID_ALT` | 261-262 | `private static final int` |

**Movement utils (2062-2160):**
| Method | Start | Sig |
|---|---|---|
| `calculateNextWaypoint` | 2062 | `public WorldPoint calculateNextWaypoint(WorldPoint,int)` |
| `checkMovementProgress` | 2089 | `public boolean checkMovementProgress(List<Integer>,int)` |
| `getDistanceMoved` | 2115 | `public int getDistanceMoved(WorldPoint)` |
| `localToMinimap` | 2125 | `public net.runelite.api.Point localToMinimap(LocalPoint)` |
| `worldToLocal` | 2133 | `public LocalPoint worldToLocal(WorldPoint)` |
| `getAngleTo` | 2141 | `public double getAngleTo(LocalPoint)` |
| `getRotationDirection` | 2158 | `public char getRotationDirection(double,double)` |

**Stuck detection (2179-2400):** `validateAgainstLocalCollision` 2179 (private), `detectIfStuck` 2243 (private,
reads/writes `lastKnownPosition`+`stuckRecoveryAttempts` @2255-2269,2393), `escapeFromStuckPosition` 2290
(private, writes `stuckRecoveryAttempts` @2292, calls clickMenuEntrySafe delegate).

**Nav core (2407-5426):**
| Method | Start | Sig / note |
|---|---|---|
| `gotoPosition(LocalPoint)` | 2407 | `public ... throws InterruptedException` |
| `gotoPosition(WorldPoint)` | 2421 | `public` — **external seam** |
| `cancelCurrentNavigation` | 2430 | `public void` — writes `shouldCancelNavigation=true` @2433 — **external seam** |
| `retryWithGlobalAStar` | 2444 | private |
| `continueWithPhase1Navigation` | 2632 | private |
| `simpleDirectionalNavigation` | 2785 | private |
| `waitForPlayerIdle(int)` | 2873 | private — **B2** (NOTE: distinct from `waitPlayerIdle()` @5443→B5) |
| `waitForArrival` | 2913 | private |
| `simpleDirectionalNavigationMultiClick` | 2972 | private |
| `clickMinimapWithBoundsCheck` | 3113 | private |
| `gotoPositionSafe` | 3216 | `public boolean gotoPositionSafe(ClientThread,WorldPoint,int)` — **~800 lines, ends 4028; HIGHEST-RISK; resets `shouldCancelNavigation=false` @3220; external seam** |
| nav data classes | 4029-4126 | `ObstacleResult` 4029, `GateData` 4042, `ObstacleScanner`+`ScanResult` 4057/4058, `MinimapNavigationData` 4076, `ItemPairCheck` 4089, `ItemBoundsPair` 4102, `AnimationCheckResult` 4115 (all priv static) |
| `detectNearbyObstacle` | 4133 | private |
| `isObstacleOnPath` | 4276 | private |
| `attemptOpenGate` | 4340 | private — calls clickMenuEntrySafe @4433 |
| `recomputePathAfterGate` | 4481 | private |
| `tryAlternativePath` | 4522 | private |
| `hasPlayerMoved` | 4581 | private |
| `clickMinimapPoint` | 4597 | private |
| `clickMinimapPointDirect` | 4689 | private |
| `findAndPrepareGameObject` | 4753 | private |
| `findAndPrepareGameObjectPublic` | 4896 | `public TileObject ...` — **external seam** (calls cameraSystem.scanAndRotateToObject @4879) |
| `clickTileDirect` | 4905 | private |
| `findFurthestVisibleWaypoint` | 4990 | private — reads MINIMAP_WIDGET_ID via getWidget @5021 |
| `waitForWaypointOrContinue` | 5068 | private — reads `shouldCancelNavigation` @5077 |
| `waitForPlayerIdle(long)` | 5255 | private — **B2** (second overload) |
| `isWaypointClickable` | 5328 | private |
| `generateIntermediateWaypoint` | 5377 | private |
| `getMinimapBounds` | 5426 | `private Rectangle` |

**EXCLUDE from B2 (these go to B5 AnimationHelpers in J2-5, leave in PH now):**
`waitPlayerIdle()` (no-arg) @5443, `waitPlayerAnimation(int,double)` @5454. **Do not move these** — they sit
between getMinimapBounds and getDistanceTo but belong to B5.

**Also B2 (after the B5 gap):** `getDistanceTo(WorldPoint)` @5499 (public), `isWithinDistance(WorldPoint,int)`
@5513 (public). **smartMinimapClick(WorldPoint)** @5897 (public, ends ~6001) + its helper class
**`MinimapClickData`** @6006-6017 (priv static). smartMinimapClick calls `getHoverActionName()` @5973/5988
(a B4 method @6025, stays in PH now).

### handleGotoCommand — currently INSIDE CommandProcessor, lines 12925-13046 (~122 lines)

`public boolean handleGotoCommand(String args)` @12925. Reads/uses: `locationManager.getLocation()` @12954/12961
(CommandProcessor field @6914, `new LocationManager()` @7165), `responseWriter.writeFailure/writeSuccess`
(CP field @6899), `helper.readFromClient` @12976, `client.getLocalPlayer()`, `clientThread`, and via the
`playerHelpers` back-ref: `clearOpenMenus()` @12999, `cancelCurrentNavigation()` @13003,
`gotoPositionSafe(clientThread,target,1)` @13013. **Internal callers inside CP:** 12693, 12703, 12860, 12876,
12881 (handleAtBank / handleElsewhere region). **External callers:** 13 `processor.handleGotoCommand` sites
in commands/ (SmeltBars, SmeltBronzeBars, KillCowGetHides, BuyGe, TelegrabWineLoop per Report B).

---

## 2. Dependency graph

### Injected ctor deps (mirror W6a / BankingSupport explicit-injection pattern)
- **B1 `PathfindingHelpers`:** `client`, `clientThread`, `worldMapData` (@219), `pathfinderApiClient` (@222).
  No back-ref needed. No mutable state.
- **B2 `NavigationHelpers`:** `client`, `clientThread`, `helper` (ClientThreadHelper), `mouse`, `cameraSystem`,
  `interactionSystem`, `worldMapData`, `random` (@221), **`pathfindingHelpers` (B1)**, and **`playerHelpers`
  back-ref (`this`)** — set at PH ctor, exactly like `interactionSystem.setPlayerHelpers(this)` @7171 template.

### B2 → methods that STAY in PlayerHelpers (reached via `playerHelpers.` back-ref)
All are **already `public`** — **NO new accessor required**:
| Called | Def line | Home | B2 call sites |
|---|---|---|---|
| `clickMenuEntrySafe` (W6a delegate → interactionSystem) | 5321/5326 | stays PH | 4433 (attemptOpenGate), 4963 (clickTileDirect region) |
| `getHoverActionName` (B4, extracted J2-5) | 6025 | stays PH now | 5973, 5988 (smartMinimapClick) |
| `waitPlayerAnimation` (B5, extracted J2-5) | 5454 | stays PH now | 4673, 4730, 4940 |

> B2 can equally call `interactionSystem.clickMenuEntrySafe(...)` directly (plan §2-B2 seam 3 preference) —
> either works; keep ONE path. `getHull`/`getMinimap`/`getWorldPoint` are **NOT** called by B2 (their only
> callers @5587-5655 are SECTION-3/B4 methods `smartMove`/`clickTarget`), so no accessor churn there.

### External callers (grep of full manny tree) — the seams that force PH public delegates
| PH-public method (moves to B2) | External callers |
|---|---|
| `gotoPositionSafe` | InteractionSystem.java:482; commands/PowerMineCommand.java:246; commands/GotoCommand.java:159 |
| `gotoPosition` | CombatSystem.java:1868; commands/LightFireCommand.java:207 |
| `cancelCurrentNavigation` | commands/GotoCommand.java:144; commands/KillCommand.java:77 |
| `findAndPrepareGameObjectPublic` | BankingSupport.java:111; InteractionSystem.java:683, 708 |
| `getDistanceTo` / `isWithinDistance` / `smartMinimapClick` / `calculateNextWaypoint` / movement utils | **none external** |

**Resolution (no external file edited in J2-4):** PlayerHelpers KEEPS public delegate stubs with identical
signatures for `gotoPositionSafe`, `gotoPosition`, `cancelCurrentNavigation`, `findAndPrepareGameObjectPublic`,
`getDistanceTo`, `isWithinDistance`, each forwarding to `navigationHelpers.*`. (`clearUseMode` stays fully in
PH until J2-5 per phase table.) InteractionSystem/CombatSystem/commands compile unchanged.

### New accessor / injection needed — ONLY `handleGotoCommand`
This is the one genuine architectural seam. handleGotoCommand is a **command handler** (parses args, writes
responses) that the plan (§2 handleGotoCommand row) wants moved to B2. But it depends on **`responseWriter`**
(CP ctor param @7122) and **`locationManager`** (CP-created @7165) — **both are CommandProcessor-scoped**,
while NavigationHelpers is constructed in the PlayerHelpers ctor, which runs BEFORE the CP ctor. NavigationHelpers
therefore cannot receive them at construction.

Three options (decision required before executing — see §4 risk flag):
- **(A) RECOMMENDED — leave the handleGotoCommand body in the CP shell.** It already routes all nav through the
  `playerHelpers.` back-ref (12999/13003/13013), which now forwards to B2. Zero new seam, zero new injection;
  the ~122 lines stay in the CP shell (well within its ~1,550 target). The *actual* nav primitive
  (`gotoPositionSafe`) still moves to B2 as intended. Cleanest and lowest-risk.
- **(B) Plan-literal — move body to `NavigationHelpers`, inject `responseWriter`+`locationManager` via a late
  back-ref setter** (`navigationHelpers.setCommandContext(responseWriter, locationManager)` called from the CP
  ctor, mirroring the `interactionSystem.setPlayerHelpers(this)` back-ref @7171 that J2-3-style injection uses).
  CP keeps `handleGotoCommand(args){ return playerHelpers.getNavigationHelpers().handleGotoCommand(args); }`
  wrapper for the 13 external + 5 internal callers. Leaks command-layer types (ResponseWriter) into the nav
  engine — architecturally worse.
- (C) Inject ResponseWriter + a shared LocationManager into the PH ctor — messy (CP does `new LocationManager()`,
  no shared singleton exists). Not recommended.

Whichever is chosen, a **CP wrapper named `handleGotoCommand(String)` MUST remain** — 13 command sites +
5 internal CP callers (12693/12703/12860/12876/12881) reference it by that exact name.

---

## 3. State / field inventory

| State (line) | Reads/writes | Destination | Note |
|---|---|---|---|
| `shouldCancelNavigation` @249 (volatile) | Write @2433 (cancelCurrentNavigation=true), @3220 (gotoPositionSafe=false); reads @2490,2652,2881,2921,3013,3450,3706,3740,5077 — **all inside B2 methods** | → **B2** (private volatile) | **CRITICAL:** writer `cancelCurrentNavigation` is delegated from PH; the field + its writer + all readers MUST land on the SAME NavigationHelpers instance, else the KILL/GotoCommand cancel path silently no-ops (see §4). |
| `lastKnownPosition` @253, `stuckRecoveryAttempts` @255 | detectIfStuck/escapeFromStuckPosition @2255-2302,2393 — B2 only | → **B2** (private, verbatim) | A method-LOCAL `lastKnownPosition` @3421 in gotoPositionSafe shadows the field — moves with the method, unrelated. |
| `STUCK_*` consts @256-258, `MINIMAP_WIDGET_ID(_ALT)` @261-262 | B2 nav loops only | → **B2** | verbatim |
| `worldMapData` @219, `pathfinderApiClient` @222, `random` @221 | B1/B2 read-only | STAY in PH, **passed by reference** into B1/B2 ctors | already final injected fields |
| `locationHistory` @230 (setter @236, getter @244) | MannyPlugin setter (LOCKED), nested consumers | **STAYS in PH** | moved code that needs it calls `playerHelpers.getLocationHistory()` |
| `responseWriter` @6899, `locationManager` @6914 | handleGotoCommand + CP handlers | **STAY in CommandProcessor** | drives the handleGotoCommand decision (§2/§4) |
| TAB_* / EQUIPMENT etc. widget-ID consts @266-280 | tab switching (B3) | STAY now (B3 = J2-5) | not a J2-4 concern |

---

## 4. Extraction order + risk flags

**Safe sequence (single-writer on PlayerHelpers.java; compile gate `:client:compileJava -x checkstyleMain
-x pmdMain`, JDK 21 pin):**

1. **Cut B1 → `utility/PathfindingHelpers.java` first.** Fully self-contained, all-private, zero external
   callers, no mutable state. Add `this.pathfindingHelpers = new PathfindingHelpers(client, clientThread,
   worldMapData, pathfinderApiClient)` to PH ctor. Compile-gate. Lowest risk — do it to de-risk B2.
2. **Cut B2 → `utility/NavigationHelpers.java`.** Construct in PH ctor AFTER B1 (B2 takes B1 + `this` back-ref).
   Move the 6 nav-state fields (249,253,255,256-258,261-262). Move ~38 methods + 8 nested classes. Leave
   `waitPlayerIdle()`@5443 / `waitPlayerAnimation`@5454 in PH (B5). Add PH public delegate stubs for
   gotoPositionSafe / gotoPosition / cancelCurrentNavigation / findAndPrepareGameObjectPublic / getDistanceTo /
   isWithinDistance forwarding to navigationHelpers. Do NOT edit InteractionSystem/CombatSystem/commands.
   Compile-gate.
3. **handleGotoCommand:** apply the §2 decision — **recommended: leave body in CP shell** (it already routes via
   the playerHelpers back-ref, which now hits B2). If plan-literal move is mandated, wire the late
   `setCommandContext` back-ref from the CP ctor and keep the CP wrapper.
4. **GATE-LIVE checkpoint** (per phase table J2-4): shadowJar + relaunch on `:2` + auto-login, then
   **GOTO named-location round-trip** (e.g. `GOTO DRAYNOR_BANK` then `GOTO LUMBRIDGE_MINE`) confirming actual
   movement + arrival, **plus a KILL-during-GOTO test** (send `GOTO <far>` then `KILL` — verifies
   cancelCurrentNavigation still flips shouldCancelNavigation on the live instance), **plus `ipc_smoke.sh` 5/5**.

**Highest-risk move (the plan's "highest-risk semantic phase" — §5 risk rank #1): B2 `gotoPositionSafe`
(3216-4028, ~800 lines).** Concretely why:
- It is the live-movement engine and the single largest method; it is the entry point behind
  InteractionSystem:482, GotoCommand:159, PowerMineCommand:246 — a fault here strands every navigation.
- **The specific regression to guard:** `shouldCancelNavigation` (@249) is written by `cancelCurrentNavigation`
  (@2433) — which is invoked externally via the PH delegate from **KillCommand:77** and **GotoCommand:144** —
  and read in 9 in-loop sites (2490…5077) and reset by gotoPositionSafe @3220. If the field, its writer, and its
  readers do not ALL move onto the **same** NavigationHelpers instance (e.g. a stray copy left in PH, or the
  delegate writing PH's field while the loop reads B2's), then **KILL/interrupt during navigation silently stops
  working** — the bot keeps walking after a KILL. This is exactly the class of latent break the GATE-LIVE
  KILL-during-GOTO test above is designed to catch. Secondary: the clickMenuEntrySafe delegate calls at 4433
  (gate opening) and 4963 (walk-here fallback) must remain reachable — verify via `playerHelpers.` or
  `interactionSystem.` directly, not a dropped private reference.

---

## 5. Grep-trap warnings

- **`isWalkable` (B1 method @494):** grep `isWalkable` yields many false positives —
  `collisionData.isWalkable()` / `liveCache.isWalkable()` (CollisionDataLoader.java:122,343),
  `data.isWalkable()` (CollisionMapCache.java:70), PathfindingVisualizer.java:138,266. Locate PH's by the decl
  `private boolean isWalkable(WorldPoint` — it is receiver-less at call sites (647, 1107, 1136 use the
  *collisionData* variant; only 647 is PH's own).
- **`localToMinimap` (B2 method @2125):** collides with RuneLite's static `Perspective.localToMinimap(client,…)`
  used in ControlSystem.java:465 and UIOverlays.java:428,431,2422,3162,3265,3266. Those are NOT PH callers —
  do not treat them as external consumers.
- **`waitForPlayerIdle` vs `waitPlayerIdle` (near-identical, different destinations):** `waitForPlayerIdle`
  has TWO overloads — `(int)`@2873 and `(long)`@5255 — **both B2**. `waitPlayerIdle()` (no "For", no-arg)@5443
  and `waitPlayerAnimation`@5454 are **B5** and stay in PH now. Easy to move the wrong one.
- **`hasLineOfSight`:** the method name @1654 is shadowed by a local `boolean hasLineOfSight` variable at
  3243-3288 (inside gotoPositionSafe). Grep the decl `private boolean hasLineOfSight(WorldPoint`, not the var.
- **`getWorldPoint` (private @5744):** collides with `marker.getWorldPoint()` (TileMarker) @15903-15904 and
  RuneLite `Point.getWorldPoint`. It STAYS in PH and is NOT a B2 method — don't accidentally pull it.
- **`new java.util.concurrent.CountDownLatch` (the plan's §5 FQN trap):** N/A for J2-4 — J2-2 already converted
  all latch sites; grep confirms **zero** `CountDownLatch` tokens in lines 408-6017. The one KEEP latch (6109,
  useItemOnItem) is in the B4 region, not touched here.
- **`gotoPosition` vs `gotoPositionSafe`:** two distinct public methods with two `gotoPosition` overloads
  (LocalPoint@2407, WorldPoint@2421) — anchor delegates on full signatures, not the `gotoPosition` prefix.

---

## Verdict

Phase is **ready to execute post-freeze.** J2-4 moves ~4,840 lines across **14 B1 methods + 3 classes** and
**~38 B2 methods + 8 classes** into two new files (PathfindingHelpers ~1,319 lines, NavigationHelpers ~3,521),
both latch-free already and both cleanly injectable. The single open decision is `handleGotoCommand`: keep it in
the CP shell (recommended, zero new seam — it already routes nav through the back-ref) rather than forcing the
plan's B2 move, which would require injecting the CommandProcessor-scoped `responseWriter`+`locationManager` into
the nav engine via a late back-ref setter.
