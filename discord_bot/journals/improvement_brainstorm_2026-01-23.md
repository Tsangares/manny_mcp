# LLM Interaction Improvements Brainstorm

**Date:** 2026-01-23
**Model:** qwen2.5:14b
**Based on:** Comprehensive test suite results

## Identified Issues

### 1. Implicit Prerequisite Blindness
**Problem:** Model doesn't check prerequisites unless explicitly mentioned.
- "Cut trees" → CHOP_TREE (no axe check)
- "Fish at Draynor" → FISH (no net check)
- But "Cook fish" → checks inventory (explicit in request)

**Root Cause:** Model only reasons about what's in the message, not what the action requires.

### 2. Emergency Handling Inconsistency
**Problem:** Low health (5 HP) doesn't reliably trigger defensive actions.
- "I'm dying!" → Moved to safety (partial)
- "Keep fighting" → Continued at 5 HP (dangerous!)

**Root Cause:** No hard-coded safety checks; relies entirely on LLM judgment.

### 3. Complex Task Simplification
**Problem:** Multi-step processes get shortcuts that may not work.
- "Get flour" → Tried to buy from store (wrong)
- Should be: Pick wheat → Mill → Use pot on bin

**Root Cause:** Model takes path of least resistance without game knowledge.

---

## Proposed Improvements

### Improvement 1: Prerequisite-Aware Observation
**Concept:** Enhance get_game_state to return prerequisite hints based on likely actions.

```python
# In mock tool executor / real MCP tool
async def _mock_get_game_state(self, args: Dict) -> Dict:
    state = {...}

    # Add prerequisite hints based on inventory
    hints = []
    items = state["inventory"]["items"]

    if not any("axe" in i.lower() for i in items):
        hints.append("No axe - cannot chop trees")
    if not any("net" in i.lower() for i in items):
        hints.append("No fishing net - cannot net fish")
    if not any("tinderbox" in i.lower() for i in items):
        hints.append("No tinderbox - cannot light fires")

    state["prerequisite_hints"] = hints
    return {"state": state}
```

**Pros:** Minimal change, model sees hints in observation
**Cons:** Adds tokens to every observation

### Improvement 2: Health Safety Gate
**Concept:** Add a safety check in the agentic loop before combat actions.

```python
# In agentic_loop.py, before executing action
if decision.tool_name == "send_command":
    command = decision.tool_args.get("command", "")
    if is_combat_command(command):
        # Force a health check
        health_state = await self.tool_executor("get_game_state", {"fields": ["health"]})
        current_hp = health_state["state"]["health"]["current"]
        max_hp = health_state["state"]["health"]["max"]

        if current_hp / max_hp < 0.2:  # Below 20%
            # Inject safety warning
            messages.append({
                "role": "user",
                "content": f"⚠️ SAFETY: Health is critical ({current_hp}/{max_hp}). Consider stopping or eating first."
            })
            continue  # Re-evaluate decision
```

**Pros:** Hard safety floor regardless of LLM judgment
**Cons:** Extra tool call, may interrupt desired behavior

### Improvement 3: Task-Specific Skill Contexts
**Concept:** Add a queryable tool that returns task-specific knowledge.

```python
# New tool: get_task_guide
TASK_GUIDES = {
    "woodcutting": {
        "prerequisites": ["Axe (any type) in inventory or equipped"],
        "commands": ["CHOP_TREE", "CHOP_TREE_LOOP <tree_type>"],
        "locations": {"regular_trees": "Lumbridge", "oaks": "Draynor"},
    },
    "fishing_net": {
        "prerequisites": ["Small fishing net in inventory"],
        "commands": ["FISH", "FISH_DRAYNOR_LOOP"],
        "locations": {"shrimp": "Draynor, Lumbridge Swamp"},
    },
    "flour_making": {
        "prerequisites": ["Pot in inventory"],
        "steps": [
            "1. Pick wheat from field (INTERACT_OBJECT Wheat Pick)",
            "2. Go to windmill, climb up",
            "3. Use grain on hopper (USE_ITEM_ON_OBJECT Grain Hopper)",
            "4. Operate hopper controls",
            "5. Climb down, use pot on flour bin"
        ],
    }
}
```

**Pros:** LLM can query for knowledge it lacks
**Cons:** LLM must know when to query; adds complexity

### Improvement 4: Enhanced System Prompt
**Concept:** Add explicit prerequisite checking instructions.

```markdown
## Before Acting - Prerequisite Check

When the user requests an action, ALWAYS check prerequisites:

| Action | Check For |
|--------|-----------|
| CHOP_TREE | Axe in inventory |
| FISH / FISH_LOOP | Net or rod in inventory |
| COOK_ALL | Raw food in inventory |
| LIGHT_FIRE | Tinderbox + logs in inventory |

If prerequisite missing:
1. Inform the user what's needed
2. Do NOT proceed with the action
3. Optionally suggest how to obtain the item
```

**Pros:** Simple, no code changes
**Cons:** Increases prompt size, model may still ignore

### Improvement 5: Two-Phase Decision Making
**Concept:** Split decisions into "analyze" and "execute" phases.

```python
# Phase 1: Analyze request
analysis_prompt = """
Given this request: "{message}"
And this game state: {state}

Answer these questions:
1. What action does the user want?
2. What prerequisites are needed?
3. Are all prerequisites met? (Yes/No)
4. If No, what's missing?

Respond as JSON.
"""

# Phase 2: Execute or inform
if analysis["prerequisites_met"]:
    # Proceed with action
else:
    # Inform user of missing prerequisites
```

**Pros:** Forces explicit prerequisite reasoning
**Cons:** Doubles LLM calls, slower

### Improvement 6: Observation Field Expansion
**Concept:** Always observe more fields by default to catch issues.

Current: `get_game_state(fields=["location", "health"])`
Proposed: `get_game_state(fields=["location", "health", "inventory", "equipment", "combat"])`

**Pros:** Model has more context to reason about
**Cons:** More tokens per observation

### Improvement 7: Action Verification Delays
**Concept:** Add delays and verification between actions.

```python
# After sending command, wait and verify
await self.tool_executor("send_command", {"command": "GOTO 3200 3200 0"})
await asyncio.sleep(2)  # Let game state update
verify_state = await self.tool_executor("get_game_state", {"fields": ["location"]})
# Check if we actually moved
```

**Pros:** Catches failed actions
**Cons:** Slower execution

---

## Recommended Priority

### High Impact, Low Effort
1. **Enhanced System Prompt** (Improvement 4) - Add prerequisite table
2. **Observation Field Expansion** (Improvement 6) - See more by default

### Medium Impact, Medium Effort
3. **Health Safety Gate** (Improvement 2) - Protect from dangerous situations
4. **Prerequisite-Aware Observation** (Improvement 1) - Hints in state

### High Impact, High Effort
5. **Task-Specific Skill Contexts** (Improvement 3) - Queryable knowledge
6. **Two-Phase Decision Making** (Improvement 5) - Explicit reasoning

---

## Quick Wins to Test Now

1. Add prerequisite checking examples to CONTEXT.md
2. Default to observing inventory in addition to location/health
3. Add health threshold warning in agentic loop

---

## Metrics to Track

- **Prerequisite check rate:** % of action requests that check prerequisites first
- **False start rate:** % of actions attempted without meeting prerequisites
- **Emergency response rate:** % of low-health situations where model takes defensive action
- **Multi-step completion:** % of complex tasks completed correctly vs simplified
