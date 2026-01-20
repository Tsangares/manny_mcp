"""
Agent brain for intelligent task routing and execution.

This module handles:
1. Task classification (simple query vs complex multi-step)
2. Dynamic context enrichment
3. Step-by-step execution with waiting
4. Planning for complex tasks
"""
import asyncio
import logging
import re
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("agent_brain")


class TaskType(Enum):
    """Classification of user requests."""
    STATUS_QUERY = "status_query"       # "is it running?", "what's my health?"
    SIMPLE_COMMAND = "simple_command"   # "stop", "restart", "open bank"
    LOOP_COMMAND = "loop_command"       # "fish at draynor", "kill cows"
    MULTI_STEP = "multi_step"           # "go to lumbridge and fish", "bank then kill"
    CONVERSATION = "conversation"       # "hello", "thanks", general chat


@dataclass
class TaskPlan:
    """A plan for executing a multi-step task."""
    task_type: TaskType
    steps: List[Dict[str, Any]]
    original_request: str
    context: Dict[str, Any]


# Pattern matchers for task classification
STATUS_PATTERNS = [
    r'\b(status|running|alive|health|where|location|inventory|level|stats)\b',
    r'\b(is it|are you|check|show me|what\'?s)\b',
    r'\bhow (much|many)\b',
]

SIMPLE_COMMAND_PATTERNS = [
    r'^stop\b',
    r'^restart\b',
    r'^kill all\b',
    r'\b(open bank|bank open)\b',
    r'^screenshot\b',
]

LOOP_PATTERNS = [
    r'\b(fish|fishing)\b(?!.*\b(and|then|after)\b)',
    r'\b(kill|attack|fight)\s+\w+(?!.*\b(and|then|after)\b)',
    r'\b(mine|mining)\b(?!.*\b(and|then|after)\b)',
    r'\b(chop|woodcut)\b(?!.*\b(and|then|after)\b)',
    r'\bloop\b',
]

MULTI_STEP_PATTERNS = [
    r'\b(and|then|after|before|first|next)\b',
    r'\bgo to\b.*\b(and|then)\b',
    r'\bbank\b.*\b(then|and)\b',
]


class TaskClassifier:
    """Classifies user requests into task types."""

    def classify(self, message: str) -> TaskType:
        """Classify a user message into a task type."""
        message_lower = message.lower().strip()

        # Check for multi-step first (highest complexity)
        for pattern in MULTI_STEP_PATTERNS:
            if re.search(pattern, message_lower):
                return TaskType.MULTI_STEP

        # Check for loop commands
        for pattern in LOOP_PATTERNS:
            if re.search(pattern, message_lower):
                return TaskType.LOOP_COMMAND

        # Check for simple commands
        for pattern in SIMPLE_COMMAND_PATTERNS:
            if re.search(pattern, message_lower):
                return TaskType.SIMPLE_COMMAND

        # Check for status queries
        for pattern in STATUS_PATTERNS:
            if re.search(pattern, message_lower):
                return TaskType.STATUS_QUERY

        # Default to conversation
        return TaskType.CONVERSATION


