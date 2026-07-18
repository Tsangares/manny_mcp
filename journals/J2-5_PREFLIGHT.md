# J2-5 UI / Item / Animation Extraction Pre-Flight

**Date:** 2026-07-18 (post J2-4; PlayerHelpers.java = 11,302 lines, commit ad288ab head)
**Author:** J2-5 executor agent
**Scope:** B3 `UiHelpers.java` + B4 `ItemUseHelpers.java` + B5 `AnimationHelpers.java` (incl. `clearUseMode` → B3).
Every line number re-derived by symbol name against the current tree. CommandProcessor now starts at
line **2077** (`public static class CommandProcessor`); everything B3/B4/B5 lives in outer-PH before it.

---

## 1. Fresh boundary map (current line ranges)

The three groups **interleave** with STAY-in-PH methods (SECTION 3 W6a delegate cluster + tab methods
sit between item and animation code). They are NOT contiguous — extract by symbol, not by range.

### Nested data holders (move with their consumer)
| Class | Lines | Consumer | Destination |
|---|---|---|---|
| `ItemPairCheck` (priv static) | 450-458 | useItemOnItemRepeatedly | **B4** |
| `ItemBoundsPair` (priv static) | 463-471 | useItemOnItem | **B4** |
| `AnimationCheckResult` (priv static) | 476-484 | waitForAnimation | **B5** |

### B3 → `UiHelpers.java` (widget / mouse / tab)
| Method | Line | Sig | Reads/writes |
|---|---|---|---|
| clearOpenMenus | 494 | `public void() throws IE` | keyboard; calls clearUseMode |
| **clearUseMode** | 511 | `public boolean() throws IE` | **client.isWidgetSelected/getSelectedWidget/setWidgetSelected**, keyboard |
| getWidget(int) | 538 | `public Widget(int)` | client |
| getWidget(int,int) | 546 | `public Widget(int,int)` | client |
| getWidgetBounds | 554 | `public Rectangle(int)` | client |
| isWidgetHidden | 567 | `public boolean(int)` | client |
| getGESlot | 580 | `public Widget(int,int)` | client |
| isGESlotEmpty | 610 | `public Boolean(int)` | getGESlot |
| isGESlotDone | 623 | `public Boolean(int)` | getGESlot |
| getCloseableInterfaceIds | 637 | `public Vector<Integer>()` | — |
| getHull | 654 | `public Shape(Object)` | client, Perspective (client-thread accessors) |
| getMinimap | 696 | `public Point(Object)` | client, Perspective (client-thread accessors) |
| getMenuRectangle | 726 | `public Rectangle(int,int,int,int)` | client.getCanvasHeight |
| getMenuRectangleVisual | 749 | `public Rectangle(...)` | getMenuRectangle |
| getClickArea | 758 | `public Rectangle()` | — |
| moveMouseToPosition | 768 | `public void(int,int)` | mouse |
| clickMouse | 779 | `public void(boolean) throws IE` | mouse |
| moveAndClick | 792 | `public void(int,int,boolean) throws IE` | mouse |
| getMouseX | 802 | `public int()` | Mouse.mouseX (static) |
| getMouseY | 810 | `public int()` | Mouse.mouseY (static) |
| openInventory/Equipment/Prayer/Magic/Combat/Skills | 1854-1901 | `public boolean() throws IE` | switchToTab |
| switchToTab | 1911 | `private boolean(String,int,int) throws IE` | helper, client, mouse, `SHORT_WAIT_MS`; calls isTabOpen |
| isTabOpen | 1962 | `public boolean(int)` | helper, client |
| isInventoryOpen/isEquipmentOpen/isPrayerOpen/isMagicOpen | 1989-2015 | `public boolean()` | isTabOpen |
| getCurrentTab | 2022 | `public int()` | isTabOpen |

**B3 deps:** client, mouse, keyboard, helper (ClientThreadHelper). Tab-ID constants (TOPLEVEL_INTERFACE,
*_TAB_CHILD @256-261, *_TAB_ICON @265-270) move to B3. **No instance mutable fields.**

