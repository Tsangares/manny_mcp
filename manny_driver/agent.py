"""Core agent loop: LLM + tool execution cycle.

Three phases:
1. PLANNING (1-5 tool calls): Observe state, understand situation
2. EXECUTION (5-50 tool calls): Send commands, navigate, interact
3. MONITORING (long-running): Python-side polling, re-engage LLM only when needed
"""
import asyncio
import json
import logging
from typing import Optional, Callable, Union

from .config import DriverConfig, get_token_cost
from .context import build_system_prompt
from .conversation import ConversationManager
from .llm_client import LLMClient, LLMResponse, create_client
from .mcp_client import MCPClient
from .request_logger import RequestLogger
from .stuck_detector import StuckDetector
from .tools import filter_tools, mcp_to_anthropic, mcp_to_openai, mcp_to_gemini, mcp_to_ollama

logger = logging.getLogger("manny_driver.agent")


class Agent:
    """Autonomous OSRS agent that uses an LLM to control gameplay via MCP tools."""

    def __init__(
        self,
        config: DriverConfig,
        mcp: MCPClient,
        llm: LLMClient,
        on_tool_call: Optional[Callable] = None,
        on_text: Optional[Callable] = None,
        on_status: Optional[Callable] = None,
    ):
        self.config = config
        self.mcp = mcp
        self.llm = llm
        self.conversation = ConversationManager(window_size=config.conversation_window_size)
        self.stuck_detector = StuckDetector()

        # Callbacks for CLI display
        self.on_tool_call = on_tool_call or (lambda *a: None)
        self.on_text = on_text or (lambda *a: None)
        self.on_status = on_status or (lambda *a: None)

        # Build provider-specific tool schemas
        gameplay_tools = filter_tools(mcp.get_tools())
        self._tool_schemas = self._convert_tools(gameplay_tools)
        self._tool_names = {t.name for t in gameplay_tools}

        # Monitoring-only tool subset (6 tools instead of 33)
        MONITORING_TOOLS = {
            "send_command", "send_and_await", "get_game_state",
            "get_logs", "query_nearby", "get_command_response",
        }
        monitoring_tools = [t for t in gameplay_tools if t.name in MONITORING_TOOLS]
        self._monitoring_tool_schemas = self._convert_tools(monitoring_tools)

        # Request logger
        self._request_logger = RequestLogger()

        # State
        self._running = False
        self._current_directive = ""
        self._original_goal = ""  # Preserved across monitoring interventions
        self._monitoring = False

    def _convert_tools(self, tools) -> list[dict]:
        """Convert MCP tools to the current provider's format."""
        provider = self.config.provider
        if provider == "anthropic":
            return mcp_to_anthropic(tools)
        elif provider == "openai":
            return mcp_to_openai(tools)
        elif provider == "gemini":
            return mcp_to_gemini(tools)
        elif provider == "ollama":
            return mcp_to_ollama(tools)
        return mcp_to_anthropic(tools)

    async def run_directive(self, directive: str, *, monitoring_intervention: bool = False):
        """Execute a user directive autonomously.

        This is the main entry point. It runs the LLM tool loop until
        the directive is complete, then enters monitoring mode if appropriate.

        Args:
            directive: The goal to pursue.
            monitoring_intervention: If True, uses reduced tool set and
                doesn't overwrite _current_directive (prevents recursive nesting).
        """
        self._running = True
        if not monitoring_intervention:
            self._current_directive = directive
        self.stuck_detector.reset()

        # Use reduced tool set for monitoring interventions
        tool_schemas = self._monitoring_tool_schemas if monitoring_intervention else self._tool_schemas

        # Build system prompt with context injection
        system_prompt = build_system_prompt(directive, self.config.account_id)

        # Add the directive as a user message
        self.conversation.add_message({
            "role": "user",
            "content": f"Goal: {directive}\n\nStart by observing the current game state, then work toward this goal autonomously.",
        })

        tool_calls_this_turn = 0

        try:
            while self._running and tool_calls_this_turn < self.config.max_tool_calls_per_turn:
                # Get messages for LLM
                messages = self.conversation.get_messages()

                # Call LLM
                response = await self.llm.chat(
                    messages=messages,
                    tools=tool_schemas,
                    system=system_prompt,
                )

                # Track stats
                self.conversation.stats.record(
                    response.input_tokens,
                    response.output_tokens,
                    len(response.tool_calls),
                )

                # Update running cost and log request
                request_cost = get_token_cost(
                    self.config.resolved_model,
                    response.input_tokens,
                    response.output_tokens,
                )
                self.conversation.stats.estimated_cost += request_cost
                self._request_logger.log(
                    model=self.config.resolved_model,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    directive=self._current_directive,
                    phase="monitoring" if self._monitoring else "execution",
                )

                # Check cost budget for paid providers (skip for local models)
                if self.config.provider not in ("ollama",):
                    estimated_cost = self.conversation.stats.estimated_cost
                    if estimated_cost > self.config.max_session_cost_usd:
                        self.on_status(
                            f"Cost budget exceeded: ${estimated_cost:.4f} > "
                            f"${self.config.max_session_cost_usd:.2f}. Stopping."
                        )
                        logger.warning(f"Cost budget exceeded: ${estimated_cost:.4f}")
                        self.stop()
                        break

                # Handle text output
                if response.text:
                    self.on_text(response.text)

                # If no tool calls, the LLM is done with this turn
                if not response.has_tool_calls:
                    # Add assistant message to history
                    if response.text:
                        self.conversation.add_message({
                            "role": "assistant",
                            "content": response.text,
                        })
                    break

                # Add assistant message with tool calls to history
                assistant_msg = self.llm.format_assistant_with_tool_calls(response)
                self.conversation.add_message(assistant_msg)

                # Execute all tool calls and collect results
                # Track if previous call was a command (needs delay before next command)
                _prev_was_command = False
                tool_results = []
                for tc in response.tool_calls:
                    tool_calls_this_turn += 1
                    self.on_tool_call(tc.name, tc.arguments)

                    # Track all tool calls for observation-loop detection
                    self.stuck_detector.record_tool_call(tc.name)

                    # Track command for stuck detection
                    is_command = tc.name in ("send_command", "send_and_await")
                    if is_command:
                        cmd = tc.arguments.get("command", "")
                        self.stuck_detector.record_command(cmd)

                    # Delay between consecutive commands to avoid overwriting
                    # (send_command writes to a file, only last write per tick executes)
                    if is_command and _prev_was_command:
                        await asyncio.sleep(0.7)  # ~1 game tick
                    _prev_was_command = is_command

                    # Auto-inject account_id for account-aware tools
                    args = dict(tc.arguments)
                    if "account_id" not in args and self.config.account_id:
                        # Most MCP tools accept account_id
                        args["account_id"] = self.config.account_id

                    # Execute via MCP
                    try:
                        result_text = await self.mcp.call_tool(tc.name, args)
                        self.stuck_detector.record_success()

                        # Extract position for stuck detection
                        self._extract_position(tc.name, result_text)

                    except Exception as e:
                        result_text = json.dumps({"error": str(e)})
                        self.stuck_detector.record_error(str(e))
                        logger.warning(f"Tool error: {tc.name}: {e}")

                    # Truncate very long results to save context
                    if len(result_text) > 8000:
                        result_text = result_text[:8000] + "\n... [truncated]"

                    tool_results.append((tc, result_text))

                # Add tool results to conversation
                # For Anthropic, each tool result must match a tool_use_id
                if self.config.provider == "anthropic":
                    # Anthropic expects all tool results in one user message
                    content_blocks = []
                    for tc, result in tool_results:
                        content_blocks.append({
                            "type": "tool_result",
                            "tool_use_id": tc.id,
                            "content": result,
                        })
                    self.conversation.add_message({
                        "role": "user",
                        "content": content_blocks,
                    })
                else:
                    # Other providers: use the format_tool_result method
                    for tc, result in tool_results:
                        msg = self.llm.format_tool_result(tc.id, result)
                        # Store tool name for Gemini reconstruction
                        if self.config.provider == "gemini":
                            for item in msg.get("content", []):
                                if isinstance(item, dict) and item.get("type") == "tool_result":
                                    item["_tool_name"] = tc.name
                        self.conversation.add_message(msg)

                # Check if stuck
                signals = self.stuck_detector.check()
                if signals.is_stuck:
                    hint = self.stuck_detector.get_recovery_hint()
                    self.on_status(f"Stuck detected: {signals.reason}")
                    logger.warning(f"Stuck: {signals.reason}")

                    # Inject recovery context
                    self.conversation.add_message({
                        "role": "user",
                        "content": (
                            f"[SYSTEM: You appear to be stuck ({signals.reason}). "
                            f"Recovery suggestion: {hint}. "
                            "Try a different approach or report the issue.]"
                        ),
                    })
                    self.stuck_detector.reset()

        except asyncio.CancelledError:
            self.on_status("Cancelled")
            raise
        except Exception as e:
            logger.exception(f"Agent error: {e}")
            self.on_status(f"Error: {e}")
            raise
        finally:
            self._running = False

        return tool_calls_this_turn

    async def run_monitoring(self, check_fn: Optional[Callable] = None):
        """Enter monitoring mode - poll game state periodically.

        Only re-engages the LLM when something interesting happens:
        - Inventory full
        - Health critical
        - Player idle unexpectedly
        - State file stale (plugin frozen)

        Args:
            check_fn: Optional callback that receives game state and returns
                      a string trigger message, or None if no intervention needed.
        """
        self._monitoring = True
        self._running = True
        self._original_goal = self._current_directive  # Preserve for interventions
        self.on_status("Entering monitoring mode")
        interval = self.config.monitoring_interval_seconds

        while self._monitoring and self._running:
            try:
                # Get compact game state (also serves as health check)
                state_args = {"fields": ["location", "inventory", "health", "skills"]}
                if self.config.account_id:
                    state_args["account_id"] = self.config.account_id
                state_text = await self.mcp.call_tool("get_game_state", state_args)
                try:
                    state = json.loads(state_text)
                except (json.JSONDecodeError, TypeError):
                    state = {}

                # If state fetch failed or state is stale, skip this cycle
                if not state.get("success", False):
                    self.on_status("State check failed, will retry next cycle")
                    await asyncio.sleep(interval)
                    continue

                # Check for intervention triggers
                trigger = None

                # Custom check function
                if check_fn:
                    trigger = check_fn(state)

                # Built-in checks
                if not trigger:
                    trigger = self._check_monitoring_triggers(state)

                if trigger:
                    if isinstance(trigger, tuple):
                        # Deterministic fix - handle in Python, no LLM needed
                        trigger_name, commands = trigger
                        self.on_status(f"Auto-fix: {trigger_name} ({len(commands)} commands)")
                        for cmd in commands:
                            try:
                                cmd_args = {"command": cmd}
                                if self.config.account_id:
                                    cmd_args["account_id"] = self.config.account_id
                                await self.mcp.call_tool("send_command", cmd_args)
                                await asyncio.sleep(0.7)
                            except Exception as e:
                                logger.warning(f"Auto-fix command failed: {cmd}: {e}")
                    else:
                        # Complex issue - use LLM with clean conversation
                        self.on_status(f"LLM intervention: {trigger}")
                        self.conversation.clear()  # Fix 3: fresh context
                        saved_max = self.config.max_tool_calls_per_turn
                        self.config.max_tool_calls_per_turn = 5
                        try:
                            await self.run_directive(
                                f"Monitoring detected: {trigger}. "
                                "Handle with 1-2 commands, then STOP.",
                                monitoring_intervention=True,
                            )
                        finally:
                            self.config.max_tool_calls_per_turn = saved_max
                            self._running = True
                else:
                    # Log status periodically
                    game_state = state.get("state", state)
                    inv = game_state.get("inventory", {})
                    loc = game_state.get("location", {})
                    skills = game_state.get("skills", {})
                    atk = skills.get("attack", {})
                    hp = game_state.get("health", {})
                    cost = self.conversation.stats.estimated_cost
                    self.on_status(
                        f"Monitoring: ({loc.get('x','?')},{loc.get('y','?')}) "
                        f"inv={inv.get('used','?')}/28 "
                        f"hp={hp.get('current','?')}/{hp.get('max','?')} "
                        f"atk_xp={atk.get('xp','?')} | "
                        f"${cost:.4f}"
                    )

            except Exception as e:
                logger.warning(f"Monitoring error: {e}")

            await asyncio.sleep(interval)

    def _check_monitoring_triggers(self, state: dict) -> Optional[Union[tuple[str, list[str]], str]]:
        """Check game state for conditions that need intervention.

        Returns:
            - tuple(trigger_name, commands): Deterministic fix, handled in Python (no LLM)
            - str: Complex issue requiring LLM intervention
            - None: No intervention needed
        """
        game_state = state.get("state", state)

        # Check inventory full - deterministic fix: bury bones, drop junk, restart loop
        inv = game_state.get("inventory", {})
        if isinstance(inv, dict) and inv.get("used", 0) >= 27:
            return ("inventory_full", ["BURY_ALL", "DROP_ALL Egg", "DROP_ALL Feather", "DROP_ALL Raw chicken"])

        # Check health critical - needs LLM to decide (eat food? teleport? wait?)
        health = game_state.get("health", {})
        if isinstance(health, dict):
            current = health.get("current", 99)
            max_hp = health.get("max", 99)
            if max_hp > 0 and current <= max_hp * 0.2 and current > 0:
                return f"Health critical: {current}/{max_hp}. Eat food or teleport to safety."

        # Track XP for idle detection
        skills = game_state.get("skills", {})
        current_xp = sum(s.get("xp", 0) for s in skills.values() if isinstance(s, dict))
        if not hasattr(self, "_last_total_xp"):
            self._last_total_xp = current_xp
            self._idle_checks = 0

        if current_xp == self._last_total_xp:
            self._idle_checks += 1
        else:
            self._idle_checks = 0
            self._last_total_xp = current_xp

        # If no XP gained for 3 consecutive checks (~90s), restart the kill loop
        if self._idle_checks >= 3:
            self._idle_checks = 0
            return ("xp_idle", ["KILL_LOOP Chicken none"])

        return None

    def _extract_position(self, tool_name: str, result_text: str):
        """Extract player position from tool results for stuck detection."""
        if tool_name != "get_game_state":
            return
        try:
            data = json.loads(result_text)
            state = data.get("state", data)
            loc = state.get("location", {})
            if loc:
                self.stuck_detector.record_position(
                    loc.get("x", 0),
                    loc.get("y", 0),
                    loc.get("plane", 0),
                )
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass

    def stop(self):
        """Stop the agent."""
        self._running = False
        self._monitoring = False

    async def handle_user_input(self, text: str):
        """Handle mid-session user input."""
        if text.lower() in ("stop", "cancel", "quit"):
            self.stop()
            return

        # Add user message and re-engage LLM
        self.conversation.add_message({
            "role": "user",
            "content": text,
        })
        await self.run_directive(text)
