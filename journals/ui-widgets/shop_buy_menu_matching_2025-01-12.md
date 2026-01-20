# Shop Buy Menu Matching - Lessons Learned
**Date:** 2025-01-12

## The Problem

`SHOP_BUY Mithril scimitar 1` command found the item in the shop but clicked "Buy 10" instead of "Buy 1", spending 10x the expected gold. The logs showed "Menu option 'Buy 1' not found" even though the menu clearly contained it.

## Root Cause

Two bugs in `matchesMenuEntry()` at `PlayerHelpers.java:5262`:

1. **Color tag asymmetry**: The menu entry's target was stripped of color tags, but the search target was not. When comparing `"Mithril scimitar"` (stripped) with `"<col=ff9040>Mithril scimitar</col>"` (not stripped), `contains()` returned false.

2. **Substring matching**: `"buy 10".contains("buy 1")` returns TRUE because "buy 1" is a substring. Menu entries are ordered [Buy 50, Buy 10, Buy 5, Buy 1], so forward search matched "Buy 10" at index 3 before reaching "Buy 1" at index 5.

## Key Lessons

### 1. Strip Color Tags from BOTH Sides of Comparison

**What happened:** `entryTarget` was stripped but `target` (search term) was not.
**Why:** Widget names include OSRS color codes like `<col=ff9040>`. The stripping was one-sided.

```java
// BAD - Only strips entry target, search target still has color tags
entryTarget = stripColorTags(entryTarget);
boolean targetMatch = entryTarget.contains(target.toLowerCase());
// "mithril scimitar".contains("<col=ff9040>mithril scimitar</col>") = FALSE

// GOOD - Strip BOTH targets
entryTarget = stripColorTags(entryTarget);
String cleanTarget = stripColorTags(target);  // Also strip search target
boolean targetMatch = entryTarget.contains(cleanTarget.toLowerCase());
// "mithril scimitar".contains("mithril scimitar") = TRUE
```

### 2. Use Exact Matching for Numbered Options

**What happened:** "Buy 1" matched "Buy 10" via substring contains().
**Why:** Partial matching works for most actions but fails for numbered variants.

```java
// BAD - Partial match hits wrong entry
optionMatch = entryOption.contains(option.toLowerCase());
// "buy 10".contains("buy 1") = TRUE (wrong!)

// GOOD - Exact match for numbered options
boolean useExactMatch = lowerOption.startsWith("buy ") ||
                        lowerOption.startsWith("sell ") ||
                        lowerOption.startsWith("withdraw-") ||
                        lowerOption.startsWith("deposit-");
if (exactMatch) {
    optionMatch = entryOption.equals(option.toLowerCase());
}
// "buy 10".equals("buy 1") = FALSE (correct)
```

### 3. Shops Create Real Widgets (Unlike Deposit Box)

**What happened:** Initially assumed shops might need virtual widgets like the deposit box.
**Why:** Different UI rendering strategies in OSRS.

| Interface | Widget Type | Item Source |
|-----------|-------------|-------------|
| Deposit Box (192,2) | Virtual - calculated grid positions | InventoryID.INVENTORY |
| Shop (300,16) | Real widgets with bounds | Shop's item container |
| Regular Bank (149,0) | Real widgets | Bank container |

**Lesson:** Check if `scan_widgets` or `find_widget` returns real bounds before building custom grid calculations.

## Anti-Patterns

1. **Don't assume symmetric stripping** - If you strip one side of a string comparison, strip both
2. **Don't use contains() for numbered options** - "Option 1" is a substring of "Option 10"
3. **Don't build virtual widget systems without checking** - Scan widgets first to see if real ones exist

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `get_logs(grep="SHOP_BUY")` | See what menu entries were found and which was clicked |
| `find_widget(text="scimitar")` | Check if shop items have real widgets |
| `get_logs(level="DEBUG", grep="MATCH")` | See exact/partial matching decisions |

## Interface Gaps Identified

None - existing `SHOP_BUY` command works correctly after the fix.

- [x] Plugin needs: Fixed `matchesMenuEntry()` to strip both targets and exact match "Buy/Sell"

## Files Modified

| File | Change |
|------|--------|
| `PlayerHelpers.java:5278` | Added `cleanTarget = stripColorTags(target)` to strip search target |
| `PlayerHelpers.java:5296` | Changed `target` to `cleanTarget` in comparison |
| `PlayerHelpers.java:5337-5342` | Added `"buy "` and `"sell "` to exact match prefixes |

## Quick Reference

```python
# Working shop purchase
send_command("INTERACT_NPC Zeke Trade")  # Open shop
send_command("SHOP_BUY Bronze scimitar 1")  # Buy 1 item
send_command("SHOP_BUY Mithril scimitar 5")  # Buy 5 items
```
