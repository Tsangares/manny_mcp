# Code Editing Workflow Improvements - Proposal

## Executive Summary

This proposal addresses gaps between the manny plugin's CLAUDE.md and the MCP code-editing workflow to prevent common mistakes across multiple Claude Code instances working with the same codebase.

## Gap Analysis

### Current State ✅
1. **Anti-pattern checking exists** (`check_anti_patterns` MCP tool with 6 rules)
2. **Guidelines auto-included** (`prepare_code_change` includes condensed CLAUDE.md)
3. **Backup/rollback workflow** exists for safety
4. **Threading patterns documented** in both places

### Identified Gaps ❌

#### 1. **Anti-pattern checking not integrated into workflow**
- `check_anti_patterns` tool exists but isn't mentioned in Code Fix Workflow section
- Subagent prompts don't instruct to use this tool before finalizing changes
- No automated validation between `validate_code_change` and `deploy_code_change`

#### 2. **Incomplete condensed guidelines**
The condensed guidelines in `prepare_code_change` (~2K chars) are missing critical patterns from plugin CLAUDE.md:
- F-key binding warning (lines 270-315) - **CRITICAL and often forgotten**
- Tab widget IDs pattern (TOPLEVEL << 16 | offset)
- GameObject interaction boilerplate anti-pattern
- Underscore-to-space conversion in item names
- Interrupt checks in loops (`shouldInterrupt`)
- ResponseWriter.writeSuccess/writeFailure pattern

#### 3. **Missing anti-patterns in automated checks**
ANTI_PATTERNS list has 6 rules but is missing common mistakes documented in plugin CLAUDE.md:
- Manual GameObject clicking boilerplate (should use `interactWithGameObject`)
- F-key usage for tab switching (should use widget IDs)
- Missing `shouldInterrupt` checks in loops
- Missing ResponseWriter calls in command handlers
- `git checkout` usage (documented in plugin CLAUDE.md line 792)

#### 4. **No institutional memory mechanism**
- Each new Claude Code instance might repeat the same mistakes
- No persistent "lessons learned" registry
- Common mistakes documented in plugin CLAUDE.md but not enforced

#### 5. **Workflow doesn't emphasize reading plugin CLAUDE.md**
- Subagent prompts should explicitly reference the full CLAUDE.md
- Currently relies on condensed version which may miss nuances

## Proposed Improvements

### 1. Enhanced MCP CLAUDE.md Code Fix Workflow

**Add anti-pattern validation step:**

```markdown
## Code Fix Workflow

When you observe a bug or issue that requires code changes to the manny plugin, follow this workflow:

### Step-by-Step

1. **Identify the problem** via logs, game state, or observation

2. **Backup files** (for rollback if needed)
   ```
   backup_files(file_paths=["/path/to/File.java"])
   ```

3. **Gather context** for the code-fixing subagent
   ```
   prepare_code_change(
     problem_description="...",
     relevant_files=["PlayerHelpers.java"],
     logs="...",
     game_state={...},
     compact=True  # For large files - subagent uses Read tool
   )
   ```

4. **Spawn a Task subagent** to implement the fix
   ```
   Task(
     prompt="Fix this issue in the manny plugin.

     CRITICAL INSTRUCTIONS:
     1. Read /home/wil/Desktop/manny/CLAUDE.md FIRST for complete guidelines
     2. Use check_anti_patterns tool to validate your changes BEFORE responding
     3. Follow manny_guidelines patterns (included in context)
     4. Make minimal, targeted changes

     If check_anti_patterns finds issues, fix them before finalizing.

     Context: {result from step 3}",
     subagent_type="general-purpose"
   )
   ```

5. **Validate compilation**
   ```
   validate_code_change(modified_files=["PlayerHelpers.java"])
   ```
   - If errors: return to step 4 with error details
   - If success: proceed to step 6

6. **Check anti-patterns** (automated validation)
   ```
   check_anti_patterns(file_path="/path/to/modified/File.java")
   ```
   - If issues found with severity="error": return to step 4
   - Warnings can proceed but should be noted

7. **Deploy and restart**
   ```
   deploy_code_change(restart_after=True)
   stop_runelite()
   start_runelite()
   ```

8. **Test the fix** by observing game behavior
   - If fix doesn't work: `rollback_code_change()` and return to step 3
```

### 2. Enhanced Condensed Guidelines in `prepare_code_change`

