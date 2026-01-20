# Fine-Tuning Plan: Specialized LLM Controller for OSRS Automation

**Created**: 2026-01-21
**Status**: Planning / Data Collection Phase
**Goal**: Train a smaller model (7B) to reliably control the OSRS automation system via tool calling

---

## Executive Summary

The current setup uses Ollama (qwen2.5:14b-multi) or Gemini to control an OSRS automation system via Discord. The LLM interprets natural language commands and calls MCP tools to execute game actions. However, the model frequently **describes** tool calls as JSON text instead of **executing** them, and struggles with complex multi-step tasks.

**Solution**: Fine-tune a smaller, specialized model that:
1. Reliably executes tools instead of describing them
2. Understands the observe → decide → act → verify pattern
3. Generalizes across task types (combat, skilling, questing)
4. Can handle multi-step task decomposition

---

## Current Architecture

```
┌─────────────────┐     Discord DM      ┌──────────────────┐
│   User (Mobile) │ ◄─────────────────► │   Discord Bot    │
└─────────────────┘                     │   (bot.py)       │
                                        └────────┬─────────┘
                                                 │
                                        ┌────────▼─────────┐
                                        │   LLM Client     │
                                        │ (Ollama/Gemini)  │
                                        └────────┬─────────┘
                                                 │ Tool Calls
                                        ┌────────▼─────────┐
                                        │   MCP Tools      │
                                        │ (send_command,   │
                                        │  get_game_state, │
                                        │  etc.)           │
                                        └────────┬─────────┘
                                                 │
                                        ┌────────▼─────────┐
                                        │  RuneLite Plugin │
                                        │  (manny)         │
                                        └──────────────────┘
```

**Key Files**:
- `discord_bot/bot.py` - Discord bot, routes messages to LLM
- `discord_bot/llm_client.py` - LLM abstraction (Ollama, Gemini, etc.)
- `discord_bot/agent_brain.py` - Task classification and context enrichment
- `discord_bot/CONTEXT.md` - System prompt / instructions for LLM
- `discord_bot/training_logger.py` - Training data collection (NEW)

---

## Problem Statement

### Current Issues

1. **Tool Description vs Execution**: Model outputs JSON like `{"name": "send_command", ...}` as text instead of actually calling the tool function.

2. **Inconsistent Tool Calling**: Works sometimes, fails unpredictably. Same request may execute correctly or just describe the action.

3. **Limited Multi-Step Reasoning**: Struggles with "go to X, then do Y" - either does partial execution or just explains what should happen.

4. **Context Window Waste**: Large models (14B+) are overkill for this structured task. A well-tuned 7B should suffice.

### Evidence from Logs

```
# User: "Kill loop giant frog 300"
# Expected: Tool call to send_command("KILL_LOOP Giant_frog none 300")
# Actual response (BAD):
"To kill 300 Giant Frogs with no food needed:
```json
{"name": "send_command", "arguments": {"command": "KILL_LOOP Giant_frog none 300"}}
```"
```

---

## Data Collection Strategy

### Data Sources

| Source | Format | Value | Status |
|--------|--------|-------|--------|
| Discord Bot | JSONL | Direct user intent → tool calls | ✅ Collecting |
| MCP Commands | YAML | Raw command sequences | ✅ Exists at /tmp/manny_sessions/ |
| Claude Code Sessions | JSONL | Complex multi-step reasoning | ⏳ Need parser |

### Training Data Format

Each example captures the full interaction loop:

```json
{
  "id": "request_id",
  "timestamp": "2026-01-21T00:00:00",
  "source": "discord",

  "input": {
    "user_message": "Kill 300 giant frogs",
    "task_type": "loop_command",
    "game_state": {
      "location": [3200, 3170, 0],
      "health": [35, 35],
      "inventory_used": 4
    },
    "history_summary": "none"
  },

  "expected_actions": [
    {"tool": "send_command", "args": {"command": "KILL_LOOP Giant_frog none 300"}}
  ],

  "execution_trace": {
    "tool_calls": [
      {"tool": "send_command", "args": {...}, "result": {...}, "latency_ms": 50}
    ],
    "response": "Started killing 300 giant frogs.",
    "state_after": {...}
  },

  "quality": {
    "success": true,
    "had_errors": false,
    "described_instead_of_executed": false,
    "human_rating": null
  }
}
```

### Data Locations

- **Discord training data**: `~/.manny/training_data/training_YYYY-MM-DD.jsonl`
- **Raw commands**: `/tmp/manny_sessions/commands_YYYY-MM-DD.yaml`
- **Claude Code sessions**: `~/.claude/projects/-home-wil-manny-mcp/*.jsonl`
- **Conversation logs**: `~/manny-mcp/logs/conversations/conversations_YYYY-MM-DD.jsonl`

---

## What to Train On

### The Core Pattern (CRITICAL)

Train the model to follow this control loop:

```
1. PARSE: Understand user intent
2. OBSERVE: Check relevant game state
3. DECIDE: Choose appropriate action(s)
4. EXECUTE: Actually call the tool (NOT describe it)
5. VERIFY: Confirm action succeeded (optional)
6. RESPOND: Brief confirmation to user
```

