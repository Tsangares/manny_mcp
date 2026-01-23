"""
Agentic execution loop for the Discord bot.

This implements a Claude Code-like execution loop:
OBSERVE -> THINK -> ACT -> VERIFY -> REPEAT

Key differences from the old architecture:
1. No regex classification - LLM decides what to do
2. Structured output via Pydantic schema
3. Observation-first enforcement
4. Two-phase execution (LLM decides, code executes)
"""
import json
import logging
import asyncio
from typing import Optional, Dict, Any, List, Callable
from pathlib import Path

from discord_bot.models import (
    ActionDecision,
    AgentResult,
    is_observation_tool,
    requires_observation,
)

logger = logging.getLogger("agentic_loop")


def get_agentic_system_prompt() -> str:
    """Load the agentic system prompt from CONTEXT.md."""
    context_file = Path(__file__).parent / "CONTEXT.md"
    try:
        return context_file.read_text()
    except FileNotFoundError:
        logger.warning("CONTEXT.md not found, using fallback prompt")
        return """You are an OSRS bot controller. Use the OBSERVE-ACT-VERIFY loop:
1. OBSERVE: Call observation tools first (get_game_state, check_health)
2. ACT: Execute commands with send_command
3. VERIFY: Confirm with get_game_state or get_logs

Your text is for the user. The game ONLY responds to tool calls.
"""


class AgenticLoop:
    """
    Claude Code-like execution loop using Ollama SDK + Pydantic.

    Architecture:
    1. User sends message
    2. LLM outputs ActionDecision JSON (structured output)
    3. Code validates and executes the decision
    4. Result fed back to LLM
    5. Repeat until LLM outputs "respond" action

    Key features:
    - Observation-first enforcement: rejects actions before observing
    - Structured output via Pydantic schema
    - No regex classification - LLM makes all decisions
    - Automatic JSON rescue for malformed outputs
    """

    def __init__(
        self,
        llm_client,  # LLMClient instance with chat_structured method
        tool_executor: Callable,
        max_iterations: int = 10
    ):
        self.llm = llm_client
        self.tool_executor = tool_executor
        self.max_iterations = max_iterations

    async def process(
        self,
        message: str,
        history: List[Dict] = None
    ) -> AgentResult:
        """
        Process a user message through the agentic loop.

        Args:
            message: User's message
            history: Conversation history (list of {role, content} dicts)

        Returns:
            AgentResult with response, actions taken, and metadata
        """
        history = history or []
        messages = self._build_messages(message, history)

        has_observed = False
        actions_taken = []
        iteration = 0

        for iteration in range(self.max_iterations):
            logger.info(f"Agentic loop iteration {iteration + 1}/{self.max_iterations}")

            # Get structured decision from LLM
            try:
                decision = await self._get_decision(messages)
            except Exception as e:
                logger.error(f"Failed to get decision: {e}")
                return AgentResult(
                    response=f"Error getting decision: {e}",
                    actions=actions_taken,
                    iterations=iteration + 1,
                    observed=has_observed,
                    error=str(e)
                )

            logger.info(f"Decision: {decision.action_type} - {decision.thought[:50]}...")

            # Handle "respond" action - we're done
            if decision.action_type == "respond":
                return AgentResult(
                    response=decision.response_text or "Done.",
                    actions=actions_taken,
                    iterations=iteration + 1,
                    observed=has_observed
                )

            # Get tool info
            tool_name = decision.tool_name
            tool_args = decision.tool_args or {}

            if not tool_name:
                # LLM didn't specify a tool - prompt it to be more specific
                messages.append({
                    "role": "assistant",
                    "content": json.dumps(decision.model_dump())
                })
                messages.append({
                    "role": "user",
                    "content": "You must specify a tool_name for observe/act/verify actions. Please try again."
                })
                continue

            # Check if this is an observation tool
            if is_observation_tool(tool_name):
                has_observed = True
                logger.info(f"Observation: {tool_name}")
            else:
                # For action tools, check if observation is required
                if requires_observation(tool_name) and not has_observed:
                    logger.warning(f"Action {tool_name} attempted without prior observation")
                    # Inject a hint to observe first
                    messages.append({
                        "role": "assistant",
                        "content": json.dumps(decision.model_dump())
                    })
                    messages.append({
                        "role": "user",
                        "content": (
                            "ERROR: You must observe the game state before taking actions. "
                            "Call get_game_state or check_health first to see the current situation."
                        )
                    })
                    continue

            # Execute the tool
            try:
                result = await self.tool_executor(tool_name, tool_args)
                actions_taken.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "result_summary": self._summarize_result(result)
                })
                logger.info(f"Tool result: {self._summarize_result(result)[:100]}")
            except Exception as e:
                logger.error(f"Tool execution failed: {e}")
                result = {"error": str(e)}
                actions_taken.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "error": str(e)
                })

            # Add the exchange to messages for context
            messages.append({
                "role": "assistant",
                "content": json.dumps({
                    "thought": decision.thought,
                    "action_type": decision.action_type,
                    "tool_name": tool_name,
                    "tool_args": tool_args
                })
            })
            messages.append({
                "role": "user",
                "content": f"Tool result: {json.dumps(result, default=str)[:2000]}"
            })

        # Max iterations reached
        logger.warning(f"Agentic loop hit max iterations ({self.max_iterations})")
        summary = self._summarize_actions(actions_taken)
        return AgentResult(
            response=summary or "Completed (max iterations reached)",
            actions=actions_taken,
            iterations=iteration + 1,
            observed=has_observed
        )

    def _build_messages(self, message: str, history: List[Dict]) -> List[Dict]:
        """Build the messages list for the LLM."""
        system_prompt = get_agentic_system_prompt()

        # Add JSON schema instruction
        schema_instruction = f"""
You must respond with a JSON object matching this schema:
{json.dumps(ActionDecision.model_json_schema(), indent=2)}

Example responses:
1. To observe: {{"thought": "Need to check game state first", "action_type": "observe", "tool_name": "get_game_state", "tool_args": {{"fields": ["location", "health", "inventory"]}}}}
2. To act: {{"thought": "Starting the kill loop", "action_type": "act", "tool_name": "send_command", "tool_args": {{"command": "KILL_LOOP Giant_frog none 100"}}}}
3. To respond: {{"thought": "Task complete, informing user", "action_type": "respond", "response_text": "Started killing 100 giant frogs."}}
"""

        messages = [
            {"role": "system", "content": system_prompt + "\n\n" + schema_instruction}
        ]

        # Add conversation history
        for msg in history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        # Add current message
        messages.append({"role": "user", "content": message})

        return messages

    async def _get_decision(self, messages: List[Dict]) -> ActionDecision:
        """
        Get a structured decision from the LLM.

        Uses Ollama's JSON mode with Pydantic schema validation.
        """
        try:
            # Use the LLM client's structured output method
            decision = await self.llm.chat_structured(
                messages=messages,
                response_model=ActionDecision
            )
            return decision
        except Exception as e:
            logger.error(f"Structured output failed: {e}")
            # Attempt recovery by parsing the raw response
            raise

    def _summarize_result(self, result: Any) -> str:
        """Create a compact summary of a tool result."""
        if isinstance(result, dict):
            if "error" in result:
                return f"Error: {result['error']}"
            if "state" in result:
                state = result["state"]
                parts = []
                if "location" in state:
                    loc = state["location"]
                    parts.append(f"at ({loc.get('x')}, {loc.get('y')})")
                if "health" in state:
                    hp = state["health"]
                    parts.append(f"HP {hp.get('current')}/{hp.get('max')}")
                if "inventory" in state:
                    inv = state["inventory"]
                    parts.append(f"inv {inv.get('used', 0)}/{inv.get('capacity', 28)}")
                return " | ".join(parts) if parts else "State retrieved"
            if "dispatched" in result:
                return "Command dispatched"
            if "alive" in result:
                return f"Client {'running' if result['alive'] else 'not running'}"
            if "found" in result:
                if result["found"]:
                    return f"Found: {result.get('name', 'location')} at {result.get('x')}, {result.get('y')}"
                return "Location not found"
            # Generic summary
            return str(result)[:200]
        return str(result)[:200]

    def _summarize_actions(self, actions: List[Dict]) -> str:
        """Generate a summary of actions taken."""
        if not actions:
            return "No actions taken."

        summaries = []
        for action in actions:
            tool = action.get("tool", "unknown")
            if "error" in action:
                summaries.append(f"- {tool}: ERROR - {action['error']}")
            else:
                result = action.get("result_summary", "done")
                if tool == "send_command":
                    cmd = action.get("args", {}).get("command", "")
                    summaries.append(f"- Executed: {cmd[:50]}")
                else:
                    summaries.append(f"- {tool}: {result[:50]}")

        return "Actions taken:\n" + "\n".join(summaries)