**Current condensed guidelines: ~2K chars**
**Proposed: ~3.5K chars** (adds critical missing patterns)

Add to `request_code_change.py` condensed guidelines:

```python
# In prepare_code_change, update non-compact manny_guidelines:
context["manny_guidelines"] = """
=== MANNY PLUGIN ESSENTIAL GUIDELINES ===

## Architecture (READ/WRITE Separation)
- GameEngine.GameHelpers = READ operations (safe anywhere, no game modifications)
- PlayerHelpers = WRITE operations (background thread only, executes actions)
- InteractionSystem = Standardized wrappers for NPCs, GameObjects, widgets

## Thread Safety (CRITICAL)
- Client thread: Widget/menu access only. NEVER block this thread!
- Background thread: Mouse, delays, I/O. Can block.
- Pattern: helper.readFromClient(() -> client.getWidget(id))
  Replaces 10+ lines of CountDownLatch boilerplate

## Required Wrappers (DON'T reinvent these)

NPC interaction:
  interactionSystem.interactWithNPC("Banker", "Bank")
  interactionSystem.interactWithNPC(name, action, maxAttempts, searchRadius)

GameObject interaction:
  interactionSystem.interactWithGameObject("Tree", "Chop down", 15)
  interactionSystem.interactWithGameObject(id, name, action, worldPoint)
  Replaces 60-120 lines of manual GameObject boilerplate!

Widget clicking:
  clickWidget(widgetId)  // 5-phase verification, 3 retries
  clickWidgetWithParam(widgetId, param0, actionName)

Inventory queries:
  gameEngine.hasItems(itemId1, itemId2)  // ALL present
  gameEngine.hasAnyItem(itemId1, itemId2)  // ANY present
  gameEngine.getItemCount(itemId), getEmptySlots(), hasInventorySpace(n)

Banking:
  handleBankOpen(), handleBankClose()
  handleBankWithdraw("Iron_ore 14")  // underscores → spaces
  handleBankDepositAll(), handleBankDepositItem("Logs")

## Tab Switching (CRITICAL - F-keys are unreliable!)
❌ NEVER use F-key bindings (user-customizable, break!)
✅ ALWAYS use tab widget IDs:
  final int TOPLEVEL = 548;
  final int MAGIC_TAB = (TOPLEVEL << 16) | 0x56;  // 35913814
  clickWidget(MAGIC_TAB);

## Command Handler Pattern (MANDATORY)
private boolean handleMyCommand(String args) {
    log.info("[MY_COMMAND] Starting...");
    try {
        // 1. Parse args (replace underscores with spaces)
        String itemName = args.replace("_", " ");

        // 2. Use existing wrappers, NOT manual boilerplate

        // 3. Check shouldInterrupt in loops
        for (int i = 0; i < count; i++) {
            if (shouldInterrupt) {
                responseWriter.writeFailure("MY_COMMAND", "Interrupted");
                return false;
            }
            // ... work
        }

        // 4. ALWAYS write response
        responseWriter.writeSuccess("MY_COMMAND", "Done");
        return true;
    } catch (Exception e) {
        log.error("[MY_COMMAND] Error", e);
        responseWriter.writeFailure("MY_COMMAND", e);
        return false;
    }
}

## Anti-Patterns (AVOID THESE - will cause bugs!)
1. ❌ smartClick() for NPCs → use interactionSystem.interactWithNPC()
2. ❌ Manual CountDownLatch → use helper.readFromClient(() -> ...)
3. ❌ Manual retry loops → wrappers have built-in retry
4. ❌ Manual GameObject boilerplate → use interactWithGameObject()
5. ❌ Direct client.getMenuEntries() → wrap in clientThread.invokeLater()
6. ❌ Thread.sleep(5000+) → use shorter sleeps with interrupt checks
7. ❌ F-key for tabs → use widget IDs (TOPLEVEL << 16 | offset)
8. ❌ Missing shouldInterrupt checks in loops
9. ❌ Missing ResponseWriter calls in handlers
10. ❌ Forgetting underscore→space conversion for item names

## IMPORTANT: Use check_anti_patterns tool
Before finalizing changes, run:
  check_anti_patterns(file_path="path/to/modified/file.java")
Fix any errors before submitting!

## Key Files
- PlayerHelpers.java (24K lines): Commands, writes. Has section markers.
- GameEngine.java: Read-only queries (inventory, NPCs, objects)
- InteractionSystem.java: NPC/GameObject/Widget wrappers
- ClientThreadHelper.java: Thread-safe client access

For COMPLETE documentation, read: /home/wil/Desktop/manny/CLAUDE.md
"""
```