### B4 → `ItemUseHelpers.java` (item-on-item / hover)
| Method | Line | Sig |
|---|---|---|
| lightFire | 1124 | `public boolean(String) throws IE` → useItemOnItem |
| cookOnFire | 1134 | `public boolean(String) throws IE` → useItemOnItem |
| smartMove | 1165 | `public boolean(Rectangle2D,String) throws IE` → getHoverTargetName, containsIgnoreCase, interactionSystem.stripColorTags, mouse |
| smartMoveToWidget | 1221 | `public boolean(int,String) throws IE` → helper, client, smartMove |
| getHoverActionName | 1251 | `public String()` → helper, client |
| getHoverTargetName | 1270 | `public String()` → helper, client |
| containsIgnoreCase | 1287 | `private boolean(String,String)` → interactionSystem.stripColorTags |
| useItemOnItem | 1305 | `public boolean(String,String) throws IE` → helper, executors, mouse, gameHelpers; **KEEP latch @1341** |
| useItemOnItemRepeatedly | 1393 | `public int(String,String,int) throws IE` → helper, gameHelpers, useItemOnItem |
| hasItems | 1445 | `public boolean(String...) throws IE` → helper, gameHelpers |

**B4 deps:** client, helper, mouse, executors (CoreUtils.Executors), gameHelpers (GameEngine.GameHelpers),
interactionSystem. `stripColorTags` (PH private→interactionSystem) becomes a direct
`interactionSystem.stripColorTags(...)` call in B4. **No instance mutable fields.**

### B5 → `AnimationHelpers.java` (animation waits)
| Method | Line | Sig |
|---|---|---|
| waitPlayerIdle | 819 | `public void() throws IE` → waitPlayerAnimation |
| waitPlayerAnimation | 830 | `public void(int,double) throws IE` → client |
| waitPlayer(int) | 1472 | `public void(int) throws IE` → waitActor |
| waitPlayer(int,double) | 1480 | `public void(int,double) throws IE` → waitActor |
| waitActor(Actor,int) | 1488 | `public void(Actor,int) throws IE` → waitActor(3) |
| waitActor(Actor,int,double) | 1496 | `public void(...) throws IE` → client |
| getWoodcuttingAnimations | 1545 | `public Set<Integer>()` |
| getMiningAnimations | 1609 | `private Set<Integer>()` |
| getFishingAnimations | 1670 | `private Set<Integer>()` |
| getFiremakingAnimations | 1712 | `private Set<Integer>()` |
| getCookingAnimations | 1733 | `private Set<Integer>()` |
| getSmeltingAnimations | 1742 | `private Set<Integer>()` |
| getExpectedAnimations | 1754 | `public Set<Integer>(String)` |
| waitForAnimation | 1796 | `public boolean(Set<Integer>,long) throws IE` → helper, client (AnimationCheckResult) |
| waitForActionAnimation | 1842 | `public boolean(String,long) throws IE` → getExpectedAnimations, waitForAnimation |

**B5 deps:** client, helper. **No instance mutable fields.** CLEAN.

---

## 2. HIGHEST-RISK item — shared mutable state audit (the "use mode" seam)

