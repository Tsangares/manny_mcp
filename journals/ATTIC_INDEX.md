# ATTIC_INDEX — Map of Buried Value in the Manny Codebase

**Purpose.** The old bot could complete Tutorial Island, mine, kill cows, collect hides, sell at the
GE, and run quests. Development stalled because object-interaction was built as **stacked special
cases** (a class per object-type × interaction-verb). A 7-wave refactor (2026-07) plus earlier
consolidations deleted/collapsed most of that. Much of the *knowledge* was good even where the
*layering* was bad. This file is the durable MAP so future agents **reference the attic instead of
re-excavating or rebuilding from scratch**. It is a map, not a dump: pointers over pasted code.

Two repos: `~/Desktop/manny` (Java plugin — deep history) and `~/Desktop/manny_mcp` (Python driver +
YAML routines). `~/Desktop/runelite` is the RuneLite **host fork** (manny integration commit
`22cc5da32`), not a separate bot.

## Archaeology commands (how this map was built — reuse to refresh)

```bash
cd ~/Desktop/manny
git log --diff-filter=D --summary                 # every deleted file + its deleting commit
git log --oneline -S'WallObject'                  # pickaxe: when a term entered/left history
git log --diff-filter=D --format='%h %ci' -1 -- <path>   # who deleted a specific file, when
git show <sha>^:<path>                             # read a dead file at its pre-deletion state
git log --follow -- <path>                         # trace through renames
```
Pointer convention below: `git show <sha>^:<path>` reads the file as it was **just before** the
listed deleting commit `<sha>`.

---

## 1. Object-interaction layers  ← the core reason development stalled

**What it did.** Interact with every OSRS clickable: game objects (trees, rocks, doors), wall objects
(doors/gates/fences are `WallObject`, NOT `GameObject`), decorative objects, ground objects, ground
items (`TileItem`), and item-on-X uses.

**The bad layering (deleted — worth reading once to understand what NOT to rebuild).** A separate
Action class for each object-type × verb combination:
- `tutorial_island/replay/` per-type classes: `ObjectInteractionAction`, `GroundItemAction`,
  `GateAction` (deleted `34133c5`, 2025-10-19); `UseItemOnObjectAction`,
  `UseItemOnGroundItemAction`, `UseItemOnItemAction`, `UseItemOnNpcAction`, `InventoryItemAction`
  (deleted `8c8591e`, 2025-10-19); `WidgetClickAction` (deleted `adee39d`, 2025-10-19).
  Read one: `git show 34133c5^:tutorial_island/replay/ObjectInteractionAction.java`.
- `actions/Actions.java` (**5,372 lines**) + `actions/InteractionActions.java` (nested
  `NPCInteractionAction` etc.) + `Action.java`/`ActionContext.java` — deleted in **Wave 6-J1
  `c01219c`** (2026-07-17, −8,344 lines) once zero live callers remained after replay retirement.
  Read: `git show c01219c^:actions/Actions.java`. Its object-type branching (`instanceof
  WallObject/DecorativeObject/GroundObject`) is the combinatorial mess the user described.

**Where it lives NOW (survived, canonical).** `manny/utility/InteractionSystem.java` (~2,809 lines) —
**one** path, not a class per type:
- `interactWithGameObject(...)` overloads (by id / by name), `:203`, `:283`.
- The key un-layering insight: **STEP 2 fallback** searches ALL TileObject types when a GameObject
  lookup misses — `findTileObjectByName()` `:623` covers GameObject → WallObject → DecorativeObject →
  GroundObject (`:350`, `:615`). Comment at `:351`: "essential for doors, gates, fences which are
  often WallObjects." `clickTileObjectSafe()` `:759`, `clickGameObjectSafe()` `:660`.
- Ground items: `manny/utility/commands/PickUpItemCommand.java` walks `Scene → Tile[][][] →
  tile.getGroundItems() → TileItem` on the client thread (`:109`–`:140`); see also
  `QueryGroundItemsCommand`, `CastSpellOnGroundItemCommand`.
- Item-on-X survives as flat commands: `UseItemOnItemCommand`, `UseItemOnObjectCommand`,
  `UseItemOnNpcCommand`.

**Mine this / avoid this.** Mine the single-canonical-path + all-types fallback in
`InteractionSystem`. Avoid resurrecting per-(type×verb) Action classes — that was the sprawl.
**When you'd need this:** any new object interaction, or debugging "found the object but clicked
nothing" (usually a WallObject the GameObject search skipped).

---

## 2. Grand Exchange selling (fully working once)

