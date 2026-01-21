# Discord Bot Faking Fix Plan

**Problem:** The qwen2.5:14b model frequently "fakes" responses - claiming to execute commands without actually calling tools.

**Data:** ~85% failure rate for `loop_command`/`simple_command` task types. `conversation` type works ~80% of the time.

## Implemented Fixes (2026-01-21)

### ✅ Fix 1: `_extract_command()` Function
Added a smart command extraction function that finds plugin commands anywhere in messages:
- Handles "Send the command KILL_LOOP Giant_frog 300"
- Handles multi-line messages with command on separate line
- Normalizes whitespace and finds command by prefix

### ✅ Fix 2: Auto-Execute on Faking Detection
When faking is detected (LLM claims action but no send_command called):
1. Try to extract a command from the original user message
2. If found, auto-execute it and respond with `✅ <command>`
3. If not found, show warning asking for more specific command

### ✅ Fix 3: Better Task Classification
Added patterns to `agent_brain.py`:
- `r'\bswitch\s+(combat\s+)?style\b'` - catches "switch combat style"
- `r'\bcombat\s+style\b'` - catches "combat style to attack"
- `r'\bgrind\s+(on\s+)?\w+'` - catches "grind giant frogs"
- `r'\bkill\s+loop\b'` - catches "kill loop giant frog"

### ✅ Fix 4: History Pollution Prevention
Already in place - conversation history stores raw responses without `[EXECUTED:...]` prefixes.

## Immediate Fixes (Do Now)

### Fix 1: Bypass LLM for Direct Commands
When user types a raw command like `KILL_LOOP Giant_frog 300`, don't send it to the LLM at all - just execute it directly.

```python
# In bot.py handle_natural_language()
if self._is_direct_command(content):
    # Bypass LLM entirely
    result = await self._execute_tool("send_command", {"command": content})
    await message.channel.send(f"✅ Sent: `{content}`")
    return
```

**Commands to detect:** All-caps commands starting with known prefixes (KILL_LOOP, GOTO, BANK_, FISH_, INTERACT_, etc.)

### Fix 2: Auto-Retry on Fake Detection
When faking is detected, automatically retry up to 3 times before showing the error.

```python
# After faking detection
if claims_action and not has_real_tool_call:
    if retry_count < 3:
        # Retry with explicit instruction
        retry_message = f"YOU MUST CALL send_command. Execute: {content}"
        response = await self._brain.process_request(retry_message, history)
        retry_count += 1
        continue
```

### Fix 3: Parse JSON from Response Text
When the LLM outputs `{"name": "send_command", ...}` as text, parse and execute it.

```python
import re
json_pattern = r'\{"name":\s*"(\w+)",\s*"arguments":\s*(\{[^}]+\})\}'
matches = re.findall(json_pattern, response)
for tool_name, args_str in matches:
    args = json.loads(args_str)
    await self._execute_tool(tool_name, args)
```

### Fix 4: Force "conversation" Classification
Since `conversation` type works better, force all actionable messages to use it.

```python
# In TaskClassifier.classify()
# Remove loop_command and simple_command - just use conversation
# Only keep: STATUS_QUERY, MULTI_STEP, CONVERSATION
```

## Medium-Term Fixes

### Fix 5: Switch Primary Provider to Gemini
Gemini has more reliable function calling. Change default:

```bash
# In discord-bot.service
ExecStart=... --provider gemini
```

### Fix 6: Collect Training Data for Fine-Tuning
Use the faking detection to label bad examples:
- `fake_detected: true` → negative example
- Tool actually called → positive example

## Implementation Priority

1. **Fix 1: Bypass LLM** - Highest impact, simplest fix
2. **Fix 4: Force conversation** - Already partially done
3. **Fix 3: Parse JSON** - Catches edge cases
4. **Fix 2: Auto-retry** - Safety net
5. **Fix 5: Gemini** - If above don't work

## Testing

After each fix:
```
"Kill loop giant frogs" → Should see TOOL: send_command in logs
"KILL_LOOP Giant_frog 300" → Should bypass LLM and execute directly
"Open inventory" → Should call TAB_OPEN
```

## Success Metrics

- Reduce faking rate from ~85% to <10%
- Commands should work on first try, not after 3-6 retries
