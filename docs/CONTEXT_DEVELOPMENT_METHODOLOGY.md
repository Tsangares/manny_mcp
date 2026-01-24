# Context Fragment Development Methodology

## Goal

Enable the Discord bot LLM to understand OSRS game mechanics through structured context fragments. This document describes how to:
1. Identify knowledge gaps
2. Gather information through gameplay
3. Create/update context fragments
4. Verify the LLM uses the knowledge correctly

---

## Phase 1: Identify Knowledge Gaps

### Signs of Missing Context

1. **LLM uses wrong tool for entity type**
   - Searches for fishing spots as objects (they're NPCs)
   - Uses PICK_UP_ITEM for static spawns (should be INTERACT_OBJECT)

2. **LLM invents commands**
   - `Net 3245, 3156` instead of `FISH shrimp`
   - `Buy Lobster` instead of `BUY_GE Lobster 100 200`

3. **LLM confuses similar actions**
   - DROP_ALL when user means BANK_DEPOSIT_ALL
   - Uses wrong command argument order

4. **Repeated failures in logs**
   ```bash
   grep "ERROR\|WARN" logs/conversations/conversations_$(date +%Y-%m-%d).log
   ```

### Priority Matrix

| Impact | Frequency | Priority |
|--------|-----------|----------|
| High (breaks task) | High | 🔴 Critical - Fix now |
| High | Low | 🟡 High - Document when encountered |
| Low | High | 🟡 Medium - Batch document |
| Low | Low | 🟢 Low - Optional |

---

## Phase 2: Gather Information Through Gameplay

### Pre-Session Setup

Before playing to document mechanics:

```python
# 1. Start session recording
start_session_recording(goal="Document smithing workflow")

# 2. Ensure camera is stable
stabilize_camera()

# 3. Check starting state
get_game_state(fields=["location", "inventory", "skills"])
```

### During Gameplay

#### A. Discovery Commands

Use these to understand what's available:

```python
# Find NPCs and objects
query_nearby(include_npcs=True, include_objects=True)

# Find specific object types
scan_tile_objects(object_name="furnace")

# Find widgets (UI elements)
find_widget(text="Smelt")
scan_widgets(filter_text="Bronze")  # Heavy - use sparingly

# Check dialogue state
get_dialogue()
```

#### B. Action Commands

Try different approaches and note which work:

```python
# Try the obvious command
send_command("SMELT_BRONZE")

# Check logs to see what happened
get_logs(grep="SMELT", level="ALL")

# Try alternative approaches
send_command("INTERACT_OBJECT Furnace Smelt")
send_command("USE_ITEM_ON_OBJECT Bronze_bar Anvil")
```

#### C. Add Markers at Key Points

```python
# When you discover something important
add_session_marker(label="Found: Furnace is object not NPC")
add_session_marker(label="PITFALL: Must select bar type in interface")
add_session_marker(label="Widget ID for bronze bar: 17694735")
```

### Key Things to Document

| Category | What to Record |
|----------|----------------|
| **Entity Types** | Is it NPC, Object, or Item? |
| **Command Format** | Exact syntax that works |
| **Widget IDs** | For interface interactions |
| **Coordinates** | Key locations (furnaces, anvils, etc.) |
| **Workflows** | Step-by-step sequences |
| **Pitfalls** | What doesn't work and why |

### Post-Session

```python
# Stop recording
result = stop_session_recording()
# Output: Session saved to /tmp/manny_sessions/session_20260124_120000.yaml

# Review session
# The file contains all commands, state changes, and markers
```

---

## Phase 3: Create/Update Context Fragment

### Template

```markdown
## [Domain] Context

### [Status if incomplete]
**STATUS: NEEDS TESTING** - [what needs verification]

### Key Commands
\`\`\`
COMMAND1 <arg>    - Description
COMMAND2 <arg>    - Description
\`\`\`

### Entity Types (if relevant)
| Thing | Type | Discovery | Interaction |
|-------|------|-----------|-------------|
| Furnace | Object | query_nearby | INTERACT_OBJECT |

### Workflow Pattern
\`\`\`python
# Step 1: Setup
send_command("...")

# Step 2: Action
send_command("...")

# Step 3: Verify
get_game_state(fields=["inventory"])
\`\`\`

### Common Locations
| Name | Coordinates | Notes |
|------|-------------|-------|
| Place | X, Y, Z | Description |

### Troubleshooting
| Problem | Solution |
|---------|----------|
| Issue | Fix |

### TODO (if incomplete)
- [ ] Need to verify X
- [ ] Missing coordinates for Y
```

### Adding to Classifier

Edit `discord_bot/activity_classifier.py`:

```python
ACTIVITY_DOMAINS = {
    # Add your domain
    "your_domain": [
        "keyword1", "keyword2",
        "multi word phrase",
    ],
}

MULTI_WORD_KEYWORDS = {
    "your_domain": ["multi word phrase"],
}
```

### Fragment Location

Save to: `discord_bot/context_fragments/<domain>.md`

---

## Phase 4: Verify

### Test Classification

```bash
./venv/bin/python -c "
from discord_bot.activity_classifier import classify_activity
print(classify_activity('your test message'))
"
```

### Test Full Flow

```bash
# With appropriate scenario
./venv/bin/python discord_bot/test_harness.py \
  --scenario default \
  "Your test message"
```

### Check Token Count

```bash
wc -w discord_bot/context_fragments/your_domain.md
# Should be under 400 words (~300 tokens)
```

### Live Test

```bash
# Restart bot
systemctl --user restart discord-bot

# Send test message via Discord
# Check logs
tail -f logs/conversations/conversations_$(date +%Y-%m-%d).log
```

---

## Quick Reference: Information Sources

| Source | Use For |
|--------|---------|
| `COMMAND_REFERENCE.md` | All 90 commands with syntax |
| `routines/*.yaml` | Working command sequences |
| `journals/*.md` | Debugging lessons |
| `manny_src/utility/PlayerHelpers.java` | Handler implementations |
| OSRS Wiki (WebFetch) | Game mechanics, item IDs |
| `get_logs(grep="X")` | Plugin behavior |
| `scan_widgets(filter_text="X")` | Widget IDs (heavy) |
| `query_nearby()` | Entity discovery |

---

## Trailblazer Main Account: Research Priorities

Based on current fragment gaps, here's what to research in-game:

### High Priority (Common Activities)

1. **Grand Exchange**
   - Open GE interface
   - Note widget IDs for buy/sell slots
   - Test `BUY_GE` command format
   - Document collect workflow

2. **Shops**
   - Find general store
   - Test `SHOP_BUY` command
   - Note shop widget IDs

3. **Smithing**
   - Locate F2P furnaces (get exact coords)
   - Test `SMELT_BRONZE` and alternatives
   - Document anvil interaction
   - Note smithing interface widgets

### Medium Priority (Occasional)

4. **Crafting** (no fragment yet)
   - Leather crafting workflow
   - Pottery workflow
   - Gem cutting

5. **Runecrafting** (no fragment yet)
   - Altar locations
   - Talisman/tiara usage

### Low Priority (Rare)

6. **Minigames** (no fragment yet)
7. **Achievement Diaries** (no fragment yet)

---

## Checklist: Adding New Fragment

- [ ] Identified knowledge gap (from logs or user feedback)
- [ ] Gathered info through gameplay or research
- [ ] Created `context_fragments/<domain>.md`
- [ ] Added keywords to `activity_classifier.py`
- [ ] Tested classification: `./venv/bin/python discord_bot/activity_classifier.py`
- [ ] Tested with harness: `./venv/bin/python discord_bot/test_harness.py "test"`
- [ ] Updated `context_fragments/README.md` table
- [ ] Restarted bot: `systemctl --user restart discord-bot`
- [ ] Verified live behavior

---

## Updating Existing Fragments

When new info is discovered:

1. **Read existing fragment** - Don't duplicate
2. **Add new section** or update existing
3. **Mark TODOs resolved** if applicable
4. **Test** - Ensure classification still works
5. **Update README.md** status if changed
