# W6-J2 Call-Edge Reports (input data for W6J2_SPLIT_PLAN.md §2-6)

Produced 2026-07-17 ~22:00 by two mapping subagents of the J2 planning agent (which was
terminated by a session limit before synthesizing §2-6). Preserved verbatim here so the
plan can be finished without re-running the survey. Line numbers measured against the
post-W6-J1 uncommitted working tree of /home/wil/Desktop/manny (PlayerHelpers.java = 23,683
lines) — re-verify by name before editing.

---

## REPORT A: External PlayerHelpers consumers (outside utility/commands/)

Only **6 files** outside `utility/commands/` and PlayerHelpers.java reference PlayerHelpers
(57 reference lines). **MannyPlugin does NOT `new PlayerHelpers(...)`** — all wiring is Guice
`@Inject`. Only InteractionSystem, BankingSupport, CombatSystem, MannyPlugin call instance
methods; UIOverlays and GameEngine use only nested static types.

### Receiver fields
| File | Names PlayerHelpers as | Decl line |
|---|---|---|
| MannyPlugin.java | `playerHelpers` (@Inject field) | 270 |
| | `commandProcessor` (CommandProcessor, @Inject) | 225 |
| | `randomEventHandler` (RandomEventHandler, @Inject) | 267 |
| InteractionSystem.java | `playerHelpers` (mutable, via setter) | 64 |
| CombatSystem.java | `playerHelpers` (final, ctor) | 52 |
| BankingSupport.java | `playerHelpers` (method PARAMETER, no field) | 58 |
| UIOverlays.java | none — static nested singletons only | — |
| GameEngine.java | none at runtime — unused import (line 27) + comments | — |

### Instance-method edges
| Method | Caller sites |
|---|---|
| setLocationHistory | MannyPlugin:477 |
| onMenuOptionClicked(String) | MannyPlugin:1130 |
| onInventoryChanged | MannyPlugin:1139 |
| gotoPositionSafe(clientThread,tile,1) | InteractionSystem:482 |
| findAndPrepareGameObjectPublic | InteractionSystem:683,708; BankingSupport:111 |
| clearUseMode | InteractionSystem:1059,1542 |
| gotoPosition(safeSpot) | CombatSystem:1868 |
| getCameraSystem() (.getYawToPoint/.calculateYawDifference/.prepareToViewTarget/.isObjectVisible) | BankingSupport:127,128,137,157,164 |
| getKeyboard().rotate | BankingSupport:152 |
| clickMenuEntrySafe("Bank",...) | BankingSupport:266,312,456 |

### Nested types used externally
| Nested type | Consumers |
|---|---|
| CommandProcessor | MannyPlugin import:98 field:225; .start()486 .resumeLastAction()495 .stop()556 .clearCommandFile()731 .executeCommand()1199; CombatConfig new'd at commands/KillLoopConfigCommand:52 |
| RandomEventHandler | MannyPlugin field:267; .handleRandomEvent 1046, .handleWidgetClosed 1111 |
| TileMarkerManager | MannyPlugin import:99 |
| EquipmentSystem (+FoodManager/EquipmentDetector/DamageCalculator) | CombatSystem import:16, fields 50,51,54, ctor 381-384, use 1816 |
| ControlSystem | GameEngine import:27 only — UNUSED |
| CommandStateManager (+CommandStep/FireObjectInfo) | UIOverlays:1289-1547 via static getInstance() |
| PathfindingStateManager (+PathfindingState) | UIOverlays:2599-3137 via static getInstance() |
| LocationManager | internal only (PH:9518) |
| MiningHelper | no external consumer |

### Construction
- PlayerHelpers @Inject ctor: PH:322-357, 13 params (Client, ClientThread, ClientThreadHelper,
  CoreUtils.Executors, Mouse, GameHelpers, WorldMapData, ItemManager, CameraSystem, MannyConfig,
  LoginHandlers, CharacterRandomizer, InteractionSystem).
- CommandProcessor @Inject ctor: PH:9466-9525, 24 params.

### Wave-6a back-ref pattern (to mirror in J2)
InteractionSystem ctor-injected into PH; back-ref set INSIDE PH ctor via setter:
PH:228 field, :336 param, :353 assign, :356 `interactionSystem.setPlayerHelpers(this)`.
DUPLICATED in CommandProcessor ctor: PH:9519, :9524 (same singleton — setter called twice).
Receiver: InteractionSystem:63-64 mutable field, :139-142 setter, null-guards at 435, 677.

