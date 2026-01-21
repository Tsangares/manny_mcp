# Discord Bot - Claude Code Guidelines

This file provides guidance for Claude Code when working on the Discord bot codebase.

## Overview

The Discord bot provides remote OSRS client control via natural language. Users send messages, an LLM interprets them, and MCP tools execute actions.

## Architecture

```
User (Discord DM)
       │
       ▼
   bot.py (message handler)
       │
       ├──► TaskClassifier (agent_brain.py)
       │    Classifies: status_query, simple_command, loop_command, multi_step, conversation
       │
       ├──► ContextEnricher (agent_brain.py)
       │    Pre-fetches game state, injects command references
       │
       ▼
   LLMClient (llm_client.py)
   ├─ Primary: Ollama (qwen2.5:14b-multi)
   └─ Fallback: Gemini (gemini-2.0-flash-lite)
       │
       ▼
   Tool Execution (_execute_tool in bot.py)
       │
       ▼
   MCP Tools → RuneLite Plugin
```

## Key Files

| File | Purpose |
|------|---------|
| `bot.py` | Main Discord bot, slash commands, tool execution |
| `llm_client.py` | LLM abstraction with tool calling support |
| `agent_brain.py` | Task classification, context enrichment |
| `CONTEXT.md` | System prompt for the LLM |
| `task_queue.py` | Conditional task execution (level triggers, etc.) |
| `conversation_logger.py` | Logs all interactions to `logs/conversations/` |
| `training_logger.py` | Collects fine-tuning data |

## Known Issues (Critical)

### Issue 1: LLM Outputs JSON Instead of Calling Tools

**Symptom:** The LLM outputs tool calls as JSON text in its response instead of actually invoking the function:

```
User: "Kill loop giant frog 300"
Response: To kill 300 Giant Frogs:
{"name": "send_command", "arguments": {"command": "KILL_LOOP Giant_frog none 300"}}
```

**Why this happens:** The qwen2.5:14b model sometimes "describes" the tool call instead of using the proper function calling mechanism.

**Logs evidence:** Jan 20 - lines 213-222, 257-268, 279-290, 301-312, 323-332

**Current mitigation:** CONTEXT.md has explicit warnings, but they're often ignored.

### Issue 2: LLM Claims Actions Without Executing Them ("Faking")

**Symptom:** The LLM says it performed an action, but logs show no corresponding tool call:

| User Message | LLM Response | Actual Tool Calls |
|--------------|--------------|-------------------|
| "Just try combat style Slash" | "Switched to Slash" | **None** |
| "Whatever. Grind Giant frog" | "Started grinding Giant frogs" | **None** |
| "Open inventory" | "Opened the inventory tab" | get_game_state only |
| "TAB_OPEN Inventory" | "Opened" | get_game_state only |
| "Restart the client" | "Client has been restarted" | **None** |
| "KILL_LOOP Giant_frog Tuna 300" | "Started killing 300 giant frogs" | **None** |

**Why this happens:**
1. ContextEnricher pre-fetches game state (line 197-201 in agent_brain.py) - LLM sees this as "having checked" and assumes action is done
2. Model confuses "knowing what to do" with "having done it"
3. No verification that tool calls actually occurred

**Logs evidence:** Jan 21 - lines 103-108, 127-135, 163-168, 177-179, 187-191, 219-222

### Issue 3: Empty Responses

**Symptom:** LLM returns empty string, causing Discord "Cannot send an empty message" error.

**Current mitigation:** bot.py line 304-306 catches empty responses and substitutes "Done."

### Issue 4: Context Enricher May Cause Confusion

The `ContextEnricher.enrich_for_task()` calls `get_game_state` BEFORE the LLM processes the request. This means:
1. A tool call appears in logs before the LLM even responds
2. LLM might interpret this as "action already taken"

**Location:** agent_brain.py lines 197-201

## Debugging Workflow

### Step 1: Check Conversation Logs

```bash
# Today's logs
cat logs/conversations/conversations_$(date +%Y-%m-%d).log

# Search for specific user/request
grep -A 20 "REQUEST 0104189592" logs/conversations/*.log
```

Log format:
```
============================================================
[2026-01-21T01:04:18.959288] REQUEST 0104189592
User: astron6695 (391354168675139594)
Account: aux
Task Type: multi_step
Message: The first one?
  TOOL: get_game_state({"fields": ["location", "health", "inventory"]}) -> {...}
  TOOL: send_command({"command": "..."}) -> {...}
Tool calls: 0
Response: ...
============================================================
```

**Key insight:** If "Tool calls: 0" but response claims action was taken, that's a "faking" bug.

### Step 2: Check LLM Provider

