"""
Recovery and fallback strategies for the agentic loop.

Handles:
1. JSON-as-text rescue (parse and execute JSON tool calls from text)
2. Infinite loop detection
3. Circuit breaker (pause on repeated failures)
4. Fallback to regex-based intent parser
"""
import json
import re
import logging
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger("recovery")


# Valid tools that can be rescued from JSON-as-text
VALID_TOOLS = {
    "send_command", "get_game_state", "lookup_location", "check_health",
    "get_screenshot", "start_runelite", "stop_runelite", "restart_runelite",
    "auto_reconnect", "run_routine", "list_routines", "get_logs",
    "switch_account", "list_accounts", "list_plugin_commands",
    "get_command_help", "queue_on_level"
}


@dataclass
class RecoveryResult:
    """Result of a recovery attempt."""
    success: bool
    response: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    method: str = "none"  # none, json_rescue, regex_fallback, circuit_breaker


class JSONRescue:
    """
    Rescue JSON tool calls that the LLM outputs as text.

    Handles patterns like:
    - {"name": "send_command", "arguments": {"command": "KILL_LOOP..."}}
    - ```json\n{"name": "send_command"...}```
    - Multiple JSON objects in response
    """

    @staticmethod
    def extract_tool_calls(text: str) -> List[Dict[str, Any]]:
        """
        Extract tool calls from text that contains JSON.

        Returns list of {name, arguments} dicts for valid tool calls.
        """
        tool_calls = []

        # Pattern 1: Try to parse entire text as JSON
        try:
            data = json.loads(text.strip())
            if JSONRescue._is_valid_tool_call(data):
                tool_calls.append(data)
                return tool_calls
        except json.JSONDecodeError:
            pass

        # Pattern 2: Look for JSON in code blocks
        code_block_pattern = r'```(?:json)?\s*(\{[\s\S]*?\})\s*```'
        for match in re.finditer(code_block_pattern, text):
            try:
                data = json.loads(match.group(1))
                if JSONRescue._is_valid_tool_call(data):
                    tool_calls.append(data)
            except json.JSONDecodeError:
                continue

        # Pattern 3: Look for bare JSON objects
        if not tool_calls:
            json_pattern = r'\{[^{}]*"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{[^{}]*\}[^{}]*\}'
            for match in re.finditer(json_pattern, text):
                try:
                    data = json.loads(match.group(0))
                    if JSONRescue._is_valid_tool_call(data):
                        tool_calls.append(data)
                except json.JSONDecodeError:
                    continue

        return tool_calls

    @staticmethod
    def _is_valid_tool_call(data: Dict) -> bool:
        """Check if data represents a valid tool call."""
        if not isinstance(data, dict):
            return False
        name = data.get("name")
        arguments = data.get("arguments")
        return (
            name in VALID_TOOLS
            and isinstance(arguments, dict)
        )

    @staticmethod
    async def rescue_and_execute(
        text: str,
        tool_executor: Callable
    ) -> RecoveryResult:
        """
        Find JSON tool calls in text and execute them.

        Returns RecoveryResult with execution results.
        """
        tool_calls = JSONRescue.extract_tool_calls(text)

        if not tool_calls:
            return RecoveryResult(success=False, method="json_rescue")

        executed = []
        for call in tool_calls:
            name = call["name"]
            args = call["arguments"]
            try:
                result = await tool_executor(name, args)
                executed.append({
                    "tool": name,
                    "args": args,
                    "result": result,
                    "success": True
                })
                logger.info(f"Rescued JSON tool call: {name}({args})")
            except Exception as e:
                executed.append({
                    "tool": name,
                    "args": args,
                    "error": str(e),
                    "success": False
                })
                logger.warning(f"Rescued tool call failed: {name} - {e}")

        return RecoveryResult(
            success=len(executed) > 0,
            response="Done." if any(e["success"] for e in executed) else None,
            tool_calls=executed,
            method="json_rescue"
        )