class AgenticLoopWithRecovery(AgenticLoop):
    """
    AgenticLoop with fallback recovery strategies.

    Extends AgenticLoop with:
    - JSON-as-text rescue
    - Infinite loop detection
    - Fallback to intent parser
    """

    def __init__(
        self,
        llm_client,
        tool_executor: Callable,
        fallback_handler: Optional[Callable] = None,
        max_iterations: int = 10
    ):
        super().__init__(llm_client, tool_executor, max_iterations)
        self.fallback_handler = fallback_handler
        self._stuck_counter = 0
        self._last_action = None

    async def process(
        self,
        message: str,
        history: List[Dict] = None
    ) -> AgentResult:
        """Process with recovery strategies."""
        try:
            result = await super().process(message, history)

            # Check for stuck state (same action repeated)
            if result.actions:
                current_action = result.actions[-1].get("tool")
                if current_action == self._last_action:
                    self._stuck_counter += 1
                else:
                    self._stuck_counter = 0
                self._last_action = current_action

                if self._stuck_counter >= 3:
                    logger.warning("Detected stuck state, breaking loop")
                    result.response = "Detected loop. " + result.response
                    self._stuck_counter = 0

            return result

        except Exception as e:
            logger.error(f"Agentic loop failed: {e}")

            # Try fallback handler if available
            if self.fallback_handler:
                logger.info("Attempting fallback handler")
                try:
                    fallback_response = await self.fallback_handler(message)
                    return AgentResult(
                        response=fallback_response,
                        actions=[{"fallback": True}],
                        iterations=0,
                        observed=False,
                        error=f"Used fallback due to: {e}"
                    )
                except Exception as fe:
                    logger.error(f"Fallback also failed: {fe}")

            return AgentResult(
                response=f"Error: {e}",
                actions=[],
                iterations=0,
                observed=False,
                error=str(e)
            )