### InteractionSystem public API (2,677 lines)
setLocationHistory 72; getConsecutiveEmptyMenuFailures 109; resetDisconnectDetection 118;
setSkipZoomForNextInteraction 131; setPlayerHelpers 139; interactWithGameObject 203,267,283,538,547;
onMenuOptionClicked 826; clearMenuVerification 840; stripColorTags 851; clickMenuEntrySafe 924,929;
performSmartClick 1426; isMenuOption 1454; smartClick 1490,1521; clickShape 1560; getWidgetSafe
1580,1593; getWidgetBoundsSafe 1605; isWidgetHiddenSafe 1624; getWidget 1640; interactWithNPC
1685,1765,2011; findNPCByNamePublic 1886; clickNPC 2029; verifyResourceGatheringStarted 2345;
verifyInterfaceOpened 2367; getExpectedInterfaceId 2403; getInterfaceName 2437;
verifyObjectInteraction 2451; isCorrectMenuOption 2479; hasMenuOption 2495; matchesMenuEntry 2518;
isCorrectMenuOptionSafe 2549; hasMenuOptionSafe 2557; openInventory/Equipment/Prayer/Magic/Combat/
Skills/Quests 2589-2619.

**matchesMenuEntry duality:** private 4-arg @867 (strips color tags, option.equals — the CANONICAL
fixed one, used by click path at 969,985,1136,1310,1463,1474); public 3-arg @2518 (legacy
option.contains, used only by isCorrectMenuOption/hasMenuOption 2488,2505).

### GameEngine duplicate matchesMenuEntry
GameEngine.java (8,451 lines): public matchesMenuEntry @4734-4760 inside nested
`ActionVerifier` (@4520). Byte-for-byte = InteractionSystem's LEGACY 3-arg public version
(contains-based, no color-strip — lacks the 4-arg fixes). Called at 4706, 4722, 4836.
GameEngine calls NOTHING on PlayerHelpers at runtime.

### ClientThreadHelper API (conversion target, 346 lines)
readFromClient(Supplier) @105 (invokeLater+latch, 5s timeout, [BLOCKING] TIMEOUT log 129-134);
readBatchFromClient @187; executeOnClient(Runnable) @212 (2s); readFromClientWithRetry @227,@295;
readFromClientSafe @308. BLOCKING_THRESHOLD_MS=100 @68.

