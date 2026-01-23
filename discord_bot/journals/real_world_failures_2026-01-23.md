# Real-World Failure Analysis

**Date:** 2026-01-23
**Model:** qwen2.5:14b
**Source:** Production Discord bot logs + test harness verification

## Summary

Tested 5 real-world failure scenarios from production logs. All 5 reproduced in test harness, confirming they are model behavior issues (not production environment quirks).

---

## Failure 1: Ground Item Scanning (HALLUCINATED_API)

**User request:** "Pick up the small fishing net off the ground"

**What happened:**
- Model tried `get_game_state(fields=["ground_items"])`
- **`ground_items` is NOT a valid field!**
- Valid fields: `location`, `inventory`, `equipment`, `skills`, `dialogue`, `nearby`, `combat`, `health`, `scenario`
- Model couldn't see ground items, gave false negative or acted blindly

**Correct approach:**
```python
query_nearby(include_ground_items=True)
# Returns: {"ground_items": ["Small fishing net", "Bones", "Raw shrimps"]}
```

**Root cause:** Model doesn't know the correct API. It invents plausible-sounding field names.

**Proposed fix:** Add explicit documentation in CONTEXT.md:
```markdown
## Ground Items
To see items on the ground, use `query_nearby(include_ground_items=True)`.
Do NOT use `get_game_state(fields=["ground_items"])` - this field does not exist!
```

---

## Failure 2: Location Lookup (NO_LOOKUP / PARTIAL_MATCH)

**User request:** "Go to the fishing spot south of lumbridge, we are nearby"

**What happened (test harness):**
- Model did NOT use `lookup_location` at all
- Just guessed coordinates: `GOTO 3240 3170 0` (5 tiles from current position)
- Player at 3242,3165 → sent to 3240,3170. That's NOT a fishing spot.

**What happened (production):**
- Model used `lookup_location("fishing spot south of lumbridge")`
- Got back "lumbridge" at 3222, 3218 (Lumbridge center, NOT fishing spot)
- Partial match on "lumbridge" ignored "fishing spot south of"

**Correct approach:**
```python
lookup_location("draynor fishing")  # or "lumbridge swamp fishing"
# Should return: 3087, 3227 (Draynor fishing spot)
```

**Root cause:**
1. Model sometimes skips lookup entirely and guesses
2. When it does lookup, the location database has partial matching issues

**Proposed fixes:**
1. Add fishing spots to location database explicitly
2. In CONTEXT.md, add guidance:
```markdown
## Location Lookup
For specific locations (fishing spots, banks, etc.), always use lookup_location.
If lookup returns unexpected results, try alternative names:
- "draynor fishing" not "fishing spot south of lumbridge"
- "varrock bank" not "bank in varrock"
```

---

## Failure 3: Directional Movement (TINY_MOVEMENT)

**User request:** "Go south"

**What happened:**
| Command | Movement |
|---------|----------|
| "Go south a bit" | 5 tiles (3165 → 3160) |
| "Go south" | **1 tile** (3165 → 3164) |

**Human expectation:**
- "Go south" = 15-30 tiles (meaningful movement)
- "Go south a bit" = 5-10 tiles (small movement)

**Model interpretation is INVERTED** - unqualified = tiny, qualified = slightly bigger.

**Root cause:** Model has no concept of reasonable OSRS movement distances.

**Proposed fix:** Add explicit guidance in CONTEXT.md:
```markdown
## Directional Movement
When user says "go [direction]" without specific distance:
- "Go south" / "Go north" / etc. → Move 20-30 tiles
- "Go south a bit" / "a little" → Move 5-10 tiles
- "Go south a lot" / "far" → Move 50+ tiles

Example: At (3242, 3165), "Go south" → GOTO 3242 3145 0 (20 tiles)
```

---

## Failure 4: Destructive Actions (NO_CONFIRMATION)

**User request:** "Drop everything in your inventory"

**What happened:**
- Production: `DROP_ALL` sent twice, no confirmation
- Test harness: Individual drops, no confirmation
- Neither behavior asked "Are you sure?"

**Human expectation:** Destructive actions (drop all, bank all, delete) should have confirmation for valuable items.

**Root cause:** Model doesn't distinguish destructive vs safe actions.

**Proposed fix options:**

1. **System prompt guidance:**
```markdown
## Destructive Actions
Before DROP_ALL, BANK_DEPOSIT_ALL, or dropping valuable items:
- List what will be affected
- Warn if items are valuable (worth 1000+ gp, quest items, runes)
- Proceed only if user confirms or items are clearly junk
```

2. **Hard-coded safety gate:** (in agentic_loop.py)
```python
DESTRUCTIVE_COMMANDS = ["DROP_ALL", "BANK_DEPOSIT_ALL"]
if any(cmd in command for cmd in DESTRUCTIVE_COMMANDS):
    # Inject confirmation request
```

---

## Issue Pattern Summary

| Issue | Description | Fix Location |
|-------|-------------|--------------|
| HALLUCINATED_API | Model invents non-existent API fields | CONTEXT.md + examples |
| NO_LOOKUP | Model guesses instead of using lookup tools | CONTEXT.md guidance |
| PARTIAL_MATCH | Location lookup returns wrong match | Location database + fuzzy matching |
| TINY_MOVEMENT | Directional commands move 1-2 tiles | CONTEXT.md with distance guidelines |
| NO_CONFIRMATION | Destructive actions execute without warning | System prompt or hard gate |

---

## Recommended Priority

### High Impact, Low Effort
1. **Document ground item scanning** - Fix hallucinated API issue with explicit docs
2. **Add movement distance guidelines** - Clear expectations for directional commands

### Medium Impact, Medium Effort
3. **Add fishing spots to location database** - Explicit entries prevent partial matches
4. **Destructive action warnings** - System prompt guidance

### High Impact, High Effort
5. **Improve location fuzzy matching** - Better handling of compound queries
6. **Hard safety gates** - Code-level enforcement for destructive actions

---

## Test Commands

```bash
# Reproduce all failures
./venv/bin/python discord_bot/test_harness.py --scenario near_ground_items -m qwen2.5:14b "Pick up the small fishing net off the ground"
./venv/bin/python discord_bot/test_harness.py --scenario near_ground_items -m qwen2.5:14b "Scan the ground tile items for a small fishing net"
./venv/bin/python discord_bot/test_harness.py --scenario near_lumbridge_south -m qwen2.5:14b "Go to the fishing spot south of lumbridge"
./venv/bin/python discord_bot/test_harness.py --scenario near_lumbridge_south -m qwen2.5:14b "Go south"
./venv/bin/python discord_bot/test_harness.py --scenario near_lumbridge_south -m qwen2.5:14b "Drop everything in your inventory"
```
