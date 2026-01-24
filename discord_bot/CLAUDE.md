# Discord Bot - Claude Code Guidelines

This file provides guidance for Claude Code when working on the Discord bot codebase.

## Overview

The Discord bot provides remote OSRS client control via natural language. Users send messages, an LLM interprets them, and MCP tools execute actions.

## Architecture (Agentic Mode - Default)

```
User (Discord DM)
       │
       ▼
   bot.py (message handler)
       │
       ├──► Direct Command Bypass (raw commands like KILL_LOOP)
       │    → Executes immediately, no LLM
       │
       ▼
   AgenticLoop (agentic_loop.py)
       │
       ├──► OBSERVE: get_game_state, check_health, lookup_location
       ├──► ACT: send_command, start_runelite, run_routine
       └──► VERIFY: get_game_state, get_logs
       │
       │   (Structured JSON output via Pydantic schema)
       │
       ▼
   LLMClient.chat_structured (llm_client.py)
   ├─ Primary: Ollama (hermes3:8b or qwen2.5:14b)
   └─ Fallback: Gemini (gemini-2.0-flash-lite)
       │
       ▼
   Tool Execution (_execute_tool in bot.py)
       │
       ▼
   MCP Tools → RuneLite Plugin
```

### Agentic Mode Toggle

Set `USE_AGENTIC_MODE=false` to use legacy architecture (TaskClassifier → IntentPlanner → AgentBrain).

## Architecture (Legacy Mode)

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
| `bot.py` | Main Discord bot, slash commands, tool execution, hint injection |
| `llm_client.py` | LLM abstraction with tool calling + structured output |
| `agentic_loop.py` | OBSERVE-ACT-VERIFY execution loop + smart context injection |
| `activity_classifier.py` | Fast keyword-based activity classification |
| `context_fragments/` | Domain-specific context files (skilling, combat, etc.) |
| `models.py` | Pydantic models for structured LLM output |
| `recovery.py` | JSON rescue, regex fallback, circuit breaker |
| `CONTEXT.md` | Slim reasoning framework (~400 tokens base) |
| `agent_brain.py` | Legacy task classification, context enrichment |
| `intent_planner.py` | Legacy intent extraction and plan generation |
| `task_queue.py` | Conditional task execution (level triggers, etc.) |
| `conversation_logger.py` | Logs all interactions to `logs/conversations/` |
| `training_logger.py` | Collects fine-tuning data |

### New Agentic Architecture Files

**`models.py`** - Pydantic models for structured output:
- `ActionDecision`: LLM decision (thought, action_type, tool_name, tool_args, response_text)
- `AgentResult`: Loop result (response, actions, iterations, observed, error)
- `TOOL_CATEGORIES`: Categorizes tools as observation/action/verification

**`agentic_loop.py`** - Core execution loop:
- `AgenticLoop`: Base OBSERVE-ACT-VERIFY loop
- `AgenticLoopWithRecovery`: Adds fallback and stuck detection
- Enforces observation before action
- Uses Pydantic schema for reliable JSON output
- **Smart context injection** based on activity classification

**`activity_classifier.py`** - Fast keyword-based activity classification:
- Classifies messages into domains: skilling, combat, navigation, banking, interaction
- <1ms classification time
- Triggers dynamic context fragment injection

**`context_fragments/`** - Domain-specific context (loaded on-demand):
- `skilling.md` - Fishing spots are NPCs, equipment requirements, FISH command
- `combat.md` - KILL_LOOP syntax, food management, combat styles
- `navigation.md` - GOTO command, coordinate system, location lookup
- `banking.md` - BANK_OPEN workflow, deposit vs drop distinction
- `interaction.md` - Entity types, NPC vs Object vs Item interaction

### Smart Context Architecture

The LLM receives **only relevant context** based on the user's request:

