# Gamescope Input Issues & Role Clarity - Lessons Learned
**Date:** 2026-01-29

## The Problem

Two distinct issues:
1. Mouse events dispatched via Java AWT's `canvas.dispatchEvent()` don't reach the game under gamescope
2. Claude Code deviated from user's instructions - executed MCP tools directly instead of testing the Discord bot's LLM decision-making

## Root Cause

### Issue 1: Gamescope Input

Gamescope is a Wayland compositor that provides nested X11 via Xwayland. The manny plugin dispatches mouse events via:

```java
// manny_src/human/Mouse.java:103
MouseEvent aClick = new MouseEvent(canvas, MouseEvent.MOUSE_PRESSED, ...);
canvas.dispatchEvent(aClick);
```

The plugin logs show clicks are "verified" (the RuneLite client-side state updates), but the OSRS game server never receives the action. The `MenuOptionClicked` event fires locally, but no network packet is sent.

**Evidence from logs:**
```
[MENU-VERIFY] ✓ Click verified: 'Attack' on attempt 1
[DEBUG-NPC-AFTER CLICK] Player attacking this NPC: true  // Client thinks it's attacking
[COMBAT-PROGRESS] anim=-1 hp=-1/-1 retaliation=false     // But no animation/combat
```

### Issue 2: session_manager.get_display_for_account()

`mcptools/session_manager.py:351-356` only checked active sessions, not the persistent `account_displays` mapping:

```python
# OLD - only checked running sessions
def get_display_for_account(self, account_id: str) -> Optional[str]:
    for display, session in self.displays.items():
        if session and session.get("account") == account_id:
            return display
    return None  # Never checked account_displays!
```

This caused MCP tools to use wrong display (:2) for monkey account (assigned to :3).

### Issue 3: Role Confusion

Claude Code's purpose when "testing the Discord bot" is to **observe** the bot's LLM decisions, not execute commands directly. By calling MCP tools directly, I bypassed the exact system I was supposed to test.

## Key Lessons

### 1. Gamescope Requires Different Input Method

**What happened:** Plugin "verifies" clicks but game doesn't respond
**Why:** AWT dispatchEvent works for RuneLite's event bus but Xwayland under gamescope doesn't forward to game client
**Solution:** Need either:
- Use `invokeMenuAction` if RuneLite API supports it (bypasses mouse)
- Use Xvfb instead of gamescope for headless automation
- Investigate gamescope input forwarding configuration

### 2. Always Check Persistent Mappings

**What happened:** MCP tools used :2 instead of :3 for monkey
**Why:** `get_display_for_account()` only checked active sessions
**Solution:**
```python
# FIXED - check both active sessions AND persistent mapping
def get_display_for_account(self, account_id: str) -> Optional[str]:
    # First check active sessions
    for display, session in self.displays.items():
        if session and session.get("account") == account_id:
            return display
    # Fall back to persistent account_displays mapping
    return self.account_displays.get(account_id)
```

### 3. Respect Testing Boundaries

**What happened:** User asked to test Discord bot's LLM. I executed MCP tools directly.
**Why:** Defaulted to "fixing the problem" instead of "testing the system"
**Solution:** Added explicit guidance to `discord_bot/CLAUDE.md`:

```markdown
## CRITICAL: Claude Code's Role When Testing

When user asks to "test the Discord bot":
- DO NOT execute MCP tools directly
- Interact via Discord DM to trigger the bot's LLM
- Monitor logs, don't control gameplay
- Follow user's exact instructions (chickens, not rats)
```

## Anti-Patterns

1. **Don't assume mouse events work under nested compositors** - Always verify game actually responded
2. **Don't deviate from stated testing goals** - "Kill chickens" means chickens, not nearby rats
3. **Don't bypass the system being tested** - If testing LLM decision-making, let the LLM decide

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `tail -f logs/conversations/*.log` | Watch Discord bot LLM decisions |
| `DISPLAY=:3 xdotool getactivewindow` | Check if window has focus |
| `get_display_status()` | See all display assignments |
| Log grep: `anim=-1` | Detect "verified" clicks that didn't execute |

## Interface Gaps Identified

- [ ] Plugin needs: Alternative to mouse events (invokeMenuAction or similar)
- [ ] Plugin needs: Detection when click verifies but action doesn't execute
- [ ] MCP needs: Better error when commands succeed locally but fail server-side
- [x] CLAUDE.md updated: Role clarity for Discord bot testing

## Files Modified

| File | Change |
|------|--------|
| `mcptools/session_manager.py:351-356` | Fixed `get_display_for_account()` to check `account_displays` |
| `discord_bot/CLAUDE.md` | Added "Claude Code's Role When Testing" section |
| `start_gamescopes.sh` | Added `--backend wayland` for GNOME nested mode |
