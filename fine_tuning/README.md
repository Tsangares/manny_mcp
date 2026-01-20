# Fine-Tuning Data Pipeline

Extract and prepare training data for fine-tuning a specialized LLM controller for OSRS automation.

## Quick Start

```bash
# 1. Extract data from all sources
python3 parsers/journal_parser.py --training -o data/extracted/journal_training.jsonl
python3 parsers/claude_session_parser.py -o data/extracted/claude_sessions.jsonl

# 2. Combine and export to training formats
python3 schemas/training_schema.py --format all

# 3. View statistics
python3 schemas/training_schema.py --stats
```

## Data Sources

| Source | Location | Size | Examples |
|--------|----------|------|----------|
| **Journals** | `journals/*.md` | 268KB (39 files) | ~223 |
| **Claude Code Sessions** | `~/.claude/projects/-home-wil-manny-mcp/` | 7.9GB (~450 files) | ~162 |
| **Discord Logs** | `logs/conversations/` | Growing daily | ~16+ |

### Journals (Most Valuable)

Structured markdown documents containing reasoning patterns, anti-patterns, and lessons learned. Unique because they encode *why* decisions were made, not just what tools were called.

**Extracted patterns:**
- Problem → Root Cause → Fix reasoning chains
- BAD vs GOOD code examples
- Anti-patterns (what NOT to do)
- Command usage examples

### Claude Code Sessions

Complex multi-turn conversations with tool calls. We filter for MCP-related interactions and extract:
- User intent → Tool call sequences
- Observation → Action → Verification patterns
- Multi-step task decomposition

### Discord Logs

Direct user commands from mobile via Discord bot. Clean format with explicit tool calls and responses. Best for simple command training.

## Example Types

| Type | Count | Description |
|------|-------|-------------|
| `direct_execution` | 291 | User intent → tool call |
| `reasoning_chain` | 61 | Problem → analysis → solution |
| `negative` | 28 | What NOT to do |
| `code_correction` | 21 | Bad code → good code |

## Output Formats

### Unified JSONL (`data/training/unified.jsonl`)

Full structured format with all metadata:

```json
{
  "id": "journal_000042",
  "source": "journal",
  "example_type": "direct_execution",
  "user_message": "kill frogs",
  "tool_calls": [{"tool": "send_command", "arguments": {"command": "KILL_LOOP Frog"}}],
  "response_text": "Started killing frogs.",
  "task_type": "loop_command"
}
```

### ChatML (`data/training/chatml.txt`)

For Qwen/Mistral fine-tuning with special tokens:

```
<|im_start|>system
You control an OSRS automation system via MCP tools...
<|im_end|>
<|im_start|>user
kill frogs
<|im_end|>
<|im_start|>assistant
<tool_call>send_command({"command": "KILL_LOOP Frog"})</tool_call>
Started killing frogs.
<|im_end|>
```

### Axolotl (`data/training/axolotl.jsonl`)

For Axolotl/LLaMA-Factory fine-tuning:

```json
{
  "instruction": "kill frogs",
  "input": "",
  "output": "<tool_call>send_command({\"command\": \"KILL_LOOP Frog\"})</tool_call>\nStarted killing frogs."
}
```

## Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DATA EXTRACTION                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   journals/*.md              ~/.claude/projects/           logs/         │
│        │                           │                   conversations/    │
│        ▼                           ▼                         │          │
│   ┌────────────┐            ┌────────────────┐              ▼          │
│   │  Journal   │            │  Claude Session │      ┌──────────────┐  │
│   │  Parser    │            │  Parser         │      │ (Direct      │  │
│   └─────┬──────┘            └────────┬────────┘      │  JSONL)      │  │
│         │                            │               └──────┬───────┘  │
│         ▼                            ▼                      │          │
│   data/extracted/             data/extracted/               │          │
│   journal_training.jsonl      claude_sessions.jsonl         │          │
│         │                            │                      │          │
│         └──────────────┬─────────────┴──────────────────────┘          │
│                        │                                                │
│                        ▼                                                │
│              ┌─────────────────┐                                       │
│              │  Training Schema │                                       │
│              │  Combiner        │                                       │
│              └────────┬─────────┘                                       │
│                       │                                                 │
│          ┌────────────┼────────────┐                                   │
│          ▼            ▼            ▼                                   │
│   unified.jsonl  chatml.txt  axolotl.jsonl                             │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Usage Examples

### Parse only journals
```bash
python3 parsers/journal_parser.py --stats
python3 parsers/journal_parser.py --training -o data/extracted/journal_training.jsonl
```

### Parse Claude sessions (may take a while for 7.9GB)
```bash
# Quick sample
python3 parsers/claude_session_parser.py --stats --max-sessions 50

# Full export
python3 parsers/claude_session_parser.py -o data/extracted/claude_sessions.jsonl
```

### View combined statistics
```bash
python3 schemas/training_schema.py --stats
```

### Export specific format
```bash
python3 schemas/training_schema.py --format axolotl
python3 schemas/training_schema.py --format chatml
```

## Data Quality Considerations

### What Makes Good Training Data

1. **Direct execution** - Tool actually called, not described
2. **Successful outcome** - Action achieved user intent
3. **Concise response** - Brief confirmation, not explanation
4. **Appropriate tool** - Right tool for the task

### Filtering Applied

- Only MCP game control tools (not Read/Edit/Bash for code)
- Only turns with actual tool calls (not pure conversation)
- Deduplicated by content hash
- Quality score based on success indicators

## Next Steps

1. **Collect more Discord data** - Run bot and improve logging
2. **Add quality annotations** - Manual review of training examples
3. **Synthetic augmentation** - Generate variations of successful patterns
4. **Fine-tuning** - Use Axolotl/Unsloth with QLoRA

See `plans/FINE_TUNING_PLAN.md` for the complete roadmap.
