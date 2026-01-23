# Manny Plugin Command Reference

**Auto-generated command documentation**
**Total Commands**: 90
**Categories**: 10

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

### `ATTACK`

**Handler**: `None`
**Location**: PlayerHelpers.java:10192

*No usage examples found yet*

### `ATTACK_NPC`

**Handler**: `handleAttackNPC`
**Location**: PlayerHelpers.java:9063

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

## Interaction

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

### `VIZ_PATH`

**Handler**: `handleVizPath`
**Location**: PlayerHelpers.java:9204

*No usage examples found yet*

## Other

### `BALANCED`

**Handler**: `None`
**Location**: PlayerHelpers.java:10198

*No usage examples found yet*

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

### `STRENGTH`

**Handler**: `None`
**Location**: PlayerHelpers.java:10195

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

### `FIND_NPC`

**Handler**: `handleFindNPC`
**Location**: PlayerHelpers.java:9191

*No usage examples found yet*

### `GET_GAME_STATE`

**Handler**: `handleGetGameState`
**Location**: PlayerHelpers.java:9060

*No usage examples found yet*

### `GET_LOCATIONS`

**Handler**: `handleGetLocationsCommand`
**Location**: PlayerHelpers.java:9149

*No usage examples found yet*

### `LIST_COMMANDS`

**Handler**: `handleListCommands`
**Location**: PlayerHelpers.java:9271

*No usage examples found yet*

### `LIST_OBJECTS`

**Handler**: `handleListObjects`
**Location**: PlayerHelpers.java:9200

*No usage examples found yet*

### `QUERY_GROUND_ITEMS`

**Handler**: `handleQueryGroundItems`
**Location**: PlayerHelpers.java:9184

*No usage examples found yet*

### `QUERY_NPCS`

**Handler**: `handleQueryNPCs`
**Location**: PlayerHelpers.java:9181

*No usage examples found yet*

### `SCAN_OBJECTS`

**Handler**: `handleScanObjects`
**Location**: PlayerHelpers.java:9197

*No usage examples found yet*

### `SCAN_WIDGETS`

**Handler**: `handleScanWidgets`
**Location**: PlayerHelpers.java:9187

*No usage examples found yet*

### `TILE_LIST`

**Handler**: `handleTileList`
**Location**: PlayerHelpers.java:9162

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

### `LOAD_CMDLOG`

**Handler**: `handleLoadCmdlog`
**Location**: PlayerHelpers.java:9001

*No usage examples found yet*

### `LOAD_SCENARIO`

**Handler**: `handleLoadScenario`
**Location**: PlayerHelpers.java:8998

*No usage examples found yet*

### `PAUSE`

**Handler**: `handlePause`
**Location**: PlayerHelpers.java:9007

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
