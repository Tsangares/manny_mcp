# Smart Context Architecture - Lessons Learned
**Date:** 2026-01-24

## The Problem

The Discord bot LLM repeatedly made entity type mistakes: searching for fishing spots as objects (they're NPCs), using `PICK_UP_ITEM` for static spawns (should use `INTERACT_OBJECT`), and inventing commands like `Net 3245, 3156`. The root cause wasn't LLM capability—it was context overload and missing domain knowledge.

## Root Cause

**Context architecture was monolithic.** The original `CONTEXT.md` was ~277 lines (~2000 tokens) covering everything. Problems:

1. **Token budget exceeded** - LLM couldn't absorb all information
2. **No domain focus** - Fishing context mixed with combat mixed with banking
3. **Missing key insights** - "Fishing spots are NPCs" was never stated
4. **No discovery guidance** - LLM didn't know which tool to use for which entity type

**Code reference:** `discord_bot/agentic_loop.py:_build_messages()` loaded full CONTEXT.md for every request.

## Key Lessons

### 1. Activity Classification Enables Focused Context

**What happened:** LLM received 2000+ tokens of context, couldn't prioritize relevant info.

**Why:** Human brains filter; LLMs don't. Giving everything = giving nothing useful.

**Solution:**
```python
# BAD - Load everything
system_prompt = get_agentic_system_prompt()  # 2000+ tokens

# GOOD - Classify and inject relevant fragment only
domain = classify_activity(message)  # "skilling", "combat", etc.
if domain:
    fragment = get_context_fragment(domain)  # ~300 tokens
    system_prompt += f"\n\n{fragment}"
```

**Implementation:** `discord_bot/activity_classifier.py` - keyword matching, <1ms

### 2. Entity Type Tables Prevent Wrong Tool Usage

**What happened:** LLM used `query_nearby(include_ground_items=True)` for fishing nets (static spawns).

**Why:** No explicit mapping of entity types to discovery tools.

**Solution:** Every fragment includes entity type table:
```markdown
| Entity Type | Discovery Tool | Interaction Command |
|-------------|----------------|---------------------|
| Fishing spots | query_nearby(include_npcs=True) | FISH or INTERACT_NPC |
| Static spawns | scan_tile_objects() | INTERACT_OBJECT ... Take |
| Dropped items | query_nearby(include_ground_items=True) | PICK_UP_ITEM |
```

### 3. Tool Response Hints Guide Next Steps

**What happened:** LLM found fishing spot via `query_nearby` but didn't know how to interact.

**Why:** Tool returned data but no guidance on what to do with it.

**Solution:** Inject `_hints` in tool responses:
```python
# In bot.py _execute_tool()
if tool_name == "query_nearby":
    result = await handle_query_nearby(...)

    # Add hints based on what was found
    hints = []
    for npc in result.get("npcs", []):
        if "Fishing" in str(npc):
            hints.append("Fishing spots are NPCs. Use FISH or INTERACT_NPC")

    if hints:
        result["_hints"] = hints
```

### 4. Fragment Size Must Fit Token Budget

**What happened:** Initial fragments were too verbose, exceeding budget.

**Why:** Combined base CONTEXT.md + fragment + schema instruction = too many tokens.

**Solution:** Keep fragments under 400 words (~300 tokens):
```
Base CONTEXT.md:  ~400 tokens
Activity fragment: ~300 tokens
Schema instruction: ~200 tokens
─────────────────────────────
Total:             ~900 tokens (under 1000 target)
```

### 5. Multi-Word Keyword Matching Needs Priority

**What happened:** "Go to GE" matched "go to" (navigation) before "GE" (grand_exchange).

**Why:** Single-word matching happened after multi-word, but domain order mattered.

**Solution:** Check multi-word keywords first, organized by specificity:
```python
MULTI_WORD_KEYWORDS = {
    "grand_exchange": ["grand exchange", "buy ge", "sell ge"],  # Specific
    "navigation": ["go to", "walk to"],  # Generic
}

# Check multi-word FIRST
for domain, keywords in MULTI_WORD_KEYWORDS.items():
    for kw in keywords:
        if kw in message_lower:
            return domain
```

## Anti-Patterns

1. **Don't** load full context for every request - classify first, inject relevant fragment
2. **Don't** assume LLM knows entity types - explicitly document NPC vs Object vs Item
3. **Don't** return tool data without hints - guide next steps
4. **Don't** write verbose fragments - keep under 400 words
5. **Don't** mix domain keywords - "ge" should be grand_exchange, not navigation

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `./venv/bin/python discord_bot/activity_classifier.py` | Test classification |
| `./venv/bin/python discord_bot/test_harness.py "msg"` | Test full flow |
| `wc -w discord_bot/context_fragments/*.md` | Check token budgets |
| `grep "_hints" logs/conversations/*.log` | Verify hints in responses |

## Interface Gaps Identified

- [x] **Solved:** Activity classification in `agentic_loop.py`
- [x] **Solved:** Hint injection in `bot.py` for `query_nearby` and `scan_tile_objects`
- [x] **Solved:** 14 context fragments covering major domains
- [ ] **Needs testing:** `grand_exchange.md`, `shops.md`, `smithing.md` need in-game verification
- [ ] **Missing fragments:** Crafting, Runecrafting, Minigames

## Files Created/Modified

| File | Change |
|------|--------|
| `discord_bot/activity_classifier.py` | NEW - Keyword-based activity classification |
| `discord_bot/context_fragments/*.md` | NEW - 14 domain-specific context files |
| `discord_bot/context_fragments/README.md` | NEW - Fragment development guide |
| `discord_bot/agentic_loop.py` | MODIFIED - Smart context injection |
| `discord_bot/bot.py` | MODIFIED - Hint injection in tool responses |
| `discord_bot/CONTEXT.md` | REWRITTEN - Slim reasoning framework (~90 lines) |
| `discord_bot/test_harness.py` | MODIFIED - Hints in mock responses |
| `discord_bot/mock_states/scenarios.json` | MODIFIED - New test scenarios |
| `docs/CONTEXT_DEVELOPMENT_METHODOLOGY.md` | NEW - Full methodology guide |

## Architecture Diagram

```
User Message: "Start fishing shrimps"
       │
       ▼
┌─────────────────────────────────────┐
│ activity_classifier.py             │
│ classify_activity() → "skilling"   │
└─────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│ agentic_loop.py                    │
│ Load: CONTEXT.md + skilling.md     │
│ Total: ~700 tokens (not 2000+)     │
└─────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│ LLM receives focused context:      │
│ - Fishing spots are NPCs           │
│ - Use FISH shrimp (lowercase)      │
│ - Equipment requirements           │
└─────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│ Tool response includes hints:      │
│ query_nearby() returns:            │
│ {"npcs": ["Fishing spot"],         │
│  "_hints": ["Use FISH or           │
│   INTERACT_NPC Fishing_spot"]}     │
└─────────────────────────────────────┘
       │
       ▼
   Correct action: FISH shrimp
```

## Time Analysis

| Phase | Time | Notes |
|-------|------|-------|
| Problem identification | ~10 min | Reviewed logs showing wrong tool usage |
| Architecture design | ~15 min | Planned fragment structure |
| Implementation | ~45 min | Created 14 fragments + classifier |
| Testing | ~10 min | Verified with test harness |
| Documentation | ~20 min | Methodology guide + this journal |

**Total:** ~100 min for complete architecture overhaul

## Success Metrics

| Metric | Before | After |
|--------|--------|-------|
| Context tokens per request | ~2000 | ~700-900 |
| Wrong entity type errors | Common | Should be rare |
| Invented commands | Occasional | Should be eliminated |
| Fragments available | 0 | 14 |
