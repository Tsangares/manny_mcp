# Context Fragments - Development Guide

## Overview

Context fragments provide domain-specific knowledge to the Discord bot LLM. Instead of loading 2000+ tokens of context for every request, we inject only the relevant ~300 token fragment based on activity classification.

## Current Fragments

| Fragment | Status | Keywords |
|----------|--------|----------|
| `skilling.md` | ✅ Complete | fish, mine, chop, train X |
| `combat.md` | ✅ Complete | kill, attack, fight, train combat |
| `navigation.md` | ✅ Complete | go to, walk to, teleport |
| `banking.md` | ✅ Complete | bank, deposit, withdraw |
| `interaction.md` | ✅ Complete | pick up, talk to, use item |
| `quests.md` | ✅ Complete | quest, dialogue, click continue |
| `inventory.md` | ✅ Complete | drop, equip, use item on |
| `magic.md` | ✅ Complete | cast, spell, teleport, telegrab |
| `cooking.md` | ✅ Complete | cook, raw, range, fire |
| `prayer.md` | ✅ Complete | pray, bury, bones, altar |
| `smithing.md` | ✅ Complete | smith, smelt, furnace, anvil |
| `grand_exchange.md` | ✅ Complete | ge, grand exchange, buy ge, sell ge |
| `shops.md` | ✅ Complete | shop, store, buy from |
| `camera.md` | ✅ Complete | camera, zoom, rotate, pitch |

## Development Workflow

### 1. Identify Need

A new fragment is needed when:
- LLM makes repeated mistakes on a topic
- New plugin commands are added
- User requests reveal knowledge gaps

### 2. Gather Information

Sources for fragment content:
- **COMMAND_REFERENCE.md** - All 90 commands with examples
- **routines/** - Working YAML examples
- **journals/** - Lessons from debugging sessions
- **Plugin code** - Handler implementations
- **OSRS Wiki** - Game mechanics (WebFetch)

### 3. Create Fragment

Template structure:
```markdown
## [Domain] Context

### Key Commands
\`\`\`
COMMAND1 <arg>    - Description
COMMAND2 <arg>    - Description
\`\`\`

### Important Concepts
- Key insight 1
- Key insight 2

### Common Patterns
\`\`\`python
# Example workflow
send_command("...")
\`\`\`

### Troubleshooting
| Problem | Solution |
|---------|----------|
| Issue 1 | Fix 1 |
```

### 4. Add to Classifier

Edit `activity_classifier.py`:

```python
ACTIVITY_DOMAINS = {
    "your_domain": [
        "keyword1", "keyword2",
        "multi word keyword",
    ],
    ...
}

MULTI_WORD_KEYWORDS = {
    "your_domain": ["multi word keyword"],
    ...
}
```

### 5. Test

```bash
# Test classification
./venv/bin/python discord_bot/activity_classifier.py

# Test with harness
./venv/bin/python discord_bot/test_harness.py "Your test message"
```

### 6. Update This README

Add fragment to the table above with status.

## Updating Fragments

When updating existing fragments:

1. **Add new info** - Don't remove working content
2. **Mark TODOs** - Use `**TODO:**` for gaps
3. **Test** - Verify with test harness
4. **Update journal** - Document what you learned

## Token Budget

| Component | Tokens |
|-----------|--------|
| Base CONTEXT.md | ~400 |
| Single fragment | ~300 |
| Schema instruction | ~200 |
| **Total per request** | **~900** |

Keep fragments under 400 tokens to stay within budget.

## Testing Tips

```bash
# Test specific scenario
./venv/bin/python discord_bot/test_harness.py --scenario at_fishing_spot "Start fishing"

# Verbose mode (see all tool calls)
./venv/bin/python discord_bot/test_harness.py -v "Kill frogs"

# JSON output for analysis
./venv/bin/python discord_bot/test_harness.py --json "Go to bank" 2>/dev/null | jq .
```

## Gathering Info In-Game

When playing to document new mechanics:

1. **Start session recording**
   ```python
   start_session_recording(goal="Document GE workflow")
   ```

2. **Add markers at key points**
   ```python
   add_session_marker(label="Opened GE interface")
   add_session_marker(label="PITFALL: Need to click slot first")
   ```

3. **Use observation tools liberally**
   ```python
   scan_widgets(filter_text="Buy")  # Find widget IDs
   query_nearby()  # Find NPCs/objects
   get_logs(grep="GE")  # See plugin behavior
   ```

4. **Stop and convert**
   ```python
   stop_session_recording()
   # Creates session file with all commands and state changes
   ```

5. **Create/update fragment** from session learnings