class CircuitBreaker:
    """
    Circuit breaker to prevent repeated failures.

    Opens (stops requests) after N failures within a time window.
    Half-opens (allows limited requests) after a cooldown period.
    Closes (normal operation) after successful requests.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        window_seconds: int = 60,
        cooldown_seconds: int = 30
    ):
        self.failure_threshold = failure_threshold
        self.window = timedelta(seconds=window_seconds)
        self.cooldown = timedelta(seconds=cooldown_seconds)
        self.failures: List[datetime] = []
        self.state = "closed"  # closed, open, half-open
        self.opened_at: Optional[datetime] = None
        self.half_open_attempts = 0

    def record_failure(self):
        """Record a failure."""
        now = datetime.now()
        self.failures.append(now)

        # Remove old failures outside window
        cutoff = now - self.window
        self.failures = [f for f in self.failures if f > cutoff]

        # Check if we should open
        if len(self.failures) >= self.failure_threshold:
            self.state = "open"
            self.opened_at = now
            logger.warning(f"Circuit breaker OPEN after {len(self.failures)} failures")

    def record_success(self):
        """Record a success."""
        if self.state == "half-open":
            self.state = "closed"
            self.failures.clear()
            logger.info("Circuit breaker CLOSED after success")

    def allow_request(self) -> bool:
        """Check if requests are allowed."""
        if self.state == "closed":
            return True

        if self.state == "open":
            # Check if cooldown has passed
            if datetime.now() - self.opened_at > self.cooldown:
                self.state = "half-open"
                self.half_open_attempts = 0
                logger.info("Circuit breaker HALF-OPEN, allowing limited requests")
                return True
            return False

        if self.state == "half-open":
            # Allow limited requests in half-open state
            if self.half_open_attempts < 2:
                self.half_open_attempts += 1
                return True
            return False

        return False

    def get_status(self) -> Dict[str, Any]:
        """Get current circuit breaker status."""
        return {
            "state": self.state,
            "recent_failures": len(self.failures),
            "threshold": self.failure_threshold,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None
        }


class RegexFallback:
    """
    Fallback to regex-based command extraction.

    Used when the LLM completely fails to produce valid output.
    """

    # Command patterns to extract
    PATTERNS = {
        "kill_loop": [
            r'(?:kill|grind|attack)\s+(?:loop\s+)?(\w+(?:_\w+)?)\s*(\d+)?',
            r'KILL_LOOP\s+(\w+)\s+(\w+)(?:\s+(\d+))?',
        ],
        "goto": [
            r'(?:go\s+to|goto|travel\s+to)\s+(\w+(?:\s+\w+)?)',
            r'GOTO\s+(\d+)\s+(\d+)(?:\s+(\d+))?',
        ],
        "stop": [
            r'^stop\b',
            r'\bstop\s+(?:everything|all|current)',
        ],
        "switch_style": [
            r'switch\s+(?:combat\s+)?style\s+(?:to\s+)?(\w+)',
            r'SWITCH_COMBAT_STYLE\s+(\w+)',
        ],
        "tab_open": [
            r'open\s+(inventory|combat|skills|equipment|prayer|magic|quest)',
            r'TAB_OPEN\s+(\w+)',
        ],
    }

    @staticmethod
    def extract_command(message: str) -> Optional[str]:
        """
        Extract a command from the message using regex patterns.

        Returns a plugin command string or None.
        """
        message_lower = message.lower().strip()
        message_original = message.strip()

        # Check for stop
        for pattern in RegexFallback.PATTERNS["stop"]:
            if re.search(pattern, message_lower):
                return "STOP"

        # Check for switch combat style
        for pattern in RegexFallback.PATTERNS["switch_style"]:
            match = re.search(pattern, message_lower)
            if match:
                style = match.group(1).capitalize()
                style_map = {
                    "Attack": "Accurate",
                    "Strength": "Aggressive",
                    "Defence": "Defensive",
                    "Controlled": "Controlled",
                    "Accurate": "Accurate",
                    "Aggressive": "Aggressive",
                    "Defensive": "Defensive",
                }
                return f"SWITCH_COMBAT_STYLE {style_map.get(style, style)}"

        # Check for tab open
        for pattern in RegexFallback.PATTERNS["tab_open"]:
            match = re.search(pattern, message_lower)
            if match:
                tab = match.group(1).capitalize()
                return f"TAB_OPEN {tab}"

        # Check for kill loop
        for pattern in RegexFallback.PATTERNS["kill_loop"]:
            match = re.search(pattern, message_original, re.IGNORECASE)
            if match:
                groups = match.groups()
                target = groups[0].replace(" ", "_").capitalize()

                # Handle "giant frog" -> "Giant_frog"
                if "giant" in message_lower and "frog" in message_lower:
                    target = "Giant_frog"

                count = groups[1] if len(groups) > 1 and groups[1] else "100"
                return f"KILL_LOOP {target} none {count}"

        # Check for goto with coordinates first
        coord_pattern = r'(?:go\s*to|goto)\s+(\d+)\s+(\d+)(?:\s+(\d+))?'
        coord_match = re.search(coord_pattern, message_lower)
        if coord_match:
            x, y = coord_match.group(1), coord_match.group(2)
            plane = coord_match.group(3) if coord_match.group(3) else "0"
            return f"GOTO {x} {y} {plane}"

        # Check for goto with named location
        for pattern in RegexFallback.PATTERNS["goto"]:
            match = re.search(pattern, message_lower)
            if match:
                groups = match.groups()
                if groups[0] and not groups[0].isdigit():
                    # Named location - will need lookup
                    return f"LOOKUP:{groups[0]}"  # Signal to lookup location

        return None

    @staticmethod
    async def execute_fallback(
        message: str,
        tool_executor: Callable,
        lookup_and_goto: Optional[Callable] = None
    ) -> RecoveryResult:
        """
        Extract command and execute using fallback patterns.
        """
        command = RegexFallback.extract_command(message)

        if not command:
            return RecoveryResult(success=False, method="regex_fallback")

        # Handle location lookup
        if command.startswith("LOOKUP:"):
            location = command[7:]
            if lookup_and_goto:
                try:
                    result = await lookup_and_goto(location)
                    return RecoveryResult(
                        success=True,
                        response=f"Traveling to {location}",
                        tool_calls=[{"tool": "lookup_and_goto", "location": location}],
                        method="regex_fallback"
                    )
                except Exception as e:
                    logger.warning(f"Lookup fallback failed: {e}")
            return RecoveryResult(success=False, method="regex_fallback")

        # Execute the extracted command
        try:
            result = await tool_executor("send_command", {"command": command})
            logger.info(f"Regex fallback executed: {command}")
            return RecoveryResult(
                success=True,
                response=f"Executed: {command}",
                tool_calls=[{
                    "tool": "send_command",
                    "args": {"command": command},
                    "result": result
                }],
                method="regex_fallback"
            )
        except Exception as e:
            logger.warning(f"Regex fallback execution failed: {e}")
            return RecoveryResult(
                success=False,
                response=str(e),
                method="regex_fallback"
            )


class RecoveryManager:
    """
    Coordinates all recovery strategies.

    Order of attempts:
    1. JSON rescue (if response contains JSON)
    2. Regex fallback (if message has extractable command)
    3. Circuit breaker check (pause if too many failures)
    """

    def __init__(self, tool_executor: Callable):
        self.tool_executor = tool_executor
        self.circuit_breaker = CircuitBreaker()

    async def attempt_recovery(
        self,
        message: str,
        llm_response: str,
        lookup_and_goto: Optional[Callable] = None
    ) -> RecoveryResult:
        """
        Attempt to recover from a failed or incomplete LLM response.

        Args:
            message: Original user message
            llm_response: The LLM's response that may need recovery
            lookup_and_goto: Optional function for location lookup + goto

        Returns:
            RecoveryResult with the outcome
        """
        # Check circuit breaker
        if not self.circuit_breaker.allow_request():
            return RecoveryResult(
                success=False,
                response="Too many recent failures. Please try again shortly.",
                method="circuit_breaker"
            )

        # Try JSON rescue first
        if "{" in llm_response and "name" in llm_response:
            result = await JSONRescue.rescue_and_execute(
                llm_response, self.tool_executor
            )
            if result.success:
                self.circuit_breaker.record_success()
                return result

        # Try regex fallback
        result = await RegexFallback.execute_fallback(
            message, self.tool_executor, lookup_and_goto
        )
        if result.success:
            self.circuit_breaker.record_success()
            return result

        # All recovery failed
        self.circuit_breaker.record_failure()
        return RecoveryResult(
            success=False,
            method="none"
        )

    def get_status(self) -> Dict[str, Any]:
        """Get recovery manager status."""
        return {
            "circuit_breaker": self.circuit_breaker.get_status()
        }
