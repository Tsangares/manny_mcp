# Manny Plugin Command Reference

**Auto-generated command documentation**
**Total Commands**: 131
**Categories**: 11

## Table of Contents
- [Banking](#banking)
- [Combat](#combat)
- [Input](#input)
- [Interaction](#interaction)
- [Inventory](#inventory)
- [Movement](#movement)
- [Other](#other)
- [Query](#query)
- [Skilling](#skilling)
- [System](#system)
- [Grand Exchange](#grand-exchange)

## Banking

### `BANK_CHECK`

**Handler**: `handleBankCheck`
**Location**: PlayerHelpers.java:9229

*No usage examples found yet*

### `BANK_CLOSE`

**Handler**: `handleBankClose`
**Location**: PlayerHelpers.java:9214

**Example Usage**:
```yaml
- action: BANK_CLOSE
  description: "Close bank interface"
```

### `BANK_DEPOSIT_ALL`

**Handler**: `handleBankDepositAll`
**Location**: PlayerHelpers.java:9217

**Example Usage**:
```yaml
- action: BANK_DEPOSIT_ALL
  description: "Deposit all items"
```

### `BANK_DEPOSIT_EQUIPMENT`

**Handler**: `handleBankDepositEquipment`
**Location**: PlayerHelpers.java:9221

*No usage examples found yet*

### `BANK_DEPOSIT_ITEM`

**Handler**: `handleBankDepositItem`
**Location**: PlayerHelpers.java:9223

*No usage examples found yet*

### `BANK_OPEN`

**Handler**: `handleBankOpen`
**Location**: PlayerHelpers.java:9211

**Example Usage**:
```yaml
- action: BANK_OPEN
  description: "Bank items to make inventory space"
```
> *Note: Need empty inventory for quest items*

### `BANK_WITHDRAW`

**Handler**: `handleBankWithdraw`
**Location**: PlayerHelpers.java:9226

**Example Usage**:
```yaml
- action: BANK_WITHDRAW
  args: "Bucket 1"
  description: "Withdraw bucket for milk"
```
> *Note: If no bucket, buy from general store or find spawn*

## Combat

### `ATTACK_NPC`

**Handler**: `handleAttackNPC`
**Location**: PlayerHelpers.java:9063

*No usage examples found yet*

### `CAST_SPELL`

**Handler**: `CastSpellCommand`
**Location**: `utility/commands/CastSpellCommand.java`

*No usage examples found yet*

### `CAST_SPELL_NPC`

**Handler**: `handleCastSpellNPC`
**Location**: PlayerHelpers.java:12090
**Format**: `CAST_SPELL_NPC <spell_name> <npc_name>`
**Example**: `CAST_SPELL_NPC Wind_Strike Chicken`

Casts a spell on an NPC. Opens magic tab, clicks the spell, then clicks the NPC.

### `CLICK_NPC`

**Handler**: `handleClickNPC`
**Location**: PlayerHelpers.java:12360
**Format**: `CLICK_NPC <npc_name>`
**Example**: `CLICK_NPC Chicken`

Clicks on an NPC's convex hull without action filtering. Useful after selecting a spell to complete the cast. Unlike INTERACT_NPC which requires a specific action (like "Attack" or "Talk-to"), this command just clicks the NPC directly.

**Use cases:**
- After selecting a spell (click_widget on spell), use CLICK_NPC to cast on target
- When you need to click an NPC but don't know/care about the specific action
- For spell casting on NPCs as an alternative to CAST_SPELL_NPC

### `CAST_SPELL_ON_GROUND_ITEM`

**Handler**: `handleCastSpellOnGroundItem`
**Location**: PlayerHelpers.java:9070

*No usage examples found yet*

### `CAST_SPELL_ON_INVENTORY_ITEM`

**Handler**: `CastSpellOnInventoryItemCommand`
**Location**: `utility/commands/CastSpellOnInventoryItemCommand.java`

*No usage examples found yet*

### `IMP_HUNT`

**Handler**: `ImpHuntCommand`
**Location**: `utility/commands/ImpHuntCommand.java`

*No usage examples found yet*

### `KILL`

**Handler**: `handleKill`
**Location**: PlayerHelpers.java:9019

*No usage examples found yet*

### `KILL_COW`

**Handler**: `handleKillCow`
**Location**: PlayerHelpers.java:9108

*No usage examples found yet*

### `KILL_COW_GET_HIDES`

**Handler**: `handleKillCowGetHides`
**Location**: PlayerHelpers.java:9111

*No usage examples found yet*

### `KILL_LOOP`

**Handler**: `handleKillLoop`
**Location**: PlayerHelpers.java:9104

*No usage examples found yet*

### `KILL_LOOP_CONFIG`

**Handler**: `KillLoopConfigCommand`
**Location**: `utility/commands/KillLoopConfigCommand.java`

*No usage examples found yet*

### `SWITCH_COMBAT_STYLE`

**Handler**: `handleSwitchCombatStyle`
**Location**: PlayerHelpers.java:9139

*No usage examples found yet*

## Input

### `CAMERA_PITCH`

**Handler**: `handleCameraPitch`
**Location**: PlayerHelpers.java:9041

*No usage examples found yet*

### `CAMERA_POINT_AT`

**Handler**: `handleCameraPointAt`
**Location**: PlayerHelpers.java:9044

*No usage examples found yet*

### `CAMERA_RESET`

**Handler**: `handleCameraReset`
**Location**: PlayerHelpers.java:9047

*No usage examples found yet*

### `CAMERA_STABILIZE`

**Handler**: `CameraStabilizeCommand`
**Location**: `utility/commands/CameraStabilizeCommand.java`

*No usage examples found yet*

### `CAMERA_YAW`

**Handler**: `handleCameraYaw`
**Location**: PlayerHelpers.java:9038

*No usage examples found yet*

### `KEY_PRESS`

**Handler**: `handleKeyPress`
**Location**: PlayerHelpers.java:9035

*No usage examples found yet*

### `TAB_OPEN`

**Handler**: `handleTabOpen`
**Location**: PlayerHelpers.java:9050

*No usage examples found yet*

### `ZOOM`

**Handler**: `ZoomCommand`
**Location**: `utility/commands/ZoomCommand.java`

*No usage examples found yet*

## Interaction

### `CLICK_AT`

**Handler**: `ClickAtCommand`
**Location**: `utility/commands/ClickAtCommand.java`

*No usage examples found yet*

### `CLICK_CHILD_WIDGET`

**Handler**: `ClickChildWidgetCommand`
**Location**: `utility/commands/ClickChildWidgetCommand.java`

*No usage examples found yet*

### `CLICK_CONTINUE`

**Handler**: `handleClickContinue`
**Location**: PlayerHelpers.java:9263

*No usage examples found yet*

### `CLICK_DIALOGUE`

**Handler**: `handleClickDialogue`
**Location**: PlayerHelpers.java:9266

**Example Usage**:
```yaml
- action: CLICK_DIALOGUE
  args: "What's wrong?"
  description: "Ask the Cook what's wrong"
```

### `CLICK_WIDGET`

**Handler**: `handleClickWidget`
**Location**: PlayerHelpers.java:9174

*No usage examples found yet*

### `CLOSE_INTERFACE`

**Handler**: `CloseInterfaceCommand`
**Location**: `utility/commands/CloseInterfaceCommand.java`

*No usage examples found yet*

### `DESELECT`

**Handler**: `DeselectCommand`
**Location**: `utility/commands/DeselectCommand.java`

*No usage examples found yet*

### `INTERACT_NPC`

**Handler**: `handleInteractNPC`
**Location**: PlayerHelpers.java:9251

**Example Usage**:
```yaml
- action: INTERACT_NPC
  args: "Cook Talk-to"
  description: "Talk to Cook to start quest"
```

### `INTERACT_OBJECT`

**Handler**: `handleInteractObject`
**Location**: PlayerHelpers.java:9254

**Example Usage**:
```yaml
- action: INTERACT_OBJECT
  args: "Wheat Pick"
  description: "Pick wheat from field"
```

**Optional coordinate qualifier** (jar ≥ 421c03e9, manny commit `7f42b54`): `args: "<name> <action> [x y]"` —
when the trailing world coordinates are given, the object NEAREST THAT POINT is targeted instead of
nearest-to-player. Use for identical ambiguous objects (doors, ladders, gates — location is identity).
The 2-arg form is unchanged. Resolution is logged as `[MENU-MATCH]` with the chosen object's coords.
```yaml
- action: INTERACT_OBJECT
  args: "Ladder Climb-up 3123 3128"
  description: "Climb the BANK ladder (not the 3116,3126 decoy)"
```

### `MOUSE_CLICK`

**Handler**: `handleMouseClick`
**Location**: PlayerHelpers.java:9032

*No usage examples found yet*

## Inventory

### `BURY_ALL`

**Handler**: `handleBuryAll`
**Location**: PlayerHelpers.java:9091

*No usage examples found yet*

### `BURY_ITEM`

**Handler**: `handleBuryItem`
**Location**: PlayerHelpers.java:9088

*No usage examples found yet*

### `DROP_ALL`

**Handler**: `handleDropAll`
**Location**: PlayerHelpers.java:9085

*No usage examples found yet*

### `DROP_ITEM`

**Handler**: `handleDropItem`
**Location**: PlayerHelpers.java:9082

*No usage examples found yet*

### `EAT`

**Handler**: `EatCommand`
**Location**: `utility/commands/EatCommand.java`

*No usage examples found yet*

### `EQUIPMENT_LOG`

**Handler**: `handleEquipmentLog`
**Location**: PlayerHelpers.java:9053

*No usage examples found yet*

### `EQUIP_BEST_MELEE`

**Handler**: `handleEquipBestMelee`
**Location**: PlayerHelpers.java:9056

*No usage examples found yet*

### `PICK_UP_ITEM`

**Handler**: `handlePickUpItem`
**Location**: PlayerHelpers.java:9079

**Example Usage**:
```yaml
- action: PICK_UP_ITEM
  args: "Egg"
  description: "Pick up egg from ground"
```
> *Note: Egg spawns inside chicken coop fence*

### `LOOT_GRAVE`

**Handler**: `LootGraveCommand`
**Location**: `utility/commands/LootGraveCommand.java`

*No usage examples found yet*

### `QUERY_INVENTORY`

**Handler**: `handleQueryInventory`
**Location**: PlayerHelpers.java:9194

*No usage examples found yet*

### `USE_ITEM_ON_ITEM`

**Handler**: `handleUseItemOnItem`
**Location**: PlayerHelpers.java:9094

*No usage examples found yet*

### `USE_ITEM_ON_NPC`

**Handler**: `handleUseItemOnNPC`
**Location**: PlayerHelpers.java:9171

**Example Usage**:
```yaml
- action: USE_ITEM_ON_NPC
  args: "Bucket Dairy cow"
  description: "Use bucket on dairy cow to get milk"
```
> *Note: Dairy cow has 'Milk' option, not regular cows*

### `USE_ITEM_ON_OBJECT`

**Handler**: `handleUseItemOnObject`
**Location**: PlayerHelpers.java:9168

**Example Usage**:
```yaml
- action: USE_ITEM_ON_OBJECT
  args: "Grain Hopper"
  description: "Put grain in hopper"
```

## Movement

### `GOTO`

**Handler**: `handleGotoCommand`
**Location**: PlayerHelpers.java:9143

**Example Usage**:
```yaml
- action: GOTO
  args: "3208 3216 0"
  description: "Walk to Lumbridge kitchen"
```

### `MOUSE_MOVE`

**Handler**: `handleMouseMove`
**Location**: PlayerHelpers.java:9029

*No usage examples found yet*

### `TELEPORT`

**Handler**: `TeleportCommand`
**Location**: `utility/commands/TeleportCommand.java`

*No usage examples found yet*

### `TELEPORT_HOME`

**Handler**: `TeleportHomeCommand`
**Location**: `utility/commands/TeleportHomeCommand.java`

*No usage examples found yet*

### `VIZ_PATH`

**Handler**: `handleVizPath`
**Location**: PlayerHelpers.java:9204

*No usage examples found yet*

## Other

### `BUY_GE`

**Handler**: `handleBuyGE`
**Location**: PlayerHelpers.java:9241

*No usage examples found yet*

### `CHECK_HP_THRESHOLD`

**Handler**: `handleCheckHPThreshold`
**Location**: PlayerHelpers.java:9073

*No usage examples found yet*

### `CLIMB_LADDER_DOWN`

**Handler**: `handleClimbLadderDown`
**Location**: PlayerHelpers.java:9260

**Example Usage**:
```yaml
- action: CLIMB_LADDER_DOWN
  description: "Climb back to ground floor"
```

### `CLIMB_LADDER_UP`

**Handler**: `handleClimbLadderUp`
**Location**: PlayerHelpers.java:9257

**Example Usage**:
```yaml
- action: CLIMB_LADDER_UP
  description: "Climb to top floor of windmill"
```
> *Note: Need to climb 2 ladders to reach hopper*

### `DUMP_COLLISION`

**Handler**: `DumpCollisionCommand`
**Location**: `utility/commands/DumpCollisionCommand.java`

*No usage examples found yet*

### `RANDOMIZE_CHARACTER`

**Handler**: `RandomizeCharacterCommand`
**Location**: `utility/commands/RandomizeCharacterCommand.java`

*No usage examples found yet*

### `SAVE_LOCATION`

**Handler**: `handleSaveLocationCommand`
**Location**: PlayerHelpers.java:9146

*No usage examples found yet*

### `SET_CONFIG`

**Handler**: `handleSetConfig`
**Location**: PlayerHelpers.java:9013

*No usage examples found yet*

### `SHOP_BUY`

**Handler**: `handleShopBuy`
**Location**: PlayerHelpers.java:9244

*No usage examples found yet*

### `SMELT_BAR`

**Handler**: `handleSmeltBars`
**Location**: PlayerHelpers.java:9238

*No usage examples found yet*

### `SMELT_BRONZE`

**Handler**: `handleSmeltBronze`
**Location**: PlayerHelpers.java:9232

*No usage examples found yet*

### `SMELT_BRONZE_BARS`

**Handler**: `handleSmeltBronzeBars`
**Location**: PlayerHelpers.java:9235

*No usage examples found yet*

### `TALK_NPC`

**Handler**: `handleTalkNPC`
**Location**: PlayerHelpers.java:9248

*No usage examples found yet*

### `TELEGRAB_WINE_LOOP`

**Handler**: `handleTelegrabWineLoop`
**Location**: PlayerHelpers.java:9076

*No usage examples found yet*

### `TILE`

**Handler**: `handleTileCommand`
**Location**: PlayerHelpers.java:9153

*No usage examples found yet*

### `TILE_CLEAR`

**Handler**: `handleTileClear`
**Location**: PlayerHelpers.java:9156

*No usage examples found yet*

### `TILE_CLEAR_ALL`

**Handler**: `handleTileClearAll`
**Location**: PlayerHelpers.java:9159

*No usage examples found yet*

### `TILE_EXPORT`

**Handler**: `handleTileExport`
**Location**: PlayerHelpers.java:9165

*No usage examples found yet*

### `VIZ_REGION`

**Handler**: `handleVizRegion`
**Location**: PlayerHelpers.java:9207

*No usage examples found yet*

### `WAIT`

**Handler**: `handleWait`
**Location**: PlayerHelpers.java:9177

*No usage examples found yet*

## Query

### `FIND_GRAVE`

**Handler**: `FindGraveCommand`
**Location**: `utility/commands/FindGraveCommand.java`

*No usage examples found yet*

### `FIND_NPC`

**Handler**: `handleFindNPC`
**Location**: PlayerHelpers.java:9191

*No usage examples found yet*

### `FIND_OBJECT`

**Handler**: `FindObjectCommand`
**Location**: `utility/commands/FindObjectCommand.java`

*No usage examples found yet*

### `GET_GAME_STATE`

**Handler**: `handleGetGameState`
**Location**: PlayerHelpers.java:9060

*No usage examples found yet*

### `GET_LOCATIONS`

**Handler**: `handleGetLocationsCommand`
**Location**: PlayerHelpers.java:9149

*No usage examples found yet*

### `GET_QUEST_STATUS`

**Handler**: `GetQuestStatusCommand`
**Location**: `utility/commands/GetQuestStatusCommand.java`

*No usage examples found yet*

### `LIST_COMMANDS`

**Handler**: `handleListCommands`
**Location**: PlayerHelpers.java:9271

*No usage examples found yet*

### `LIST_OBJECTS`

**Handler**: `handleListObjects`
**Location**: PlayerHelpers.java:9200

*No usage examples found yet*

### `QUERY_EQUIPMENT`

**Handler**: `QueryEquipmentCommand`
**Location**: `utility/commands/QueryEquipmentCommand.java`

*No usage examples found yet*

### `QUERY_GROUND_ITEMS`

**Handler**: `handleQueryGroundItems`
**Location**: PlayerHelpers.java:9184

*No usage examples found yet*

### `QUERY_NPCS`

**Handler**: `handleQueryNPCs`
**Location**: PlayerHelpers.java:9181

*No usage examples found yet*

### `QUERY_PLAYERS`

**Handler**: `QueryPlayersCommand`
**Location**: `utility/commands/QueryPlayersCommand.java`

*No usage examples found yet*

### `QUERY_TRANSITIONS`

**Handler**: `QueryTransitionsCommand`
**Location**: `utility/commands/QueryTransitionsCommand.java`

*No usage examples found yet*

### `SCAN_BANK`

**Handler**: `ScanBankCommand`
**Location**: `utility/commands/ScanBankCommand.java`

*No usage examples found yet*

### `SCAN_OBJECTS`

**Handler**: `handleScanObjects`
**Location**: PlayerHelpers.java:9197

*No usage examples found yet*

### `SCAN_TILEOBJECTS`

**Handler**: `ScanTileObjectsCommand`
**Location**: `utility/commands/ScanTileObjectsCommand.java`

*No usage examples found yet*

### `SCAN_WIDGETS`

**Handler**: `handleScanWidgets`
**Location**: PlayerHelpers.java:9187

*No usage examples found yet*

### `TILE_LIST`

**Handler**: `handleTileList`
**Location**: PlayerHelpers.java:9162

*No usage examples found yet*

### `WIKI_QUERY`

**Handler**: `WikiQueryCommand`
**Location**: `utility/commands/WikiQueryCommand.java`

*No usage examples found yet*

## Skilling

### `CHOP_TREE`

**Handler**: `handleChopTree`
**Location**: PlayerHelpers.java:9133

*No usage examples found yet*

### `COLLECT_LUMBRIDGE_TIN_COPPER`

**Handler**: `handleFish`
**Location**: PlayerHelpers.java:9120

*No usage examples found yet*

### `COOK_ALL`

**Handler**: `handleCookAll`
**Location**: PlayerHelpers.java:9101

*No usage examples found yet*

### `FISH`

**Handler**: `handleFish`
**Location**: PlayerHelpers.java:9123

*No usage examples found yet*

### `FISH_DRAYNOR_LOOP`

**Handler**: `handleFishDraynorLoop`
**Location**: PlayerHelpers.java:9129

*No usage examples found yet*

### `FISH_DROP`

**Handler**: `handleFishDrop`
**Location**: PlayerHelpers.java:9126

*No usage examples found yet*

### `LIGHT_FIRE`

**Handler**: `handleLightFire`
**Location**: PlayerHelpers.java:9098

*No usage examples found yet*

### `MINE_ORE`

**Handler**: `handleMineOre`
**Location**: PlayerHelpers.java:9117

*No usage examples found yet*

### `POWER_CHOP`

**Handler**: `handlePowerChop`
**Location**: PlayerHelpers.java:9136

*No usage examples found yet*

### `POWER_MINE`

**Handler**: `handlePowerMine`
**Location**: PlayerHelpers.java:9114

*No usage examples found yet*

## System

### `EMERGENCY_STOP`

**Handler**: `handleEmergencyStop`
**Location**: PlayerHelpers.java:9016

*No usage examples found yet*

### `F2P_MODE`

**Handler**: `F2PModeCommand`
**Location**: `utility/commands/F2PModeCommand.java`

*No usage examples found yet*

### `LOGIN`

**Handler**: `LOGIN` (legacy switch case, inline in PlayerHelpers.java)
**Location**: PlayerHelpers.java (legacy switch, uses `LoginHandlers`)

Triggers the Java login routine (clicks the "Play Now" button).

*No usage examples found yet*

### `PAUSE`

**Handler**: `handlePause`
**Location**: PlayerHelpers.java:9007

*No usage examples found yet*

### `PING`

**Handler**: `PingCommand`
**Location**: `utility/commands/PingCommand.java`

*No usage examples found yet*

### `RESUME`

**Handler**: `handleResume`
**Location**: PlayerHelpers.java:9010

*No usage examples found yet*

### `START_PROCESSOR`

**Handler**: `handleStartProcessor`
**Location**: PlayerHelpers.java:9025

*No usage examples found yet*

### `STOP`

**Handler**: `handleStop`
**Location**: PlayerHelpers.java:9004

*No usage examples found yet*

### `STOP_PROCESSOR`

**Handler**: `handleStopProcessor`
**Location**: PlayerHelpers.java:9022

*No usage examples found yet*

## Grand Exchange

### `GE_ABORT`

**Handler**: `GEAbortCommand`
**Location**: `utility/commands/GEAbortCommand.java`

*No usage examples found yet*

### `GE_ADJUST_PRICE`

**Handler**: `GEAdjustPriceCommand`
**Location**: `utility/commands/GEAdjustPriceCommand.java`

*No usage examples found yet*

### `GE_BUY`

**Handler**: `GEBuyCommand`
**Location**: `utility/commands/GEBuyCommand.java`

*No usage examples found yet*

### `GE_CANCEL`

**Handler**: `GECancelCommand`
**Location**: `utility/commands/GECancelCommand.java`

*No usage examples found yet*

### `GE_CLICK_BUY`

**Handler**: `GEClickSlotCommand` (buy mode)
**Location**: `utility/commands/GEClickSlotCommand.java`

*No usage examples found yet*

### `GE_CLICK_SELL`

**Handler**: `GEClickSlotCommand` (sell mode)
**Location**: `utility/commands/GEClickSlotCommand.java`

*No usage examples found yet*

### `GE_COLLECT`

**Handler**: `GECollectCommand`
**Location**: `utility/commands/GECollectCommand.java`

*No usage examples found yet*

### `GE_CONFIRM`

**Handler**: `GEConfirmCommand`
**Location**: `utility/commands/GEConfirmCommand.java`

*No usage examples found yet*

### `GE_INPUT_PRICE`

**Handler**: `GEInputPriceCommand`
**Location**: `utility/commands/GEInputPriceCommand.java`

*No usage examples found yet*

### `GE_INPUT_QUANTITY`

**Handler**: `GEInputQuantityCommand`
**Location**: `utility/commands/GEInputQuantityCommand.java`

*No usage examples found yet*

### `GE_OPEN`

**Handler**: `GEOpenCommand`
**Location**: `utility/commands/GEOpenCommand.java`

*No usage examples found yet*

### `GE_SEARCH`

**Handler**: `GESearchCommand`
**Location**: `utility/commands/GESearchCommand.java`

*No usage examples found yet*

### `GE_SELECT_ITEM`

**Handler**: `GESelectItemCommand`
**Location**: `utility/commands/GESelectItemCommand.java`

*No usage examples found yet*

### `GE_SELL`

**Handler**: `GESellCommand`
**Location**: `utility/commands/GESellCommand.java`

*No usage examples found yet*

### `GE_SELL_ITEM`

**Handler**: `GESellItemCommand`
**Location**: `utility/commands/GESellItemCommand.java`

*No usage examples found yet*

### `GE_SET_QUANTITY`

**Handler**: `GESetQuantityCommand`
**Location**: `utility/commands/GESetQuantityCommand.java`

*No usage examples found yet*

### `GE_SLOW_BUY`

**Handler**: `GESlowBuyCommand`
**Location**: `utility/commands/GESlowBuyCommand.java`

*No usage examples found yet*

> Note: `BUY_GE` (a separate, older high-level "buy from GE" workflow command) is
> documented under [Other](#other) rather than here, since it predates this
> Grand Exchange command cluster and is not part of the low-level `GE_*` widget
> sequence.