class ContextEnricher:
    """Enriches context dynamically based on task type."""

    # Command categories for context injection
    COMMAND_CATEGORIES = {
        "combat": [
            "KILL <npc_name> - Kill a single NPC",
            "KILL_LOOP <npc_name> - Continuously kill NPCs (use for grinding)",
            "ATTACK_NPC <name> - Attack specific NPC once",
            "STOP - Stop current combat loop",
        ],
        "skilling": [
            "FISH - Fish at current spot",
            "FISH_DRAYNOR_LOOP - Fish shrimp at Draynor, bank when full",
            "FISH_DROP - Fish and drop (power fishing)",
            "CHOP_TREE - Chop nearest tree",
            "COOK_ALL - Cook all raw food in inventory",
            "LIGHT_FIRE - Light a fire with logs",
        ],
        "banking": [
            "BANK_OPEN - Open nearest bank",
            "BANK_CLOSE - Close bank interface",
            "BANK_DEPOSIT_ALL - Deposit entire inventory",
            "BANK_WITHDRAW <item> <quantity> - Withdraw items",
        ],
        "movement": [
            "GOTO <x> <y> <plane> - Walk to coordinates",
            "WAIT <ms> - Wait for milliseconds",
        ],
        "interaction": [
            "INTERACT_NPC <name> <action> - Interact with NPC (e.g., 'Cook Talk-to')",
            "INTERACT_OBJECT <name> <action> - Interact with object (use underscores: 'Large_door Open')",
            "PICK_UP_ITEM <name> - Pick up ground item",
            "USE_ITEM_ON_NPC <item> <npc> - Use item on NPC",
            "USE_ITEM_ON_OBJECT <item> <object> - Use item on object",
        ],
        "system": [
            "STOP - Stop current activity immediately",
            "LIST_COMMANDS - List all available commands",
        ],
    }

    # Common locations for context
    COMMON_LOCATIONS = {
        "lumbridge": {"x": 3222, "y": 3218, "plane": 0},
        "lumbridge_swamp": {"x": 3197, "y": 3169, "plane": 0},
        "draynor_fishing": {"x": 3087, "y": 3228, "plane": 0},
        "varrock_bank": {"x": 3253, "y": 3420, "plane": 0},
        "falador_bank": {"x": 2946, "y": 3368, "plane": 0},
    }

    def __init__(self, tool_executor: Callable = None):
        self.tool_executor = tool_executor

    async def enrich_for_task(self, task_type: TaskType, message: str) -> Dict[str, Any]:
        """Build enriched context based on task type."""
        context = {
            "task_type": task_type.value,
            "available_commands": {},
            "current_state": None,
            "hints": [],
        }

        # Always include relevant command categories
        if task_type == TaskType.LOOP_COMMAND:
            context["available_commands"]["combat"] = self.COMMAND_CATEGORIES["combat"]
            context["available_commands"]["skilling"] = self.COMMAND_CATEGORIES["skilling"]
            context["hints"].append("For continuous tasks, use _LOOP commands (KILL_LOOP, FISH_DRAYNOR_LOOP)")
            context["hints"].append("Use STOP to end any loop")

        elif task_type == TaskType.MULTI_STEP:
            # Include all categories for planning
            context["available_commands"] = self.COMMAND_CATEGORIES
            context["hints"].append("Execute steps sequentially: send command, check state ONCE, then next step")
            context["hints"].append("DON'T poll repeatedly - check game_state once per step, then move on")
            context["hints"].append("GOTO commands auto-complete, just send them and proceed to next step")

        elif task_type == TaskType.SIMPLE_COMMAND:
            context["available_commands"]["system"] = self.COMMAND_CATEGORIES["system"]
            context["available_commands"]["banking"] = self.COMMAND_CATEGORIES["banking"]

        # Try to get current game state if we have a tool executor
        if self.tool_executor and task_type != TaskType.CONVERSATION:
            try:
                state = await self.tool_executor("get_game_state", {"fields": ["location", "health", "inventory"]})
                context["current_state"] = state.get("state", {})
            except Exception as e:
                logger.warning(f"Failed to get game state for context: {e}")

        # Add location hints based on message content
        message_lower = message.lower()
        for loc_name, coords in self.COMMON_LOCATIONS.items():
            if loc_name.replace("_", " ") in message_lower:
                context["hints"].append(f"Location '{loc_name}': GOTO {coords['x']} {coords['y']} {coords['plane']}")

        return context


