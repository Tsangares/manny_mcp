# Journal Template

## Purpose

Journals capture **lessons for future agents**, not activity logs. Focus on:
- What went wrong and WHY (root cause)
- Patterns that work vs patterns that fail
- Interface gaps between Claude Code ↔ MCP ↔ Plugin ↔ Game
- Debugging techniques that helped

**Don't document:** Session stats, level progress, play-by-play narration, "what I did today"

---

## Template

```markdown
# [Problem/Topic] - Lessons Learned
**Date:** YYYY-MM-DD

## The Problem

[1-3 sentences: What failed or was confusing? What was the symptom?]

## Root Cause

[Technical explanation of WHY it failed. Be specific - file names, line numbers, architectural issues.]

## Key Lessons

### 1. [Lesson Title]

**What happened:** [Brief description]
**Why:** [Technical reason]
**Solution:**
\`\`\`python
# BAD - explain why
bad_code_example()

# GOOD - explain why
good_code_example()
\`\`\`

### 2. [Next Lesson]
...

## Anti-Patterns

1. **Don't** [bad pattern] - [why it fails]
2. **Don't** [bad pattern] - [why it fails]

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `tool_name()` | What it reveals |

## Interface Gaps Identified

[What's missing or broken in the MCP↔Plugin↔Game chain that caused this issue?]

- [ ] Plugin needs: [feature/fix]
- [ ] MCP needs: [feature/fix]
- [ ] CLAUDE.md needs: [documentation]

## Files Modified (if applicable)

| File | Change |
|------|--------|
| `path/to/file.java` | Brief description |
```

---

## What Makes a Valuable Journal

### High Value Content

1. **Root cause with code references**
   - "Grid was 4 cols, code assumed 7" (deposit_box)
   - "Plugin processes commands on GameTick - no ticks when disconnected" (manny_plugin)

2. **BAD vs GOOD code patterns**
   ```python
   # BAD
   INTERACT_NPC Captain Tobias Travel  # Parser splits on spaces

   # GOOD
   INTERACT_NPC Captain_Tobias Travel  # Underscores for multi-word
   ```

3. **Interface boundary discoveries**
   - "Deposit box doesn't create real widgets - items rendered from container"
   - "When state file is >30s stale, plugin has frozen"

4. **Debugging techniques that worked**
   - "Add logging at each step of the chain, don't debug end-to-end"
   - "Test multiple grid slots - corners AND middle"

5. **Time wasted per pitfall** (helps prioritize fixes)
   - "Fishing spot ID issue: 45+ min (still unresolved)"

### Low Value Content (Skip)

- Session stats ("caught 47 fish", "level 25→30")
- Play-by-play ("first I opened bank, then deposited...")
- Progress updates ("50% done with goal")
- Activity summaries ("completed 7 trips")

---

## Example Titles

Good titles focus on the lesson, not the activity:

- "Deposit Box Widget Clicking - Lessons Learned"
- "Indoor Navigation - Why Naive GOTO Fails"
- "NPC ID Conflicts at Multi-Spot Fishing Locations"
- "State File Staleness as Plugin Health Indicator"

Not:
- "Fishing Session 2025-01-07"
- "Cooking Quest Progress"
- "Today's Bot Run"

---

## When to Write a Journal

Write when you discover:
1. **A bug with a non-obvious root cause** - Future agents will hit this
2. **A pattern that works** - After 30+ min debugging, document what finally worked
3. **An interface gap** - Missing plugin command, MCP limitation, etc.
4. **Coordinate/naming quirks** - These are constantly forgotten

Don't write for:
- Routine successful sessions
- Simple bugs with obvious fixes
- Progress updates