```bash
# Current provider (in service file)
grep "ExecStart" ~/.config/systemd/user/discord-bot.service
# Look for --provider flag

# Check Ollama status
curl http://10.66.66.10:11434/api/tags
```

### Step 3: Test with Different Provider

```bash
# Restart with Gemini
systemctl --user stop discord-bot
cd ~/manny-mcp && ./venv/bin/python run_discord.py --account aux --provider gemini
```

## Implemented Fixes (2026-01-21)

### Fix 1: Tool Calls in History

Bot now tracks actual tool calls and includes them in conversation history:
- `[EXECUTED: KILL_LOOP Giant_frog none]` - shows what was really done
- `[NO TOOLS CALLED]` - makes faking visible in history

This prevents the LLM from learning that "text responses = action taken".

Location: `bot.py` lines ~175, ~325

### Fix 2: "THIS IS LIVE" System Prompt

Added explicit emphasis in CONTEXT.md that this is a REAL system, not a simulation:
- "THIS IS LIVE - NOT A SIMULATION" header
- "The REAL GAME does not respond to your text. It ONLY responds to tool calls."
- Removed "Response Patterns" examples that encouraged pattern-matching

### Fix 3: Faking Detection

Bot now detects when LLM claims action but didn't call tools:
```python
if claims_action and not has_real_tool_call:
    response = "⚠️ I described an action but didn't actually execute it..."
```

Location: `bot.py` lines ~318-325

### Fix 4: Reduced History

History reduced from 20 to 12 messages (6 exchanges) to prevent pattern learning.

## Further Improvements

### Option A: Fine-Tune the Model

Long-term solution. Training data being collected in:
- `~/.manny/training_data/training_YYYY-MM-DD.jsonl`
- `logs/conversations/conversations_YYYY-MM-DD.jsonl`

### Option B: Switch to Claude

Claude has more reliable tool calling. Set `--provider claude` when starting bot.

### Option C: Verify and Retry

If faking detected, could auto-retry with stronger prompt. Currently just warns user.

## Testing Changes

### Manual Test Flow

1. Send a simple command via Discord DM: "KILL_LOOP Giant_frog none 1"
2. Check logs immediately:
   ```bash
   tail -50 logs/conversations/conversations_$(date +%Y-%m-%d).log
   ```
3. Verify:
   - `TOOL: send_command(...)` appears in log
   - Response acknowledges the action
   - Plugin logs show command received: `get_logs(grep="KILL_LOOP")`

### Automated Verification

The conversation_logger tracks all tool calls. You can analyze patterns:
```python
# Count faking incidents
import json
with open('logs/conversations/conversations_2026-01-21.jsonl') as f:
    for line in f:
        entry = json.loads(line)
        if entry.get('response'):
            claims_action = any(w in entry['response'].lower()
                              for w in ['started', 'switched', 'opened', 'restarted'])
            has_send_command = any('send_command' in str(tc)
                                  for tc in entry.get('tool_calls', []))
            if claims_action and not has_send_command:
                print(f"FAKE: {entry['message'][:50]} -> {entry['response'][:50]}")
```

## Common Patterns in Code

### Adding a New Tool

1. Add definition in `llm_client.py` TOOL_DEFINITIONS
2. Add handler in `bot.py` `_execute_tool()`
3. Update CONTEXT.md with usage instructions

### Modifying Task Classification

Edit patterns in `agent_brain.py`:
- `STATUS_PATTERNS` - queries that need game state
- `SIMPLE_COMMAND_PATTERNS` - single-shot commands
- `LOOP_PATTERNS` - continuous activities
- `MULTI_STEP_PATTERNS` - sequences of actions

### Changing LLM Provider

```python
# In run_discord.py or direct instantiation
bot = create_bot(llm_provider="gemini", account_id="aux")
```

Providers: `ollama` (default), `gemini`, `claude`, `openai`

## Service Management

```bash
# Restart bot
systemctl --user restart discord-bot

# View logs
journalctl --user -u discord-bot -f

# Check status
systemctl --user status discord-bot
```

## Logs Location

| Log Type | Location |
|----------|----------|
| Conversation logs (human) | `logs/conversations/conversations_YYYY-MM-DD.log` |
| Conversation logs (JSON) | `logs/conversations/conversations_YYYY-MM-DD.jsonl` |
| Training data | `~/.manny/training_data/training_YYYY-MM-DD.jsonl` |
| Service logs | `journalctl --user -u discord-bot` |

## What NOT to Do

1. **Don't trust LLM claims** - Always verify tool calls in logs
2. **Don't add more JSON examples to CONTEXT.md** - The model imitates them as text
3. **Don't use pkill broadly** - Use `stop_runelite(account_id=...)` to stop specific clients
4. **Don't switch to blocked accounts** - `main` is protected (see BLOCKED_ACCOUNTS in bot.py)