```
User: "Start fishing"
       │
       ├─ activity_classifier.py → "skilling"
       │
       ├─ Load context_fragments/skilling.md (~300 tokens)
       │
       └─ CONTEXT.md + skilling.md → LLM
           (Total: ~700 tokens vs 2000+ without optimization)
```

**Why this matters:**
1. Reduces token usage by ~60-70%
2. Gives LLM focused, relevant knowledge
3. Prevents confusion from unrelated context
4. Enables teaching game mechanics without exhaustive documentation

**Tool response hints:** Tools like `query_nearby` and `scan_tile_objects` include
`_hints` in their responses (e.g., "Fishing spots are NPCs. Use FISH or INTERACT_NPC")

**`recovery.py`** - Fallback strategies:
- `JSONRescue`: Parses and executes JSON tool calls from text
- `RegexFallback`: Extracts commands using regex patterns
- `CircuitBreaker`: Pauses on repeated failures
- `RecoveryManager`: Coordinates all recovery strategies

## Known Issues (Fixed by Agentic Mode)

The following issues are **FIXED** by the new agentic architecture (`USE_AGENTIC_MODE=true`):

### Issue 1: LLM Outputs JSON Instead of Calling Tools ✅ FIXED

**Was:** LLM outputs `{"name": "send_command", ...}` as text instead of calling tools.

**Fix:** Structured output via Pydantic schema constrains LLM to valid JSON. Recovery module (`JSONRescue`) catches and executes any JSON-as-text that still occurs.

### Issue 2: LLM Claims Actions Without Executing ("Faking") ✅ FIXED

**Was:** LLM says "Started killing frogs" without calling `send_command`.

**Fix:** Agentic loop enforces OBSERVE-ACT-VERIFY pattern:
- Must call observation tool before action
- Actions tracked and logged
- Response only generated after tool execution

### Issue 3: Misclassification ✅ FIXED

**Was:** "Scan for fishing net" triggers fishing because "fish" is in the message.

**Fix:** No regex classification in agentic mode. LLM decides what to do based on context, not keywords.

### Issue 4: Context Enricher Confusion ✅ FIXED

**Was:** Pre-fetched game state confuses LLM into thinking action already taken.

**Fix:** Agentic loop doesn't pre-fetch. LLM explicitly calls observation tools when needed.

## Legacy Issues (Still Present in Legacy Mode)

The following issues still occur when `USE_AGENTIC_MODE=false`:

### Issue 1: LLM Outputs JSON Instead of Calling Tools

**Symptom:** The LLM outputs tool calls as JSON text in its response instead of actually invoking the function.

**Mitigation:** JSON rescue in bot.py parses and executes the JSON.

### Issue 2: LLM Claims Actions Without Executing Them ("Faking")

**Symptom:** The LLM says it performed an action, but logs show no corresponding tool call.

**Mitigation:** Faking detection in bot.py warns user and attempts auto-execution.

### Issue 3: Empty Responses

**Symptom:** LLM returns empty string, causing Discord error.

**Mitigation:** bot.py catches empty responses and substitutes "Done."

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

### Fix 1: Direct Command Bypass (HIGHEST IMPACT)

When user types a raw command like `KILL_LOOP Giant_frog 300`, it bypasses the LLM entirely and executes directly.

```python
if self._is_direct_command(content):
    result = await self._execute_tool("send_command", {"command": content})
    await message.channel.send(f"✅ `{content}`")
    return
```

**Detected commands:** KILL_LOOP, GOTO, BANK_*, FISH*, INTERACT_*, TAB_OPEN, SWITCH_COMBAT_STYLE, etc.

Location: `bot.py` `_is_direct_command()` and `handle_natural_language()`

### Fix 2: JSON Rescue

When the LLM outputs `{"name": "send_command", ...}` as text instead of calling the tool, we parse and execute it.

Location: `bot.py` around line ~350

### Fix 3: Tool Calls in History

