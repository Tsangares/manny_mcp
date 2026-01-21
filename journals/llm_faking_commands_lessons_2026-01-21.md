# LLM Faking Commands - Lessons Learned
**Date:** 2026-01-21

## The Problem

Discord bot users would send commands like "KILL_LOOP Giant_frog 300" and the LLM would respond "Started killing 300 giant frogs" without actually calling `send_command`. Users had to retry 3-5 times before commands executed. ~85% failure rate for `loop_command` and `simple_command` task types.

## Root Cause

Multiple compounding issues in the Discord bot → LLM → MCP tool chain:

1. **LLM learned to mimic success patterns** - Conversation history included `[EXECUTED: KILL_LOOP...]` prefixes, so the model learned to output these as TEXT instead of calling tools
2. **Direct command bypass too strict** - `_is_direct_command()` required exact uppercase match at start of message (`bot.py:281-282`)
3. **No fallback when faking detected** - Code detected faking but only warned user, didn't auto-retry
4. **Task classification put commands in wrong buckets** - "switch combat style" matched `LOOP_PATTERNS` due to containing "attack"

## Key Lessons

### 1. LLMs Mimic Patterns They See in History

**What happened:** Bot added `[EXECUTED: send_command]` to conversation history. Model started outputting this as literal text.

**Why:** The qwen2.5:14b model pattern-matches heavily. When it sees `[EXECUTED: X]` in assistant messages, it learns to produce similar strings without understanding they represent tool calls.

**Solution:**
```python
# BAD - pollutes history with mimicable patterns
assistant_content = f"[{'; '.join(tool_calls)}] {response}"
history.append({"role": "assistant", "content": assistant_content})

# GOOD - store raw response only
assistant_content = response
history.append({"role": "assistant", "content": assistant_content})
```

### 2. Extract Commands from Natural Language as Fallback

**What happened:** User typed "switch combat style to block" but `_extract_command()` only found literal `SWITCH_COMBAT_STYLE` uppercase commands.

**Why:** Original extraction used `content_upper.find(prefix)` which requires exact match. Natural language has spaces, lowercase, different word order.

**Solution:**
```python
# BAD - only finds literal commands
idx = content_upper.find('SWITCH_COMBAT_STYLE')  # Misses "switch style to block"

# GOOD - pattern match natural language first
style_match = re.search(r'switch\s+(?:combat\s+)?style\s+(?:to\s+)?(\w+)', content_lower)
if style_match:
    return f"SWITCH_COMBAT_STYLE {style_match.group(1).capitalize()}"
```

### 3. Auto-Execute on Faking Detection

**What happened:** Faking detection worked but only showed warning. User still had to retry manually.

**Why:** Original code assumed warning was sufficient. In practice, users don't want to retype commands.

**Solution:**
```python
# BAD - just warn
if claims_action and not has_send_command:
    response = "I described an action but didn't execute it..."

# GOOD - extract and auto-execute
if claims_action and not has_send_command:
    extracted_cmd = self._extract_command(content)
    if extracted_cmd:
        result = await self._execute_tool("send_command", {"command": extracted_cmd})
        response = f"✅ `{extracted_cmd}`"
```

### 4. Check for send_command Specifically, Not Just Any Tool Call

**What happened:** LLM called `get_game_state` (context fetch) but not `send_command`. Original detection counted any tool call as "real".

**Why:** `ContextEnricher` pre-fetches game state for some task types. This counted as a tool call but didn't execute the user's command.

**Solution:**
```python
# BAD - any tool call counts
has_real_tool_call = bool(self._current_tool_calls)

# GOOD - specifically check for send_command
has_send_command = any('send_command' in tc or 'EXECUTED' in tc for tc in self._current_tool_calls)
```

## Anti-Patterns

1. **Don't add execution markers to conversation history** - LLM mimics them as text output
2. **Don't rely solely on task classification** - Commands can be misclassified; always have extraction fallback
3. **Don't just warn on faking** - Auto-execute if command is extractable
4. **Don't use case-sensitive command matching** - Users type mixed case

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `tail -50 logs/conversations/conversations_$(date +%Y-%m-%d).log` | See recent requests/responses with tool calls |
| `grep "type.*tool_call" logs/conversations/*.jsonl \| tail -20` | Verify tool calls are being made |
| `journalctl --user -u discord-bot -f` | Live bot logs |
| Check for `TOOL: send_command(...)` in .log file | Confirm command actually dispatched |

## Interface Gaps Identified

- [x] Bot needs: Natural language → command extraction (`_extract_command()` added)
- [x] Bot needs: Auto-execute on faking detection (implemented)
- [ ] LLM needs: Fine-tuning on tool calling vs describing (training data being collected)
- [ ] Consider: Switch default provider to Gemini (more reliable tool calling)

## Files Modified

| File | Change |
|------|--------|
| `discord_bot/bot.py` | Added `_extract_command()` with NL patterns, updated faking detection to auto-execute |
| `discord_bot/agent_brain.py` | Added patterns for "switch combat style", "grind X", "kill loop X" |
| `discord_bot/FAKING_FIX_PLAN.md` | Documented implemented fixes |

## Metrics

- **Before:** ~85% faking rate, users retry 3-5x
- **After:** 0% faking in logs post-fix, commands execute on first try
