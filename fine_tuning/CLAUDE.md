# Fine-Tuning Data Pipeline - Claude Instructions

This directory contains tools for extracting training data from Discord bot conversations.

## Quick Reference

```bash
# Parse a specific day's Discord logs (Stage 1 - automated)
python3 parsers/discord_parser.py --date 2026-01-25

# Parse all unparsed Discord logs
python3 parsers/discord_parser.py --all

# List what's been parsed
python3 parsers/discord_parser.py --status

# Enrich with Claude analysis (Stage 2 - you do this manually)
# See "Claude Enrichment" section below
```

## Directory Structure

```
fine_tuning/
├── CLAUDE.md              # This file
├── README.md              # Overview and full pipeline docs
├── parsers/
│   ├── discord_parser.py  # Stage 1: Automated extraction
│   ├── journal_parser.py  # Journal markdown parser
│   └── claude_session_parser.py
├── data/
│   ├── extracted/         # Raw extractions by source
│   │   ├── discord_2026-01-25.jsonl
│   │   ├── journal_training.jsonl
│   │   └── claude_sessions.jsonl
│   └── training/          # Combined training formats
│       ├── unified.jsonl
│       ├── chatml.txt
│       └── axolotl.jsonl
└── schemas/
    └── training_schema.py # Combines all sources
```

## Two-Stage Discord Parsing

### Stage 1: Automated Parser (`discord_parser.py`)

Extracts basic structure from Discord JSONL logs:
- User message → tool calls → response
- Task type from log metadata
- Command categorization (banking, fishing, navigation, etc.)
- Neutral quality score (0.7 default)

**Output:** `data/extracted/discord_YYYY-MM-DD.jsonl`

### Stage 2: Claude Enrichment (Manual)

When you see a Discord conversation worth enriching (failures, corrections, lessons), do this:

1. **Read the raw conversation:**
   ```
   Read logs/conversations/conversations_YYYY-MM-DD.jsonl
   ```

2. **Read existing extraction (if any):**
   ```
   Read fine_tuning/data/extracted/discord_YYYY-MM-DD.jsonl
   ```

3. **Enrich the examples by adding:**
   - `example_type: "negative"` for bad examples
   - `reasoning` field explaining what went wrong/right
   - `problem` and `root_cause` for failures
   - `quality_score` adjustment (0.0-1.0)
   - New `reasoning_chain` examples for lessons learned
   - New `code_correction` examples for BAD vs GOOD patterns

4. **Write enriched file back**

## What Makes a Good Training Example

### Direct Execution (quality_score: 1.0)
User intent clearly maps to correct tool call with successful outcome.

```json
{
  "example_type": "direct_execution",
  "user_message": "Bank Open",
  "tool_calls": [{"tool": "send_command", "arguments": {"command": "BANK_OPEN"}}],
  "response_text": "Opening the bank.",
  "quality_score": 1.0
}
```

### Negative Example (quality_score: 0.2-0.5)
Something went wrong - useful for teaching what NOT to do.

```json
{
  "example_type": "negative",
  "user_message": "Do the fishing routine",
  "tool_calls": [{"tool": "send_command", "arguments": {"command": "FISH_LOOP"}}],
  "reasoning": "BAD: Started routine without checking for required fishing net in inventory",
  "problem": "Routine failed - missing required equipment",
  "quality_score": 0.3
}
```

### Reasoning Chain (quality_score: 1.0)
Captures lessons learned - no user message, just the insight.

```json
{
  "example_type": "reasoning_chain",
  "user_message": "",
  "reasoning": "Before starting any loop routine, ALWAYS check inventory for required items.",
  "problem": "Loop routines fail silently when prerequisites missing",
  "tags": ["lesson", "prerequisites"]
}
```

### Code Correction (quality_score: 1.0)
BAD vs GOOD pattern comparison.

```json
{
  "example_type": "code_correction",
  "bad_code": "send_command(\"BANK_WITHDRAW 1 Fishing_net\")  # Wrong order",
  "good_code": "send_command(\"BANK_WITHDRAW Fishing_net 1\")  # Item first, quantity second"
}
```

## Common Patterns to Watch For

### Prerequisite Failures
- Starting loop routines without required items
- **Action:** Mark as negative, add reasoning about checking inventory

### Command Format Errors
- Wrong argument order (BANK_WITHDRAW quantity vs item)
- Missing underscores in multi-word names
- **Action:** Create code_correction example

### Incomplete Multi-Step Execution
- User asks for A + B, bot only does A
- **Action:** Mark as negative, note what was missed

### Self-Corrections
- Bot retries with different format
- **Action:** Note the correction, moderate quality score (0.7-0.8)

### Successful Atomic Commands
- Clean mapping from intent to tool call
- **Action:** Direct execution, quality 1.0

## Tags Reference

Use these tags for categorization:

| Tag | When to Use |
|-----|-------------|
| `fishing` | Fishing-related commands |
| `banking` | Bank open/close/withdraw/deposit |
| `navigation` | GOTO, movement commands |
| `combat` | Kill loops, combat actions |
| `prerequisites` | Examples about checking requirements |
| `command_format` | Argument order, naming conventions |
| `atomic_command` | Single direct command execution |
| `multi_step` | Complex requests needing multiple actions |
| `self_correction` | Bot fixed its own mistake |
| `typo_handling` | Correctly interpreted user typo |
| `lesson` | Reasoning chain with general lesson |
| `negative` | What NOT to do |

## Enrichment Workflow Example

Given this conversation:
```
User: "Do fishing routine" → FISH_LOOP sent → Failed (no net)
User: "Go to bank" → GOTO bank → Success
User: "Bank Open" → BANK_OPEN → Success
User: "Withdraw net" → BANK_WITHDRAW wrong format → Partial
User: "Close bank" → Retried + BANK_CLOSE → Success
User: "Start fishing" → FISH_LOOP with net → Success
```

Generate:
1. **Negative example** for starting without net (quality 0.3)
2. **Direct execution** for "Go to bank" (quality 1.0)
3. **Direct execution** for "Bank Open" (quality 1.0)
4. **Negative example** for wrong BANK_WITHDRAW format (quality 0.4)
5. **Direct execution** with self-correction for close (quality 0.8)
6. **Direct execution** for successful fishing start (quality 1.0)
7. **Reasoning chain** about prerequisite checking
8. **Code correction** for BANK_WITHDRAW format

## Re-Parsing

To re-parse a day's logs (e.g., after fixing parser bugs):
```bash
rm fine_tuning/data/extracted/discord_2026-01-25.jsonl
python3 parsers/discord_parser.py --date 2026-01-25
```

Enrichments are stored in the same file, so manual work will be lost on re-parse. Consider keeping a backup of heavily-enriched files.
