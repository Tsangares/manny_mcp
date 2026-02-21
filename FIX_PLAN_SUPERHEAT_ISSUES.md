# Fix Plan: Superheat Mining Issues

## Current Status
- Steel bar production: 62/1000 (6.2%)
- Mining and basic interactions work
- **Spell casting fails** - blocking superheat workflow

---

## Root Cause Analysis

### Issue 1: `isTabOpen()` Detection Bug (Task #9)
**Location:** `manny_src/utility/PlayerHelpers.java:7271`

**Current Implementation:**
```java
public boolean isTabOpen(int childId) {
    Widget widget = client.getWidget(TOPLEVEL_INTERFACE, childId);
    return widget != null && !widget.isHidden();
}
```

**Problem:** `widget.isHidden()` is unreliable for detecting tab state. The widget may exist and report `isHidden=false` even when the tab content isn't actually visible.

**Evidence from logs:**
```
Magic tab click sent but verification check failed (known isTabOpen bug) - assuming success
[CAST_SPELL_ON_INVENTORY_ITEM] Could not find spell widget: Superheat Item
```

**Proposed Fix Options:**

**Option A: Check the content widget instead of tab button**
Instead of checking if the tab button widget is visible, check if the actual spellbook content widget (group 218) has visible children.

```java
public boolean isMagicTabOpen() {
    // Check if spellbook container has visible widgets
    Widget spellbook = client.getWidget(218, 0);
    return spellbook != null && !spellbook.isHidden() && spellbook.getChildren() != null;
}
```

**Option B: Check VarClientInt for current tab**
RuneLite tracks the currently open tab via client variables.

```java
public int getCurrentTab() {
    return client.getVarcIntValue(VarClientInt.INVENTORY_TAB);
}

public boolean isMagicTabOpen() {
    return getCurrentTab() == 6; // Magic tab index
}
```

**Option C: Use getSpriteId() on tab button**
Active tabs have different sprites than inactive ones.

**Recommendation:** Option B is most reliable - use VarClientInt.

---

### Issue 2: Spell Widget Not Found
**Location:** `manny_src/utility/PlayerHelpers.java:12628`

**Current flow:**
1. Open Magic tab (clicks F6 or tab widget)
2. Wait SHORT_WAIT_MS
3. Try to find spell widget by ID (e.g., 14286881 for Superheat Item)
4. **FAILS** - widget not found

**Why it fails:**
- Tab may not have fully loaded
- Widget ID calculation may be wrong for different spellbooks
- Need to verify tab is actually open before searching

**Proposed Fix:**
1. Use fixed isTabOpen() (Option B above)
2. Add retry logic with exponential backoff
3. Verify spell widget exists before clicking

```java
// Wait for magic tab to be ready
for (int i = 0; i < 5; i++) {
    if (isMagicTabOpen()) {
        Widget spell = client.getWidget(spellWidgetId);
        if (spell != null && !spell.isHidden()) {
            break; // Ready to cast
        }
    }
    Thread.sleep(100 * (i + 1));
}
```

---

### Issue 3: Camera Zoom Defaults
**Current defaults in stabilize_camera:**
- pitch=400
- zoom_in_scrolls=8

**Better defaults based on user feedback:**
- pitch=350
- zoom_in_scrolls=15

**Fix:** Update `mcp__runelite-debug__stabilize_camera` defaults.

---

### Issue 4: Right-click Menu Blocking Actions
**Problem:** Sometimes a right-click menu stays open, blocking subsequent commands.

**Fix:** Add ESC key press before critical operations:
```java
// Clear any open menus before spell casting
client.keyPressed(KeyEvent.VK_ESCAPE);
Thread.sleep(50);
```

---

## Implementation Plan

### Phase 1: Fix isTabOpen() - CRITICAL
1. Add `getCurrentTab()` method using VarClientInt
2. Update `isTabOpen()` to use it
3. Update `isMagicTabOpen()`, `isInventoryOpen()`, etc.
4. Build and test

### Phase 2: Fix Spell Casting
1. Add retry logic in CAST_SPELL_ON_INVENTORY_ITEM
2. Verify tab open with new method
3. Add ESC before opening tab
4. Build and test

### Phase 3: Update Camera Defaults
1. Change stabilize_camera defaults
2. Test in Mining Guild

### Phase 4: Resume Superheat Mining
1. Start client
2. Go to Mining Guild
3. Test full superheat cycle
4. Monitor for issues

---

## Files to Modify

1. **manny_src/utility/PlayerHelpers.java**
   - Line ~7271: `isTabOpen()` method
   - Line ~7324: `isMagicTabOpen()` method
   - Line ~12620: `CAST_SPELL_ON_INVENTORY_ITEM` handler

2. **mcptools/tools/commands.py** (if camera defaults stored there)
   - Update stabilize_camera default parameters

---

---

### Issue 5: Mining Clicks Too Fast
**Problem:** Algorithm clicks next rock before current mining completes.

**Evidence:** Multiple "Mine" clicks in quick succession, rock-hopping behavior.

**Proposed Fix:** Wait for confirmation before clicking next rock:
```java
// Option A: Wait for inventory change
int initialCount = getInventoryCount("Coal");
// click rock...
waitUntil(() -> getInventoryCount("Coal") > initialCount, 15000);

// Option B: Wait for XP drop
int initialXp = client.getSkillExperience(Skill.MINING);
// click rock...
waitUntil(() -> client.getSkillExperience(Skill.MINING) > initialXp, 15000);

// Option C: Wait for idle animation
waitUntil(() -> client.getLocalPlayer().getAnimation() == -1, 15000);
```

**Recommendation:** Use inventory count for MINE_ORE command since we want the ore.

---

### Issue 6: Unnecessary Right-Clicks on Rocks
**Problem:** "Mine" should be left-click but code does right-click + menu selection.

**Evidence from logs:**
```
'Mine' is not first option - performing right click and menu selection
```

**Likely Causes:**
1. Mouse hover not registering before menu check
2. Rock is depleted (shows "Prospect" not "Mine")
3. Another entity under cursor

**Proposed Fix:**
1. Add delay after moving to target before checking menu
2. Verify "Mine" is in menu entries before deciding click type
3. Retry hover if first option isn't expected

---

## Testing Checklist
- [ ] isTabOpen() correctly detects Magic tab state
- [ ] CAST_SPELL_ON_INVENTORY_ITEM finds Superheat Item spell
- [ ] Superheat Item successfully cast on Iron ore
- [ ] Full mining cycle works: mine 2 coal, mine 1 iron, superheat
- [ ] Camera zoom stays comfortable during mining

---

## Delegation Opportunity
These tasks could be worked on in parallel by other agents:
- Task #7: Add currentTab field to game state JSON
- Task #11: Add logging for successful CAST_SPELL commands
- Task #4: Fix pathfinding door detection