### 3. Expanded Anti-Pattern Detection

Add to `manny_tools.py` ANTI_PATTERNS list:

```python
ANTI_PATTERNS = [
    # ... existing 6 patterns ...

    # NEW: Manual GameObject boilerplate
    {
        "pattern": r"(gameEngine\.getGameObject|GameObject.*clickBox.*CountDownLatch)",
        "context_hint": r"(?!interactWithGameObject)",
        "severity": "error",
        "message": "Manual GameObject interaction boilerplate detected",
        "suggestion": "Use interactionSystem.interactWithGameObject(name, action, radius) instead (replaces 60-120 lines)"
    },

    # NEW: F-key usage for tabs
    {
        "pattern": r"(keyboard\.pressKey\(KeyEvent\.VK_F[0-9]|tabSwitcher\.open)",
        "severity": "error",
        "message": "Using F-keys for tab switching (unreliable - user can rebind!)",
        "suggestion": "Use clickWidget((548 << 16) | offset) for tab switching instead"
    },

    # NEW: Missing interrupt checks in loops
    {
        "pattern": r"(for|while)\s*\([^)]*\)\s*\{",
        "context_hint": r"(?!shouldInterrupt).*\{[\s\S]{50,}",
        "severity": "warning",
        "message": "Loop without shouldInterrupt check (may not be cancellable)",
        "suggestion": "Add 'if (shouldInterrupt) { responseWriter.writeFailure(...); return false; }' in loop body"
    },

    # NEW: Missing ResponseWriter in command handlers
    {
        "pattern": r"private\s+boolean\s+handle[A-Z]\w+\s*\([^)]*\)",
        "context_hint": r"(?!responseWriter\.write)",
        "severity": "warning",
        "message": "Command handler missing ResponseWriter calls",
        "suggestion": "Add responseWriter.writeSuccess/writeFailure calls"
    },

    # NEW: Underscore handling
    {
        "pattern": r"(handleBank\w+|getItemCount|findItemByName)\s*\([^)]*\"[^\"]*\s[^\"]*\"",
        "severity": "info",
        "message": "Item name with spaces - consider underscore support",
        "suggestion": "Use args.replace(\"_\", \" \") to support both formats"
    }
]
```

### 4. Common Pitfalls Registry (New Section in MCP CLAUDE.md)

Add after "Code Fix Workflow" section:

```markdown
## Common Pitfalls Registry

**Purpose**: Document recurring mistakes across Claude Code instances to prevent repetition.

### Pitfall 1: Using smartClick() for NPCs
**Symptom**: Thread violations, menu click failures
**Why it happens**: smartClick() was deprecated but still exists in codebase
**Prevention**: `check_anti_patterns` detects this (error severity)
**Fix**: Use `interactionSystem.interactWithNPC(name, action)` instead

### Pitfall 2: Manual GameObject boilerplate
**Symptom**: 60-120 lines of CountDownLatch, clickbox fetching, menu clicking
**Why it happens**: Subagent doesn't know the wrapper exists
**Prevention**: Condensed guidelines now explicitly mention this
**Fix**: Use `interactionSystem.interactWithGameObject(name, action, radius)`

### Pitfall 3: F-key usage for tab switching
**Symptom**: Tab switching fails silently on different user configs
**Why it happens**: F-keys are customizable in OSRS settings
**Prevention**: `check_anti_patterns` now detects F-key usage
**Fix**: Use tab widget IDs: `clickWidget((548 << 16) | 0x56)` for Magic tab

### Pitfall 4: Missing interrupt checks in long loops
**Symptom**: Commands can't be cancelled with KILL/STOP
**Why it happens**: Forgot to add `shouldInterrupt` check
**Prevention**: `check_anti_patterns` warns about loops without interrupt checks
**Fix**: Add in loop body:
```java
if (shouldInterrupt) {
    responseWriter.writeFailure("CMD", "Interrupted");
    return false;
}
```

### Pitfall 5: Forgetting ResponseWriter in command handlers
**Symptom**: MCP client doesn't know if command succeeded/failed
**Why it happens**: Pattern not obvious to subagent
**Prevention**: Condensed guidelines now include command handler template
**Fix**: Always call `responseWriter.writeSuccess/writeFailure`

### Pitfall 6: Manual CountDownLatch instead of ClientThreadHelper
**Symptom**: UI freezes, race conditions, complex error-prone code
**Why it happens**: CountDownLatch pattern is well-known, helper is not
**Prevention**: Existing anti-pattern check
**Fix**: `helper.readFromClient(() -> client.getWidget(id))`

### How to Update This Registry
When you discover a new recurring mistake:
1. Add entry with: Symptom, Why it happens, Prevention, Fix
2. Update ANTI_PATTERNS in manny_tools.py if automatable
3. Update condensed guidelines if pattern is common
```