**What it did.** Search → select → set price/qty → confirm → collect, for both buy and sell.

**Origin.** `2a181ba` "Added GE system updates" (2026-01-20): `GEBuyCommand` (758 lines),
`GESlowBuyCommand` (674), `GEAbortCommand`, `GECollectCommand`, `GESellItemCommand` — logic then
lived partly in the `PlayerHelpers` God-object.

**Where it lives NOW (survived).** `manny/utility/GEInterfaceSupport.java` (747) +
`manny/utility/commands/GeWidgetSupport.java` (584) hold the widget knowledge (e.g.
`GE_COLLECT_BUTTON = 30474246`, packed `group<<16|child`). The verb set is a ~20-command family:
`GEOpen/Search/SelectItem/InputPrice/InputQuantity/SetQuantity/Confirm/Collect/Abort/Cancel/AdjustPrice/
ClickSlot/Sell/SellItem/SlowBuy/Buy`. Item matching converged onto `utility/ItemNameMatcher.java`
(DEFECT-28/-28b, `bc186eb`/`00f0069`).

**Mine this / avoid this.** Mine the packed widget-id constants and the offer-screen flow — that is
expensive-to-re-earn knowledge. The ~20 micro-commands are the "click-tool sprawl" (see memory
`project_manny_click_tool_sprawl`); fix the canonical path, don't add variants.
**When you'd need this:** implementing autonomous selling to close a money-maker loop.

---

## 3. Quest execution machinery

**Key finding: there is no Java "quest engine."** Quests are authored as **YAML routines** in
`manny_mcp/routines/quests/`: `cooks_assistant.yaml`, `romeo_and_juliet.yaml`, `sheep_shearer.yaml`,
`restless_ghost.yaml`, `imp_catcher.yaml` (+ `quest_cooks_assistant.md`). They are executed by the
routine engine (`manny_mcp/run_routine.py`) over atomic Java commands.
- State only, on the Java side: `manny/utility/commands/GetQuestStatusCommand.java` reads
  `net.runelite.api.Quest` / `QuestState` (hardcoded quest-name list `:41`).
- Dialogue plumbing: `manny/automation/DialogueTracker.java` + `ClickContinueCommand`,
  `ClickDialogueCommand`, `TalkNpcCommand`.
- **Hard-won dialogue/widget knowledge lives in journals, not code** — mine these before re-running a
  quest live: `journals/apothecary_quest_dialogue_2026-01-27.md`,
  `cooks_assistant_flour_interaction_2026-01-26.md`, `romeo_quest_widget193_death_2026-02-09.md`,
  `gravestone_retrieval_2026-01-27.md`, `death_domain_escape_2026-01-27.md`.

**When you'd need this:** adding/repairing a quest — start from the YAML + the dated dialogue journal,
not from scratch.

---

## 4. Cow/hide + mining loops

**Cow/hide (survived).** `manny/utility/commands/KillCowGetHidesCommand.java` — `COW_PEN_CENTER =
WorldPoint(3178,3327,0)`, kills → picks up `Cowhide` at death tile → banks at Draynor, with
**resume-if-inventory-full** logic (`:90`) so a restarted run skips straight to banking. Companions:
`KillCowCommand`, `KillLoopCommand`/`KillLoopConfigCommand`. Routine:
`manny_mcp/routines/money_making/cowhide_banking.yaml` (+ `configs/cowhides.json`),
`chicken_feathers.yaml`.

**Mining (survived).** `manny/utility/MiningHelper.java` — rock selection, avoids the just-mined rock,
sorts by xp/ore. Ore table: `manny/CoreUtils.java` `:315` `MINING_ORES` (`OreData` = name, levelReq,
xpPerOre, rating, objectIds — e.g. Iron lvl15/35xp `:317`). Commands: `MineOreCommand`,
`PowerMineCommand`, support in `utility/MiningWorkflowSupport.java`. Routines:
`routines/skilling/mine_iron_ore.yaml`, `mining_falador_iron.yaml`, `superheat_mining_guild.yaml`.

**Deleted routines (recover via git).** `routines/combat/cow_killer_no_bones.yaml`,
`hill_giants.yaml` deleted `396f27f` (2026-07-18) during catalog cleanup —
`git show 396f27f^:routines/combat/cow_killer_no_bones.yaml`. Live equivalents:
`cow_killer_training.yaml`, `hill_giants_*.yaml`.
**When you'd need this:** standing up an unattended grind; the coordinate/id tables are the value.

---

## 5. Banking

