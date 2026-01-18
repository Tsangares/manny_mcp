# Feature Request: Bank Navigation Improvements

## Summary
The `BANK_WITHDRAW` command fails when the bank has many items because items may not be visible in the current bank view. Need scroll and search functionality to locate items reliably.

## Current Behavior
- `BANK_WITHDRAW <item> <quantity>` only works if the item is visible in the current bank tab/scroll position
- Banks with many items require scrolling to find specific items
- Commands silently fail when the item isn't visible

## Observed Issue
```
BANK_DEPOSIT_ALL  # Works - deposits everything
BANK_WITHDRAW Coins 20000  # Fails - coins may be off-screen
BANK_WITHDRAW Coins All  # Fails - same issue
```

Inventory remained empty after withdraw attempts, suggesting the item wasn't found in the visible bank area.

## Proposed Solutions

### 1. Bank Search Feature (Recommended)
Use the bank's built-in search functionality:
```
BANK_SEARCH <item_name>  # Opens search, types item name
BANK_WITHDRAW <item> <quantity>  # Now item is visible
```

Implementation:
- Click the search icon (magnifying glass) in bank interface
- Type the item name
- Item appears in filtered view
- Then click to withdraw

### 2. Bank Scroll Feature
Scroll through bank tabs to find items:
```
BANK_SCROLL_TO <item_name>  # Scrolls until item found
```

Implementation:
- Scan visible items for target
- If not found, scroll down and repeat
- Stop when item found or end of bank reached

### 3. Bank Tab Navigation
Navigate to specific bank tabs:
```
BANK_TAB <tab_number>  # Switch to tab 1-9
```

## Priority
High - Banking is essential for most activities (skilling, questing, combat)

## Workaround
Currently none reliable. Manual intervention required when items aren't visible.

## Related
- Bank interface widget IDs needed for scroll/search implementation
- May need to handle "Withdraw-X" dialogue for custom quantities