### Example Training Categories

#### 1. Simple Commands (40% of data)
```yaml
input: "stop"
actions: [send_command(STOP)]
response: "Stopped."

input: "restart the client"
actions: [restart_runelite()]
response: "Client restarted."
```

#### 2. Loop/Grinding Commands (30% of data)
```yaml
input: "kill frogs"
observe: [get_game_state(location)]  # Check if near frogs
actions: [send_command(KILL_LOOP Frog none)]
response: "Started killing frogs."

input: "fish at draynor"
actions: [send_command(FISH_DRAYNOR_LOOP)]
response: "Started fishing at Draynor."
```

#### 3. Multi-Step Tasks (20% of data)
```yaml
input: "go to lumbridge swamp and kill giant frogs"
actions:
  - lookup_location(lumbridge_swamp)
  - send_command(GOTO 3197 3169 0)
  - send_command(KILL_LOOP Giant_frog none)
response: "Walking to swamp, then will start killing frogs."
```

#### 4. Status/Query (10% of data)
```yaml
input: "what are my levels?"
actions: [get_game_state(skills)]
response: "Attack: 39, Strength: 38, Defence: 20..."

input: "is it running?"
actions: [check_health()]
response: "Yes, client is running. Player at Lumbridge."
```

### Negative Examples (IMPORTANT)

Include examples of what NOT to do:

```yaml
bad_example:
  input: "kill frogs"
  bad_response: |
    To kill frogs, use this command:
    {"name": "send_command", "arguments": {"command": "KILL_LOOP Frog none"}}
  why_bad: "Described the tool call instead of executing it"

good_example:
  input: "kill frogs"
  actions: [send_command(KILL_LOOP Frog none)]
  response: "Started killing frogs."
```

---

## Fine-Tuning Approach

### Model Selection

| Model | Size | Pros | Cons |
|-------|------|------|------|
| Qwen2.5-7B | 7B | Good at tool calling, fast | May need more examples |
| Llama3.1-8B | 8B | Strong reasoning | Tool calling less native |
| Mistral-7B | 7B | Fast, efficient | Older architecture |

**Recommendation**: Start with Qwen2.5-7B since we're already using Qwen2.5-14B.

### Training Method

**QLoRA** (Quantized Low-Rank Adaptation):
- Keeps base model frozen (4-bit quantized)
- Only trains small adapter layers (~1-5% of parameters)
- Can run on single 24GB GPU (RTX 3090/4090)
- Training time: 2-4 hours for 2000 examples

### Training Format

Use ChatML format with explicit tool call tokens:

```
<|im_start|>system
You are an OSRS automation controller. Execute tools directly, never describe them.
<|im_end|>
<|im_start|>user
[State: loc=(3200,3170,0) hp=35/35 inv=4/28]
Kill 300 giant frogs
<|im_end|>
<|im_start|>assistant
<tool_call>send_command({"command": "KILL_LOOP Giant_frog none 300"})</tool_call>
Started killing 300 giant frogs.
<|im_end|>
```

### Tools for Training

- **Axolotl**: https://github.com/OpenAccess-AI-Collective/axolotl
- **LLaMA-Factory**: https://github.com/hiyouga/LLaMA-Factory
- **Unsloth**: https://github.com/unslothai/unsloth (2x faster training)

---

## Implementation Plan

### Phase 1: Data Collection (Current)
**Status**: ✅ In Progress

- [x] Create training_logger.py
- [x] Integrate with Discord bot
- [ ] Build Claude Code session parser
- [ ] Collect 500+ examples via Discord
- [ ] Annotate quality scores on collected data

**Estimated time**: 1-2 weeks of normal usage

### Phase 2: Data Processing
**Status**: ⏳ Not Started

- [ ] Export training data to ChatML format
- [ ] Filter by quality (exclude failures, description patterns)
- [ ] Balance dataset across task types
- [ ] Create train/validation split (90/10)
- [ ] Create held-out test set of novel tasks

### Phase 3: Fine-Tuning
**Status**: ⏳ Not Started

- [ ] Set up training environment (Axolotl or Unsloth)
- [ ] Configure QLoRA parameters
- [ ] Run initial training (small subset)
- [ ] Evaluate on validation set
- [ ] Iterate on hyperparameters
- [ ] Full training run

### Phase 4: Evaluation
**Status**: ⏳ Not Started

Evaluation metrics:
- **Tool Execution Rate**: % of requests that result in actual tool calls
- **Correct Tool Selection**: Did it choose the right tool?
- **Argument Accuracy**: Were the arguments correct?
- **Task Completion**: Did the user's intent get fulfilled?
- **Generalization**: Performance on unseen task types

### Phase 5: Deployment
**Status**: ⏳ Not Started

- [ ] Export fine-tuned model to GGUF format
- [ ] Deploy to Ollama
- [ ] Update discord_bot to use new model
- [ ] A/B test against base model
- [ ] Monitor and collect more training data

---

## Data Requirements

### Minimum Viable Dataset

