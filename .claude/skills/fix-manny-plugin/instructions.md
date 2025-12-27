# Fix Manny Plugin - Enhanced Workflow Skill

This skill guides you through the enhanced 8-step code fix workflow with automated validation and anti-pattern detection.

## What This Skill Does

Helps fix bugs in the manny RuneLite plugin using:
- ✅ Smart sectioning (90% context reduction)
- ✅ Automated anti-pattern detection (11 rules)
- ✅ Backup/rollback safety
- ✅ Combined validation (compilation + patterns)
- ✅ Institutional memory (Common Pitfalls Registry)

## When to Use

Use this skill when:
- A command is failing (BANK_OPEN, MINE_ORE, etc.)
- Logs show errors in the manny plugin
- Game behavior is incorrect
- You need to modify PlayerHelpers.java, GameEngine.java, or other plugin files

## Workflow Steps

### Step 1: Identify the Problem

**What to do:**
```
1. Get recent error logs: get_logs(level="ERROR", since_seconds=120)
2. Get game state: get_game_state()
3. Analyze what's failing
```

**Questions to answer:**
- What command is failing?
- What error message appears in logs?
- At what line number does the error occur?
- What is the expected vs actual behavior?

### Step 2: Backup Files

**What to do:**
```
backup_files(file_paths=["/home/wil/Desktop/manny/utility/PlayerHelpers.java"])
```

**Why:** Safety net - allows rollback if the fix doesn't work.

### Step 3: Gather Context with Smart Sectioning

**What to do:**
```python
prepare_code_change(
    problem_description="""
    Clear description of the problem.
    Include: what command, what error, what line number.
    """,
    relevant_files=["utility/PlayerHelpers.java"],
    logs="<paste error logs here>",
    game_state={...},
    compact=True,          # For large files
    smart_sectioning=True  # Extracts only relevant code
)
```

**Benefits:**
- Smart sectioning extracts only the relevant command handler
- 90% context reduction (24K lines → 150 lines)
- Subagent stays focused

### Step 4: Spawn Subagent with Validation Requirement

**CRITICAL:** Use this exact prompt template:

```python
Task(
    prompt=f"""Fix this manny plugin issue.

    CRITICAL INSTRUCTIONS:
    1. Read /home/wil/Desktop/manny/CLAUDE.md FIRST for complete guidelines
    2. Use check_anti_patterns tool to validate your changes BEFORE responding
    3. Follow manny_guidelines patterns (included in context)
    4. Make minimal, targeted changes

    If check_anti_patterns finds issues, fix them before finalizing.

    Problem: {{describe the problem}}

    Context: {{result from step 3}}
    """,
    subagent_type="general-purpose"
)
```

**The subagent will:**
1. Read condensed guidelines (all 10 anti-patterns)
2. Use Read tool for specific code sections
3. Make the fix
4. Run check_anti_patterns to validate
5. Report back

### Step 5: Validate Compilation

**What to do:**
```python
validate_code_change(modified_files=["utility/PlayerHelpers.java"])
```

**What to check:**
- Does it compile successfully?
- Are there any compilation errors?
- If errors, return to step 4 with error details

### Step 6: Check Anti-Patterns (Automated Validation)

**What to do (RECOMMENDED):**
```python
validate_with_anti_pattern_check(modified_files=["utility/PlayerHelpers.java"])
```

**This checks:**
- ✅ Compilation (already done in step 5)
- ✅ All 11 anti-pattern rules
- ✅ Blocks deployment if error-severity issues

**What to check:**
- `ready_to_deploy: true` → proceed to deploy
- `ready_to_deploy: false` → return to step 4, fix issues

**Common anti-patterns caught:**
1. smartClick() for NPCs
2. Manual CountDownLatch
3. F-key usage for tabs
4. Manual GameObject boilerplate
5. Missing interrupt checks
6. Missing ResponseWriter calls

### Step 7: Deploy and Restart

**What to do:**
```python
deploy_code_change(restart_after=True)
stop_runelite()
start_runelite()
```

