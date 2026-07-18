# J2-6 Preflight — CP-support extraction (ItemQuerySupport + InventoryActionSupport + BankingSupport absorb)

**Date:** 2026-07-18
**Writer:** J2-6 executor (single writer of PlayerHelpers.java)
**Baseline:** PlayerHelpers.java = 10,118 lines (post J2-1/2/3 un-nest, J2-4 nav, J2-5 UI/item/anim).
All plan line numbers stale; boundaries below re-derived by symbol against the current tree.

## Scope decision: J2-6 ONLY (do NOT combine J2-7/J2-8 this pass)

Considered J2-6 alone vs J2-6+J2-7(+J2-8). Decision: **execute J2-6 only.**

Reasoning:
- **J2-7 has a distinct live-gate need + distinct risk.** Per the split plan J2-7 is the only
  GATE-LIVE Group-C phase (MINE_ORE short run) and carries the campaign's highest Group-C risk:
  mining-workflow correctness, enum FQN moves (`CommandProcessor.WorkflowLocation`/`InventoryOreType`
  → MiningWorkflowSupport), public-field moves (`lastDepositedOre`/`nextOreToMine`),
  CollectLumbridgeTinCopperCommand rewiring, plus C5 (cooking) is the heaviest cross-domain caller.
  The plan's own combine criterion says keep a phase with a distinct live-gate separate.
- **J2-8 is a different region** (spell/equip/GE/smithing) and touches SmeltBarsCommand; bundling it
  with J2-6's inventory/ground-item/banking region gives no locality benefit and a much larger,
  harder-to-review single diff whose one live-gate would span unrelated domains.
- **J2-6 is already a coherent, self-contained unit** with a clean linear dependency chain
  (C2 is the foundational pure-read base that C3 — and later C6/C10 — consume). Landing C2 first
  de-risks J2-7/J2-8. Combining would push the diff from ~1.6k to ~4.9k–7.3k moved lines.

Net: J2-6 = 2 new files + BankingSupport absorb, compile gate only. J2-7/J2-8 remain clean
follow-on passes for the orchestrator.

## Boundary map (re-derived by symbol)

### C2 → utility/ItemQuerySupport.java (NEW). Deps: Client, ClientThreadHelper. Pure reads.
| Method | Current lines | Visibility | CP wrapper kept? |
|---|---|---|---|
| waitForInventoryChange(String,boolean,long) | 3558-3601 | private | NO (only caller = handlePickUpItem, which moves to C3) |
| isNearLocation(WorldPoint,int) | 8139-8145 | public | YES (command callers via processor.) |
| hasSmeltingOres() | 8151-8173 | public | YES |
| hasBronzeBars() | 8179-8198 | public | YES |
| getItemCount(String) | 8206-8230 | public | YES (+ internal callers handleSmeltBar 8606/8621) |
| hasOre(int) | 8333-8350 | public | YES |
| hasBar(int) | 8356-8373 | public | YES |

11 command call-sites hit these via `processor.` → all 6 public methods keep identical-signature CP wrappers.

### C3 → utility/InventoryActionSupport.java (NEW).
Deps: Client, ClientThreadHelper, CoreUtils.Executors, Mouse, Keyboard, GameHelpers, CameraSystem,
ResponseWriter, PlayerHelpers, ItemQuerySupport, BooleanSupplier interruptSupplier.
(Confirmed by grep: region uses NO clientThread, NO interactionSystem, NO itemManager field — the
`itemManager` tokens in dropItemAtSlot are a local var via RuneLite injector.)
| Method | Current lines | Visibility | CP wrapper kept? |
|---|---|---|---|
| handlePickUpItem(String) | 3166-3452 | public | YES (ImpHunt:148) |
| verifyAndClickGroundItem(String) | 3457-3549 | private | NO (internal to handlePickUpItem) |
| handleBuryItem(String) | 3608-3757 | public | YES (BuryAll:121) — **KEEP latch @3643 (executor barrier) moves verbatim** |
| handleBuryAll(String) | 3765-3879 | private | YES private wrapper (buryAllBonesInInventory in C4/CP calls it) |
| PROTECTED_ITEMS + isProtectedItem(String) | 3890-3907 | private | NO |
| dropItemAtSlot(int,String) | 3909-4001 | private | NO (internal to handleDropAll) |
| handleDropAll(String) | 4013-4150 | public | YES (KillLoop:633 + cookRawMeatRoutine in CP) |

