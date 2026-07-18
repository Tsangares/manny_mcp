# W6-J2: PlayerHelpers.java Split Plan (Execution Contract)

**Date:** 2026-07-17 (planned during deployment freeze; execute after tutorial-driver run)
**Author:** W6-J2 planning agent (read-only survey; no code was modified)
**Target:** `/home/wil/Desktop/manny/utility/PlayerHelpers.java` @ 23,683 lines
**Baseline commit:** manny `c01219c` (W6-J1, COMMITTED). This plan and its companion data file
`journals/W6J2_CALL_EDGES.md` (Reports A/B/C — external consumers, command call edges, latch
classification) were measured against exactly that tree.
**Goal state:** every file under `utility/` < 5,000 lines; PlayerHelpers reduced to a facade + shared-state core; CommandProcessor reduced to a dispatch shell; all convertible latches on ClientThreadHelper.

> Line numbers in this document were measured against `c01219c`.
> **They are only valid until the first J2 phase lands.**
> Every phase MUST re-verify its line ranges with grep/Read before editing — treat ranges
> here as "where to look," and method/class names as the authoritative identifiers.
> Later phases inherit shifted line numbers; each phase prompt says "locate by name."

---

## 0. Baseline corrections (prompt-vs-reality reconciliation)

Measured against the working tree; these correct stale figures in the campaign notes:

| Campaign note said | Measured now | Explanation |
|---|---|---|
| "115 CountDownLatches in PlayerHelpers" | **77 `new CountDownLatch` sites** (112 total `CountDownLatch` token references incl. `.await`/`.countDown` lines) | The 115 was the W5-P3 baseline count taken **before** W6-J1 deleted −759 PlayerHelpers lines. 77 instantiation sites is the number that matters for conversion. Full list in §4. |
| "38 command classes in utility/commands/" | **128 .java files** in `utility/commands/` (incl. CommandBase, GeWidgetSupport, SpellWidgetHelper support classes) | 38 was the W5-P3 "classes that had latches" count, not the class total. |
| "123 register() calls" | **122 `register(` calls** in PlayerHelpers (registration block `9677-9806`) | W6-J1 removed LOAD_SCENARIO/LOAD_CMDLOG (133→131 commands; 131 = 121 registry + 10 legacy switch). |
| "~45 helpers made public in Wave 4c" | **54 public methods** on CommandProcessor; 46 are domain helpers, 8 are lifecycle (`start/stop/clearCommandFile/getLastPollMillis/isProcessingEnabled/executeCommand/resumeLastAction/clearLastResumableAction`) | Matches "~45". Full list in §1.5. |

Status changes since the survey started:
- W6-J1 (incl. ScenarioExporter.java) is now COMMITTED: manny `c01219c`. J2 starts from there.
- **DEFECT-1** (journals/TUTORIAL_TEST_DEFECTS_2026-07-17.md): `CameraSystem.getYawToPoint:1064`
  calls `TileObject.getWorldLocation()` off-client-thread → every INTERACT_OBJECT that
  camera-orients on a TileObject throws IllegalStateException. A separate opus agent owns the
  CameraSystem fix. Consequences for J2: (a) NO J2 phase edits CameraSystem.java; (b) J2-0
  pre-flight confirms that fix landed before J2 deploys; (c) the J2-2 latch agent must AUDIT
  (report, not fix) other off-client-thread `getWorldLocation()/getLocalLocation()/getCanvas*()`
  calls in code it touches — Wave-5-style latch removals are the suspected origin of this bug
  class, and J2-2 repeats that operation 60+ times.

**Hard constraints (unchanged):**
- `MannyPlugin.java` is LOCKED. No edits ever; needed changes go into the manifest notes.
  Consequence: any type or member MannyPlugin references must keep its exact FQN and
  signature (verified in §1.6).
- Single-writer rule: only ONE agent edits `PlayerHelpers.java` per phase.
- Per-phase gate: `./gradlew :client:compileJava -x checkstyleMain -x pmdMain` green
  (JDK 21 pin; see handoff runbook). Full shadowJar + live smoke at the milestones marked GATE-LIVE.
- No commits by phase agents; orchestrator gates and commits.

---

## 1. Complete map of PlayerHelpers.java (23,683 lines)

### 1.1 Class-level anatomy (brace-verified extents)

Indentation in this file is UNRELIABLE (classes merged in from other files kept one-tab
bodies). The extents below were computed by brace-depth analysis, not indentation.

| # | Nested type | Lines | Size | Notes |
|---|---|---|---|---|
| — | `PlayerHelpers` (outer) | 214-23683 | 23,470 | fields/ctor 214-401 |
| 1 | `PathNode` (priv static) | 409-448 | 40 | A* node |
| 2 | `MinimapData` (priv static) | 453-465 | 13 | |
| 3 | `MinimapPointData` (priv static) | 470-480 | 11 | |
| 4 | `ObstacleResult` (priv static) | 4023-4031 | 9 | nav obstacle data |
| 5 | `GateData` (priv static) | 4036-4046 | 11 | |
| 6 | `ObstacleScanner` + `ScanResult` | 4051-4065 | 15 | |
| 7 | `MinimapNavigationData` | 4070-4078 | 9 | |
| 8 | `ItemPairCheck` | 4083-4091 | 9 | |
| 9 | `ItemBoundsPair` | 4096-4104 | 9 | |
| 10 | `AnimationCheckResult` | 4109-4117 | 9 | |
| 11 | `MinimapClickData` (priv static) | 6000-6011 | 12 | used by smartMinimapClick |
| 12 | `EquipmentSystem` (pub static) | 6813-7923 | 1,111 | contains EquipmentDetector 6886-7066 (+enum CombatStyle 6892), WeaponInfo 7077-7150, WeaponComparator 7156-7222 (+enum ComparisonStyle), EquipmentHelper 7234-7498, DamageCalculator 7510-7670, FoodManager 7682-7922 (+FoodItem 7907) |
| 13 | `CombatStyleSystem` (pub static) | 7934-8183 | 250 | |
| 14 | `ControlSystem` (pub static) | 8190-8728 | 539 | contains Conditions 8260-8596 (Condition iface + 5 impls), MovementHelper 8606-8726 |
| 15 | `CommandStateManager` (pub static) | 8738-8899 | 162 | + CommandStep enum, FireObjectInfo |
| 16 | `PathfindingStateManager` (pub static) | 8905-9059 | 155 | + PathfindingState enum |
| 17 | `LocationManager` (pub static) | 9070-9197 | 128 | constructed with `new` in CP ctor (9518) |
| 18 | **`CommandProcessor` (pub static)** | **9204-22631** | **13,428** | THE monster. Detail in §1.4 |
| 19 | `TileMarkerManager` (pub static) | 22650-23018 | 369 | singleton `getInstance()` |
| 20 | `MiningHelper` (pub static) | 23030-23530 | 501 | + RockWithOre 23109-23117 |
| 21 | `RandomEventHandler` (pub static) | 23551-23682 | 132 | |

PlayerHelpers-proper (outer-class methods, excluding all nested classes): lines 214-9203
region ≈ 8,990 lines. CommandProcessor alone is 57% of the file.

### 1.2 PlayerHelpers-proper section map (grep of section comments + method index)

