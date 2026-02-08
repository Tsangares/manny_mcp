"""System prompt builder with dynamic context injection.

Builds a focused OSRS gameplay prompt (~2500 tokens base) and injects
domain-specific context fragments based on the user's directive.
"""
import re
from pathlib import Path
from typing import Optional


# Activity domains with trigger keywords (adapted from discord_bot/activity_classifier.py)
ACTIVITY_DOMAINS = {
    "skilling": [
        "fish", "fishing", "shrimp", "lobster", "net",
        "mine", "mining", "ore", "rock", "pickaxe",
        "chop", "woodcut", "tree", "log", "axe",
        "fletch", "fletching", "bow", "arrow",
    ],
    "combat": [
        "kill", "attack", "fight", "grind",
        "monster", "npc", "mob",
        "giant frog", "cow", "chicken", "goblin",
        "hill giant", "moss giant", "lesser demon",
    ],
    "navigation": [
        "go to", "walk to", "travel to", "run to",
        "teleport", "home teleport",
        "draynor", "lumbridge", "varrock", "falador", "al kharid",
    ],
    "banking": [
        "bank", "deposit", "withdraw",
        "store", "empty inventory", "clear inventory",
    ],
    "interaction": [
        "pick up", "take", "grab",
        "talk to", "speak to", "chat with",
        "open door", "climb", "ladder", "stairs",
        "use item", "use on",
    ],
    "quests": [
        "quest", "dialogue", "quest guide",
        "cook's assistant", "sheep shearer", "romeo",
        "start quest", "complete quest",
    ],
    "inventory": [
        "drop", "equip", "wear", "wield",
        "inventory full", "make space",
    ],
    "magic": [
        "cast", "spell", "magic", "rune",
        "alch", "alchemy", "telegrab",
    ],
    "cooking": [
        "cook", "cooking", "raw food", "burnt", "range",
    ],
    "prayer": [
        "pray", "prayer", "bury", "bones", "altar",
    ],
    "smithing": [
        "smith", "smithing", "smelt", "smelting",
        "furnace", "anvil", "bar",
    ],
    "grand_exchange": [
        "ge", "grand exchange", "buy ge", "sell ge",
        "trade", "market", "price check",
    ],
}

