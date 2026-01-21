# Fine-Tuning Data Extraction - Lessons Learned
**Date:** 2026-01-20

## The Problem

Needed to extract training data for fine-tuning an LLM controller from existing Claude Code sessions (7.9GB, ~450 files) and journals (38 files). The existing `CLAUDE_SESSION_PARSER.md` plan was too simple - it assumed a flat message structure and ignored journals entirely.

## Root Cause

Three structural issues made naive parsing fail:

1. **Claude Code sessions have nested content blocks** - Messages contain arrays of `{type: "tool_use"}`, `{type: "text"}`, `{type: "thinking"}` blocks, not simple strings.

2. **Most sessions are "mixed"** - Same session contains both MCP tool calls (game control) and Read/Edit/Bash (code editing). Only ~30% of turns have MCP-relevant content.

3. **Journals encode reasoning, not just actions** - Raw tool logs show *what* happened; journals show *why* decisions were made. This reasoning is the differentiator for training.

## Key Lessons

### 1. Claude Code Session Format Is Complex

**What happened:** Initial parsing attempts returned empty results.
**Why:** The JSONL format nests tool calls inside content block arrays.

**Solution:**
```python
# BAD - assumes flat structure
tool_name = message.get("tool_name")  # Returns None

# GOOD - navigate nested blocks
content = message.get("message", {}).get("content", [])
for block in content:
    if block.get("type") == "tool_use":
        tool_name = block.get("name")  # "mcp__runelite-debug__send_command"
```

### 2. Filter for MCP Tools, Not All Tools

**What happened:** First pass extracted thousands of Read/Edit/Bash calls - useless for game control training.
**Why:** Sessions mix code editing with game control.

**Solution:**
```python
# Define game control tools explicitly
MCP_GAME_CONTROL_TOOLS = {
    "send_command", "send_and_await", "get_game_state",
    "click_text", "query_nearby", "start_runelite", ...
}

# Ignore file operations
IGNORE_TOOLS = {"Read", "Write", "Edit", "Bash", "Glob", "Grep"}
```

### 3. Journals Are Structured and Parseable

**What happened:** Expected free-form prose; found consistent markdown structure.
**Why:** `TEMPLATE.md` enforces patterns like `## The Problem`, `### 1. Lesson Title`, `**What happened:**`.

**Solution:**
```python
# Extract structured sections with regex
PROBLEM_HEADERS = [r"##\s*The Problem", r"##\s*The Disaster"]
LESSON_PATTERN = r"###\s*\d+\.\s*(.+?)\n(.*?)(?=###\s*\d+\.|\n##)"

# Extract BAD/GOOD code annotations
if re.search(r"#\s*(?:BAD|WRONG)", code):
    annotation = "bad"
elif re.search(r"#\s*(?:GOOD|CORRECT)", code):
    annotation = "good"
```

### 4. Three Types of Training Examples

**What happened:** Tried to force everything into "user → tool call" format.
**Why:** Different sources provide different training signals.

**Solution:** Define distinct example types:

| Type | Source | Training Value |
|------|--------|----------------|
| `direct_execution` | Discord, sessions | Intent → action mapping |
| `reasoning_chain` | Journals | Problem → analysis → solution |
| `negative` | Journal anti-patterns | What NOT to do |
| `code_correction` | Journal BAD/GOOD blocks | Fix common mistakes |

## Anti-Patterns

1. **Don't parse all 7.9GB at once** - Use `--max-sessions` for testing, full export takes minutes
2. **Don't ignore assistant "thinking" blocks** - They contain reasoning that could be valuable for chain-of-thought training
3. **Don't treat all tool calls equally** - Observations (get_game_state) vs actions (send_command) serve different roles
4. **Don't skip journals for "just tool logs"** - Journals are 223 examples of *reasoning*, not just actions

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `python3 parsers/journal_parser.py --stats` | See extracted pattern counts |
| `python3 parsers/claude_session_parser.py --stats --max-sessions 50` | Quick session analysis |
| `head -5 data/extracted/*.jsonl` | Verify output format |
| `python3 schemas/training_schema.py --stats` | Combined statistics |

## Data Yields

| Source | Size | Examples | Notes |
|--------|------|----------|-------|
| Journals | 268KB | 223 | Highest quality - reasoning patterns |
| Claude Sessions | 7.9GB | 162 | Filtered to MCP-only turns |
| Discord | ~21KB | 16 | Will grow with bot usage |

## Interface Gaps Identified

- [x] Parser needs: Journal structure extraction (BUILT)
- [x] Parser needs: Claude session MCP filtering (BUILT)
- [x] Schema needs: Multiple export formats - ChatML, Axolotl (BUILT)
- [ ] Discord bot needs: Better conversation logging for training data
- [ ] Training pipeline needs: Quality annotation tool
- [ ] Training pipeline needs: Synthetic augmentation from convention tables

## Files Created

| File | Purpose |
|------|---------|
| `fine_tuning/parsers/journal_parser.py` | Extract reasoning patterns from journals |
| `fine_tuning/parsers/claude_session_parser.py` | Extract MCP sequences from sessions |
| `fine_tuning/schemas/training_schema.py` | Combine sources, export to training formats |
| `fine_tuning/README.md` | Pipeline documentation |