| Region | Lines | ~Size | Contents (method → decl line) |
|---|---|---|---|
| Fields + ctor + plugin forwarders | 214-401 | 188 | DI fields 216-231; locationHistory setter 240/getter 248; nav-cancel flag 253; stuck fields 257-262; widget-ID constants 264-320; ctor 322-357 (wires `interactionSystem.setPlayerHelpers(this)` at 356); getters getCameraSystem 362, getKeyboard 370, getCharacterRandomizer 378; MannyPlugin forwarders onMenuOptionClicked 387, onInventoryChanged 397 |
| SECTION 0: A* pathfinding | 402-1721 | 1,320 | PathNode/MinimapData/MinimapPointData; isWalkable 488, findPathAStar 559, reconstructPath 687, thinWaypoints 709, thinWaypointsByDistance 823, insertIntermediateWaypoints 873, insertGateWaypoints 934, findFurthestCachedWaypoint 1075, isWalkableHybrid 1153, findPathGlobalAStar 1183/1188, isPlayerEnclosed 1511, findNearestExitTile 1550, hasLineOfSight 1648 |
| SECTION 1: widget operations | 1722-1883 | 162 | clearOpenMenus 1729, clearUseMode 1746, getWidget 1773/1781, getWidgetBounds 1789, isWidgetHidden 1802, getGESlot 1815, isGESlotEmpty 1845, isGESlotDone 1858, getCloseableInterfaceIds 1872 |
| SECTION 2: mouse utilities | 1884-2049 | 166 | getHull 1889, getMinimap 1931, getMenuRectangle 1961, getMenuRectangleVisual 1984, getClickArea 1993, moveMouseToPosition 2003, clickMouse 2014, moveAndClick 2027, getMouseX 2037, getMouseY 2045 |
| SECTION 2b: movement & pathfinding utils | 2050-2160 | 111 | calculateNextWaypoint 2056, checkMovementProgress 2083, getDistanceMoved 2109, localToMinimap 2119, worldToLocal 2127, getAngleTo 2135, getRotationDirection 2152 |
| Stuck detection & recovery | 2161-2400 | 240 | validateAgainstLocalCollision 2173, detectIfStuck 2237, escapeFromStuckPosition 2284 |
| Navigation execution core | 2401-4015 | 1,615 | gotoPosition 2401/2415, cancelCurrentNavigation 2424, retryWithGlobalAStar 2438, continueWithPhase1Navigation 2626, simpleDirectionalNavigation 2779, waitForPlayerIdle(int) 2867, waitForArrival 2907, simpleDirectionalNavigationMultiClick 2966, clickMinimapWithBoundsCheck 3107, **gotoPositionSafe 3210-4015 (~800 lines)** |
| Obstacle/gate handling + data classes | 4016-4590 | 575 | data classes 4023-4117; detectNearbyObstacle 4127, isObstacleOnPath 4270, attemptOpenGate 4334, recomputePathAfterGate 4475, tryAlternativePath 4516, hasPlayerMoved 4575 |
| Minimap/tile click + object prep | 4591-5511 | 921 | clickMinimapPoint 4591, clickMinimapPointDirect 4683, findAndPrepareGameObject 4747, findAndPrepareGameObjectPublic 4890, clickTileDirect 4899, findFurthestVisibleWaypoint 4984, waitForWaypointOrContinue 5062, waitForPlayerIdle(long) 5249, isWaypointClickable 5322, generateIntermediateWaypoint 5371, getMinimapBounds 5420, waitPlayerIdle 5437, waitPlayerAnimation 5448, getDistanceTo 5493, isWithinDistance 5507 |
| SECTION 3: interaction & clicking (W6a thin delegates) | 5512-5755 | 244 | clickTarget 5522/5536, moveMouse 5579, stripColorTags 5668, parseRequestId 5680, removeRequestId 5703, clickMenuEntrySafe 5722/5727, getWorldPoint 5738 |
| SECTION 4: skilling/item ops | 5756-6234 | 479 | lightFire 5763, cookOnFire 5773, smartClick 5781/5786 (delegates), smartMove 5804, smartMoveToWidget 5860, smartMinimapClick 5891 (+MinimapClickData 6000), getHoverActionName 6019, getHoverTargetName 6038, containsIgnoreCase 6055, useItemOnItem 6073 (latch 6109), useItemOnItemRepeatedly 6161, hasItems 6213 |
| SECTION 5: animation tracking | 6235-6615 | 381 | waitPlayer 6240/6248, waitActor 6256/6264, getWoodcuttingAnimations 6313, getMiningAnimations 6377, getFishingAnimations 6438, getFiremakingAnimations 6480, getCookingAnimations 6501, getSmeltingAnimations 6510, getExpectedAnimations 6522, waitForAnimation 6564, waitForActionAnimation 6610 |
| SECTION 6: tab switching | 6616-6807 | 192 | openInventory 6622, openEquipment 6631, openPrayer 6640, openMagic 6649, openCombat 6658, openSkills 6667, switchToTab 6679, isTabOpen 6730, isInventoryOpen 6757, isEquipmentOpen 6765, isPrayerOpen 6773, isMagicOpen 6781, getCurrentTab 6790 |
| SECTION 8-9.5 merged systems | 6808-9197 | 2,390 | nested classes #12-17 above (EquipmentSystem…LocationManager) |
| CommandProcessor | 9204-22631 | 13,428 | §1.4 |
| Tail nested classes | 22633-23683 | 1,051 | TileMarkerManager, MiningHelper, RandomEventHandler (#19-21) |

### 1.3 (reserved)

### 1.4 CommandProcessor internal map (9204-22631)

**Shell (dispatch/lifecycle/state) — 9204-10488, ~1,285 lines:**
- READ_ONLY_COMMANDS set 9210-9235, isReadOnly 9240
- DI fields 9246-9272; 131 command-instance fields 9275-9406; BankingSupport field 9271
- commandRegistry decl 9418; pollTask/running 9420-9421; processingEnabled 9425;
  lastPollMillis 9430; shouldInterrupt 9432; currentCommand 9433; currentCommandTask 9435;
  currentCommandTaskRef 9437; loopRunning 9440; lastDepositedOre/nextOreToMine 9443-9444;
  activeCombatConfig 9447; CombatConfig class 9452-9461; lastResumableAction 9464
- ctor 9466-9813 (deps 9495-9524, incl. duplicate `interactionSystem.setPlayerHelpers` back-ref
  at 9524; command instantiation 9527-9664; registration block `register(...)` ×122 9677-9806)
- register() 9814-9829; start 9831; stop 9853; clearCommandFile 9880; getLastPollMillis 9898;
  isProcessingEnabled 9907; processCommands 9918-10071 (read-only lane 9959, exclusive lane 9991)
- executeCommand 10073-10232: registry-first dispatch 10102-10106; legacy switch 10108-10204
  (PING 10110 / PAUSE 10115 / RESUME 10121 / CAMERA_RESET 10127 all inline-`new` their command;
  BURY_ALL 10143-10144 → `buryAllCommand.execute(parts.length>1 ? parts[1] : "Bones")`;
  LIGHT_FIRE 10147 default "Logs"; LOGIN fully inline via loginHandlers 10167-10174;
  LIST_OBJECTS 10176 default "15"; INTERACT_OBJECT 10184-10192 with resume-tracking side
  effect; LIST_COMMANDS 10195 fixed ""); default+suggestion 10198-10203; finally block with
  KILL-flag-preservation 10213-10232 (**do not touch — Wave 3c fix**). The switch
  hard-references 5 command fields + loginHandlers
- suggestSimilarCommand 10238-10315; isResumableSkillingAction 10316; resumeLastAction 10342;
  clearLastResumableAction 10378

**Handler regions — 10389-22631, ~12,240 lines** (D = dead, verified zero callers repo-wide, see §1.7):

| Region | Lines | Methods (→ = calls) |
|---|---|---|
| Mission-control handlers (ALL DEAD) | 10389-10755 | D handleSetConfig 10389, D handleStopProcessor 10450, D handleStartProcessor 10475, D handleMouseMove 10496, D handleMouseClick 10528, D handleKeyPress 10553, D handleCameraYaw 10580, D handleCameraPitch 10606, D handleCameraPointAt 10632, D handleCameraReset 10662, D handleTabOpen 10673, D handleEquipmentLog 10741 |
| Equipment | 10756-11259 | handleEquipBestMelee 10756 (ALIVE: KillLoopCommand:152), equipItem 11021 (← handleEquipBestMelee), ensureRingOfForgingEquipped 11135 (ALIVE: ×1 via `processor.`, Report B), latches 11041 |
| Meta/state (DEAD) | 11260-11479 | D handleGetGameState 11260, D handleListCommands 11352 |
| Combat/magic | 11480-12300 | D handleAttackNPC 11480; handleTeleportHome 11548 (ALIVE: TeleportCommand:49), handleCastSpell 11624 (ALIVE: TeleportCommand:117), capitalizeSpellName 11719, handleCastSpellOnGroundItem 11773 (ALIVE: TelegrabWineLoopCommand:162), handleCheckHPThreshold 12112 (ALIVE: TelegrabWineLoopCommand:110), getSpellWidgetId 12226; latches 11817/11852/11890/11931/12027/12144 |
| Inventory/ground items | 12301-13825 | handlePickUpItem 12301 (ALIVE: ImpHuntCommand:148 + pickUpLootNearby), verifyAndClickGroundItem 12632, waitForInventoryChange 12748, D handleDropItem 12811, handleBuryItem 12981 (ALIVE: BuryAllCommand:121 + handleBuryAll:13351), D handleUseItemOnItem 13151, handleBuryAll 13273 (ALIVE: buryAllBonesInInventory), isProtectedItem 13415, dropItemAtSlot 13426, handleDropAll 13536 (ALIVE: KillLoopCommand:633 + cookRawMeatRoutine:15645), D handleUseItemOnNPC 13686, D handleClickWidget 13736, D handleWait 13791; latches 12521 |
| Query/scan (DEAD) | 13829-14297 | D handleQueryNPCs 13829, D handleQueryGroundItems 13909, D handleScanWidgets 13977, D addWidgetInfo 14122, D handleFindNPC 14190; getTileClickBounds 14256 KEPT (← handleCookAll:14769); latch 14313 is in handleLightFire below |
| Firemaking/cooking | 14298-15975 | handleLightFire 14298 (ALIVE: findOrLightFire:15437), handleCookAll 14489 (ALIVE: cookRawMeatRoutine:15636), shouldCookRawMeat 15117, hasAxeInInventory 15183, hasPickaxeEquippedOrInventory 15277, findOrLightFire 15356, findCookingInterfaceWidget 15445, findCookingWidgetRecursive 15464, cookRawMeatRoutine 15582 (ALIVE: KillLoopCommand:741), chopNearestOakTree 15660; latches 14526/14801/14868/14937/15006/15122/15188/15282/15362/15718/15763/15900 |
| Player-ready / doors / loot | 15976-16557 | waitForPlayerReady 15976 (ALIVE ×1 via `processor.`), findAndOpenNearbyDoor 16033/16202 (ALIVE ×1), checkAndOpenDoorInPath 16215 (ALIVE ×1), findAnyValuableLootNearby 16438 (ALIVE ×1), D pickUpLootNearby 16489 (zero callers); latch 15983 |
| Combat-style (DEAD) | 16558-16641 | D handleSwitchCombatStyle 16558, D openCombatTab 16621 (only caller is dead) |
| Mining + tin/copper workflow | 16642-17390 | handleMineOre 16642 (ALIVE: handleAtMine:17163/17178), WorkflowLocation 16960, InventoryOreType 16969, detectCurrentLocation 16983, getInventoryOreType 17038, getBankOreCounts 17079, executeWorkflowStep 17125 (ALIVE: CollectLumbridgeTinCopperCommand), handleAtMine 17155, handleAtBank 17199, handleElsewhere 17350; latches 16818/16996/17041/17082 |
| Fishing (ALL DEAD — FishDraynorLoopCommand has own copies) | 17392-17818 | D handleFish 17392, D FishingLocation 17544, D detectFishingLocation 17554, D isInventoryFullForFishing 17587, D handleFishDraynorLoop 17621, D getFishingLevel 17789; latches 17557/17590/17792 |
| Woodcutting (DEAD) | 17820-17975 | D handleChopTree 17820 |
| Navigation/locations/tiles | 17977-18422 | handleGotoCommand 17977 (ALIVE: ~20 callers — the shared nav primitive), D handleSaveLocationCommand 18107, D handleGetLocationsCommand 18170, D handleTileCommand 18222, D handleTileClear 18271, D handleTileClearAll 18309, D handleTileList 18331, D handleTileExport 18353, D parseColor 18375; latch 18122 (dead region) |
| NPC despawn / loot pickup / bones | 18423-19066 | waitForNPCDespawn 18423, pickUpLootAt 18480, pickUpAllBonesAt 18716, buryAllBonesInInventory 18825 (→ handleBuryAll), D clickGroundItem 18907 (zero callers); latches 18641 |
| Query/viz (ALL DEAD — Viz commands have own copies) | 19067-19490 | D handleQueryInventory 19067, D handleScanObjects 19158, D handleListObjects 19218, D generatePathVisualization 19338, D handleVizPath 19363, D handleVizRegion 19430 |
| Banking | 19492-20087 | handleBankOpen 19492, handleBankClose 19521, handleBankDepositAll 19550 (all three = thin wrappers over BankingSupport since W4b), D handleBankDepositEquipment 19590, handleBankDepositItem 19639, handleBankWithdraw 19780, D handleBankCheck 20049; latches 19663/19717/19868/19953/20147(→in handleBankWithdraw region) |
| Smelting | 20088-21052 | handleSmeltBronze 20088 (ALIVE: SmeltBronzeBarsCommand:326), isNearLocation 20234, hasSmeltingOres 20246, hasBronzeBars 20285, getItemCount 20324, BarTypeInfo 20368, getBarTypeInfo 20389, hasOre 20462, hasBar 20497, handleSmeltBar 20535 (ALIVE: SmeltBarsCommand:335), D clickWidgetByAction 20909 (zero callers), D findWidgetsWithAction 20992 (only caller dead — verify); latches 20252/20290/20327/20465/20500/20567/20657/20823/20915/20951 |
| Shopping / NPC interact / widget click family | 21053-21918 | D handleShopBuy 21053 (zero callers), withdrawCoinsFromBank 21243 (ALIVE ×1 via `processor.`), interactWithNPC 21285/21297 (internal callers), clickWidget 21411/21423 (ALIVE ×5 via `processor.`), clickWidgetWithParam 21606 (ALIVE ×5), clickChildWidgetByAction 21726, findChildByAction 21789, checkWidgetForActionMatch 21830, D waitForWidget 21866 (zero callers); latches 21303/21332/21366/21431/21510/21550/21611/21685/21732/21873 |
| GE search/collect | 21919-22345 | findGESearchResultByName 21919, searchWidgetRecursively 21950, collectFromGEToBank 22008, findCollectButton 22176, clickCompletedOfferSlot 22232, D clickWidgetWithMenu 22302 (zero callers); latches 21922/22018/22082/22119/22246/22307 |
| isRunning + dialogue handlers (dialogue ALL DEAD) | 22346-22631 | isRunning 22346; D handleTalkNPC 22350, D handleInteractNPC 22391, D handleInteractObject 22434, D handleClimbLadderUp 22477, D handleClimbLadderDown 22508, D handleClickContinue 22539, D clickWidgetByBounds 22603 |

### 1.5 The Wave-4c public helper surface on CommandProcessor (54 public methods)

Lifecycle (stay on the shell): start 9831, stop 9853, clearCommandFile 9880, getLastPollMillis 9898,
isProcessingEnabled 9907, executeCommand 10073, resumeLastAction 10342, clearLastResumableAction 10378,
isRunning 22346.

Domain helpers (the extraction surface — decl lines): handleEquipBestMelee 10756,
ensureRingOfForgingEquipped 11135, handleTeleportHome 11548, handleCastSpell 11624,
handleCastSpellOnGroundItem 11773, handleCheckHPThreshold 12112, handlePickUpItem 12301,
handleBuryItem 12981, handleDropAll 13536, shouldCookRawMeat 15117, hasAxeInInventory 15183,
cookRawMeatRoutine 15582, waitForPlayerReady 15976, findAndOpenNearbyDoor 16033,
checkAndOpenDoorInPath 16215, findAnyValuableLootNearby 16438, detectCurrentLocation 16983,
getInventoryOreType 17038, getBankOreCounts 17079, executeWorkflowStep 17125,
handleGotoCommand 17977, waitForNPCDespawn 18423, pickUpLootAt 18480, pickUpAllBonesAt 18716,
buryAllBonesInInventory 18825, handleBankOpen 19492, handleBankClose 19521,
handleBankDepositAll 19550, handleBankDepositItem 19639, handleBankWithdraw 19780,
handleSmeltBronze 20088, isNearLocation 20234, hasSmeltingOres 20246, hasBronzeBars 20285,
getItemCount 20324, getBarTypeInfo 20389, hasOre 20462, hasBar 20497, handleSmeltBar 20535,
withdrawCoinsFromBank 21243, clickWidget 21411/21423, clickWidgetWithParam 21606,
findGESearchResultByName 21919, collectFromGEToBank 22008.

### 1.6 External-consumer map (what pins FQNs and signatures)

Source: Report A in `journals/W6J2_CALL_EDGES.md` (full tables there). Only **6 files** outside
`utility/commands/` reference PlayerHelpers (57 lines total). All wiring is Guice `@Inject` —
nobody `new`s PlayerHelpers.

**MannyPlugin (LOCKED) — the FQN/signature pin list.** Everything on this list must keep its
exact name, nesting, and signature through all of J2:
- `PlayerHelpers` @Inject field :270 — instance calls: `setLocationHistory` :477,
  `onMenuOptionClicked(String)` :1130, `onInventoryChanged` :1139.
- `PlayerHelpers.CommandProcessor` import :98, @Inject field :225 — calls `.start()` :486,
  `.resumeLastAction()` :495, `.stop()` :556, `.clearCommandFile()` :731, `.executeCommand()` :1199.
  → CommandProcessor MUST remain a nested class of PlayerHelpers; these 5 methods + ctor
  injectability are frozen. (`resumeLastAction` is NOT dead — MannyPlugin calls it.)
- `PlayerHelpers.RandomEventHandler` @Inject field :267 — calls `.handleRandomEvent` :1046,
  `.handleWidgetClosed` :1111. → **A9 CANNOT MOVE. Stays nested.**
- `PlayerHelpers.TileMarkerManager` import :99. → **A7 CANNOT MOVE. Stays nested.**

**Other external consumers (all editable):**
| Consumer | What it touches |
|---|---|
| InteractionSystem.java | mutable `playerHelpers` field :64 via `setPlayerHelpers` :139-142 (null-guards 435, 677); calls gotoPositionSafe(clientThread,tile,1) :482, findAndPrepareGameObjectPublic :683/:708, clearUseMode :1059/:1542 |
| CombatSystem.java | final ctor-injected `playerHelpers` :52; calls gotoPosition(safeSpot) :1868; imports EquipmentSystem :16, fields :50-54, ctor :381-384, use :1816 |
| BankingSupport.java | PlayerHelpers as method PARAMETER (no field) :58; calls findAndPrepareGameObjectPublic :111, getCameraSystem() chains :127-164, getKeyboard().rotate :152, clickMenuEntrySafe("Bank",…) :266/:312/:456 |
| UIOverlays.java (ui/) | CommandStateManager statics :1289-1547, PathfindingStateManager statics :2599-3137 — both via `getInstance()` → un-nesting A4/A5 requires UIOverlays import updates (file is editable) |
| GameEngine.java | UNUSED import of ControlSystem :27 (delete in J2-3); zero runtime calls into PlayerHelpers |
| commands/KillLoopConfigCommand.java | `new CommandProcessor.CombatConfig()` :52 → CombatConfig stays nested in CP (file editable, but no reason to move) |

LocationManager and MiningHelper have **no external consumers** (LocationManager is built at
CP:9518 and passed into 6 command ctors; MiningHelper is internal-only).

**Constructors (Guice):** PlayerHelpers @Inject ctor PH:322-357 (13 params);
CommandProcessor @Inject ctor PH:9466-9525 (24 params).

**Wave-6a back-ref pattern (the template J2 mirrors):** InteractionSystem ctor-injected into
PH (field :228, param :336, assign :353), back-ref set inside PH ctor :356
`interactionSystem.setPlayerHelpers(this)`; DUPLICATE call in CP ctor :9524 (same singleton —
the duplicate is deletable in J2-6, zero behavior change).

**InteractionSystem API (2,677 lines) — matchesMenuEntry duality (feeds J2-9):**
- private 4-arg `matchesMenuEntry` @867 — the CANONICAL fixed version (strips color tags,
  option.equals), used by the click path (969, 985, 1136, 1310, 1463, 1474).
- public 3-arg `matchesMenuEntry` @2518 — LEGACY contains-based, used only by
  isCorrectMenuOption/hasMenuOption (2488, 2505).
- GameEngine's duplicate: public `matchesMenuEntry` @4734-4760 inside nested `ActionVerifier`
  (@4520), byte-for-byte equal to the LEGACY 3-arg version; called at 4706, 4722, 4836.
  → J2-9 collapses the GameEngine copy onto the public IS 3-arg method (same semantics,
  zero behavior change). It does NOT upgrade ActionVerifier to the 4-arg version — that
  would be a behavior change (flag §6.11).

**ClientThreadHelper API (346 lines) — the conversion target for §4:**
`readFromClient(Supplier)` @105 (invokeLater+latch, 5s, THROWS on timeout, [BLOCKING] log);
`readBatchFromClient` @187; `executeOnClient(Runnable)` @212 (2s, fire-and-forget — NOT a
blocking run); `readFromClientWithRetry` @227/@295; `readFromClientSafe` @308 (no-throw).
GAP: no blocking void-run-with-timeout — needed by the one REVIEW site (§4, 21685); see §6.12.

**Thin-delegate internal callers (W6a cluster — why it stays in PH):**
clickMenuEntrySafe ×11 internal (4427, 4957 from outer PH; 12738, 12931, 19037, 19732, 19968,
21385, 22151, 22156, 22339 from CommandProcessor code via `playerHelpers.`); smartClick ×1
(20118); stripColorTags ×5 (5826, 5832, 5842, 5847, 6061); onMenuOptionClicked ×0 internal
(only MannyPlugin:1130). Delegates must remain reachable from both the outer class and the
extracted C-files (C-files receive `playerHelpers` and keep calling the delegates — or call
interactionSystem directly where the move makes that natural).

### 1.7 Dead-code inventory (verified 2026-07-17 against working tree)

Method-level `grep -rn "<name>(" --include='*.java'` across the whole plugin found ZERO call
sites for every method marked D in §1.4. Root causes: Wave 3b/3c/4 migrated these handlers to
`utility/commands/` classes but only removed switch cases, not bodies; Viz/FishDraynorLoop
command classes carry their own private copies (`VizPathCommand.java:116`,
`FishDraynorLoopCommand.java:116/125/126` call LOCAL copies, not the processor's).

**Delete list (each executor re-verifies with grep before deleting — cheap insurance):**

| Method(s) | Lines (approx, verify braces) | ~LOC |
|---|---|---|
| handleSetConfig…handleEquipmentLog (12 mission-control) | 10389-10755 | 367 |
| handleGetGameState, handleListCommands | 11260-11479 | 220 |
| handleAttackNPC | 11480-11547 | 68 |
| handleDropItem | 12811-12980 | 170 |
| handleUseItemOnItem | 13151-13272 | 122 |
| handleUseItemOnNPC, handleClickWidget, handleWait | 13686-13828 | 143 |
| handleQueryNPCs, handleQueryGroundItems, handleScanWidgets, addWidgetInfo, handleFindNPC | 13829-14255 | 427 |
| pickUpLootNearby | 16489-16557 | 69 |
| handleSwitchCombatStyle + openCombatTab | 16558-16641 | 84 |
| Entire fishing block: handleFish, FishingLocation, detectFishingLocation, isInventoryFullForFishing, handleFishDraynorLoop, getFishingLevel | 17392-17818 | 427 |
| handleChopTree | 17820-17975 | 156 |
| handleSaveLocationCommand, handleGetLocationsCommand, handleTileCommand, handleTileClear/All/List/Export, parseColor | 18107-18422 | 316 |
| clickGroundItem | 18907-19066 | 160 |
| handleQueryInventory, handleScanObjects, handleListObjects, generatePathVisualization, handleVizPath, handleVizRegion | 19067-19490 | 424 |
| handleBankDepositEquipment | 19590-19638 | 49 |
| handleBankCheck | 20049-20087 | 39 |
| clickWidgetByAction + findWidgetsWithAction | 20909-21052 | 144 |
| handleShopBuy | 21053-21242 | 190 |
| waitForWidget | 21866-21918 | 53 |
| clickWidgetWithMenu | 22302-22345 | 44 |
| handleTalkNPC, handleInteractNPC, handleInteractObject, handleClimbLadderUp/Down, handleClickContinue, clickWidgetByBounds | 22350-22630 | 281 |
| **TOTAL** | | **~3,950 LOC** |

Latch sites that die with the dead code (no conversion needed — 8 of the 77): 17557/17590/
17792 (fishing block), 18122 (handleSaveLocationCommand), 20915/20951 (clickWidgetByAction),
21873 (waitForWidget), 22307 (clickWidgetWithMenu). (12144 is in handleCheckHPThreshold —
ALIVE, converts.) Cross-checked against the §4 classifier table.

Borderline (0 callers but part of a public lifecycle API — DELETE only with orchestrator nod,
listed in §6): getLastPollMillis 9898, isProcessingEnabled 9907, clearLastResumableAction 10378.

---

## 2. Split design — target files

All new files live in `utility/` (matching the BankingSupport precedent). Every file below
lands < 5,000 lines. Three groups: **A** = un-nest existing `public static` nested classes
(verbatim moves, import fixes only); **B** = extract PlayerHelpers-proper method regions;
**C** = extract CommandProcessor handler domains behind kept thin wrappers.

**Naming note:** sizes marked "after purge" assume Phase J2-1 (§1.7 dead-code delete) has
already run; line numbers cited are PRE-purge (the current tree) — executors locate by name.

### Group A — un-nest the merged systems (mechanical)

| New file | Source (lines today) | Size | Dependency edges | Clean/Seam |
|---|---|---|---|---|
| A1 `utility/EquipmentSystem.java` | `PlayerHelpers.EquipmentSystem` 6813-7923 | 1,111 | self-contained (client, clientThread, itemManager, keyboard); consumers: CP ctor (`EquipmentSystem.EquipmentHelper` param 9250-field, `EquipmentSystem.FoodManager` 9266-field), CombatSystem (import :16, fields :50-54, ctor :381-384, use :1816), EatCommand, KillLoopCommand | CLEAN — was its own file pre-merge; change refs `PlayerHelpers.EquipmentSystem` → `EquipmentSystem` + imports (CombatSystem + commands + CP). Guice keeps injecting the un-nested `EquipmentSystem.EquipmentHelper`/`FoodManager` unchanged. Latches 7594, 7638 (converted in J2-2, before the move) |
| A2 `utility/CombatStyleSystem.java` | 7934-8183 | 250 | client/clientThread/mouse; no external consumers found (SwitchCombatStyleCommand is self-contained) — import fixes only if compiler flags any | CLEAN. Latches 7959, 8046 |
| A3 `utility/ControlSystem.java` | 8190-8728 | 539 | Conditions + MovementHelper; factory getters getConditions 8217 / getMovementHelper 8229 / getResponseWriter 8241 live INSIDE the class; only external ref = GameEngine's UNUSED import :27 (delete it) | CLEAN. Latches 8370/8428/8505/8555 (Conditions.evaluate signature caveat — §4) |
| A4 `utility/CommandStateManager.java` | 8738-8899 | 162 | ui/UIOverlays.java :1289-1547 uses it via static `getInstance()` (+CommandStep/FireObjectInfo) → update UIOverlays imports in the same phase | CLEAN (UIOverlays is editable) |
| A5 `utility/PathfindingStateManager.java` | 8905-9059 | 155 | ui/UIOverlays.java :2599-3137 via static `getInstance()` (+PathfindingState) → same import update | CLEAN (UIOverlays is editable) |
| A6 `utility/LocationManager.java` | 9070-9197 | 128 | `new LocationManager()` in CP ctor 9518; injected into SaveLocation/GetLocations/Goto/KillCowGetHides/CollectLumbridgeTinCopper/SmeltBars command ctors; NO other consumers | CLEAN |
| A7 ~~TileMarkerManager~~ | 22650-23018 | 369 | **PINNED: MannyPlugin import :99** | **DOES NOT MOVE — stays nested in PlayerHelpers** (369 lines retained) |
| A8 `utility/MiningHelper.java` | 23030-23530 | 501 | NO external consumers (internal-only per Report A) | CLEAN. Latches 23223/23282/23403/23441/23481 |
| A9 ~~RandomEventHandler~~ | 23551-23682 | 132 | **PINNED: MannyPlugin @Inject field :267 + calls :1046/:1111** | **DOES NOT MOVE — stays nested in PlayerHelpers** (132 lines retained) |

Group A (A1-A6, A8) removes ~2,850 lines from PlayerHelpers with zero logic changes;
A7 + A9 (501 lines) stay nested because MannyPlugin (LOCKED) names them.
Manifest note for the eventual MannyPlugin unlock: re-home TileMarkerManager import :99 and
RandomEventHandler field :267 → then A7/A9 can un-nest too.

### Group B — PlayerHelpers-proper domain files

**B1 `utility/PathfindingHelpers.java` (~1,330)** — SECTION 0 verbatim: lines 402-1721
(PathNode 409, MinimapData 453, MinimapPointData 470, isWalkable 488 … hasLineOfSight 1648).
- Deps: client, clientThread, CollisionDataLoader/CollisionMapCache, worldMapData,
  pathfinderApiClient (findPathGlobalAStar cache-coverage path 1249+).
- State: no mutable cross-domain state. CLEAN move. B2 depends on it (ctor-inject B1 into B2).

**B2 `utility/NavigationHelpers.java` (~3,600)** — the navigation execution engine:
- Moves: 2050-2160 (movement utils), 2161-2400 (stuck detection incl. fields 257-262 + 253),
  2401-5511 (gotoPosition/gotoPositionSafe/obstacles/gates/minimap+tile clicking/
  findAndPrepareGameObject/waypoint waits/getMinimapBounds; data classes 4023-4117),
  smartMinimapClick 5891-6018 (+MinimapClickData 6000-6011), MINIMAP_WIDGET_ID constants 264-266.
  EXCEPT: waitPlayerIdle 5437 / waitPlayerAnimation 5448 → B5; getDistanceTo 5493 /
  isWithinDistance 5507 → move to B2, PH keeps 1-line delegates (widely called).
- Deps: B1, client, clientThread, helper, mouse, cameraSystem, interactionSystem (clicks),
  worldMapData, random.
- **SEAMS (all confirmed by Reports A/B):**
  1. `InteractionSystem` back-ref calls `playerHelpers.gotoPositionSafe` (IS:482),
     `.findAndPrepareGameObjectPublic` (IS:683/708), `.clearUseMode` (IS:1059/1542).
     Resolution: PH keeps public delegates with identical signatures forwarding to B2/B3 —
     InteractionSystem is NOT edited in this phase.
  2. External nav callers via `playerHelpers.`: CombatSystem:1868 `gotoPosition`;
     GotoCommand `clearOpenMenus`/`cancelCurrentNavigation`/`gotoPositionSafe` (139/143/158);
     KillCommand `cancelCurrentNavigation`; PowerMine `gotoPositionSafe`; LightFire
     `gotoPosition`; BankingSupport:111 `findAndPrepareGameObjectPublic`. Resolution: PH
     delegates for gotoPosition, gotoPositionSafe, cancelCurrentNavigation,
     findAndPrepareGameObjectPublic, clearOpenMenus (B3), getDistanceTo, isWithinDistance.
  3. `escapeFromStuckPosition` 2284 and `gotoPositionSafe` call clickMenuEntrySafe/smartClick
     delegates (internal sites 4427, 4957) — B2 calls interactionSystem directly instead
     (delegates exist for legacy callers; do not propagate them into new files).
- Risk: HIGHEST of Group B (live movement behavior; biggest single region). GATE-LIVE.

**B3 `utility/UiHelpers.java` (~530)** — widget/mouse/tab plumbing:
- Moves: 1722-1883 (clearOpenMenus, clearUseMode, getWidget×2, getWidgetBounds,
  isWidgetHidden, getGESlot, isGESlotEmpty/Done, getCloseableInterfaceIds), 1884-2049
  (getHull, getMinimap, menu rectangles, moveMouseToPosition, clickMouse, moveAndClick,
  getMouseX/Y), 6616-6807 (tab switching + isTabOpen/getCurrentTab), tab constants 269-292.
- Deps: client, mouse, keyboard, interactionSystem, helper.
- SEAM: clearUseMode called by InteractionSystem back-ref (IS:1059/1542) → PH delegate
  retained. clearOpenMenus called by DropAll ×2/DropItem/Goto commands → PH delegate retained.
  getHull/getMinimap consumed by B2 (nav clicking) → B2 ctor-takes B3 or the two methods move
  to B2 instead (executor's choice; keep ONE home, no copies). Otherwise CLEAN.

**B4 `utility/ItemUseHelpers.java` (~450)** — item-on-item and hover:
- Moves: lightFire 5763, cookOnFire 5773, smartMove 5804, smartMoveToWidget 5860,
  getHoverActionName 6019, getHoverTargetName 6038, containsIgnoreCase 6055,
  useItemOnItem 6073 (latch 6109), useItemOnItemRepeatedly 6161, hasItems 6213.
- Stays in PH: smartClick 5781/5786, clickMenuEntrySafe 5722/5727, clickTarget 5522/5536,
  moveMouse 5579, stripColorTags 5668, parseRequestId/removeRequestId 5680/5703,
  getWorldPoint 5738, onMenuOptionClicked 387 (W6a delegate cluster — LOCKED MannyPlugin
  forwarder + ~25 internal callers; PH stays the facade).
- Deps: client, helper, mouse, gameHelpers, interactionSystem. CLEAN otherwise.

**B5 `utility/AnimationHelpers.java` (~400)** — animation waits:
- Moves: 6235-6615 (waitPlayer/waitActor/animation-ID sets/getExpectedAnimations/
  waitForAnimation/waitForActionAnimation) + waitPlayerIdle 5437 + waitPlayerAnimation 5448.
- Deps: client, clientThread/helper. CLEAN. External callers needing PH delegates:
  waitForActionAnimation ← PowerMine + SmeltBronze commands; smartMoveToWidget (B4) ←
  CastSpell/CastSpellOnInventoryItem/TeleportHome commands; openMagic (B3) ←
  CastSpellOnInventoryItem. Keep PH 1-line delegates for exactly these; new B/C files
  reference the helpers directly.

### Group C — CommandProcessor handler domains

**Pattern (applies to every C-file):** the support class is constructed in the CP ctor with
explicit dependencies + `BooleanSupplier interruptSupplier` (`() -> shouldInterrupt`) +
`ResponseWriter` where handlers write responses. CommandProcessor KEEPS every Wave-4c public
helper as a 1-3 line delegating wrapper with an unchanged signature, so the 12 stateful
command classes (KillLoop, TeleportCommand, TelegrabWineLoop, BuryAll, ImpHunt, KillLoopConfig,
KillCow, KillCowGetHides, CollectLumbridgeTinCopper, BuyGe, SmeltBars, SmeltBronzeBars)
compile UNCHANGED in the extraction phases. Rewiring them onto the supports directly is the
optional cleanup phase J2-10 (flagged §6.7).

| New file | Moves (current lines) | Size after purge | Dependency edges / seams |
|---|---|---|---|
| C1 `BankingSupport.java` (EXISTING, 742) | handleBankDepositItem 19639-19779, handleBankWithdraw 19780-20048, withdrawCoinsFromBank 21243-21284 (+ their latches 19663/19717/19868/19953/20147) | ~1,300 | Already holds the W4b bank clickers and already receives PlayerHelpers as a method param (:58 pattern); deps client/helper/mouse/keyboard/gameHelpers/widgetClickHelper unchanged + itemManager. Wrapper call counts from commands: handleBankClose ×9, handleBankOpen ×5, handleBankDepositAll ×5, handleBankWithdraw ×3, handleBankDepositItem ×1 (Report B) — all through kept CP wrappers. SEAM: none new |
| C2 `utility/ItemQuerySupport.java` (NEW) | getItemCount 20324, hasOre 20462, hasBar 20497, hasSmeltingOres 20246, hasBronzeBars 20285, isNearLocation 20234, waitForInventoryChange 12748-12810 | ~300 | client + helper only (pure reads). Consumed by C3/C4/C5/C6/C7. CLEAN — breaks the would-be smelting↔mining cross-dependency |
| C3 `utility/InventoryActionSupport.java` (NEW) | handlePickUpItem 12301-12631, verifyAndClickGroundItem 12632-12747, handleBuryItem 12981-13150, handleBuryAll 13273-13414, isProtectedItem 13415-13425, dropItemAtSlot 13426-13535, handleDropAll 13536-13685 | ~1,050 | deps: client, clientThread, helper, executors, mouse, keyboard, gameHelpers, itemManager, interactionSystem, cameraSystem, C2. SEAM: handleBuryAll is called by buryAllBonesInInventory (→C4) — C4 ctor-takes C3 |
| C4 `utility/WorldActionSupport.java` (NEW) | waitForPlayerReady 15976-16032, findAndOpenNearbyDoor 16033-16214, checkAndOpenDoorInPath 16215-16437, findAnyValuableLootNearby 16438-16488, waitForNPCDespawn 18423-18479, pickUpLootAt 18480-18715, pickUpAllBonesAt 18716-18824, buryAllBonesInInventory 18825-18906, interactWithNPC 21285-21410 | ~1,100 | deps: client, helper, interactionSystem, playerHelpers (gotoPositionSafe), cameraSystem, C3 (bury), C2. SEAM: cross-calls INTO C3 (bury) and PH nav delegates |
| C5 `utility/CookingFiremakingSupport.java` (NEW) | getTileClickBounds 14256-14297, handleLightFire 14298-14488, handleCookAll 14489-15116, shouldCookRawMeat 15117-15182, hasAxeInInventory 15183-15276, hasPickaxeEquippedOrInventory 15277-15355, findOrLightFire 15356-15444, findCookingInterfaceWidget 15445-15581, cookRawMeatRoutine 15582-15659, chopNearestOakTree 15660-15975 | ~1,700 | deps: client, clientThread, helper, executors, mouse, gameHelpers, skillingHelper, interactionSystem, playerHelpers (nav + useItemOnItem/B4 + animation/B5), C3 (handleDropAll from cookRawMeatRoutine:15645), C2. SEAM: heaviest cross-domain caller — extract LAST of the C-files |
| C6 `utility/MiningWorkflowSupport.java` (NEW) | handleMineOre 16642-16959, enums WorkflowLocation 16960/InventoryOreType 16969, detectCurrentLocation 16983-17037, getInventoryOreType 17038-17078, getBankOreCounts 17079-17124, executeWorkflowStep 17125-17154, handleAtMine 17155-17198, handleAtBank 17199-17349, handleElsewhere 17350-17390 + CP fields lastDepositedOre/nextOreToMine 9443-9444 | ~800 | deps: client, helper, gameHelpers, gameStateTracker, cameraSystem, interactionSystem, playerHelpers (nav/animations), CP bank wrappers, C2. SEAM 1: enum FQNs move (`CommandProcessor.WorkflowLocation` → `MiningWorkflowSupport.WorkflowLocation`) — CollectLumbridgeTinCopperCommand references executeWorkflowStep/detectCurrentLocation/getInventoryOreType + both enums via `processor.` (Report B) — update it in the same phase (file editable). SEAM 2: `processor.lastDepositedOre`/`processor.nextOreToMine` are PUBLIC FIELD accesses from commands (×1 each) — fields move to C6 as public, and the accessing command lines are updated in the same phase; CP keeps no copy |
| C7 `utility/SpellCombatSupport.java` (NEW) | handleTeleportHome 11548-11623, handleCastSpell 11624-11718, capitalizeSpellName 11719-11772, handleCastSpellOnGroundItem 11773-12111, handleCheckHPThreshold 12112-12225, getSpellWidgetId 12226-12300 | ~750 | deps: client, clientThread, helper, executors, mouse, keyboard, cameraSystem, playerHelpers (tabs/B3). FLAG: getSpellWidgetId overlaps `commands/SpellWidgetHelper` — dedup direction needs a decision (§6.4) |
| C8 `utility/EquipmentSupport.java` (NEW) | handleEquipBestMelee 10756-11020, equipItem 11021-11134, ensureRingOfForgingEquipped 11135-11259 (latch 11041) | ~510 | deps: client, clientThread, helper, mouse, gameHelpers, itemManager, EquipmentSystem (A1). Alternative: fold into A1 EquipmentSystem file (~1,620 total, still <5k) — executor's choice, prefer separate file for blast-radius |
| C9 `utility/GEInterfaceSupport.java` (NEW) | clickWidget 21411-21605, clickWidgetWithParam 21606-21725, clickChildWidgetByAction 21726-21788, findChildByAction 21789-21829, checkWidgetForActionMatch 21830-21865, findGESearchResultByName 21919-21949, searchWidgetRecursively 21950-22007, collectFromGEToBank 22008-22175, findCollectButton 22176-22231, clickCompletedOfferSlot 22232-22301 | ~850 | deps: client, clientThread, helper, mouse, widgetClickHelper. FLAG §6.5: clickWidget family is generic (not GE-specific) — candidate later merge into WidgetClickHelper; move verbatim now |
| C10 `utility/SmithingSupport.java` (NEW) | handleSmeltBronze 20088-20233, BarTypeInfo 20368-20382, getBarTypeInfo 20389-20461, handleSmeltBar 20535-20908 (+ latches 20147, 20567/20657/20823) | ~650 | deps: client, clientThread, helper, mouse, gameHelpers, C2 (getItemCount/hasOre/hasBar/hasSmeltingOres/hasBronzeBars/isNearLocation), CP bank + goto wrappers, C8 (ensureRingOfForgingEquipped), C9 clickWidget family (via CP wrappers until J2-10). SEAM: BarTypeInfo FQN moves (`CommandProcessor.BarTypeInfo` → `SmithingSupport.BarTypeInfo`) — SmeltBarsCommand references `processor.getBarTypeInfo` (Report B); update in same phase |
| — `handleGotoCommand` 17977-18106 | → **B2 NavigationHelpers** (it is the named-location nav primitive: parses args, LocationManager lookup, calls gotoPositionSafe) | +130 to B2 | deps: LocationManager (A6), cameraSystem. CP wrapper stays (13 command call sites + internal handleAtBank/handleElsewhere callers, Report B) |

**CommandProcessor shell after Group C:** ~1,285 (dispatch/lifecycle/state) + ~46 wrappers
(~250 lines) ≈ **~1,550 lines**, still nested in PlayerHelpers (FQN pinned by MannyPlugin
import :98 / field :225 — §1.6 CONFIRMED).

**PlayerHelpers.java end state:** head/fields/ctor (~190) + W6a delegate cluster 5512-5755
(~250) + nav/UI delegate stubs (~80) + CP shell (~1,550) + pinned nested classes
TileMarkerManager (369) + RandomEventHandler (132) ≈ **~2,600 lines**. Target met.

### 2.1 End-state file inventory (all < 5,000)

PlayerHelpers ~2,600 (incl. nested CP shell + pinned TileMarkerManager/RandomEventHandler);
NavigationHelpers ~3,600; CookingFiremakingSupport ~1,700; BankingSupport ~1,300;
PathfindingHelpers ~1,330; EquipmentSystem ~1,110; WorldActionSupport ~1,100;
InventoryActionSupport ~1,050; GEInterfaceSupport ~850; MiningWorkflowSupport ~800;
SpellCombatSupport ~750; SmithingSupport ~650; ControlSystem ~540; UiHelpers ~530;
EquipmentSupport ~510; MiningHelper ~500; ItemUseHelpers ~450; AnimationHelpers ~400;
ItemQuerySupport ~300; CombatStyleSystem ~250; CommandStateManager ~160;
PathfindingStateManager ~155; LocationManager ~130.
Sum ≈ 20,150 (23,683 − ~3,950 dead + wrappers/ctors overhead).

## 3. Shared-state core

**Decision: NO new context object.** Mirror the existing Wave-6a / BankingSupport pattern —
explicit constructor injection, with `PlayerHelpers` as the composition root for Group B and
`CommandProcessor`'s ctor as the composition root for Group C. Rationale: every precedent in
this codebase (InteractionSystem, BankingSupport, all 128 command classes) uses explicit ctor
deps; introducing a HelperContext would create a second pattern and force MannyPlugin-adjacent
Guice changes. Fat ctors (≤ 12 args) are accepted — they match the existing CP ctor style.

**Wiring pattern (mirrors W6a exactly):**
```java
// PlayerHelpers ctor (after line 353):
this.pathfindingHelpers = new PathfindingHelpers(client, clientThread, worldMapData, pathfinderApiClient);
this.navigationHelpers  = new NavigationHelpers(client, clientThread, helper, mouse,
        cameraSystem, interactionSystem, worldMapData, random, pathfindingHelpers, this); // back-ref
this.uiHelpers          = new UiHelpers(client, mouse, keyboard, helper, interactionSystem);
// ... B4/B5 similar. interactionSystem.setPlayerHelpers(this) stays (356) — IS keeps
// calling PH delegates, which now forward to navigationHelpers/uiHelpers.
```
Group C supports are constructed at the TOP of the CP ctor command-instantiation block
(before 9527) and handed `() -> shouldInterrupt` + responseWriter.

**Ownership table for shared mutable state:**

| State (current line) | Touched by | New owner | Access pattern |
|---|---|---|---|
| shouldCancelNavigation 253 | nav loops, cancelCurrentNavigation (KillCommand path) | NavigationHelpers (B2) | PH delegate `cancelCurrentNavigation()` forwards; sole writer B2 |
| stuck-detection fields 257-262 | nav only | B2 | private, moves verbatim |
| locationHistory 234 | MannyPlugin setter 240 (LOCKED caller), nested consumers via getter 248 | PlayerHelpers (stays) | moved code calls `playerHelpers.getLocationHistory()` |
| interactionSystem back-ref (356, 9524) | IS → gotoPositionSafe :482 / findAndPrepareGameObjectPublic :683,708 / clearUseMode :1059,1542 | PlayerHelpers facade | KEEP the PH-ctor call :356; the CP-ctor duplicate :9524 is redundant (same singleton) — delete in J2-6. PH delegates forward to B2/B3. Do NOT rewire IS in J2 (live-gated in W6a) |
| shouldInterrupt 9432, currentCommand 9433, currentCommandTaskRef 9437 | executeCommand finally (KILL-preservation fix), KillCommand, every registered command via interruptSupplier | CommandProcessor shell | supports receive `BooleanSupplier interruptSupplier`; NEVER give supports write access |
| processingEnabled 9425, pollTask/running 9420, lastPollMillis 9430 | lifecycle | CP shell | unchanged |
| loopRunning 9440 | FishDraynorLoopCommand ctor 9597 | CP shell | unchanged (passed by ref) |
| lastResumableAction 9464 + resume methods | INTERACT_OBJECT switch case 10184-10192; `resumeLastAction` called by MannyPlugin:495 (LOCKED) | CP shell | unchanged — resumeLastAction signature frozen |
| lastDepositedOre/nextOreToMine 9443-9444 (public!) | mining workflow + `processor.` field access from commands (×1 each, Report B) | MiningWorkflowSupport (C6), public fields | update the accessing command lines in J2-7 (editable); CP keeps no copy |
| activeCombatConfig 9447 + CombatConfig 9452 | `processor.activeCombatConfig` ×4 from commands; KillLoopConfigCommand:52 does `new CommandProcessor.CombatConfig()` | CP shell (both stay) | combat config is dispatch-level state; nested FQN kept — no gain from moving |
| commandRegistry 9418 | dispatch + ListCommandsCommand lambda 9598 | CP shell | unchanged |
| Widget-ID constants 264-320 | per domain | move WITH their domain (tabs→B3, GE→C9, bank→C1, minimap→B2); delete leftovers the compiler flags | |
| TileMarkerManager singleton | TileCommand/TileClearCommand ctors 9562/9596 + MannyPlugin import :99 | stays nested (pinned, §1.6) | unchanged |

## 4. Latch conversion inventory

Source: Report C in `journals/W6J2_CALL_EDGES.md` (full per-site table there). All 77
`new CountDownLatch` sites classified against the BuryItemCommand:85 executor-barrier
exemplar (latch counted down by a backgroundExecutor task = KEEP) vs the invokeLater
data-fetch pattern (= CONVERT to ClientThreadHelper).

**Verdict totals: 75 CONVERT · 1 KEEP · 1 REVIEW.**

- **KEEP (1): 6109** in `useItemOnItem` (B4 region) — latch is counted down by a
  backgroundExecutor mouse-click task, exactly the BuryItemCommand:85 pattern. It travels
  verbatim to ItemUseHelpers in J2-5. It is the ONLY executor-completion barrier among the 77.
- **REVIEW (1): 21685** in `clickWidgetWithParam` (C9 region) — the invokeLater performs a
  MUTATION (client.createMenuEntry + entry.onClick) before counting down, and the following
  mouse.click must not race it. ClientThreadHelper has NO blocking void-run-with-timeout
  (`executeOnClient` @212 is fire-and-forget). Resolution options (§6.12): add
  `runOnClient(Runnable)` blocking variant, or use `readFromClient(() -> { …; return true; })`
  (documented contract-abuse). Do NOT silently convert.
- **CONVERT (75)** — but J2-1 (dead purge) deletes 8 of them first:
  17557, 17590, 17792 (fishing block), 18122 (handleSaveLocationCommand), 20915, 20951
  (clickWidgetByAction), 21873 (waitForWidget), 22307 (clickWidgetWithMenu) are in DEAD
  methods — deleted, not converted. 21303/21332/21366 (interactWithNPC) survive (C4 takes
  interactWithNPC). **Net J2-2 conversion workload: 67 sites.**

**Conversion sub-recipes (from Report C caveats — paste into the J2-2 prompt):**
1. Straight single-value reads → `helper.readFromClient(Supplier)` (5s, throws on timeout).
2. Multi-value holders (7959, 8046, 11041, 12027, 14526, 19868, 21431, 21611, 22018, 22246)
   → `readBatchFromClient` with a small record/array return, ONE client-thread hop.
3. Sites that branch on `!latch.await(…)` instead of throwing (12521, 21732)
   → `readFromClientSafe` to preserve the no-throw control flow.
4. Polling loops (15983 waitForPlayerReady; 23441/23481 MiningHelper.dropAllOres)
   → one readFromClient per iteration; dropAllOres' per-slot reads are collapsible into a
   single batch read (do it — same data, fewer hops).
5. **ControlSystem.Conditions caveat (8370/8428/8505/8555):** `Condition.evaluate(Client,
   ClientThread)` takes a raw ClientThread and no helper — converting these requires adding a
   ClientThreadHelper param to the `Condition` interface (interface + 5 impls + call sites,
   all inside the nested ControlSystem class). Small self-contained refactor; do it within
   J2-2 or skip these 4 sites and convert them during A3's un-nest in J2-3. Either is fine;
   do not leave them half-converted.
6. Timeout semantics: most sites await 1-2s and PROCEED on timeout; readFromClient waits 5s
   and THROWS. This is the accepted W5-P3 semantic change (§6.6) — but for sites in recipe 3,
   preserve no-throw via readFromClientSafe.

**Remaining CONVERT sites by future home** (so later phases know what they inherit —
all converted in J2-2, before any move):
- → A1 EquipmentSystem: 7594 (DamageCalculator.getPlayerHealth), 7638 (FoodManager.isEnemyTooStrong)
- → A2 CombatStyleSystem: 7959 (detectCurrentStyle), 8046 (switchCombatStyle)
- → A3 ControlSystem: 8370, 8428, 8505, 8555 (Conditions.evaluate — recipe 5)
- → A8 MiningHelper: 23223 (findAvailableRocks), 23282 (selectNextRock), 23403/23441/23481 (dropAllOres)
- → stays nested (TileMarkerManager, pinned): 22781 (scanForObject)
- → C8 EquipmentSupport: 11041 (equipItem)
- → C7 SpellCombatSupport: 11817/11852/11890/11931/12027 (handleCastSpellOnGroundItem),
  12144 (handleCheckHPThreshold)
- → C3 InventoryActionSupport: 12521 (handlePickUpItem)
- → C5 CookingFiremakingSupport: 14313 (handleLightFire), 14526/14801/14868/14937/15006
  (handleCookAll), 15122 (shouldCookRawMeat), 15188 (hasAxeInInventory), 15282
  (hasPickaxeEquippedOrInventory), 15362 (findOrLightFire), 15718/15763/15900
  (chopNearestOakTree)
- → C4 WorldActionSupport: 15983 (waitForPlayerReady), 18641 (pickUpLootAt),
  21303/21332/21366 (interactWithNPC)
- → C6 MiningWorkflowSupport: 16818 (handleMineOre), 16996 (detectCurrentLocation),
  17041 (getInventoryOreType), 17082 (getBankOreCounts)
- → C1 BankingSupport: 19663/19717 (handleBankDepositItem), 19868/19953 (handleBankWithdraw)
- → C2 ItemQuerySupport: 20252 (hasSmeltingOres), 20290 (hasBronzeBars), 20327 (getItemCount),
  20465 (hasOre), 20500 (hasBar)
- → C10 SmithingSupport: 20147 (handleSmeltBronze), 20567/20657/20823 (handleSmeltBar)
- → C9 GEInterfaceSupport: 21431/21510/21550 (clickWidget), 21611 (clickWidgetWithParam),
  21685 (REVIEW — see above), 21732 (clickChildWidgetByAction), 21922 (findGESearchResultByName),
  22018/22082/22119 (collectFromGEToBank), 22246 (clickCompletedOfferSlot)

**DEFECT-1 audit rider (mandatory in J2-2):** while converting each site, grep the enclosing
method for `getWorldLocation()`/`getLocalLocation()`/`getCanvasTilePoly()`/`getClickbox()`
reached OUTSIDE an invokeLater/readFromClient wrap; REPORT every hit in the phase output
(CameraSystem.getYawToPoint:1064 is the known instance, owned by a separate fix agent —
do not fix others, just list them).

## 5. Phase sequencing (execution contract)

Rules inherited from the campaign: single writer on PlayerHelpers.java per phase; every phase
ends with the compile gate (`:client:compileJava -x checkstyleMain -x pmdMain`, JDK 21 pin);
GATE-LIVE additionally requires shadowJar + relaunch on :2 + smoke 5/5 + the phase-specific
live check; no agent commits — the orchestrator gates and commits per phase (author Tsangares).
Each phase = one subagent, prompt self-contained with the relevant §1/§2 tables pasted in.
**Every phase re-derives line numbers by name (grep) — numbers in this doc drift after J2-1.**

**Risk ranking (highest first), so the risky work is sequenced deliberately:**
1. B2 NavigationHelpers extraction (live movement, InteractionSystem back-ref seam) — J2-4.
2. CP shell rewiring / Group-C wrapper layer (dispatch correctness, interrupt plumbing) — J2-6..8.
3. Un-nesting FQN churn (repo-wide imports; Guice injection of `EquipmentSystem.EquipmentHelper`
   etc. must keep resolving) — J2-3.
4. Dead purge + latch conversion (mechanical, compiler-guarded) — J2-1/J2-2.
The mechanical phases go FIRST anyway: they shrink the monolith ~25% and reduce every later
diff; the highest-risk semantic move (nav) follows immediately after, early in the campaign,
with its own live gate.

| Phase | Owner-model | Scope | Files owned (exclusive) | Gate |
|---|---|---|---|---|
| **J2-0 pre-flight** (orchestrator) | — | W6-J1 already committed (`c01219c`). Confirm the DEFECT-1 CameraSystem fix has landed (separate agent) and is included in the next deploy; baseline compile+smoke; tag rollback point `pre-j2` | — | GATE-LIVE (existing recipe) |
| **J2-1 dead purge** | sonnet | Delete §1.7 list (~3,950 LOC incl. 8 latch sites) from PlayerHelpers; re-grep each name before deleting; drop imports/constants the compiler flags. NO other edits | PlayerHelpers.java | compile |
| **J2-2 latch conversion** | sonnet | Convert the 67 surviving CONVERT sites to ClientThreadHelper per §4 recipes 1-6; KEEP 6109 untouched; REVIEW 21685 per §6.12 decision; run the DEFECT-1 audit rider (report off-client-thread API calls, fix nothing outside latches); CameraSystem.java is off-limits | PlayerHelpers.java (+ClientThreadHelper.java ONLY if §6.12 approves the runOnClient variant) | compile |
| **J2-3 un-nest** | opus | Group A moves (A1-A6, A8 — A7/A9 are pinned and stay); repo-wide import/reference fixes (`PlayerHelpers.EquipmentSystem` → `EquipmentSystem` etc. in CombatSystem/commands/CP); delete GameEngine's unused ControlSystem import :27; update UIOverlays imports for CommandStateManager/PathfindingStateManager; Guice: injected nested types (`EquipmentSystem.EquipmentHelper`, `EquipmentSystem.FoodManager`) resolve unchanged after un-nesting (plain @Inject ctors) | PlayerHelpers.java + 7 new files + import-only edits in GameEngine/CombatSystem/ui/UIOverlays/commands/* | compile |
| **J2-4 nav extraction** | opus | B1 + B2 (+ handleGotoCommand → B2); PH delegates for gotoPositionSafe/cancelCurrentNavigation/findAndPrepareGameObjectPublic/getDistanceTo/isWithinDistance (clearUseMode stays in PH until J2-5); InteractionSystem NOT edited | PlayerHelpers.java, PathfindingHelpers.java(new), NavigationHelpers.java(new) | **GATE-LIVE**: GOTO named location round-trip on :2 + smoke 5/5 |
| **J2-5 UI/item/anim** | sonnet | B3 + B4 + B5; move clearUseMode into B3, PH delegate retained | PlayerHelpers.java + 3 new files | compile |
| **J2-6 CP supports I** | opus | C2 ItemQuerySupport first, then C1 absorb + C3 InventoryActionSupport; CP wrappers for all moved publics | PlayerHelpers.java, BankingSupport.java, ItemQuerySupport.java(new), InventoryActionSupport.java(new) | compile |
| **J2-7 CP supports II** | opus | C4 WorldActionSupport + C6 MiningWorkflowSupport (incl. enum/field moves + CollectLumbridgeTinCopperCommand updates) + C5 CookingFiremakingSupport (in that order — C5 depends on C3/C2 + B4/B5 delegates) | PlayerHelpers.java + 3 new files + CollectLumbridgeTinCopperCommand.java | **GATE-LIVE**: MINE_ORE short run (or POWER_MINE) + smoke 5/5 |
| **J2-8 CP supports III** | sonnet | C7 SpellCombatSupport + C8 EquipmentSupport + C9 GEInterfaceSupport + C10 SmithingSupport (incl. BarTypeInfo FQN update in SmeltBarsCommand) | PlayerHelpers.java + 4 new files + SmeltBarsCommand.java | compile |
| **J2-9 cleanup (PARALLEL-SAFE with J2-4..8)** | sonnet | GameEngine `ActionVerifier.matchesMenuEntry` @4734-4760 (byte-for-byte = IS legacy 3-arg) → delete; call sites 4706/4722/4836 → public `InteractionSystem.matchesMenuEntry` @2518. ActionVerifier has no IS ref: preferred fix = make the IS 3-arg method static (it is pure), call `InteractionSystem.matchesMenuEntry(...)`; alternative = pass IS into ActionVerifier. Same contains-semantics, zero behavior change — do NOT upgrade to the 4-arg version (§6.11) | GameEngine.java + InteractionSystem.java (staticify only) | compile |
| **J2-10 rewire (OPTIONAL, after sign-off §6.7)** | sonnet | Point the 12 stateful commands at supports directly; delete CP wrappers that lose their last caller | commands/*.java + PlayerHelpers.java | compile |
| **J2-11 final** (orchestrator) | — | Full live gate: relaunch, auto-login, smoke 5/5, non-preemption test, GOTO + one skilling loop + KILL interrupt (`WAIT 30000` + KILL — LOAD_CMDLOG recipe is dead post-J1); commit sequence + push; update REFACTOR_CAMPAIGN_HANDOFF.md | — | GATE-LIVE |

Parallelism map: J2-9 is the only code phase safely concurrent with the PH-serial chain
(disjoint files). J2-1→J2-8 are strictly sequential (all write PlayerHelpers). Within
J2-6/7/8 the new files are exclusive to their phase. Python-side work (if any) is fully
concurrent as usual.

Failure handling (campaign rule): gate failure → fix-up agent same model with the error; two
failures → orchestrator does it directly.

## 6. Flag list — judgment calls needing user/orchestrator sign-off

| # | Flag | Detail | Default if no answer |
|---|---|---|---|
| 6.1 | **ActivityStatistics + FarmingStatsTracker merge** (GameEngine 6530-6999 / 7393-7759, ~340-line twins) | Log-text output DIFFERS between the two = user-visible behavioral change. Campaign rule: log-text sign-off required. NOT scheduled in any J2 phase — decision only | Leave both; revisit Wave 7 |
| 6.2 | **BURY_ALL registry migration** | Legacy switch @10143-10144 dispatches `buryAllCommand.execute(… : "Bones")`; registry would pass `""`. **NEW EVIDENCE (Report B): the difference is functionally COSMETIC** — empty arg falls into substring-"bones" matching in BOTH BuryAllCommand (93/97) and legacy handleBuryAll (13316/13321), bug-for-bug identical; "Bones" also lands in substring mode. The campaign's "exact-match changes" worry does not hold. Options: (a) blank-arg default inside BuryAllCommand.execute, `register("BURY_ALL",…)`, delete the case; (b) keep switch | (a) is now low-risk and recommended — but still user sign-off (campaign explicitly flagged it); verify with a live BURY_ALL after |
| 6.3 | **Borderline public deletes** | `getLastPollMillis` 9898, `isProcessingEnabled` 9907, `clearLastResumableAction` 10378 — zero callers repo-wide but designed as external liveness API (state exporter). Delete or keep? | Keep (3 tiny methods) |
| 6.4 | **getSpellWidgetId vs commands/SpellWidgetHelper** | Probable duplicate spell-widget tables; after C7 extraction both live in separate files. Dedup direction (canonical = SpellWidgetHelper?) | Move verbatim in J2-8, dedup later |
| 6.5 | **clickWidget-family final home** | clickWidget/clickWidgetWithParam/clickChildWidgetByAction are generic widget actions placed in C9 GEInterfaceSupport by this plan (their callers are GE/shop/stateful commands); alternative is merging into WidgetClickHelper (API churn) | C9 verbatim now |
| 6.6 | **Latch-conversion timeout semantics** | Conversions adopt ClientThreadHelper's 5s throw-on-timeout (W5-P3 precedent; CookAll already noted as watch-for-flakiness). Any site the §4 table marks REVIEW needs an explicit call | Convert Pattern-A only |
| 6.7 | **J2-10 rewire of 12 stateful commands** | Dropping CP wrappers touches 12 command files for zero behavior change — churn vs cleanliness | Do it (it completes the extraction) but LAST |
| 6.8 | **handleDropAll / handleMineOre duplicates vs DropAllCommand / MineOreCommand** | Both inline helper AND command class implementations exist; KillLoopCommand:633 calls `processor.handleDropAll`, handleAtMine calls `handleMineOre`. Consolidating onto the command classes would double-write response files (command.execute writes success/failure) — behavior nuance. FishDraynorLoop precedent says acceptable | Keep both; extraction moves them verbatim (C3/C6); consolidate post-campaign |
| 6.9 | **MannyPlugin manifest additions** (no edits — notes only) | Carry-over from J1: auto-play block :798-830, 3 scenario imports/fields, :1959 callback. J2 adds (CONFIRMED via §1.6): when MannyPlugin unlocks, re-home `TileMarkerManager` import :99 and `RandomEventHandler` field :267 so A7/A9 can finally un-nest; CommandProcessor facade (5 methods) and the 3 PlayerHelpers forwarders stay regardless | — |
| 6.10 | ~~Dead state managers?~~ RESOLVED | §1.6: UIOverlays consumes both CommandStateManager (:1289-1547) and PathfindingStateManager (:2599-3137) — NOT dead. Un-nest (A4/A5) + update UIOverlays imports | closed |
| 6.11 | **ActionVerifier menu-matching semantics** | J2-9 collapses GameEngine's copy onto the LEGACY contains-based 3-arg IS method (zero behavior change). Upgrading ActionVerifier to the CANONICAL 4-arg color-strip/equals version would likely FIX latent mis-matches but changes verification behavior — separate decision, not in J2-9 | Stay on legacy 3-arg; revisit post-campaign |
| 6.12 | **ClientThreadHelper API addition for REVIEW site 21685** | clickWidgetWithParam's invokeLater MUTATES (createMenuEntry+onClick) then the code mouse-clicks — needs a blocking void-run: add `runOnClient(Runnable, timeoutMs)` to ClientThreadHelper (~15 lines, mirrors readFromClient), or abuse `readFromClient(() -> {…; return true;})` | Add `runOnClient` in J2-2 (clean, reusable — DEFECT-1-class fixes will want it too) |
| 6.13 | **CameraSystem thread audit (DEFECT-1 class)** | getYawToPoint:1064 proved Wave-5/6a conversions can strand client-thread-only calls on the background executor. J2-2's audit rider reports further instances; each hit needs its own fix decision (out of J2 scope, CameraSystem owned by the defect agent) | Audit + report only in J2; fixes queued separately |
