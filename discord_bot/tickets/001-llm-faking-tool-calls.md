# Ticket #001: LLM "Faking" Tool Calls

**Status:** Partially Mitigated
**Priority:** Critical
**Created:** 2026-01-21
**Component:** discord_bot / llm_client

---

## Summary

The Discord bot's LLM (qwen2.5:14b-multi via Ollama) frequently claims to execute commands without actually calling the tools. The user sees responses like "Started killing giant frogs" but nothing happens in-game because `send_command` was never invoked.

---

## Symptoms

1. **User sends:** `Kill loop giant frogs`
2. **Bot responds:** "Started killing 300 giant frogs with Tuna as food."
3. **Reality:** No `send_command` tool was called. Game state unchanged.
4. **User must retry 3-8 times** before the command actually executes.

---

## Data Analysis (2026-01-21 Logs)

| Task Type | Tool Call Success Rate | Notes |
|-----------|------------------------|-------|
| `conversation` | ~80% | Most reliable |
| `status_query` | ~90% | Works well |
| `loop_command` | **~5%** | Almost always fakes |
| `simple_command` | **~15%** | Fails, works after 3-6 retries |
| `multi_step` | ~40% | Mixed |

### Failure Examples

```
[03:19:47] Message: "Kill loop giant frog 300"
           Task Type: loop_command
           Tool calls: 0
           Response: "Started killing 300 giant frogs..."  ← FAKE

[03:20:45] Message: "KILL_LOOP Giant_frogs 300"
           Task Type: simple_command
           Tool calls: 0
           Response: "Started killing..."  ← FAKE (retry 1)

[03:20:51] Message: "KILL_LOOP Giant_frogs 300"
           Tool calls: 0
           Response: "Started killing..."  ← FAKE (retry 2)

[03:20:58] Message: "KILL_LOOP Giant_frogs 300"
           TOOL: send_command(...)  ← Finally worked on retry 3
```

### Success Pattern

When classified as `conversation` (minimal context augmentation), tools work:

```
[03:19:19] Message: "Grind giant frog"
           Task Type: conversation
           TOOL: send_command({"command": "KILL_LOOP Giant_frog Tuna 300"})  ← Works!
```

---

## Root Causes

### 1. Context Augmentation Confuses the Model

The `agent_brain.py` adds extra instructions for `loop_command` and `simple_command` types:

```
**Task Type: Loop/Continuous Command**
You CAN and SHOULD send commands...

**Available Commands:**
Combat:
  - KILL_LOOP <npc> <food> [count]...
```

This extra context appears to make the model think it's in a training/example scenario where it should *describe* the action rather than execute it.

**Evidence:** When the same request is classified as `conversation` (no extra context), tools are called reliably.

### 2. Conversation History Teaches Faking

The conversation history only stores text, not tool calls:

```python
history.append({"role": "user", "content": content})
history.append({"role": "assistant", "content": response})  # Just text!
```

The LLM sees:
```
User: "Switch to strength combat style"
Assistant: "Switched to strength combat style."
```

It learns: "When user asks X, respond with 'Done X'" - without knowing tools were involved.

### 3. State Pre-Fetch Creates False Sense of Completion

For non-conversation types, `agent_brain.py` pre-fetches game state:

```python
if task_type != TaskType.CONVERSATION:
    state = await self.tool_executor("get_game_state", {...})
```

The LLM sees state was already retrieved and may interpret this as "action taken."

### 4. Model Limitation

qwen2.5:14b-multi has inconsistent function calling behavior. The same prompt sometimes triggers tool calls, sometimes doesn't. This appears to be probabilistic - retrying eventually works.

---

## Attempted Fixes

### Fix 1: Direct Command Bypass ✅ EFFECTIVE

Bypass the LLM entirely for raw commands:

