# Code Fix Workflow - Quick Reference

## New Enhanced Workflow (8 Steps)

### 1. Identify Problem
```python
get_logs(level="ERROR", since_seconds=60)
get_game_state()
```

### 2. Backup Files
```python
backup_files(file_paths=[
    "/home/wil/Desktop/manny/utility/PlayerHelpers.java"
])
```

### 3. Gather Context (with smart sectioning!)
```python
prepare_code_change(
    problem_description="BANK_OPEN command fails with NullPointerException",
    relevant_files=["utility/PlayerHelpers.java"],
    logs="[BANK_OPEN] Error: NPE at line 1234",
    game_state={...},
    compact=True,          # For large files
    smart_sectioning=True  # NEW: Extracts only BANK_OPEN handler
)
```

### 4. Spawn Subagent (with validation instruction!)
```python
Task(
    prompt="""Fix this manny plugin issue.

    CRITICAL INSTRUCTIONS:
    1. Read /home/wil/Desktop/manny/CLAUDE.md FIRST
    2. Use check_anti_patterns tool to validate BEFORE responding
    3. Follow manny_guidelines patterns
    4. Make minimal, targeted changes

    If check_anti_patterns finds issues, fix them before finalizing.

    Context: {result from step 3}""",
    subagent_type="general-purpose"
)
```

### 5. Validate Compilation
```python
validate_code_change(modified_files=["utility/PlayerHelpers.java"])
```

### 6. Check Anti-Patterns (NEW!)
```python
# Option A: Individual check
check_anti_patterns(file_path="/home/wil/Desktop/manny/utility/PlayerHelpers.java")

# Option B: Combined validation (RECOMMENDED)
validate_with_anti_pattern_check(modified_files=["utility/PlayerHelpers.java"])
# ✅ Checks BOTH compilation AND anti-patterns
# ✅ Blocks deployment if error-severity issues found
```

### 7. Deploy
```python
deploy_code_change(restart_after=True)
stop_runelite()
start_runelite()
```

### 8. Test
```python
# If fix doesn't work:
rollback_code_change()
# Then return to step 3
```

## What's New vs Old Workflow?

| Step | Old Workflow | New Workflow |
|------|-------------|--------------|
| 2 | ❌ No backup | ✅ Backup files for rollback |
| 3 | Basic context | ✅ Smart sectioning (90% smaller) |
| 4 | No validation instruction | ✅ MUST use check_anti_patterns |
| 6 | ❌ No anti-pattern check | ✅ Automated validation |

## New Features

### Smart Sectioning
```python
# When problem mentions "BANK_OPEN":
# OLD: Returns all 24K lines of PlayerHelpers.java
# NEW: Returns only BANK_OPEN handler (~200 lines)
# Savings: 90% context reduction
```

### Anti-Pattern Detection (11 Rules)
1. smartClick() for NPCs → use interactWithNPC()
2. Manual CountDownLatch → use helper.readFromClient()
3. Unsafe client.getMenuEntries()
4. Manual retry loops
5. Long Thread.sleep()
6. Chained widget access
7. **Manual GameObject boilerplate** ← NEW
8. **F-key for tabs** ← NEW
9. **Missing interrupt checks** ← NEW
10. **Missing ResponseWriter** ← NEW
11. **Item name underscore handling** ← NEW

### Combined Validation (Recommended)
```python
# Instead of:
validate_code_change(...)
check_anti_patterns(...)

# Use:
validate_with_anti_pattern_check(...)
# ✅ One call
# ✅ Blocks deployment if errors
# ✅ Warnings don't block but are reported
```

## Common Pitfalls (Now Auto-Detected!)

### Pitfall 1: F-key for tabs
```java
// ❌ BAD - Detected by anti-pattern #8
keyboard.pressKey(KeyEvent.VK_F6);

// ✅ GOOD
clickWidget((548 << 16) | 0x56);
```

### Pitfall 2: smartClick for NPCs
```java
// ❌ BAD - Detected by anti-pattern #1
smartClick(npc.getConvexHull());

// ✅ GOOD
interactionSystem.interactWithNPC("Banker", "Bank");
```

### Pitfall 3: Missing interrupt check
```java
// ❌ BAD - Detected by anti-pattern #9
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

## Performance Tips

### Use compact mode for large files
```python
prepare_code_change(
    ...,
    compact=True  # Returns metadata only, subagent uses Read tool
)
```

### Enable smart sectioning
```python
prepare_code_change(
    ...,
    smart_sectioning=True  # 90% context reduction
)
```

### Use combined validation
```python
# Faster than running two separate checks
validate_with_anti_pattern_check(modified_files=[...])
```

## Troubleshooting

### Subagent didn't use check_anti_patterns?
→ Check your prompt includes the CRITICAL INSTRUCTIONS section

### Anti-pattern giving false positive?
→ Report in Common Pitfalls Registry
→ Pattern may need refinement

### Smart sectioning didn't extract command?
→ Ensure problem/logs mention command name or handler method

### Validation passed but code still buggy?
→ Validation only checks compilation + known anti-patterns
→ Not all bugs are detectable statically

## Resources

- **Full Documentation**: `/home/wil/manny-mcp/CLAUDE.md`
- **Implementation Details**: `/home/wil/manny-mcp/IMPLEMENTATION_SUMMARY.md`
- **Test Results**: `/home/wil/manny-mcp/TEST_RESULTS.md`
- **Improvement Proposal**: `/home/wil/manny-mcp/improvements_proposal.md`
- **Plugin Guidelines**: `/home/wil/Desktop/manny/CLAUDE.md`

## Quick Commands

```bash
# Check anti-patterns in existing file
python3 -c "from manny_tools import check_anti_patterns; print(check_anti_patterns(file_path='path/to/file.java'))"

# Extract commands from problem
python3 -c "from request_code_change import _extract_commands_from_problem; print(_extract_commands_from_problem('BANK_OPEN fails', '[BANK_OPEN] Error'))"

# Test regex pre-compilation
python3 -c "from manny_tools import _COMPILED_ANTI_PATTERNS; print(f'{len(_COMPILED_ANTI_PATTERNS)} patterns loaded')"
```
