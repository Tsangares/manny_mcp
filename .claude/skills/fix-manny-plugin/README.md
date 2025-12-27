# Fix Manny Plugin Skill

Enhanced workflow for fixing bugs in the manny RuneLite plugin.

## Installation

This skill is automatically available in Claude Code if the `.claude/skills` directory exists.

## Usage

Invoke this skill when you need to fix a bug in the manny plugin:

```
Use the fix-manny-plugin skill to fix the BANK_OPEN command failure
```

Or simply:
```
fix-manny-plugin
```

## What It Does

Guides you through the complete 8-step code fix workflow:
1. Identify problem (logs + game state)
2. Backup files (safety)
3. Gather context (smart sectioning)
4. Spawn subagent (with validation)
5. Validate compilation
6. Check anti-patterns (11 automated rules)
7. Deploy and restart
8. Test the fix

## Features

- **Smart Sectioning**: 90% context reduction
- **Anti-Pattern Detection**: 11 automated rules
- **Safety**: Backup/rollback support
- **Validation**: Combined compilation + pattern checking
- **Performance**: 10x faster with pre-compiled patterns

## Version

**2.0.0** - Enhanced workflow with smart sectioning and automated validation

## Documentation

- Instructions: See `instructions.md` in this directory
- Quick Reference: `/home/wil/manny-mcp/QUICK_REFERENCE.md`
- Example: `/home/wil/manny-mcp/EXAMPLE_WORKFLOW.md`
- Full Details: `/home/wil/manny-mcp/IMPLEMENTATION_SUMMARY.md`
