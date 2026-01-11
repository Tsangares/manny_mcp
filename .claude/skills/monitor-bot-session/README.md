# Monitor Bot Session Skill

**Purpose:** Efficiently monitor long-running OSRS bot sessions (1+ hours) with token-aware polling and intelligent intervention.

**When to use:**
- User starts a long-running routine (fishing, mining, combat training)
- Monitoring multi-hour autonomous operation
- User says "monitor this" or "watch the bot"
- After starting routines like FISH_DRAYNOR_LOOP, KILL_LOOP, etc.

**What this skill does:**
- Implements sparse polling (30-60s intervals) to save tokens
- Detects when intervention is needed vs normal operation
- Filters noise from logs (thread contention, expected retries)
- Logs progress milestones (levels gained, XP increases)
- Maintains session journals for long operations

**What this skill doesn't do:**
- Execute routines (use build-skilling-routine for that)
- Fix bugs in routines (use fix-manny-plugin for that)
- Create new routines (use build-skilling-routine for that)
