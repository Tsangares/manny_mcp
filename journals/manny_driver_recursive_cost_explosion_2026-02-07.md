# Manny Driver Recursive Context Explosion - Lessons Learned
**Date:** 2026-02-07

## The Problem

A 2-hour autonomous chicken farming session cost $26 in Gemini API billing. Each API request sent ~237K input tokens with only ~7 output tokens. This happened every ~30 seconds for hours during monitoring mode.

## Root Cause

Recursive directive nesting in `agent.py`. When monitoring detects an issue, it calls:

```python
await self.run_directive(
    f"Monitoring detected an issue: {trigger}. "
    f"Original goal: {self._current_directive}. "
    "Handle this with 1-2 commands, then STOP."
)
```

But `run_directive()` sets `self._current_directive = directive`. So after the first intervention, `_current_directive` contains the full intervention text. The next intervention nests it again:

```
Iteration 1: "Original goal: Kill chickens"
Iteration 2: "Original goal: Monitoring detected... Original goal: Kill chickens... Handle with 1-2 commands"
Iteration 3: "Original goal: Monitoring detected... Original goal: Monitoring detected... Original goal: Kill chickens..."
```

After 20+ iterations, each message was 82K+ chars of recursive text. Combined with conversation history accumulation and 33 tool schemas per request, this created 237K token requests.

## Key Lessons

### 1. Self-Referential State Creates Exponential Growth

**What happened:** A field (`_current_directive`) was read AND written during the same operation, creating a feedback loop.
**Why:** `run_directive()` always overwrites `_current_directive`, but monitoring reads it to provide context in the next `run_directive()` call.
**Solution:**
```python
# BAD - reads _current_directive, then run_directive overwrites it with the full text
await self.run_directive(
    f"Issue: {trigger}. Original goal: {self._current_directive}. Fix it."
)

# GOOD - preserve original goal separately, don't embed it in new directives
self._original_goal = self._current_directive  # saved once at monitoring start

await self.run_directive(
    f"Monitoring detected: {trigger}. Handle with 1-2 commands, then STOP.",
    monitoring_intervention=True,  # prevents _current_directive overwrite
)
```

### 2. Deterministic Responses Don't Need an LLM

**What happened:** Every monitoring trigger (inventory full, XP idle) called the LLM to decide what to do, but the actions were always the same: BURY_ALL, DROP_ALL, restart KILL_LOOP.
**Why:** The system prompt literally told the LLM exactly what commands to run. It was a $0.02 API call to execute a hardcoded decision.
**Solution:**
```python
# BAD - pay for LLM to read a long prompt and output "send_command('BURY_ALL')"
return "Inventory full. Use BURY_ALL to clear bones."

# GOOD - just do it directly in Python
return ("inventory_full", ["BURY_ALL", "DROP_ALL Egg", "DROP_ALL Raw chicken"])
# Agent executes commands via send_command directly, zero LLM calls
```

This eliminated ~95% of LLM calls during monitoring.

### 3. Conversation History Accumulates Across Interventions

**What happened:** Each monitoring intervention inherited 40 messages from previous interventions. After 10 interventions, the context was packed with stale tool results.
**Why:** `ConversationManager` was shared across all `run_directive()` calls, including monitoring interventions.
**Solution:** Call `self.conversation.clear()` before each LLM-based monitoring intervention. Each intervention is independent - it doesn't need history from the last one.

### 4. Tool Schemas Are Expensive Context

**What happened:** All 33 gameplay tool schemas were sent with every monitoring request, even though monitoring only needs 6 (send_command, send_and_await, get_game_state, get_logs, query_nearby, get_command_response).
**Why:** No distinction between "full" and "monitoring" tool sets.
**Solution:** Build a `_monitoring_tool_schemas` subset at init time, pass it during monitoring interventions. Saves ~1K tokens per call.

### 5. Gemini System Prompt Was Not Cacheable

**What happened:** The system prompt (~2K tokens) was prepended to the first user message content instead of using Gemini's `system_instruction` parameter.
**Why:** Initial implementation copied a pattern that works for simple chat but misses Gemini's caching optimization.
**Solution:** Pass `system_instruction=system` in `GenerateContentConfig`. Gemini can cache this across requests.

### 6. Token Usage Was Invisible

**What happened:** Gemini and Ollama clients returned `input_tokens=0, output_tokens=0` in every response, making it impossible to detect the runaway cost.
**Why:** Neither client read the provider's usage metadata from responses.
**Solution:**
- Gemini: Read `response.usage_metadata.prompt_token_count` / `candidates_token_count`
- Ollama: Read `data["prompt_eval_count"]` / `data["eval_count"]`

## Anti-Patterns

1. **Don't embed mutable state in directive text** - If the text references a field that gets overwritten by the same function, you get recursive growth
2. **Don't call an LLM for decisions you've already hardcoded in the prompt** - If the system prompt says "do X when Y happens", just do X in Python
3. **Don't share conversation history across independent interventions** - Each monitoring fix is atomic, clear the history
4. **Don't send all tools when you only need a subset** - Context is expensive, especially for small local models
5. **Don't ignore token usage metadata** - Without visibility, runaway costs are invisible until the bill arrives

## Impact Summary

| Fix | What it does | Context savings |
|-----|-------------|-----------------|
| Stop recursive nesting | Messages stay ~500 chars instead of 82K+ | ~160x |
| Python-side handling | Zero LLM calls for inventory/XP triggers | ~95% fewer calls |
| Clear conversation | Fresh context per intervention | ~5x per call |
| system_instruction | Cacheable system prompt | ~2K tokens/call |
| Monitoring tool subset | 6 tools instead of 33 | ~1K tokens/call |
| Token tracking | Visibility into usage | Enables budget enforcement |
| Cost budget | Auto-stop at $1.00 | Safety net |

Combined: $26/2hr session -> ~$0.02-0.05 (~500x reduction).

For local models (Ollama): context explosion would have overflowed an 8K window in minutes. Conversation window auto-shrinks to 10 messages for Ollama.

## Files Modified

| File | Change |
|------|--------|
| `manny_driver/agent.py` | `monitoring_intervention` param, Python-side trigger handling, conversation clearing, monitoring tool subset, cost budget (skipped for Ollama) |
| `manny_driver/llm_client.py` | Gemini `system_instruction`, Gemini + Ollama token tracking |
| `manny_driver/config.py` | `max_session_cost_usd` field, auto-shrink window for Ollama |
