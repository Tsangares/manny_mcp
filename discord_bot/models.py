"""
Pydantic models for structured LLM output in the agentic loop.

These models ensure type-safe, validated decisions from the LLM.
Using Pydantic for validation means malformed JSON gets caught early.
"""
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator


class ActionDecision(BaseModel):
    """
    Structured decision from LLM - validated by Pydantic.

    The LLM outputs this JSON schema, and Pydantic validates it.
    This prevents the "JSON-as-text" issue since the LLM is constrained
    to output valid JSON matching this schema.
    """
    thought: str = Field(
        description="Brief reasoning about what to do next (1-2 sentences)"
    )
    action_type: Literal["observe", "act", "verify", "respond"] = Field(
        description="Type of action: observe (get info), act (do something), verify (confirm result), respond (reply to user)"
    )
    tool_name: Optional[str] = Field(
        default=None,
        description="Name of tool to call (required for observe/act/verify)"
    )
    tool_args: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments to pass to the tool"
    )
    response_text: Optional[str] = Field(
        default=None,
        description="Text response to user (required for respond action_type)"
    )

    @field_validator('tool_name')
    @classmethod
    def validate_tool_required_for_actions(cls, v, info):
        """Ensure tool_name is provided for observe/act/verify actions."""
        action_type = info.data.get('action_type')
        if action_type in ('observe', 'act', 'verify') and not v:
            # Don't raise error - let the loop handle missing tool gracefully
            pass
        return v

    @field_validator('response_text')
    @classmethod
    def validate_response_for_respond(cls, v, info):
        """Ensure response_text is provided for respond action."""
        action_type = info.data.get('action_type')
        if action_type == 'respond' and not v:
            return "Done."  # Default response
        return v

    @field_validator('tool_args')
    @classmethod
    def validate_kill_loop_args(cls, v, info):
        """Validate KILL_LOOP command format if present."""
        if not v:
            return v

        command = v.get('command', '')
        if isinstance(command, str) and 'KILL_LOOP' in command.upper():
            parts = command.split()
            # KILL_LOOP requires at least: KILL_LOOP <npc> <food>
            if len(parts) < 3:
                # Auto-fix: add 'none' for food if missing
                if len(parts) == 2:
                    v['command'] = f"{parts[0]} {parts[1]} none"
        return v


class AgentResult(BaseModel):
    """Result from the agentic loop execution."""
    response: str = Field(description="Final response to send to user")
    actions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of actions taken during execution"
    )
    iterations: int = Field(
        default=0,
        description="Number of loop iterations executed"
    )
    observed: bool = Field(
        default=False,
        description="Whether observation was performed before acting"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if execution failed"
    )


class ToolCategory(BaseModel):
    """Categorization of a tool for the agentic loop."""
    name: str
    category: Literal["observation", "action", "verification"]
    description: str
    requires_observation: bool = Field(
        default=True,
        description="Whether this tool requires prior observation"
    )


# Tool categorizations - used to enforce observation-first behavior
TOOL_CATEGORIES = {
    # Observation tools - always allowed, don't require prior observation
    "get_game_state": ToolCategory(
        name="get_game_state",
        category="observation",
        description="Get current game state (location, inventory, health, skills)",
        requires_observation=False
    ),
    "check_health": ToolCategory(
        name="check_health",
        category="observation",
        description="Check if RuneLite client is healthy",
        requires_observation=False
    ),
    "get_screenshot": ToolCategory(
        name="get_screenshot",
        category="observation",
        description="Capture screenshot of game window",
        requires_observation=False
    ),
    "get_logs": ToolCategory(
        name="get_logs",
        category="observation",
        description="Get recent plugin logs for debugging",
        requires_observation=False
    ),
    "lookup_location": ToolCategory(
        name="lookup_location",
        category="observation",
        description="Look up coordinates for a named location",
        requires_observation=False
    ),
    "list_plugin_commands": ToolCategory(
        name="list_plugin_commands",
        category="observation",
        description="List available plugin commands",
        requires_observation=False
    ),
    "get_command_help": ToolCategory(
        name="get_command_help",
        category="observation",
        description="Get help for a specific command",
        requires_observation=False
    ),
    "list_routines": ToolCategory(
        name="list_routines",
        category="observation",
        description="List available automation routines",
        requires_observation=False
    ),
    "list_accounts": ToolCategory(
        name="list_accounts",
        category="observation",
        description="List available OSRS accounts",
        requires_observation=False
    ),

    # Action tools - require observation first (for most cases)
    "send_command": ToolCategory(
        name="send_command",
        category="action",
        description="Send a command to the manny plugin",
        requires_observation=True
    ),
    "start_runelite": ToolCategory(
        name="start_runelite",
        category="action",
        description="Start the RuneLite client",
        requires_observation=False  # Starting client doesn't need observation
    ),
    "stop_runelite": ToolCategory(
        name="stop_runelite",
        category="action",
        description="Stop the RuneLite client",
        requires_observation=False  # Stopping doesn't need observation
    ),
    "restart_runelite": ToolCategory(
        name="restart_runelite",
        category="action",
        description="Restart the RuneLite client",
        requires_observation=False
    ),
    "auto_reconnect": ToolCategory(
        name="auto_reconnect",
        category="action",
        description="Handle disconnection by clicking OK dialog",
        requires_observation=False
    ),
    "run_routine": ToolCategory(
        name="run_routine",
        category="action",
        description="Run a YAML automation routine",
        requires_observation=True
    ),
    "switch_account": ToolCategory(
        name="switch_account",
        category="action",
        description="Switch to a different OSRS account",
        requires_observation=False
    ),
    "queue_on_level": ToolCategory(
        name="queue_on_level",
        category="action",
        description="Queue a command to run when skill reaches level",
        requires_observation=True
    ),

    # Verification tools - check that actions succeeded
    # (In practice, these often overlap with observation tools)
}


def get_tool_category(tool_name: str) -> Optional[ToolCategory]:
    """Get the category for a tool, or None if unknown."""
    return TOOL_CATEGORIES.get(tool_name)


def requires_observation(tool_name: str) -> bool:
    """Check if a tool requires prior observation before use."""
    category = get_tool_category(tool_name)
    if category:
        return category.requires_observation
    # Default: require observation for unknown tools
    return True


def is_observation_tool(tool_name: str) -> bool:
    """Check if a tool is an observation tool."""
    category = get_tool_category(tool_name)
    return category is not None and category.category == "observation"