| Category | Examples Needed | Priority |
|----------|-----------------|----------|
| Simple commands | 500 | High |
| Loop commands | 400 | High |
| Multi-step tasks | 300 | High |
| Status queries | 200 | Medium |
| Error recovery | 100 | Medium |
| Negative examples | 200 | High |
| **Total** | **1700** | |

### Quality Criteria

Only include examples where:
- Tool was actually executed (not described)
- User's intent was fulfilled
- No errors occurred
- Response was concise and appropriate

### Data Augmentation

Can generate synthetic examples for:
- Different NPC names with same pattern
- Different locations with same structure
- Paraphrased user requests

---

## Claude Code Session Parser

### Purpose

Extract training examples from complex Claude Code sessions that show:
- Multi-step task execution
- State-based decision making
- Error recovery
- Task transitions

### Implementation

```python
# Pseudocode for parser
def parse_claude_session(jsonl_path):
    examples = []

    for message in read_jsonl(jsonl_path):
        if message.type == "user":
            current_example = {
                "user_message": message.content,
                "tool_calls": []
            }

        elif message.type == "assistant":
            # Extract tool calls from content blocks
            for block in message.content:
                if block.type == "tool_use":
                    # Filter for MCP-related tools
                    if is_mcp_tool(block.name):
                        current_example["tool_calls"].append({
                            "tool": block.name,
                            "args": block.input
                        })

            # Extract text response
            current_example["response"] = extract_text(message.content)

            if current_example["tool_calls"]:
                examples.append(current_example)

    return examples
```

### Filtering

Only extract examples where:
- MCP tools were used (send_command, get_game_state, etc.)
- The task relates to game control (not code editing)
- The interaction was successful

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Overfitting to combat | Model only good at killing | Balance dataset, include diverse tasks |
| Catastrophic forgetting | Model loses general capabilities | Use LoRA, keep base frozen |
| Tool format mismatch | Model uses wrong format | Standardize on one format, many examples |
| Insufficient data | Model doesn't generalize | Augment with synthetic examples |
| Training instability | Loss doesn't converge | Lower learning rate, gradient clipping |

---

## Success Criteria

The fine-tuned model should:

1. **Execute tools ≥95% of the time** (vs ~60% currently)
2. **Select correct tool ≥90% of the time**
3. **Handle multi-step tasks** with proper sequencing
4. **Generalize** to tasks not in training data (e.g., train on combat, test on fishing)
5. **Run efficiently** on local hardware (should be faster than 14B model)

---

## Resources

### Documentation
- Qwen2.5 Fine-tuning: https://qwen.readthedocs.io/en/latest/training/SFT.html
- Axolotl Guide: https://github.com/OpenAccess-AI-Collective/axolotl#quickstart
- LoRA Paper: https://arxiv.org/abs/2106.09685

### Hardware Requirements
- **Minimum**: 16GB VRAM (RTX 4080, A4000)
- **Recommended**: 24GB VRAM (RTX 3090/4090, A5000)
- **Training time**: ~2-4 hours for 2000 examples

### Existing Code
- `discord_bot/training_logger.py` - Training data collection
- `discord_bot/llm_client.py` - LLM client with tool calling
- `discord_bot/CONTEXT.md` - Current system prompt (useful reference)

---

## Next Actions

1. **Continue using Discord bot** to collect training data organically
2. **Build Claude Code parser** to extract examples from existing sessions
3. **Review collected data** after ~100 examples to check quality
4. **Annotate data** with human ratings where possible
5. **Set up training environment** on machine with GPU

---

## Appendix: Example Training Data

### Raw Discord Training Example

```json
{
  "id": "2354176060",
  "source": "discord",
  "input": {
    "user_message": "The attack style might require an actual style relevant to the scimitar",
    "task_type": "loop_command",
    "game_state": {"location": [3191, 3179, 0], "health": [32, 35]}
  },
  "expected_actions": [
    {"tool": "send_command", "args": {"command": "ATTACK_STYLE Strength"}},
    {"tool": "send_command", "args": {"command": "KILL_LOOP Giant_frog none 1"}}
  ],
  "execution_trace": {
    "tool_calls": [
      {"tool": "get_game_state", "args": {"fields": ["location", "health", "inventory"]}},
      {"tool": "send_command", "args": {"command": "ATTACK_STYLE Strength"}},
      {"tool": "send_command", "args": {"command": "KILL_LOOP Giant_frog none 1"}},
      {"tool": "get_game_state", "args": {"fields": ["skills"]}}
    ],
    "response": "Your attack style has been switched to Strength..."
  },
  "quality": {
    "success": true,
    "had_errors": false,
    "described_instead_of_executed": false
  }
}
```

### Converted to ChatML

```
<|im_start|>system
You control an OSRS automation system. Execute tools directly - never output JSON as text.
<|im_end|>
<|im_start|>user
[State: loc=(3191,3179,0) hp=32/35]
The attack style might require an actual style relevant to the scimitar
<|im_end|>
<|im_start|>assistant
<tool_call>send_command({"command": "ATTACK_STYLE Strength"})</tool_call>
<tool_call>send_command({"command": "KILL_LOOP Giant_frog none 1"})</tool_call>
Switched to Strength style and started killing 1 giant frog.
<|im_end|>
```