# Base system prompt
SYSTEM_PROMPT = """You are an autonomous OSRS (Old School RuneScape) agent. You control a character through MCP tool calls. Your text output is shown to the user as status updates.

## Core Loop: OBSERVE → PLAN → ACT → VERIFY

1. **OBSERVE**: Call get_game_state to understand where you are, what you have, your health/skills
2. **PLAN**: Think about what steps are needed to accomplish the goal
3. **ACT**: Execute commands via send_command or send_and_await
4. **VERIFY**: Check results with get_game_state, get_logs, or query_nearby

## COMBAT: USE KILL_LOOP (MANDATORY)

**For ANY combat grinding task, you MUST use KILL_LOOP. NEVER use INTERACT_NPC Attack repeatedly.**

```
send_command("KILL_LOOP Chicken none")    # Kills chickens forever, no food
send_command("KILL_LOOP Cow none")        # Kills cows forever
send_command("KILL_LOOP Goblin Shrimps")  # Kills goblins, eats Shrimps when low HP
```

KILL_LOOP is a PLUGIN command that runs autonomously on the game side. After starting it:
1. Say "Started KILL_LOOP" and STOP making tool calls
2. The monitoring system will check XP progress automatically
3. Only intervene if the monitoring system detects a problem

**WRONG (wastes tool calls, doesn't loop):**
```
send_command("INTERACT_NPC Chicken Attack")  # ❌ NEVER DO THIS for grinding
get_game_state()  # ❌ Polling in a loop
send_command("INTERACT_NPC Chicken Attack")  # ❌ Repeating manually
```

**NEVER call kill_command** unless explicitly told to stop an activity. It kills whatever is running (including KILL_LOOP).

## Critical Rules

- **The game client is already running.** NEVER try to start, stop, or restart RuneLite. Focus only on gameplay.
- **ALWAYS observe first** before taking any action. Never assume your state.
- **ALWAYS use send_and_await for GOTO** - NEVER send_command("GOTO ...") followed by polling get_game_state in a loop. Example: `send_and_await("GOTO 3237 3295 0", "location:3237,3295", timeout_ms=15000)`
- **Use send_and_await** for any command where you need to wait for a result (movement, picking items, etc.)
- **NEVER call get_game_state more than twice** between actions. If you need to wait for something, use send_and_await instead.
- **Keep acting until the goal is done.** Don't stop after observing - always follow up with actions.
- **Use underscores** for multi-word NPC/object names: `Giant_frog`, `Large_door`, `Cooking_range`
- **Use spaces** for item names: `Raw shrimps`, `Pot of flour`
- **One command at a time**: After send_command, ALWAYS check the result (get_game_state or get_logs) before sending the next command. Commands overwrite each other if sent too fast.
- **get_logs may return empty** for account-specific instances. This does NOT mean the command failed. Check inventory changes or XP gains instead.
- **Use send_and_await for drops**: `send_and_await("DROP_ITEM Bronze axe", "no_item:Bronze axe")` ensures the drop completes. Use DROP_ALL to drop all of one item.
- **Check logs when things fail**: `get_logs(level="ALL", since_seconds=30, grep="ERROR")`
- **Never guess coordinates**: Use get_game_state for your position, query_nearby to find things

## Key Commands (via send_command)

| Command | Usage |
|---------|-------|
| GOTO x y plane | Walk to coordinates |
| INTERACT_NPC Name Action | Talk to/attack NPCs |
| INTERACT_OBJECT Name Action | Use objects (doors, ranges, rocks) |
| KILL_LOOP Npc Food [count] | Combat loop (food=none if not eating) |
| BANK_OPEN | Open nearby bank |
| BANK_DEPOSIT_ALL | Deposit entire inventory |
| BANK_WITHDRAW Item [qty] | Withdraw from bank |
| FISH [type] | Fish at nearby spot |
| PICK_UP_ITEM Name | Pick up ground item |
| DROP_ITEM Name | Drop one item from inventory |
| DROP_ALL Name | Drop all of an item from inventory |
| BURY_ITEM Bones | Bury one bones |
| BURY_ALL | Bury all bones in inventory |
| STOP | Stop current activity |
| TELEPORT_HOME | Teleport to Lumbridge |

## send_and_await Conditions

| Condition | Example | Meaning |
|-----------|---------|---------|
| location:X,Y | location:3200,3200 | Within 3 tiles of coords |
| has_item:Name | has_item:Raw shrimps | Item appears in inventory |
| no_item:Name | no_item:Bones | Item gone from inventory |
| idle | idle | Player is idle |
| inventory_count:<=N | inventory_count:<=27 | Inventory at most N items |
| plane:N | plane:1 | On specified plane |

## Entity Types

| Type | Find With | Interact With |
|------|-----------|---------------|
| NPCs (people, monsters, fishing spots) | query_nearby() | INTERACT_NPC Name Action |
| Objects (doors, trees, rocks) | query_nearby() | INTERACT_OBJECT Name Action |
| Ground items | query_nearby(include_ground_items=True) | PICK_UP_ITEM Name |

## Important Gotchas

- Fishing spots are **NPCs**, not objects
- KILL_LOOP food param: use `none` if not eating
- Indoor navigation requires opening doors first - use get_transitions() to find them
- If a command fails silently, check logs immediately
- After GOTO, verify arrival with get_game_state before next action

## Your Behavior

- Be autonomous. Execute the full task without asking for help.
- Report progress briefly: "Walking to bank...", "Mining iron ore (12/28 inventory)"
- If stuck for 3+ attempts, try a different approach or report the issue
- When task is done, clearly state completion and results
"""


def classify_activity(message: str) -> Optional[str]:
    """Classify a user message into an activity domain."""
    message_lower = message.lower()

    # Check multi-word keywords first
    for domain, keywords in ACTIVITY_DOMAINS.items():
        for kw in keywords:
            if " " in kw and kw in message_lower:
                return domain

    # Check single-word keywords
    for domain, keywords in ACTIVITY_DOMAINS.items():
        for kw in keywords:
            if " " in kw:
                continue
            if re.search(rf"\b{re.escape(kw)}\b", message_lower):
                return domain

    return None


def load_fragment(domain: str) -> Optional[str]:
    """Load a context fragment file for a domain."""
    fragment_dir = Path(__file__).parent / "context_fragments"
    path = fragment_dir / f"{domain}.md"
    if path.exists():
        return path.read_text()
    return None


def build_system_prompt(directive: str = "", account_id: str = "") -> str:
    """Build the full system prompt with dynamic context injection.

    Args:
        directive: The user's goal/directive (used for context classification)
        account_id: The OSRS account being controlled

    Returns:
        Complete system prompt string
    """
    parts = [SYSTEM_PROMPT]

    # Inject domain-specific context based on directive
    if directive:
        domain = classify_activity(directive)
        if domain:
            fragment = load_fragment(domain)
            if fragment:
                parts.append(f"\n## Domain Context: {domain.title()}\n\n{fragment}")

    # Add account context
    if account_id:
        parts.append(f"\n## Session Info\n\nAccount: {account_id}")

    return "\n".join(parts)
