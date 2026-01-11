# Autonomy Configuration - Quick Reference

This document explains the autonomous decision-making setup for Claude Code in this project.

## What Was Configured

### 1. Global Settings (`~/.claude/settings.json`)

```json
{
  "model": "opus",                          // Most capable model
  "alwaysThinkingEnabled": true,            // Better reasoning
  "permissions": {
    "defaultMode": "acceptEdits",           // Auto-accept file edits
    "allow": [...],                         // Whitelist safe operations
    "deny": [...]                           // Blacklist dangerous operations
  },
  "hooks": {
    "PermissionRequest": [...]              // Auto-approve safe edits
  }
}
```

**Effect:** Claude will automatically accept file edits without asking, unless they're to sensitive files.

### 2. Decision-Maker Agent (`.claude/agents/decision-maker.md`)

A specialized subagent that makes technical decisions autonomously:
- Chooses implementation approaches
- Makes architectural decisions
- Approves refactoring
- Handles trade-offs
- Prioritizes tasks

**When invoked:** Makes decisions and implements them immediately without asking user.

### 3. Project CLAUDE.md Updates

Added "Autonomy Guidelines" section that instructs Claude to:
- Make technical decisions independently
- Use the decision-maker agent instead of AskUserQuestion
- Only ask about fundamental requirement ambiguities
- Be decisive, not deferential

## How This Works in Practice

### Before (Without Autonomy)

```
Claude: "I found the issue with the hopper interaction. Should I:
         A) Fix USE_ITEM_ON_OBJECT command
         B) Add a new MILL_GRAIN command
         C) Use widget click approach

         Which would you prefer?"

User: "2"

Claude: "OK, implementing option B..."
```

**Problems:**
- Interrupts user workflow
- User has to make technical decisions
- Slows down progress

### After (With Autonomy)

```
Claude: "I found the issue with the hopper interaction.

         Analysis:
         - USE_ITEM_ON_OBJECT has a bug in inventory item handling
         - Fixing it will solve this and future similar issues
         - More general solution than a quest-specific command

         DECISION: Fixing USE_ITEM_ON_OBJECT

         Delegating to decision-maker agent..."

Decision-Maker: "Implementing the fix in PlayerHelpers.java:1247.
                 Fixed by adding inventory item validation.
                 Testing with hopper interaction...
                 Success! Hopper now accepts grain properly."
```

**Benefits:**
- No user interruption
- Claude makes informed technical decision
- Faster implementation
- Clear reasoning documented

## When Claude Will Still Ask You

Claude will only interrupt you for:

1. **Fundamental requirement ambiguities**
   - "Add authentication" → OAuth? JWT? Session-based?
   - "Optimize performance" → What's the performance target?

2. **External system decisions**
   - "Should I deploy to production?" (affects external systems)
   - "Should I purchase this paid API?" (business decision)

3. **Security policies**
   - "Should I commit credentials?" (NO - but you control this)

## How to Use the Decision-Maker Agent Manually

If you want Claude to make a specific decision autonomously:

```bash
# In Claude Code chat
"Use the decision-maker agent to figure out the best approach
 for fixing the banking system bug, then implement it."
```

Claude will delegate to the decision-maker agent, which will:
1. Analyze the options
2. Choose the best approach
3. Implement it immediately
4. Report back the result

## Reverting to Manual Mode

If you want Claude to ask you about decisions again:

1. **Temporarily** (single session):
   ```bash
   claude --model sonnet  # Sonnet is less autonomous than Opus
   ```

2. **Permanently**:
   Edit `~/.claude/settings.json`:
   ```json
   {
     "model": "sonnet",
     "permissions": {
       "defaultMode": "default"  // Back to asking for everything
     }
   }
   ```

## Testing the Setup

Try this command to see autonomous decision-making in action:

```bash
"There's a bug in the USE_ITEM_ON_OBJECT command.
 It's not working with the hopper. Fix it."
```

**Expected behavior:**
- Claude analyzes the issue
- Makes a decision about the fix approach
- Implements it without asking
- Reports the result

**Old behavior (before autonomy):**
- Claude would ask "Should I use approach A, B, or C?"

## Advanced: Creating More Specialized Agents

You can create additional autonomous agents for specific domains:

```bash
# Create a new agent
mkdir -p .claude/agents
cat > .claude/agents/performance-optimizer.md << 'EOF'
---
name: performance-optimizer
description: PROACTIVELY optimize code performance. Use automatically when performance issues detected.
model: opus
---

You autonomously improve performance without asking.
When invoked, profile the code, identify bottlenecks, and optimize them.
EOF
```

Now Claude will automatically invoke this agent when it detects performance issues.

## Monitoring Autonomous Decisions

Claude will still log what it's doing. You can review decisions by:

1. **Reading chat history** - All decisions are documented
2. **Git commits** - Changes are visible in diffs
3. **Test results** - Autonomous changes are validated by tests

## Tips for Maximum Effectiveness

1. **Trust the system** - Let Claude make technical decisions
2. **Provide high-level goals** - "Fix the quest system" not "Change line 42"
3. **Review outcomes, not plans** - Check what was implemented, not how
4. **Course-correct as needed** - If a decision was wrong, just tell Claude to fix it

## Troubleshooting

### "Claude is still asking me questions"

Check:
- Is the question about fundamental requirements? (Expected)
- Is it a technical decision? (Use: "Delegate to decision-maker agent")
- Are you on a new Claude Code session? (Settings persist, but each session is fresh)

### "Claude made a bad decision"

Just tell it:
```
"That approach wasn't quite right. The issue is actually X.
 Fix it by doing Y instead."
```

Claude will learn from the feedback and adjust.

### "I want to control a specific type of decision"

Edit `.claude/agents/decision-maker.md` to add constraints:

```markdown
**Exception: Always ask user about:**
- Database schema changes
- API contract changes
- Dependency upgrades
```

## Summary

**Configuration changes:**
- ✅ Opus model enabled (better decisions)
- ✅ Auto-accept edits permission mode
- ✅ Auto-approval hooks for safe operations
- ✅ Decision-maker agent created
- ✅ CLAUDE.md updated with autonomy guidelines

**Expected behavior:**
- Claude makes technical decisions autonomously
- Only interrupts for fundamental ambiguities
- Delegates complex decisions to specialized agent
- Documents reasoning clearly

**Your role:**
- Provide high-level goals
- Review outcomes
- Course-correct when needed
- Trust the autonomous system

**Enjoy uninterrupted, autonomous Claude Code! 🚀**
