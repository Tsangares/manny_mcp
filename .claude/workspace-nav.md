# Manny Plugin Workspace Navigation

## Quick Start: Use the Symlink!

The `manny_src` directory is a symlink to `/home/wil/Desktop/manny`. **Always use relative paths via the symlink:**

```bash
# ✅ GOOD - Relative via symlink
Read("manny_src/utility/PlayerHelpers.java")
Glob("manny_src/**/*.java")
Edit(file_path="manny_src/CLAUDE.md", ...)

# ❌ BAD - Absolute paths (harder to read, less portable)
Read("/home/wil/Desktop/manny/utility/PlayerHelpers.java")
```

## Common File Paths

### Core Plugin Files
- **Main plugin:** `manny_src/MannyPlugin.java`
- **Guidelines:** `manny_src/CLAUDE.md`
- **Command processor:** `manny_src/utility/CommandProcessor.java`
- **Command handlers:** `manny_src/utility/PlayerHelpers.java` (24K lines, use `get_section`)

### System Managers
- **Combat:** `manny_src/utility/CombatSystem.java`
- **Banking:** `manny_src/utility/BankingManager.java`
- **Interaction:** `manny_src/utility/InteractionSystem.java`
- **Pathing:** `manny_src/utility/PathingManager.java`
- **Camera:** `manny_src/utility/CameraSystem.java`
- **Game state:** `manny_src/utility/GameEngine.java`

### Helpers & Utilities
- **Thread safety:** `manny_src/utility/ClientThreadHelper.java`
- **Response writing:** `manny_src/utility/ResponseWriter.java`
- **Collision data:** `manny_src/utility/CollisionDataLoader.java`

### Command Implementations
Individual command handlers are in: `manny_src/utility/commands/*.java`

## Quick Search Patterns

### Find all commands
```python
Grep(pattern="case \"[A-Z_]+\":", path="manny_src/utility/PlayerHelpers.java")
```

### Find usages of a method
```python
Grep(pattern="interactWithNPC", path="manny_src")
```

### Find threading issues
```python
Grep(pattern="CountDownLatch|clientThread\\.invokeLater", path="manny_src")
```

### Find all event handlers
```python
Grep(pattern="@Subscribe", path="manny_src")
```

### Find specific command handler
```python
# Use MCP tool instead of manual grep
find_command(command="BANK_OPEN")
# Returns switch case + handler method with line numbers
```

## Navigation by Section (PlayerHelpers.java)

PlayerHelpers.java is 24K lines with section markers. Use `get_section` instead of reading the whole file:

```python
# List all sections
get_section(section="list")

# Get specific section
get_section(section="SKILLING OPERATIONS")
get_section(section="4")  # Or by number

# For subagents (minimize context)
get_section(section="COMBAT", summary_only=True)  # Just line ranges
```

## Build & Run Commands

### Via MCP tools (recommended)
```python
build_plugin()                    # Compile (incremental, fast)
validate_code_change()            # Compile check (safe, temp dir)
deploy_code_change()              # Full rebuild + restart signal
start_runelite()                  # Launch on display :2
stop_runelite()                   # Stop process
```

### Via Bash (if needed)
```bash
cd /home/wil/Desktop/runelite
mvn compile -pl runelite-client         # Full compile
mvn compile -pl runelite-client -o      # Offline mode
```

## Testing Patterns

### Run specific test
```bash
cd /home/wil/Desktop/runelite
mvn test -Dtest=PathingManagerTest
```

### Run all tests for a package
```bash
mvn test -Dtest=net.runelite.client.plugins.manny.*
```

## Code Change Workflow

### Standard flow
```python
# 1. Backup
backup_files(file_paths=["manny_src/utility/SomeFile.java"])

# 2. Gather context for subagent
context = prepare_code_change(
    problem_description="Description of issue",
    relevant_files=["manny_src/utility/SomeFile.java"],
    compact=True  # For large files
)

# 3. Spawn subagent to fix
Task(prompt=f"Fix issue. Context: {context}", subagent_type="general-purpose")

# 4. Validate
validate_code_change(modified_files=["manny_src/utility/SomeFile.java"])

# 5. Check anti-patterns
check_anti_patterns(file_path="manny_src/utility/SomeFile.java")

# 6. Deploy if all good
deploy_code_change(restart_after=True)

# 7. Rollback if needed
rollback_code_change()
```

## Finding Things Fast

### Where is a class defined?
```python
Glob(pattern="manny_src/**/*ClassName.java")
```

### Where is a method used?
```python
Grep(pattern="methodName\\(", path="manny_src")
```

### What commands exist?
```python
list_available_commands()  # MCP tool
# Or manually:
Grep(pattern="case \"", path="manny_src/utility/PlayerHelpers.java", output_mode="content")
```

### How is a pattern implemented?
```python
find_similar_fix(problem="NPC interaction boilerplate")
# Returns examples from codebase
```

### What are common anti-patterns?
```python
find_pattern(pattern_type="anti_pattern")
```

## Getting Context

### Manny plugin guidelines
```python
Read("manny_src/CLAUDE.md")
# Full guidelines for in-depth understanding

# Or use prepare_code_change which auto-includes condensed version
```

### Architecture overview
```python
get_plugin_context(context_type="architecture")
get_plugin_context(context_type="wrappers")
get_plugin_context(context_type="commands")
```

### Quick class overview
```python
get_class_summary(class_name="CombatSystem")
# Returns purpose, key methods, dependencies (much faster than reading full file)
```

## Editing Conventions

### Always prefer Edit over Write
```python
# ✅ GOOD - Surgical edit
Edit(
    file_path="manny_src/utility/File.java",
    old_string="old code",
    new_string="new code"
)

# ❌ BAD - Overwrites entire file (risky)
Write(file_path="manny_src/utility/File.java", content="entire file contents")
```

### Use exact indentation
When editing, preserve exact indentation from `Read` output (ignore line number prefix).

### Check anti-patterns before deploying
```python
check_anti_patterns(file_path="manny_src/utility/File.java")
# Fix any errors before deploy_code_change
```

## Common Workflows

### Add a new command
1. Read `manny_src/CLAUDE.md` for command handler pattern
2. Generate template: `generate_command_template(command_name="MY_COMMAND")`
3. Find where to add: `get_section(section="list")` to see structure
4. Add switch case and handler method via `Edit`
5. Validate: `validate_code_change()`
6. Check patterns: `check_anti_patterns()`
7. Deploy: `deploy_code_change()`

### Fix a bug
1. Observe issue via logs/game state
2. Find relevant files: `find_relevant_files(error_message="...")`
3. Backup: `backup_files()`
4. Gather context: `prepare_code_change()`
5. Spawn subagent with context
6. Validate and deploy
7. Test, rollback if needed

### Refactor legacy code
1. Find anti-patterns: `check_anti_patterns(file_path="...")`
2. Find precedents: `find_similar_fix(problem="...")`
3. Apply refactoring via `Edit`
4. Validate and deploy

### Understand a system
1. Class summary: `get_class_summary(class_name="...")`
2. Find usages: `Grep(pattern="ClassName", path="manny_src")`
3. Read architecture: `get_plugin_context(context_type="architecture")`
4. Read full file if needed: `Read("manny_src/...")`