Bot tracks actual tool calls and includes them in conversation history:
- `[EXECUTED: KILL_LOOP Giant_frog none]` - shows what was really done
- `[NO TOOLS CALLED]` - makes faking visible in history

### Fix 4: "THIS IS LIVE" System Prompt

Added explicit emphasis in CONTEXT.md:
- "THIS IS LIVE - NOT A SIMULATION" header
- Removed "Response Patterns" examples that encouraged pattern-matching

### Fix 5: Faking Detection

Bot detects when LLM claims action but didn't call tools:
```
⚠️ I described an action but didn't actually execute it...
```

### Fix 6: Minimal Context Augmentation

Removed extra instructions for loop_command/simple_command that were confusing the model. Only STATUS_QUERY gets pre-fetched state now.

Location: `agent_brain.py`

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

### Test Harness (Fast Iteration)

The test harness lets you test LLM reasoning **without RuneLite running**. It mocks MCP tools and shows exactly what the LLM decides to do.

```bash
# Quick single test
./venv/bin/python discord_bot/test_harness.py "Kill 100 giant frogs"

# Interactive mode (REPL)
./venv/bin/python discord_bot/test_harness.py

# Verbose mode - see all tool calls as they happen
./venv/bin/python discord_bot/test_harness.py -v "Go fish at draynor"

# JSON output for scripting/analysis
./venv/bin/python discord_bot/test_harness.py --json "What's my health?" 2>/dev/null
```

**Using Pre-built Scenarios:**

Test different game situations without needing live data:

```bash
# List all available scenarios
./venv/bin/python discord_bot/test_harness.py --list-scenarios

# Test with specific scenario
./venv/bin/python discord_bot/test_harness.py --scenario low_health "I'm dying!"
./venv/bin/python discord_bot/test_harness.py --scenario full_inventory "Bank my stuff"
./venv/bin/python discord_bot/test_harness.py --scenario in_combat "Stop fighting"
```

| Scenario | Description |
|----------|-------------|
| `default` | At Lumbridge Castle, basic gear |
| `low_health` | 5 HP, in combat with frogs |
| `full_inventory` | 28/28 slots, at Draynor fishing |
| `at_bank` | Standing at Draynor bank |
| `in_combat` | Fighting giant frog |
| `has_fishing_net` | Has net, at Lumbridge |
| `no_fishing_net` | No net, at fishing spot |
| `high_level_combat` | Level 40+ combat stats |

**Recording Live State:**

Capture real game state for realistic testing (requires RuneLite running):

```bash
./venv/bin/python discord_bot/test_harness.py --record
# Saves to discord_bot/mock_states/state_YYYYMMDD_HHMMSS.json

# Then use it:
./venv/bin/python discord_bot/test_harness.py --state-file discord_bot/mock_states/state_20260123_120000.json "message"
```

**Interactive Mode Commands:**

When running without arguments, you get a REPL:

| Command | Action |
|---------|--------|
| `/quit` | Exit |
| `/state` | Show current mock state |
| `/reset` | Reset history and state |
| `/verbose` | Toggle verbose mode |
| `/history` | Show conversation history |
| `/help` | Show help |

**What the Output Shows:**

```
============================================================
USER: Kill 100 giant frogs
============================================================

💬 RESPONSE: Started killing 100 giant frogs at the Lumbridge swamp.

============================================================
TOOL CALL SUMMARY
============================================================

📊 OBSERVATIONS (1):
  • get_game_state({"fields": ["location", "health", "inventory"]})

⚡ ACTIONS (1):
  • send_command: KILL_LOOP Giant_frog none 100

✅ Observed before acting: YES    <-- Key metric! Should always be YES
📝 Total tool calls: 2
🎮 Commands sent: 1
```

**Key things to check:**
- "Observed before acting: YES" - confirms OBSERVE-ACT-VERIFY is working
- Actions list shows actual commands sent
- Response matches what was actually done (no faking)

### Manual Test Flow (Full Stack)

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
