## Quest Context

### Dialogue Handling - The Core Challenge

Quests involve multi-step dialogue with NPCs. The LLM must:
1. Detect dialogue state
2. Choose correct option OR click continue
3. Repeat until dialogue ends

### Dialogue Tools

| Tool | Purpose |
|------|---------|
| `get_dialogue` | Check if dialogue is open, get options |
| `get_game_state(fields=["dialogue"])` | Get dialogue state with hint |

### Dialogue Commands

```
CLICK_CONTINUE              - Click "Click here to continue" button
CLICK_DIALOGUE <option>     - Click a numbered dialogue option (1-5)
INTERACT_NPC <name> Talk-to - Start conversation with NPC
```

### Dialogue Flow Pattern

```python
# Step 1: Start conversation
send_command("INTERACT_NPC Cook Talk-to")

# Step 2: Check dialogue state
state = get_game_state(fields=["dialogue"])
# Returns: {"dialogue": {"type": "options", "options": ["What's wrong?", "Goodbye"]}}

# Step 3: Handle based on type
if state["dialogue"]["type"] == "continue":
    send_command("CLICK_CONTINUE")
elif state["dialogue"]["type"] == "options":
    send_command("CLICK_DIALOGUE 1")  # Select first option
```

### Using dialogue.hint

The game state includes a `hint` field that tells you what to do:
- `"Click to continue"` → Use CLICK_CONTINUE
- `"Select an option"` → Use CLICK_DIALOGUE with option number
- `null` → No dialogue open

### Quest Item Management

```
BANK_WITHDRAW <item> <qty>  - Get quest items from bank
USE_ITEM_ON_NPC <item> <npc> - Give item to NPC
USE_ITEM_ON_OBJECT <item> <obj> - Use item on world object
```

### Common Quest Patterns

**Talk-through dialogue:**
```yaml
- action: INTERACT_NPC
  args: "Cook Talk-to"
- action: CLICK_CONTINUE
  delay_after_ms: 1000
- action: CLICK_DIALOGUE
  args: "1"  # "What's wrong?"
- action: CLICK_CONTINUE
  delay_after_ms: 1000
```

**Fetch quest items:**
```yaml
- action: GOTO
  args: "3253 3270 0"  # Cow pen
- action: USE_ITEM_ON_NPC
  args: "Bucket Dairy_cow"
  await_condition: "has_item:Bucket of milk"
```

### Quest Locations

Use `lookup_location` for common quest areas:
- `lumbridge` - Starting area, Cook's Assistant
- `draynor` - Vampire Slayer, fishing
- `varrock` - Romeo & Juliet, many quests

### Debugging Quests

```
get_dialogue()           - See current dialogue state
get_game_state(fields=["inventory"]) - Check quest items
get_logs(grep="DIALOGUE") - Debug dialogue issues
```