### Thin delegates in PH + internal callers
Delegates: clickMenuEntrySafe 3-arg@5722→4-arg@5727→IS; smartClick @5781,@5786; stripColorTags
private@5668; onMenuOptionClicked @387.
Internal call sites: clickMenuEntrySafe ×11 (4427, 4957 outer-this; 12738, 12931, 19037, 19732,
19968, 21385, 22151, 22156, 22339 via nested CommandProcessor's `playerHelpers.` receiver);
smartClick ×1 (20118); stripColorTags ×5 (5826,5832,5842,5847,6061); onMenuOptionClicked ×0
internal (only MannyPlugin:1130). Delegates must stay reachable from BOTH outer class and
CommandProcessor inner class after the split.

---

## REPORT B: commands/ → PlayerHelpers/CommandProcessor edges

131 command files + CommandBase in utility/commands/.

### Delegation pattern
CommandBase (352 lines): only commandName + responseWriter fields (33-34) + setter-injected
interruptSupplier (42/66). NO PlayerHelpers/CommandProcessor ref. execute() final @132 wraps
abstract executeCommand @179. Deps are PER-COMMAND ctor injection. Three styles:
1. Reimplement using support classes + PH-proper (most). E.g. BankOpenCommand → bankingSupport.
   openNearestBank(playerHelpers); GotoCommand calls playerHelpers.clearOpenMenus()139,
   .cancelCurrentNavigation()143, .gotoPositionSafe(...)158.
2. Self-contained (no PH at all). E.g. BuryItemCommand (client, clientThread, executors, mouse,
   gameHelpers, helper).
3. Delegate into CommandProcessor via injected `PlayerHelpers.CommandProcessor processor` field —
   12 commands: BuryAll, BuyGe, CollectLumbridgeTinCopper, ImpHunt, KillCowGetHides,
   KillLoopConfig, KillCow, KillLoop, SmeltBronzeBars, SmeltBars, TelegrabWineLoop, Teleport.

Two receivers: `playerHelpers` → PH-proper (def < 9204); `processor` → CommandProcessor
handleX + internals (9204 < def < ~22648). No command calls handleX through PlayerHelpers.

### handleX called from commands/ (46 sites)
| handleX | n | callers (lines) |
|---|---|---|
| handleGotoCommand | 13 | SmeltBars 324,345,360,365; SmeltBronzeBars 315,336,351,356; KillCowGetHides 113,230,263; BuyGe 128; TelegrabWineLoop 147 |
| handleBankClose | 9 | SmeltBars 286,299,319; SmeltBronzeBars 264,289,310; BuyGe 148; CollectLumbridgeTinCopper 189; KillCowGetHides 256 |
| handleBankOpen | 5 | BuyGe 353; CollectLumbridgeTinCopper 184; SmeltBars 259; SmeltBronzeBars 246; KillCowGetHides 241 |
| handleBankDepositAll | 5 | SmeltBars 274,312; SmeltBronzeBars 254,278,303 |
| handleBankWithdraw | 3 | SmeltBars 295; SmeltBronzeBars 260,285 |
| handleBankDepositItem | 1 | KillCowGetHides 252 |
| handleSmeltBar | 1 | SmeltBars 335 |
| handleSmeltBronze | 1 | SmeltBronzeBars 326 |
| handleEquipBestMelee | 1 | KillLoop 152 |
| handleDropAll | 1 | KillLoop 633 |
| handlePickUpItem | 1 | ImpHunt 148 |
| handleBuryItem | 1 | BuryAll 121 |
| handleCheckHPThreshold | 1 | TelegrabWineLoop 110 |
| handleCastSpellOnGroundItem | 1 | TelegrabWineLoop 162 |
| handleTeleportHome | 1 | Teleport 49 |
| handleCastSpell | 1 | Teleport 117 |

### CommandProcessor INTERNAL helpers reached via processor. (coupling hotspot)
clickWidgetWithParam ×5, clickWidget ×5, isNearLocation ×4, activeCombatConfig field ×4,
getItemCount ×3, pickUpLootAt ×2, getInventoryOreType ×2; ×1 each: withdrawCoinsFromBank,
waitForPlayerReady (def 15976), waitForNPCDespawn, shouldCookRawMeat, pickUpAllBonesAt,
nextOreToMine, lastDepositedOre, hasSmeltingOres, hasOre, hasBronzeBars, hasBar,
hasAxeInInventory, getBarTypeInfo, getBankOreCounts, findGESearchResultByName,
findAnyValuableLootNearby, findAndOpenNearbyDoor (def 16033), executeWorkflowStep,
ensureRingOfForgingEquipped, detectCurrentLocation, cookRawMeatRoutine, collectFromGEToBank,
checkAndOpenDoorInPath, buryAllBonesInInventory (def 18825). Nested statics: CombatConfig
(def 9452), BarTypeInfo (def 20368), WorkflowLocation, InventoryOreType.
NOTE: waitForPlayerReady, findAndOpenNearbyDoor, pickUpLootAt, buryAllBonesInInventory are
INSIDE CommandProcessor (>9204) — they travel with `processor`, not PH-proper.

### PH-proper (def <9204) called via playerHelpers.
| Method (def) | n | callers |
|---|---|---|
| getLocationHistory | 7 | ClickDialogue ×4, ClickContinue, PickUpItem, UseItemOnObject |
| clickMenuEntrySafe (5722/5727) | 6 | BankDepositItem, BankWithdraw, ClickWidget, DropItem, PickUpItem, ShopBuy |
| clearOpenMenus (1729) | 4 | DropAll ×2, DropItem, Goto |
| smartMoveToWidget (5860) | 3 | CastSpell, CastSpellOnInventoryItem, TeleportHome |
| smartClick (5781/5786) | 2 | PowerMine, SmeltBronze |
| gotoPositionSafe (3210) | 2 | Goto, PowerMine |
| cancelCurrentNavigation (2424) | 2 | Goto, Kill |
| waitForActionAnimation (6610) | 2 | PowerMine, SmeltBronze |
| gotoPosition | 1 | LightFire |
| lightFire | 1 | LightFire |
| openMagic | 1 | CastSpellOnInventoryItem |
| getCharacterRandomizer | 1 | RandomizeCharacter |
| worldMapData field | 1 | KillLoop:354 |

### BuryItemCommand latch (KEEP pattern exemplar)
Latch @85 = executor-completion barrier: line 88 submits whole bury sequence to
backgroundExecutor; client-thread fetch is SEPARATE (helper.readFromClient @103-121);
finally countDown @172; await(3s) @177. Contrast legacy handleBuryAll: raw invokeLater+latch
for the data fetch itself (13296-13341).

### BURY_ALL dispatch
Legacy switch case @10143-10144 → buryAllCommand.execute(default "Bones"); NOT registered
(comments 10139-10142, 9792-9794: registry would pass ""). handleBuryAll (13273-13396) dead as
dispatch target but called by buryAllBonesInInventory @18884; handleBuryAll → handleBuryItem
@13351. Default-semantics: empty arg → substring "bones" match in BOTH implementations
(BuryAllCommand 93/97 vs handleBuryAll 13316/13321 — identical bug-for-bug); the "Bones"
default is functionally cosmetic; registering uniformly would ALSO land in substring mode.

### Legacy switch (executeCommand @10073-10232)
Registry-first guard 10102-10106; switch 10108-10204; default 10198-10203.
PING 10110 (inline new PingCommand), PAUSE 10115, RESUME 10121, CAMERA_RESET 10127 (inline
new); BURY_ALL 10143 (field, default "Bones"); LIGHT_FIRE 10147 (field, default "Logs");
LOGIN 10167-10174 (fully inline via loginHandlers); LIST_OBJECTS 10176 (field, default "15");
INTERACT_OBJECT 10184-10192 (resumable-skilling side effects then field); LIST_COMMANDS 10195
(field, fixed ""). Switch hard-references 5 command fields + loginHandlers.

### Registry
register() calls 9677-9805 (122 calls; waves: base 9677-9782, 3b 9760-9782, 3c 9785-9789,
4-B2 9795-9805); register() helper def @9814.

---

## REPORT C: Latch classification — all 77 `new CountDownLatch` sites in PlayerHelpers.java

**Totals: CONVERT (Pattern A, client-read) = 75; KEEP (Pattern B, executor barrier) = 1; REVIEW (Pattern C) = 1.**

- KEEP: 6109 `useItemOnItem` — latch counted down by backgroundExecutor mouse-click task
  (canonical BuryItemCommand:85 pattern).
- REVIEW: 21685 `clickWidgetWithParam` — invokeLater performs a MUTATION
  (client.createMenuEntry + entry.onClick) then counts down; following mouse.click must not
  race it. ClientThreadHelper gap: no blocking void-run-with-timeout ("runOnClient(Runnable)");
  executeOnClient(212) is fire-and-forget. Either add the variant or use
  readFromClient(() -> { ...; return true; }) (abuses read-only contract).

CONVERT sites by enclosing method (line: method — what it reads):
7594 DamageCalculator.getPlayerHealth; 7638 FoodManager.isEnemyTooStrong;
7959 CombatStyleSystem.detectCurrentStyle; 8046 CombatStyleSystem.switchCombatStyle;
8370 HealthBelowCondition.evaluate*; 8428 InventoryFullCondition.evaluate*;
8505 InventoryItemCondition.evaluate*; 8555 PlayerIdleCondition.evaluate*;
11041 equipItem; 11817/11852/11890/11931/12027 handleCastSpellOnGroundItem;
12144 handleCheckHPThreshold; 12521 handlePickUpItem; 14313 handleLightFire;
14526/14801/14868/14937/15006 handleCookAll; 15122 shouldCookRawMeat; 15188 hasAxeInInventory;
15282 hasPickaxeEquippedOrInventory; 15362 findOrLightFire; 15718/15763/15900
chopNearestOakTree; 15983 waitForPlayerReady; 16818 handleMineOre; 16996 detectCurrentLocation;
17041 getInventoryOreType; 17082 getBankOreCounts; 17557 detectFishingLocation;
17590 isInventoryFullForFishing; 17792 getFishingLevel; 18122 handleSaveLocationCommand;
18641 pickUpLootAt; 19663/19717 handleBankDepositItem; 19868/19953 handleBankWithdraw;
20147 handleSmeltBronze; 20252 hasSmeltingOres; 20290 hasBronzeBars; 20327 getItemCount;
20465 hasOre; 20500 hasBar; 20567/20657/20823 handleSmeltBar; 20915/20951 clickWidgetByAction;
21303/21332/21366 interactWithNPC; 21431/21510/21550 clickWidget; 21611 clickWidgetWithParam;
21732 clickChildWidgetByAction; 21873 waitForWidget; 21922 findGESearchResultByName;
22018/22082/22119 collectFromGEToBank; 22246 clickCompletedOfferSlot; 22307 clickWidgetWithMenu;
22781 TileMarkerManager.scanForObject; 23223 MiningHelper.findAvailableRocks;
23282 MiningHelper.selectNextRock; 23403/23441/23481 MiningHelper.dropAllOres.

Caveats:
- *8370/8428/8505/8555 (ControlSystem.Conditions static nested): evaluate(Client, ClientThread)
  takes raw ClientThread, no helper injected — needs Condition interface signature change or
  helper param (small refactor, not drop-in).
- Timeout semantics: most sites await 1-2s and proceed on timeout; readFromClient = 5s + THROWS.
  Sites branching on !latch.await() (12521, 20915, 20951, 21732) → readFromClientSafe.
  waitForWidget 21873 swallows InterruptedException, returns false (minor behavior change).
- Multi-holder sites (7959, 8046, 11041, 12027, 14526, 19868, 21431, 21611, 22018, 22246,
  22307) → readBatchFromClient with record/array return.
- Polling loops (15983, 21873, 23441/23481): one readFromClient per iteration; dropAllOres
  per-slot reads collapsible into one batch read.