**Wait:** Give RuneLite 10-15 seconds to fully restart.

### Step 8: Test the Fix

**What to do:**
```python
# Test the fixed command
send_command("BANK_OPEN")  # or whatever command you fixed

# Check response
get_command_response()

# Check for errors
get_logs(level="ERROR", since_seconds=30, grep="BANK_OPEN")
```

**If fix works:** ✅ Done! Update Common Pitfalls Registry if this was a recurring issue.

**If fix doesn't work:** ❌ Rollback and iterate:
```python
rollback_code_change()
deploy_code_change()
stop_runelite()
start_runelite()
# Return to step 3 with more analysis
```

## Common Pitfalls to Avoid

### Pitfall 1: Using smartClick() for NPCs
**Anti-pattern #1 will catch this**
```java
// ❌ BAD
smartClick(npc.getConvexHull());

// ✅ GOOD
interactionSystem.interactWithNPC("Banker", "Bank");
```

### Pitfall 2: F-key for tabs
**Anti-pattern #8 will catch this**
```java
// ❌ BAD
keyboard.pressKey(KeyEvent.VK_F6);

// ✅ GOOD
clickWidget((548 << 16) | 0x56);
```

### Pitfall 3: Manual GameObject boilerplate
**Anti-pattern #7 will catch this**
```java
// ❌ BAD (60-120 lines of boilerplate)
GameObject obj = gameEngine.getGameObject(x, y);
CountDownLatch latch = new CountDownLatch(1);
// ... 50+ more lines

// ✅ GOOD (1 line)
interactionSystem.interactWithGameObject("Furnace", "Smelt", 15);
```

### Pitfall 4: Missing interrupt check
**Anti-pattern #9 will catch this**
```java
// ❌ BAD
for (int i = 0; i < 100; i++) {
    doWork();
}

// ✅ GOOD
for (int i = 0; i < 100; i++) {
    if (shouldInterrupt) {
        responseWriter.writeFailure("CMD", "Interrupted");
        return false;
    }
    doWork();
}
```

### Pitfall 5: Missing ResponseWriter
**Anti-pattern #10 will catch this**
```java
// ❌ BAD
private boolean handleCommand(String args) {
    log.info("[CMD] Starting...");
    doWork();
    return true;  // No response!
}

// ✅ GOOD
private boolean handleCommand(String args) {
    log.info("[CMD] Starting...");
    try {
        doWork();
        responseWriter.writeSuccess("CMD", "Done");
        return true;
    } catch (Exception e) {
        responseWriter.writeFailure("CMD", e);
        return false;
    }
}
```

## Quick Reference

### Essential Tools (in order)
1. `backup_files()` - Safety first
2. `prepare_code_change()` - Smart context gathering
3. `Task()` - Spawn subagent with validation
4. `validate_with_anti_pattern_check()` - Combined validation
5. `deploy_code_change()` - Deploy if clean
6. `rollback_code_change()` - Undo if needed

### Performance Tips
- Use `smart_sectioning=True` for 90% context reduction
- Use `compact=True` for files >500 lines
- Use `validate_with_anti_pattern_check()` instead of two separate calls

### Documentation
- Quick lookup: `/home/wil/manny-mcp/QUICK_REFERENCE.md`
- Example: `/home/wil/manny-mcp/EXAMPLE_WORKFLOW.md`
- Full details: `/home/wil/manny-mcp/IMPLEMENTATION_SUMMARY.md`
- Plugin guidelines: `/home/wil/Desktop/manny/CLAUDE.md`

## Success Criteria

You've successfully used this skill when:
- ✅ Bug is fixed and command works
- ✅ No error logs after testing
- ✅ All anti-pattern checks passed
- ✅ Code compiles successfully
- ✅ RuneLite restarts without issues

## Version

**Skill Version**: 2.0.0
**Workflow Version**: Enhanced 8-step workflow
**Anti-Patterns**: 11 automated rules
**Context Reduction**: 90% via smart sectioning
**Performance**: 10x faster validation