```python
def _is_direct_command(self, content: str) -> bool:
    direct_prefixes = ['KILL_LOOP', 'GOTO', 'BANK_', ...]
    return any(content.upper().startswith(p) for p in direct_prefixes)

if self._is_direct_command(content):
    result = await self._execute_tool("send_command", {"command": content})
    await message.channel.send(f"✅ `{content}`")
    return
```

**Result:** 100% reliable for explicit commands like `KILL_LOOP Giant_frog 300`.

### Fix 2: JSON Rescue ✅ PARTIAL

Parse JSON tool calls from response text:

```python
json_pattern = r'\{"name":\s*"(send_command|...)".*"arguments":\s*(\{[^}]+\})\}'
matches = re.findall(json_pattern, response)
for tool_name, args_str in matches:
    await self._execute_tool(tool_name, json.loads(args_str))
```

**Result:** Catches edge cases where LLM outputs JSON as text.

### Fix 3: Minimal Context ⚠️ PARTIAL

Removed extra instructions for loop_command/simple_command:

```python
# Before: Added task type labels, command lists, hints
# After: Just pass the message through
```

**Result:** Reduced faking but didn't eliminate it.

### Fix 4: Tool History ⚠️ DIAGNOSTIC

Include tool calls in conversation history:

```python
if self._current_tool_calls:
    assistant_content = f"[EXECUTED: {tools}] {response}"
else:
    assistant_content = f"[NO TOOLS CALLED] {response}"
```

**Result:** Makes faking visible in history. May help with fine-tuning.

### Fix 5: Faking Detection ⚠️ DIAGNOSTIC

Detect when LLM claims action without tools:

```python
if claims_action and not has_real_tool_call:
    response = "⚠️ I described an action but didn't execute it..."
```

**Result:** User knows when faking occurred. Doesn't prevent it.

### Fix 6: "THIS IS LIVE" Prompt ❌ INEFFECTIVE

Added to system prompt:
```
## ⚠️ THIS IS LIVE - NOT A SIMULATION ⚠️
You are controlling a REAL RuneLite client...
```

**Result:** No measurable improvement. Model ignores it.

---

## Current Status

**Mitigated but not solved.**

- Direct commands (`KILL_LOOP X`) work 100% via bypass
- Natural language commands still have ~30-50% failure rate
- User can work around by typing explicit commands

---

## Remaining Work

### Option A: Auto-Retry on Fake Detection

```python
if faking_detected and retry_count < 3:
    response = await self._brain.process_request(
        f"EXECUTE NOW: {content}",  # Stronger prompt
        history
    )
    retry_count += 1
```

### Option B: Switch to Gemini

Gemini has more reliable function calling. Change default provider:

```bash
--provider gemini
```

### Option C: Fine-Tune qwen2.5

Use collected training data with `fake_detected` labels:
- Positive examples: Tool was called
- Negative examples: Faking detected

### Option D: Simplify to Keyword Matching

For common actions, bypass LLM entirely:
- "kill frogs" → `KILL_LOOP Giant_frog none 100`
- "open bank" → `BANK_OPEN`
- "stop" → `STOP`

---

## Files Changed

| File | Changes |
|------|---------|
| `bot.py` | Direct bypass, JSON rescue, faking detection, tool history |
| `agent_brain.py` | Removed context augmentation, disabled state pre-fetch |
| `CONTEXT.md` | Added "THIS IS LIVE", removed response patterns |
| `CLAUDE.md` | Documented issues and fixes |
| `FAKING_FIX_PLAN.md` | Implementation plan |

---

## Reproduction Steps

1. Start bot: `systemctl --user start discord-bot`
2. Send DM: "Kill giant frogs"
3. Check logs: `tail -20 logs/conversations/conversations_$(date +%Y-%m-%d).log`
4. Observe: Response claims action, but `Tool calls: 0`

---

## Related

- `logs/conversations/conversations_2026-01-21.log` - Full failure log
- `FAKING_FIX_PLAN.md` - Implementation details
- `CLAUDE.md` - Developer guidelines