class StepExecutor:
    """Executes multi-step plans with proper waiting."""

    def __init__(self, tool_executor: Callable, state_checker: Callable):
        self.tool_executor = tool_executor
        self.state_checker = state_checker

    async def execute_command_and_wait(
        self,
        command: str,
        wait_condition: Optional[str] = None,
        timeout_seconds: float = 30.0
    ) -> Dict[str, Any]:
        """Execute a command and wait for completion.

        Args:
            command: The command to send
            wait_condition: Optional condition to wait for (e.g., "idle", "location:3200,3200")
            timeout_seconds: Max time to wait

        Returns:
            Result dict with success status and final state
        """
        # Send the command
        result = await self.tool_executor("send_command", {"command": command})

        if not wait_condition:
            # No wait condition, just pause briefly
            await asyncio.sleep(1.0)
            return {"success": True, "command": command, "result": result}

        # Wait for condition
        start_time = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
            state = await self.state_checker()

            if self._check_condition(state, wait_condition):
                return {
                    "success": True,
                    "command": command,
                    "condition_met": wait_condition,
                    "final_state": state
                }

            await asyncio.sleep(2.0)  # Check every 2 seconds

        return {
            "success": False,
            "command": command,
            "error": f"Timeout waiting for condition: {wait_condition}",
            "timeout_seconds": timeout_seconds
        }

    def _check_condition(self, state: Dict, condition: str) -> bool:
        """Check if a wait condition is met."""
        if condition == "idle":
            # Check if player is idle (not moving, not in combat)
            scenario = state.get("scenario", {})
            return scenario.get("currentTask") == "Idle"

        if condition.startswith("location:"):
            # Check if player is near target location
            target = condition.split(":")[1]
            parts = target.split(",")
            if len(parts) >= 2:
                target_x, target_y = int(parts[0]), int(parts[1])
                loc = state.get("location", {})
                player_x = loc.get("x", 0)
                player_y = loc.get("y", 0)
                # Within 5 tiles
                return abs(player_x - target_x) <= 5 and abs(player_y - target_y) <= 5

        if condition.startswith("has_item:"):
            item_name = condition.split(":")[1].lower()
            inventory = state.get("inventory", {})
            items = inventory.get("items", [])
            return any(item_name in str(item).lower() for item in items)

        return False


class AgentBrain:
    """Main coordinator for intelligent task handling."""

    def __init__(self, llm_client, tool_executor: Callable):
        self.llm = llm_client
        self.tool_executor = tool_executor
        self.classifier = TaskClassifier()
        self.enricher = ContextEnricher(tool_executor)
        self.executor = StepExecutor(
            tool_executor,
            lambda: tool_executor("get_game_state", {"fields": ["location", "scenario", "inventory"]})
        )

    async def process_request(
        self,
        message: str,
        conversation_history: List[Dict] = None
    ) -> str:
        """Process a user request with intelligent routing."""
        conversation_history = conversation_history or []

        # 1. Classify the task
        task_type = self.classifier.classify(message)
        logger.info(f"Classified '{message[:50]}...' as {task_type.value}")

        # 2. Enrich context based on task type
        enriched_context = await self.enricher.enrich_for_task(task_type, message)

        # 3. Build the augmented message with context
        augmented_message = self._build_augmented_message(message, task_type, enriched_context)

        # 4. Get LLM response
        response = await self.llm.chat(
            message=augmented_message,
            game_state={"player": enriched_context.get("current_state")} if enriched_context.get("current_state") else None,
            conversation_history=conversation_history
        )

        return response

    def _build_augmented_message(
        self,
        message: str,
        task_type: TaskType,
        context: Dict
    ) -> str:
        """Build an augmented message with injected context."""
        parts = []

        # Add task-specific instructions
        if task_type == TaskType.LOOP_COMMAND:
            parts.append("**Task Type: Loop/Continuous Command**")
            parts.append("You CAN and SHOULD send commands. Use the appropriate _LOOP command for continuous tasks.")

        elif task_type == TaskType.MULTI_STEP:
            parts.append("**Task Type: Multi-Step Task**")
            parts.append("Break this into steps. Execute ONE step at a time.")
            parts.append("After each command, use get_game_state to verify before proceeding.")

        elif task_type == TaskType.SIMPLE_COMMAND:
            parts.append("**Task Type: Simple Command**")
            parts.append("Execute this directly with send_command.")

        # Add available commands
        if context.get("available_commands"):
            parts.append("\n**Available Commands:**")
            for category, commands in context["available_commands"].items():
                parts.append(f"\n{category.title()}:")
                for cmd in commands:
                    parts.append(f"  - {cmd}")

        # Add hints
        if context.get("hints"):
            parts.append("\n**Hints:**")
            for hint in context["hints"]:
                parts.append(f"- {hint}")

        # Add the actual user message
        parts.append(f"\n**User Request:** {message}")

        return "\n".join(parts)


# Convenience function to create the brain
def create_agent_brain(llm_client, tool_executor: Callable) -> AgentBrain:
    """Create an AgentBrain instance."""
    return AgentBrain(llm_client, tool_executor)