`shouldInterrupt` read 4× in C3 (handleBuryAll, handleDropAll) → `interruptSupplier.getAsBoolean()`.
`playerHelpers.` calls kept: getLocationHistory, clickMenuEntrySafe, clearOpenMenus.

### C1 → absorb into utility/BankingSupport.java (EXISTING 742 lines).
Add 2 ctor fields: ItemManager itemManager, ResponseWriter responseWriter. Move (PlayerHelpers passed
as method param, matching existing openNearestBank(playerHelpers) convention):
| Method | Current lines | CP wrapper |
|---|---|---|
| handleBankDepositItem(String) | 7625-7741 | YES → bankingSupport.handleBankDepositItem(args, playerHelpers) (KillCowGetHides:253) |
| handleBankWithdraw(String) | 7750-7992 | YES → bankingSupport.handleBankWithdraw(args, playerHelpers) (SmeltBars/SmeltBronzeBars ×3) |

**Deviation from plan:** withdrawCoinsFromBank() (8740-8773) is KEPT in CommandProcessor rather than
moved to BankingSupport. It is a 34-line orchestrator that calls handleBankOpen() (CP wrapper, stays)
+ handleBankWithdraw() (now a CP wrapper) + a coin-count fallback. Leaving it in CP preserves exact
behavior (incl. the intermediate BANK_OPEN response write) with zero coupling risk; moving it would
require reproducing handleBankOpen's response side-effect inside BankingSupport. Only 1 caller
(BuyGe:138 via processor.withdrawCoinsFromBank) — its public CP signature is unchanged.

No name collision: BankingSupport already has depositItem(int,int)/withdrawItem(int,int) — different
signatures from the String-arg handlers being added.

## Shared-state / invariants
- `shouldInterrupt`: supports receive `BooleanSupplier interruptSupplier = () -> shouldInterrupt`
  (read-only; never write access). Verified C2/C3 never WRITE shouldInterrupt.
- Single instance: C2/C3 constructed once each in the CP ctor; BankingSupport still the single
  instance at CP-ctor (its construction args extended, not duplicated).
- Latches: PlayerHelpers has 2 `new CountDownLatch` sites — 3643 (handleBuryItem, KEEP executor
  barrier, moves verbatim to C3) and 9106 (clickWidgetWithParam = C9/J2-8, NOT touched this phase).
  No new latches introduced.

## DEFECT-3-class audit (client-thread accessors on background thread)
Scanned the moved regions for off-thread getWorldLocation()/getCanvas*()/getConvexHull() reached
OUTSIDE a readFromClient/invokeLater wrap:
- **FLAG (pre-existing, NOT introduced by J2-6, not fixed):** handlePickUpItem background task calls
  `LocalPoint.fromWorld(client.getTopLevelWorldView(), worldLocation)` and `cameraSystem.isTileVisible`
  / `cameraSystem.prepareToViewTarget` directly on the background executor (lines ~3259-3263), reading
  `worldLocation = tile.getWorldLocation()` which was itself captured inside a readBatchFromClient hop
  (safe). `LocalPoint.fromWorld` off-thread is the DEFECT-1/3 pattern but is pre-existing behavior;
  moved verbatim, flagged for the defect agent. handleBankDepositItem/handleBankWithdraw wrap all
  client reads in helper.readFromClient (clean).
- No other new off-thread accessors. isNearLocation calls `client.getLocalPlayer().getWorldLocation()`
  directly (pre-existing, synchronous-context helper, unchanged).