### 5. Automated Validation Function

Add to `request_code_change.py`:

```python
def validate_with_anti_pattern_check(
    runelite_root: str,
    modified_files: list[str],
    manny_src: str
) -> dict:
    """
    Validate code changes with both compilation AND anti-pattern checks.

    Combines validate_code_change + check_anti_patterns for comprehensive validation.

    Args:
        runelite_root: Path to RuneLite source root
        modified_files: List of modified files to check
        manny_src: Path to manny plugin source

    Returns:
        Dict with combined validation results
    """
    from manny_tools import check_anti_patterns

    # Step 1: Compilation check
    compile_result = validate_code_change(runelite_root, modified_files)

    if not compile_result["success"]:
        return {
            "success": False,
            "compilation": compile_result,
            "anti_patterns": None,
            "message": "Compilation failed - fix errors before checking anti-patterns"
        }

    # Step 2: Anti-pattern check
    all_issues = []
    error_count = 0

    for file_path in modified_files:
        # Resolve relative paths
        full_path = file_path if os.path.isabs(file_path) else os.path.join(manny_src, file_path)

        if os.path.exists(full_path):
            pattern_result = check_anti_patterns(file_path=full_path)

            if pattern_result.get("success"):
                all_issues.extend(pattern_result.get("issues", []))
                error_count += pattern_result.get("errors", 0)

    # Determine overall success
    # Compilation passed, but error-severity anti-patterns = FAIL
    overall_success = error_count == 0

    return {
        "success": overall_success,
        "compilation": compile_result,
        "anti_patterns": {
            "total_issues": len(all_issues),
            "errors": error_count,
            "issues": all_issues
        },
        "message": (
            "All validations passed - ready to deploy" if overall_success
            else f"Anti-pattern validation failed: {error_count} error(s) found. Fix before deploying."
        ),
        "ready_to_deploy": overall_success
    }
```

## Implementation Priority

### Phase 1: Critical (Immediate)
1. ✅ Update MCP CLAUDE.md Code Fix Workflow (add anti-pattern validation step)
2. ✅ Enhance condensed guidelines in `prepare_code_change` (add missing patterns)
3. ✅ Update subagent prompt template to instruct anti-pattern checking

### Phase 2: High (Within 1 week)
4. ✅ Add 5 new anti-patterns to ANTI_PATTERNS list
5. ✅ Create Common Pitfalls Registry section
6. ✅ Add `validate_with_anti_pattern_check` function

### Phase 3: Nice-to-Have (Future)
7. Add logging of subagent mistakes to pitfalls registry (automated learning)
8. Create pre-commit hook that runs check_anti_patterns locally
9. Add metrics: track how often each anti-pattern is caught

## Expected Benefits

1. **Reduced recurring mistakes**: Automated anti-pattern detection catches issues before deployment
2. **Better subagent alignment**: Enhanced guidelines give subagents better context
3. **Institutional memory**: Pitfalls registry captures lessons across instances
4. **Faster iteration**: Validation catches issues early, reducing rollback cycles
5. **Consistent code quality**: All changes follow the same patterns

## Testing Plan

1. Test with a known anti-pattern (smartClick for NPC):
   - Spawn subagent with old workflow
   - Spawn subagent with new workflow
   - Verify new workflow catches and fixes the issue

2. Test condensed guidelines completeness:
   - Give subagent a task requiring F-key knowledge
   - Verify condensed guidelines include the warning

3. Test validate_with_anti_pattern_check:
   - Create PR with intentional anti-pattern
   - Verify validation fails appropriately

## Rollout Strategy

1. **Week 1**: Update documentation (CLAUDE.md, condensed guidelines)
2. **Week 2**: Implement code changes (ANTI_PATTERNS, validation function)
3. **Week 3**: Test with controlled scenarios
4. **Week 4**: Full deployment + monitor for issues
