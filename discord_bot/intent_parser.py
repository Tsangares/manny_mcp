"""
Intent Parser - Separates understanding from execution.

Instead of hoping the LLM calls tools, we:
1. Ask LLM to output ONLY structured intent
2. Parse the intent ourselves
3. Execute commands deterministically

This removes the unreliable tool-calling behavior entirely.
"""
import re
import json
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("intent_parser")


class IntentType(Enum):
    KILL_LOOP = "kill_loop"
    STOP = "stop"
    GOTO = "goto"
    BANK = "bank"
    FISH = "fish"
    STATUS = "status"
    SWITCH_STYLE = "switch_style"
    TAB_OPEN = "tab_open"
    UNKNOWN = "unknown"
    CONVERSATION = "conversation"


@dataclass
class ParsedIntent:
    intent: IntentType
    command: Optional[str] = None  # The actual command to send
    params: Dict[str, Any] = None
    confidence: float = 1.0
    raw_text: str = ""

    def __post_init__(self):
        if self.params is None:
            self.params = {}


# Regex patterns for direct parsing (no LLM needed)
INTENT_PATTERNS = [
    # Kill/Combat
    (r'kill\s*(?:loop)?\s+(\d+)?\s*(\w+)', IntentType.KILL_LOOP,
     lambda m: {"npc": m.group(2), "count": m.group(1) or "100"}),

    (r'grind\s+(?:on\s+)?(\w+)(?:\s+(\d+))?', IntentType.KILL_LOOP,
     lambda m: {"npc": m.group(1), "count": m.group(2) or "100"}),

    (r'attack\s+(\w+)', IntentType.KILL_LOOP,
     lambda m: {"npc": m.group(1), "count": "1"}),

    # Stop
    (r'^stop$|^cancel$|^halt$', IntentType.STOP, lambda m: {}),

    # Combat style
    (r'(?:switch|change)\s+(?:combat\s+)?(?:style|attack)\s+(?:to\s+)?(\w+)', IntentType.SWITCH_STYLE,
     lambda m: {"style": m.group(1)}),

    # Banking
    (r'open\s+bank|bank\s+open', IntentType.BANK, lambda m: {"action": "open"}),
    (r'deposit\s+all|bank\s+all', IntentType.BANK, lambda m: {"action": "deposit_all"}),

    # Fishing
    (r'fish\s+(?:at\s+)?(\w+)?', IntentType.FISH, lambda m: {"location": m.group(1) or "draynor"}),

    # Tabs
    (r'open\s+(inventory|equipment|combat|skills|prayer|magic)', IntentType.TAB_OPEN,
     lambda m: {"tab": m.group(1)}),

    # Status
    (r'status|stats|levels?|health|where|location', IntentType.STATUS, lambda m: {}),
]


def parse_intent_regex(text: str) -> Optional[ParsedIntent]:
    """Try to parse intent using regex patterns (fast, reliable)."""
    text_lower = text.lower().strip()

    for pattern, intent_type, param_extractor in INTENT_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            params = param_extractor(match)
            command = build_command(intent_type, params)
            return ParsedIntent(
                intent=intent_type,
                command=command,
                params=params,
                confidence=0.9,
                raw_text=text
            )

    return None


def build_command(intent: IntentType, params: Dict) -> Optional[str]:
    """Build the actual command string from parsed intent."""
    if intent == IntentType.KILL_LOOP:
        npc = params.get("npc", "").replace(" ", "_")
        # Capitalize properly: giant_frog -> Giant_frog
        npc = "_".join(word.capitalize() for word in npc.split("_"))
        count = params.get("count", "100")
        food = params.get("food", "none")
        return f"KILL_LOOP {npc} {food} {count}"

    elif intent == IntentType.STOP:
        return "STOP"

    elif intent == IntentType.SWITCH_STYLE:
        style = params.get("style", "").capitalize()
        return f"SWITCH_COMBAT_STYLE {style}"

    elif intent == IntentType.BANK:
        action = params.get("action", "open")
        if action == "open":
            return "BANK_OPEN"
        elif action == "deposit_all":
            return "BANK_DEPOSIT_ALL"

    elif intent == IntentType.FISH:
        location = params.get("location", "draynor")
        if "draynor" in location.lower():
            return "FISH_DRAYNOR_LOOP"
        return "FISH"

    elif intent == IntentType.TAB_OPEN:
        tab = params.get("tab", "inventory")
        return f"TAB_OPEN {tab}"

    return None


class IntentExecutor:
    """
    Executes parsed intents deterministically.

    This replaces unreliable LLM tool calling with reliable execution.
    """

    def __init__(self, send_command_func, get_state_func):
        self._send_command = send_command_func
        self._get_state = get_state_func

    async def execute(self, intent: ParsedIntent) -> Dict[str, Any]:
        """Execute a parsed intent and return result."""
        if intent.intent == IntentType.STATUS:
            # Get state instead of sending command
            state = await self._get_state({"fields": ["location", "health", "skills", "inventory"]})
            return {"success": True, "type": "status", "state": state}

        elif intent.intent == IntentType.CONVERSATION:
            return {"success": True, "type": "conversation", "needs_llm": True}

        elif intent.intent == IntentType.UNKNOWN:
            return {"success": False, "type": "unknown", "needs_llm": True}

        elif intent.command:
            result = await self._send_command({"command": intent.command})
            return {
                "success": True,
                "type": "command",
                "command": intent.command,
                "result": result
            }

        return {"success": False, "error": "No command generated"}


def format_response(intent: ParsedIntent, result: Dict) -> str:
    """Format a human-readable response for the executed intent."""
    if result.get("type") == "command":
        cmd = result.get("command", "")
        if "KILL_LOOP" in cmd:
            parts = cmd.split()
            npc = parts[1] if len(parts) > 1 else "target"
            count = parts[3] if len(parts) > 3 else "100"
            return f"✅ Killing {count} {npc.replace('_', ' ')}"
        elif "SWITCH_COMBAT_STYLE" in cmd:
            style = cmd.split()[-1] if cmd.split() else "style"
            return f"✅ Switched to {style} combat style"
        elif "TAB_OPEN" in cmd:
            tab = cmd.split()[-1] if cmd.split() else "tab"
            return f"✅ Opened {tab} tab"
        elif "STOP" in cmd:
            return "✅ Stopped current activity"
        elif "BANK" in cmd:
            return f"✅ {cmd.replace('_', ' ').title()}"
        elif "FISH" in cmd:
            return f"✅ Started fishing"
        else:
            return f"✅ Sent: `{cmd}`"

    elif result.get("type") == "status":
        state = result.get("state", {}).get("state", {})
        loc = state.get("location", {})
        health = state.get("health", {})
        return f"📍 Location: ({loc.get('x')}, {loc.get('y')})\n❤️ Health: {health.get('current')}/{health.get('max')}"

    return "Done."