**FINDING: There is NO PlayerHelpers-instance mutable use-mode flag.** The task anticipated a
use-mode flag on the instance (à la J2-4's `shouldCancelNavigation`). It does not exist.

`clearUseMode` (511) reads/writes the **RuneLite `Client` singleton's** selection state directly:
`client.isWidgetSelected()`, `client.getSelectedWidget()`, `client.setWidgetSelected(false)` +
`keyboard.pressKey(VK_ESCAPE)`. The "use mode" lives inside the RuneLite client, not in any
PlayerHelpers field. I re-verified: **no B3/B4/B5 method writes any instance field** (grep of the
whole 494-2039 region; the only mutable touches are `client.set*` and local vars incl. the KEEP
CountDownLatch local in useItemOnItem).

**Therefore the single-instance invariant reduces to: UiHelpers must be constructed with the SAME
`client` and `keyboard` singletons the rest of the plugin uses**, so `setWidgetSelected(false)` and
the ESC keypress act on the same client the item/UI readers read. Both are Guice singletons injected
into PlayerHelpers and passed by reference into the `new UiHelpers(...)` ctor — same objects, one
instance. **Verification:** every external `clearUseMode` caller (InteractionSystem:1061/1544,
MiningHelper:373) reaches it via `playerHelpers.clearUseMode()` → the retained PH delegate →
`uiHelpers.clearUseMode()` → the single `uiHelpers` field → the single injected `client`. There is no
second copy and no field to strand. Grep of all `clearUseMode` / `setWidgetSelected` /
`isWidgetSelected` references confirms every path resolves through the one instance.

Contrast with J2-4: because the shared state here is client-owned (not instance-owned), the "delegate
writes PH's field while the loop reads the new instance" failure mode from B2 **cannot occur** for
use-mode. This phase is materially lower-risk than J2-4.

---

## 3. Seams — PH public delegates that MUST be retained

Callers reach moved methods three ways: external files (`playerHelpers.`), the nested CommandProcessor
(via its `playerHelpers` back-ref, same file), and the already-extracted NavigationHelpers (via its
`playerHelpers` back-ref). All three need PH to keep the method public and forwarding.

| Retained PH delegate | Forwards to | Callers (verified by grep) |
|---|---|---|
| clearOpenMenus | uiHelpers | ext: GotoCommand:140, DropItemCommand:73, DropAllCommand:85/201; CP:5212/5327/8023/8226 |
| clearUseMode | uiHelpers | ext: InteractionSystem:1061/1544, MiningHelper:373 |
| getWidget(int) | uiHelpers | NavigationHelpers:3499/3502 |
| getWidget(int,int) | uiHelpers | (public API; kept for parity, no live caller) |
| openMagic | uiHelpers | ext: CastSpellOnInventoryItemCommand:90 |
| smartMoveToWidget | itemUseHelpers | ext: CastSpellCommand:80, CastSpellOnInventoryItemCommand:100, TeleportHomeCommand:66; CP:3704/3792 |
| lightFire | itemUseHelpers | ext: LightFireCommand:219; CP:5543 |
| getHoverActionName | itemUseHelpers | NavigationHelpers:3617/3632 |
| waitForActionAnimation | animationHelpers | ext: PowerMineCommand:291, SmeltBronzeCommand:149; CP:9274/9777 |
| waitPlayerIdle | animationHelpers | CP:9577/9802 + PH.moveMouse:985/1018 |
| waitPlayerAnimation | animationHelpers | NavigationHelpers:2744/2801/3011 |

**No external / cross-instance callers** (safe to drop from PH, no delegate) for: getWidgetBounds,
isWidgetHidden, getGESlot, isGESlotEmpty/Done, getCloseableInterfaceIds, getHull, getMinimap,
getMenuRectangle(Visual), getClickArea, moveMouseToPosition, clickMouse, moveAndClick, getMouseX/Y,
openInventory/Equipment/Prayer/Combat/Skills, isTabOpen, isInventoryOpen/etc, getCurrentTab,
cookOnFire, smartMove, getHoverTargetName, useItemOnItem(Repeatedly), hasItems, waitPlayer, waitActor,
the six animation-set getters, getExpectedAnimations, waitForAnimation.
(The `interactionSystem.openInventory/openMagic/isTabOpen` and `animationHelper.waitForActionAnimation`
hits in the grep are InteractionSystem's OWN tabSwitcher/animationHelper copies — NOT PH callers.)

**PH-retained method that calls moved code:** `moveMouse` (stays, SECTION 3) calls getHull ×3
(942/988/1010), getMinimap (963), getClickArea (952) → rewire these 5 sites to `uiHelpers.*`;
its `waitPlayerIdle()` calls (985/1018) resolve to the retained PH delegate, no edit.

---

## 4. Wiring plan (mirror J2-4 / BankingSupport explicit ctor injection)

PH ctor (after the navigationHelpers construction @344-345), add:
```java
this.animationHelpers = new AnimationHelpers(client, helper);
this.uiHelpers        = new UiHelpers(client, mouse, keyboard, helper);
this.itemUseHelpers   = new ItemUseHelpers(client, helper, mouse, executors, gameHelpers, interactionSystem);
```
No back-ref needed (none of B3/B4/B5 call back into PH). No construction-order coupling
(NavigationHelpers reaches getWidget/getHoverActionName/waitPlayerAnimation at RUNTIME via its
back-ref, forwarded by the PH delegates — order-independent). Three new private final fields.

---

## 5. DEFECT-3-class audit (off-client-thread accessor rider)

While surveying the moved code I checked for the DEFECT-3 pattern (client-thread-only RuneLite
accessors invoked on `manny-background` without a readFromClient wrap):

- **`getHull` (654) and `getMinimap` (696) — FLAG as follow-up (pre-existing, NOT introduced here).**
  Both call client-thread-only accessors OUTSIDE any readFromClient wrap:
  getHull → `Perspective.getCanvasTilePoly(client, …)`, `((TileObject)target).getClickbox()`,
  `((Actor)target).getConvexHull()`, `LocalPoint.fromWorld(client.getTopLevelWorldView(), …)`;
  getMinimap → `Perspective.localToMinimap(client, …)`, `((TileObject)target).getLocalLocation()`.
  Their sole live caller is `PlayerHelpers.moveMouse`, which runs on the background thread. This is
  the same class as DEFECT-1/DEFECT-3 but is LONG-STANDING behavior moving **verbatim** (zero
  behavior change this phase). Not fixed here per the brief; queued as a follow-up defect (wrap the
  getHull/getMinimap bodies — or moveMouse's use of them — in `helper.readFromClient`/`readFromClientSafe`
  with an `isClientThread()` guard, mirroring the DEFECT-3 fix). Note: RuneLite's `getClickbox()` has
  historically been tolerant off-thread which is likely why this never surfaced, but it is unsafe by
  the same rule.
- All other B3/B4/B5 client reads (getWidget, isTabOpen, switchToTab, smartMoveToWidget,
  getHoverActionName/TargetName, useItemOnItem bounds fetch, hasItems, waitForAnimation) already wrap
  their client access in `helper.readFromClient(...)` — SAFE, no new flags.
- No command **result-building** path is touched by this phase (that is Group C), so no new
  SCAN-style DEFECT-3 instances introduced.

---

## 6. Grep-trap warnings

- **`getWidget`**: overwhelmingly `client.getWidget(...)` (RuneLite) and `interactionSystem.getWidget`
  across the tree — NOT PH's method. PH's is only called cross-file by `playerHelpers.getWidget`
  (NavigationHelpers 3499/3502). Keep the delegate; do not treat client.getWidget as a caller.
- **`openInventory/openMagic/isTabOpen/waitForActionAnimation`**: InteractionSystem and GameEngine
  have their OWN copies via `tabSwitcher`/`animationHelper` fields (`interactionSystem.openInventory`,
  `animationHelper.waitForActionAnimation`). Only `playerHelpers.openMagic` (CastSpellOnInventoryItem)
  and `playerHelpers.waitForActionAnimation` (PowerMine/SmeltBronze) are PH callers.
- **KEEP latch**: useItemOnItem @1341 `new CountDownLatch(1)` is the executor-barrier KEEP (counted
  down by a backgroundExecutor mouse task) — moves verbatim to B4, do NOT convert.
  `grep -E 'new (java\.util\.concurrent\.)?CountDownLatch'` in the B3/B4/B5 region hits ONLY this site.
- `containsIgnoreCase` / `stripColorTags` are private in PH; B4 gets `interactionSystem` and calls
  `interactionSystem.stripColorTags` directly (containsIgnoreCase moves into B4 as private).

---

## Verdict

Ready to execute. ~1,180 lines move into 3 new files. The anticipated "use-mode flag" shared-state
seam does not exist (state is client-owned), so the single-instance invariant is satisfied by injecting
the same `client`/`keyboard` singletons — materially lower risk than J2-4. 11 PH delegates retained
(3 for CP back-ref, 3 for NavigationHelpers back-ref, the rest external). One DEFECT-3-class follow-up
flagged (getHull/getMinimap off-thread via moveMouse — pre-existing, moved verbatim, not fixed here).