**Where it lives NOW (survived).** `manny/utility/BankingSupport.java` — the expensive game-knowledge
tables: `BANK_BOOTH_IDS` / `BANK_CHEST_IDS` (dozens of ids, `:37`–`:38`), `BANKER_NAMES` `:39`,
`DEPOSIT_INVENTORY_BUTTON = 786473`, `BANK_ITEM_CONTAINER = 786445`. Command family:
`BankOpen/Close/Check/DepositAll/DepositItem/DepositEquipment/Withdraw`, plus `ScanBankCommand`.
Predecessor `utility/BankingHelper.java` was deleted in the Oct-2025 consolidation (`915f2d7`).
**When you'd need this:** any deposit/withdraw flow — copy the id tables, don't rediscover them live.

---

## 6. Other high-value buried things

- **The `PlayerHelpers` God-object saga.** All `handleX` object logic once lived in one file. Dead
  bodies purged in `bc4838c` (W6-J2 phase 1, −3,919 lines); then split into focused supports across
  W6-J2-4..8 (`ad288ab`, `2fcb602`, `069b71d`, `ee525e1`, `059cdb2`) →
  `InventoryActionSupport`, `ItemQuerySupport`, `BankingSupport`, `MiningWorkflowSupport`,
  `WorldActionSupport`, `CookingFiremakingSupport`, `SpellCombatSupport`, `EquipmentSupport`,
  `SmithingSupport`, `GEInterfaceSupport`, navigation helpers. To read any old inline handler:
  `git show bc4838c^:utility/PlayerHelpers.java`.
- **The named-backup breadcrumbs.** 16 `PlayerHelpers.java.backup_*` were deleted in `f476ff3`
  (Wave 0). Each name encodes a specific fix worth reading if that subsystem misbehaves:
  `backup_before_fish_fix`, `backup_wiki`, `backup_smelt_fix`, `backup_before_camera_scan`,
  `backup_enclosed`, `backup_python`. Recover: `git show f476ff3^:utility/PlayerHelpers.java.backup_wiki`.
- **Deleted combat/detection subsystems (game knowledge).** `AutonomousCombatManager`,
  `CombatManager`, `CombatDetector`, `DamageCalculator`, `NPCAggressionDetector`,
  `CombatStrategyDecider` (deleted `915f2d7`, 2025-10-22). Aggression/health-bar/dead-NPC skip logic
  also lived in the old `InteractionActions.NPCInteractionAction`
  (`git show 15bf5b18^:actions/InteractionActions.java`, combat-skip checks ~`:95`–`:233`). Current
  combat: `utility/CombatSystem.java`, `CombatStyleSystem.java`, `KillCommand`, `AttackNpcCommand`.
- **Deleted login flow.** `login/LoginButtonClicker`, `PlayButtonFinder`, `WorldSelector`,
  `WelcomeScreenButtonClicker`, `TryAgainButtonClicker` (2025-10-22) → collapsed into
  `login/LoginHandlers.java`.
- **Deleted recorder/inspector UI tooling.** `ui/CoordinateRecorder*`, `WidgetClickLogger`,
  `WidgetInspectorOverlay`, `WidgetResolver` (2025-10-22). Survivor:
  `tools/ExternalWidgetInspector.java` + `ui/WidgetInspectorPanel.java` — use these for widget ids.
- **MCP driver pruning (105→40 tools).** Deleted scripts carry display-isolation know-how:
  `start_screen_xephyr.sh` / `_cage.sh` / `_borderless.sh`, `server_with_dashboard.py`, the
  `test_gemini*.py` set (deleted `4782afc`, 2026-01-11; `1d5988d`, 2025-12-21). Recover a display
  launcher: `git show 4782afc^:start_screen_cage.sh`.

---

## Cross-references (read instead of re-deriving)

- `journals/2026-07-17_refactor_campaign.md`, `REFACTOR_CAMPAIGN_HANDOFF.md`,
  `REFACTOR_CAMPAIGN_LESSONS.md`, `architecture_review_2026-07-17.md` — the wave-by-wave record of
  what was deleted/collapsed and why.
- `journals/W6J2_SPLIT_PLAN.md`, `W6J2_CALL_EDGES.md` — the PlayerHelpers decomposition map.
- Memory notes: `project_manny_click_tool_sprawl`, `project_manny_automation_philosophy`.

## Maintenance note

Refresh this map during quiet windows (idle time between live runs), or whenever a large deletion
lands. Re-run the archaeology commands at the top; add a pointer for any newly-buried subsystem worth
referencing. Keep it skimmable in ~5 minutes — pointers, not pasted code.
