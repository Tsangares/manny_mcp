# Add Command Skill

Guide users through adding a new command handler to the manny RuneLite plugin.

## When to Use

- User requests to add a new command/feature to the plugin
- Creating new automation capabilities
- Extending the plugin's command set

## Workflow

### 1. Discovery Phase

Ask the user what the command should do:
```
- What should the command be called? (e.g., "SMELT_BARS", "AGILITY_COURSE")
- What action should it perform?
- What arguments does it need? (e.g., "item_name quantity", "course_name")
- Should it loop or run once?
```

### 2. Check for Existing Commands

Before creating a new command, check if similar functionality exists:
```
list_available_commands(search="<keyword>")
get_command_examples(command="SIMILAR_COMMAND")
```

### 3. Get manny Guidelines

Load the development guidelines to understand command patterns:
```
get_manny_guidelines(mode="condensed")
```

Focus on:
- Command handler structure
- Available wrappers (interactionSystem, gameEngine, etc.)
- Thread safety rules
- Common pitfalls

### 4. Generate Command Template

Use the template generator to create skeleton code:
```
generate_command_template(
    command_name="<COMMAND_NAME>",
    description="<what it does>",
    args_format="<arg1> <arg2>",  # e.g., "item_name quantity"
    has_args=true/false,
    has_loop=true/false
)
```

This generates:
- Switch case entry
- Handler method skeleton
- Proper logging tags
- ResponseWriter calls
- Interrupt checks (if looping)

### 5. Find Similar Implementations

Look for precedents to learn from existing code:
```
find_similar_fix(problem="<what the command does>")
```

Examples:
- "NPC interaction" → shows interactionSystem.interactWithNPC() usage
- "banking workflow" → shows BANK_OPEN/DEPOSIT/WITHDRAW patterns
- "inventory checking" → shows gameEngine.hasItems() usage

### 6. Implementation

Guide user through implementation:

**a. Backup files**
```
backup_files(file_paths=["manny_src/utility/PlayerHelpers.java"])
```

**b. Add switch case**

Tell user where to add (based on get_section output):
```
get_section(section="list")  # Find the right section
```

Then add switch case around line XXXX (find via grep):
```java
case "YOUR_COMMAND":
    return handleYourCommand(args);
```

**c. Add handler method**

Add the handler method implementation using wrappers:
```java
private boolean handleYourCommand(String args) {
    log.info("[YOUR_COMMAND] Starting...");

    // Parse arguments
    String[] parts = args.split("\\s+");

    try {
        // Use wrappers instead of manual code:
        // - interactionSystem.interactWithNPC(name, action)
        // - interactionSystem.interactWithGameObject(name, action, radius)
        // - gameEngine.hasItems(itemId1, itemId2, ...)
        // - clickWidget(widgetId)

        responseWriter.writeSuccess("YOUR_COMMAND", "Completed");
        return true;

    } catch (Exception e) {
        log.error("[YOUR_COMMAND] Error", e);
        responseWriter.writeFailure("YOUR_COMMAND", e);
        return false;
    }
}
```

### 7. Validation

**a. Check for anti-patterns**
```
check_anti_patterns(file_path="manny_src/utility/PlayerHelpers.java")
```

Fix any errors before proceeding.

**b. Compile check**
```
validate_code_change(modified_files=["manny_src/utility/PlayerHelpers.java"])
```

### 8. Deployment

```
deploy_code_change(restart_after=True)
```

### 9. Testing

**a. Start RuneLite (if not running)**
```
start_runelite()
```

**b. Send test command**
```
send_command("YOUR_COMMAND <test args>")
```

**c. Observe results**
```
get_logs(level="INFO", since_seconds=30, grep="YOUR_COMMAND")
get_command_response()
get_game_state()  # Check side effects
```

**d. If issues occur**
```
rollback_code_change()
```

Then iterate on the fix.

## Common Patterns

### Simple NPC Interaction Command

```java
private boolean handleTalkToNpc(String args) {
    log.info("[TALK_TO_NPC] Target: {}", args);

    try {
        boolean success = interactionSystem.interactWithNPC(args, "Talk-to");

        if (success) {
            responseWriter.writeSuccess("TALK_TO_NPC", "Talked to " + args);
            return true;
        } else {
            responseWriter.writeFailure("TALK_TO_NPC", "NPC not found: " + args);
            return false;
        }
    } catch (Exception e) {
        log.error("[TALK_TO_NPC] Error", e);
        responseWriter.writeFailure("TALK_TO_NPC", e);
        return false;
    }
}
```

### Looping Command with Interrupt

```java
private boolean handleFishLoop(String args) {
    log.info("[FISH_LOOP] Starting fishing loop");

    try {
        while (!shouldInterrupt) {
            // Do work
            interactionSystem.interactWithNPC("Fishing spot", "Net");

            // Wait
            Thread.sleep(1000);

            // Check inventory
            if (!gameEngine.hasInventorySpace(1)) {
                log.info("[FISH_LOOP] Inventory full, banking");
                handleBankOpen("");
                handleBankDepositAll("");
                handleBankClose("");
            }
        }

        responseWriter.writeSuccess("FISH_LOOP", "Stopped");
        return true;

    } catch (InterruptedException e) {
        log.info("[FISH_LOOP] Interrupted");
        responseWriter.writeFailure("FISH_LOOP", "Interrupted");
        return false;
    } catch (Exception e) {
        log.error("[FISH_LOOP] Error", e);
        responseWriter.writeFailure("FISH_LOOP", e);
        return false;
    }
}
```

### Command with Arguments

```java
private boolean handleSmelt Bars(String args) {
    // Parse: "SMELT_BARS bronze_bar 28"
    String[] parts = args.split("\\s+");
    if (parts.length < 2) {
        responseWriter.writeFailure("SMELT_BARS", "Usage: SMELT_BARS <bar_type> <quantity>");
        return false;
    }

    String barType = parts[0];
    int quantity = Integer.parseInt(parts[1]);

    log.info("[SMELT_BARS] Type: {}, Quantity: {}", barType, quantity);

    try {
        // Implementation...
        responseWriter.writeSuccess("SMELT_BARS", "Smelted " + quantity + " " + barType);
        return true;
    } catch (Exception e) {
        log.error("[SMELT_BARS] Error", e);
        responseWriter.writeFailure("SMELT_BARS", e);
        return false;
    }
}
```

## Anti-Patterns to Avoid

❌ **Don't use smartClick() for NPCs** → Use `interactionSystem.interactWithNPC()`

❌ **Don't manually fetch widgets with CountDownLatch** → Use `ClientThreadHelper.readFromClient()`

❌ **Don't write manual retry loops** → Wrappers have retries built-in

❌ **Don't use F-keys for tab switching** → Use widget IDs (F-keys are user-configurable)

❌ **Don't forget ResponseWriter** → Always call writeSuccess/writeFailure

❌ **Don't forget interrupt checks in loops** → Check `shouldInterrupt` regularly

## Success Criteria

- [ ] Command compiles without errors
- [ ] No anti-pattern violations
- [ ] Command appears in list_available_commands()
- [ ] Test execution succeeds
- [ ] Logs show proper [TAG] format
- [ ] ResponseWriter called correctly
- [ ] Code follows existing patterns

## Tips

- **Start simple**: Get basic version working first, then add features
- **Use wrappers**: Don't reinvent NPC/GameObject interaction
- **Check precedents**: Find similar commands and learn from them
- **Test incrementally**: Deploy and test after each significant change
- **Use interrupts**: All loops should check `shouldInterrupt`
- **Log liberally**: Use [COMMAND_NAME] prefix for easy filtering
