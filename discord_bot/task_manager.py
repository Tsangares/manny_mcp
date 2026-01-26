"""
Task Manager - Orchestrates the capability registry, task queue, and execution.

This is the main interface for complex task execution.
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta

from .capability_registry import CapabilityRegistry, registry, CommandCategory, AbstractionLevel
from .task_queue import (
    TaskQueue, Task, Condition, ConditionType, TaskStatus,
    when_level, after_level_up, when_inventory_full, when_health_below,
    after_task, immediately, after_duration, at_time
)

logger = logging.getLogger("task_manager")


class TaskManager:
    """
    High-level task management combining:
    - Capability discovery
    - Task queuing with conditions
    - State monitoring
    - Execution orchestration
    """

    def __init__(self, send_command_func: Callable, get_state_func: Callable):
        self._send_command = send_command_func
        self._get_state = get_state_func

        # Initialize registry
        self.registry = registry

        # Initialize queue
        self.queue = TaskQueue(
            execute_func=self._execute_command,
            get_state_func=get_state_func
        )

        # Set up callbacks
        self.queue.set_callbacks(
            on_complete=self._on_task_complete,
            on_fail=self._on_task_fail,
            on_condition=self._on_condition_met
        )

        # Event callbacks for bot notifications
        self._notify_callback: Optional[Callable] = None

        # System command callbacks (for STOP_CLIENT, etc.)
        self._stop_client_func: Optional[Callable] = None
        self._account_id: Optional[str] = None

        # Active timers tracking
        self._active_timers: Dict[str, Dict] = {}  # task_id -> {deadline, description}

        # Track state for smart decisions
        self._last_state: Optional[Dict] = None
        self._state_history: List[Dict] = []

    def set_notify_callback(self, callback: Callable):
        """Set callback for notifications (e.g., Discord messages)."""
        self._notify_callback = callback

    def set_stop_client_func(self, func: Callable, account_id: str):
        """
        Set the function to call for STOP_CLIENT command.

        Args:
            func: Async function that stops the RuneLite client
            account_id: Account ID to pass to the stop function
        """
        self._stop_client_func = func
        self._account_id = account_id

    async def initialize(self):
        """Initialize the task manager."""
        # Load capabilities
        self.registry._load_static_capabilities()
        logger.info(f"Loaded {len(self.registry.list_all())} capabilities")

        # Start the queue processor
        await self.queue.start()
        logger.info("Task queue started")

    async def shutdown(self):
        """Shutdown the task manager."""
        await self.queue.stop()
        logger.info("Task manager shutdown")

    # =========================================================================
    # High-Level Task Creation
    # =========================================================================

    def queue_task(self,
                   command: str,
                   params: Dict = None,
                   condition: Condition = None,
                   priority: int = 0) -> str:
        """Queue a simple task."""
        return self.queue.add(command, params, condition, priority)

    def queue_sequence(self, tasks: List[Dict]) -> List[str]:
        """
        Queue a sequence of tasks.

        Example:
            queue_sequence([
                {"command": "GOTO", "params": {"x": 3200, "y": 3200, "plane": 0}},
                {"command": "KILL_LOOP", "params": {"npc": "Giant_frog", "food": "none"}}
            ])
        """
        return self.queue.add_sequence(tasks)

    def queue_on_level(self,
                       skill: str,
                       level: int,
                       command: str,
                       params: Dict = None) -> str:
        """
        Queue a task to run when a skill reaches a level.

        Example:
            queue_on_level("strength", 40, "SET_ATTACK_STYLE", {"style": "defensive"})
        """
        return self.queue.add(
            command=command,
            params=params,
            condition=when_level(skill, level)
        )

    def queue_after_level_up(self,
                             skill: str,
                             command: str,
                             params: Dict = None) -> str:
        """
        Queue a task to run after a level up.

        Example:
            queue_after_level_up("strength", "SET_ATTACK_STYLE", {"style": "controlled"})
        """
        return self.queue.add(
            command=command,
            params=params,
            condition=after_level_up(skill)
        )

    def queue_on_inventory_full(self, command: str, params: Dict = None) -> str:
        """Queue a task for when inventory is full."""
        return self.queue.add(
            command=command,
            params=params,
            condition=when_inventory_full()
        )

    def queue_on_low_health(self,
                            threshold: int,
                            command: str,
                            params: Dict = None) -> str:
        """Queue a task for when health drops below threshold."""
        return self.queue.add(
            command=command,
            params=params,
            condition=when_health_below(threshold),
            priority=10  # High priority for health-related tasks
        )

    # =========================================================================
    # Timer / Kill-Switch Methods
    # =========================================================================

    def set_timer(self,
                  hours: float = 0,
                  minutes: float = 0,
                  seconds: float = 0,
                  description: str = None) -> Dict[str, Any]:
        """
        Set a timer to stop the client after a duration.

        Examples:
            set_timer(hours=4)                    # Stop in 4 hours
            set_timer(hours=2, minutes=30)        # Stop in 2.5 hours
            set_timer(minutes=30, description="Quick session")

        Returns:
            {
                "task_id": "timer_1",
                "deadline": "2026-01-24T18:00:00",
                "description": "Stop client in 4 hours"
            }
        """
        total_seconds = hours * 3600 + minutes * 60 + seconds
        deadline = datetime.now() + timedelta(seconds=total_seconds)

        # Format duration for display
        parts = []
        if hours >= 1:
            parts.append(f"{int(hours)}h")
        if minutes >= 1 or (hours > 0 and minutes > 0):
            parts.append(f"{int(minutes)}m")
        if seconds > 0 and hours == 0:
            parts.append(f"{int(seconds)}s")
        duration_str = " ".join(parts) if parts else "0s"

        desc = description or f"Stop client after {duration_str}"

        # Queue the stop command with time condition
        task_id = self.queue.add(
            command="STOP_CLIENT",
            params={},
            condition=after_duration(hours=hours, minutes=minutes, seconds=seconds),
            priority=-1,  # Low priority - doesn't interrupt other tasks
            task_id=f"timer_{len(self._active_timers) + 1}"
        )

        # Track the timer
        self._active_timers[task_id] = {
            "deadline": deadline.isoformat(),
            "deadline_dt": deadline,
            "description": desc,
            "created": datetime.now().isoformat()
        }

        # Add 5-minute warning notification (if timer is > 5 minutes)
        warning_task_id = None
        if total_seconds > 300:  # Only add warning if timer > 5 minutes
            warning_deadline = deadline - timedelta(minutes=5)
            warning_task_id = self.queue.add(
                command="TIMER_WARNING",  # Special command handled in _execute_command
                params={"minutes_remaining": 5},
                condition=at_time(warning_deadline),
                priority=-2,  # Even lower than timer itself
                task_id=f"{task_id}_warning"
            )

        logger.info(f"Timer set: {task_id} - {desc} (deadline: {deadline})")

        return {
            "task_id": task_id,
            "deadline": deadline.isoformat(),
            "deadline_human": deadline.strftime("%I:%M %p"),
            "duration": duration_str,
            "description": desc
        }

    def cancel_timer(self, task_id: str = None) -> Dict[str, Any]:
        """
        Cancel an active timer.

        Args:
            task_id: Specific timer to cancel. If None, cancels all timers.

        Returns:
            {"cancelled": ["timer_1"], "remaining": []}
        """
        cancelled = []

        if task_id:
            # Cancel specific timer and its warning
            if task_id in self._active_timers:
                self.queue.remove(task_id)
                self.queue.remove(f"{task_id}_warning")  # Also remove warning
                del self._active_timers[task_id]
                cancelled.append(task_id)
                logger.info(f"Cancelled timer: {task_id}")
        else:
            # Cancel all timers and warnings
            for tid in list(self._active_timers.keys()):
                self.queue.remove(tid)
                self.queue.remove(f"{tid}_warning")  # Also remove warning
                cancelled.append(tid)
            self._active_timers.clear()
            logger.info(f"Cancelled all timers: {cancelled}")

        return {
            "cancelled": cancelled,
            "remaining": list(self._active_timers.keys())
        }

    def get_active_timers(self) -> List[Dict[str, Any]]:
        """
        Get all active timers with time remaining.

        Returns:
            [
                {
                    "task_id": "timer_1",
                    "deadline": "2026-01-24T18:00:00",
                    "remaining": "3h 45m",
                    "description": "Stop client after 4h"
                }
            ]
        """
        now = datetime.now()
        timers = []

        for task_id, info in self._active_timers.items():
            deadline = datetime.fromisoformat(info["deadline"])
            remaining = deadline - now

            if remaining.total_seconds() <= 0:
                remaining_str = "expired"
            else:
                hours, remainder = divmod(int(remaining.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                parts = []
                if hours > 0:
                    parts.append(f"{hours}h")
                if minutes > 0:
                    parts.append(f"{minutes}m")
                if seconds > 0 and hours == 0:
                    parts.append(f"{seconds}s")
                remaining_str = " ".join(parts) if parts else "<1s"

            timers.append({
                "task_id": task_id,
                "deadline": info["deadline"],
                "deadline_human": deadline.strftime("%I:%M %p"),
                "remaining": remaining_str,
                "description": info["description"]
            })

        return timers

    def has_active_timer(self) -> bool:
        """Check if there's an active timer."""
        return len(self._active_timers) > 0

    # =========================================================================
    # Complex Task Patterns
    # =========================================================================

    def setup_combat_rotation(self,
                              skill_rotations: List[Dict]) -> List[str]:
        """
        Set up combat style rotations based on levels.

        Example:
            setup_combat_rotation([
                {"skill": "strength", "until_level": 40, "style": "aggressive"},
                {"skill": "attack", "until_level": 40, "style": "accurate"},
                {"skill": "defence", "until_level": 40, "style": "defensive"},
            ])
        """
        task_ids = []

        for i, rotation in enumerate(skill_rotations):
            skill = rotation["skill"]
            level = rotation["until_level"]
            style = rotation["style"]

            # Set style when we start this rotation
            if i == 0:
                # First one runs immediately
                tid = self.queue.add(
                    command="SET_ATTACK_STYLE",
                    params={"style": style},
                    condition=immediately()
                )
            else:
                # Subsequent ones wait for previous skill level
                prev = skill_rotations[i - 1]
                tid = self.queue.add(
                    command="SET_ATTACK_STYLE",
                    params={"style": style},
                    condition=when_level(prev["skill"], prev["until_level"])
                )

            task_ids.append(tid)

        return task_ids

    def setup_grind_with_banking(self,
                                 grind_command: str,
                                 grind_params: Dict,
                                 bank_location: tuple = None) -> List[str]:
        """
        Set up a grind loop with automatic banking when inventory full.

        Example:
            setup_grind_with_banking(
                "FISH_DRAYNOR_LOOP", {},
                bank_location=(3092, 3245, 0)
            )
        """
        task_ids = []

        # Main grind task
        grind_id = self.queue.add(
            command=grind_command,
            params=grind_params,
            condition=immediately()
        )
        task_ids.append(grind_id)

        # Bank when full (repeating pattern would need more complex logic)
        # For now, just queue one banking sequence
        if bank_location:
            bank_id = self.queue.add(
                command="GOTO",
                params={"x": bank_location[0], "y": bank_location[1], "plane": bank_location[2]},
                condition=when_inventory_full(),
                priority=5
            )
            task_ids.append(bank_id)

            deposit_id = self.queue.add(
                command="BANK_DEPOSIT_ALL",
                condition=after_task(bank_id)
            )
            task_ids.append(deposit_id)

        return task_ids

    # =========================================================================
    # Execution
    # =========================================================================

    async def _execute_command(self, command: str) -> Dict:
        """Execute a command - handles both game commands and system commands."""
        logger.info(f"Executing: {command}")

        # Handle special system commands
        if command.startswith("STOP_CLIENT"):
            return await self._handle_stop_client(command)

        if command.startswith("TIMER_WARNING"):
            return await self._handle_timer_warning(command)

        # Regular game command
        result = await self._send_command(command)
        return result

    async def _handle_stop_client(self, command: str) -> Dict:
        """Handle the STOP_CLIENT system command."""
        if not self._stop_client_func:
            logger.error("STOP_CLIENT called but no stop function configured")
            return {"success": False, "error": "Stop function not configured"}

        try:
            logger.info(f"⏰ Timer expired! Stopping client for account: {self._account_id}")

            # Notify user before stopping
            if self._notify_callback:
                await self._notify_callback(
                    f"⏰ **Timer expired!** Stopping RuneLite client..."
                )

            # Call the stop function
            result = await self._stop_client_func(self._account_id)

            if self._notify_callback:
                await self._notify_callback(
                    f"✅ Client stopped. Session ended."
                )

            return {"success": True, "result": result}

        except Exception as e:
            logger.error(f"Failed to stop client: {e}")
            if self._notify_callback:
                await self._notify_callback(f"❌ Failed to stop client: {e}")
            return {"success": False, "error": str(e)}

    async def _handle_timer_warning(self, command: str) -> Dict:
        """Handle the TIMER_WARNING notification command."""
        try:
            logger.info("⚠️ Timer warning: 5 minutes remaining!")

            if self._notify_callback:
                await self._notify_callback(
                    f"⚠️ **5 minutes remaining!** Client will stop soon.\n"
                    f"Use `cancel timer` to abort."
                )

            return {"success": True, "warning_sent": True}

        except Exception as e:
            logger.error(f"Failed to send timer warning: {e}")
            return {"success": False, "error": str(e)}

    async def execute_now(self, command: str, params: Dict = None) -> Dict:
        """Execute a command immediately (bypass queue)."""
        if params:
            param_str = " ".join(str(v) for v in params.values())
            full_command = f"{command} {param_str}"
        else:
            full_command = command

        return await self._execute_command(full_command)

    # =========================================================================
    # Callbacks
    # =========================================================================

    async def _on_task_complete(self, task: Task):
        """Called when a task completes."""
        if self._notify_callback:
            await self._notify_callback(
                f"Task completed: {task.command}"
            )

    async def _on_task_fail(self, task: Task):
        """Called when a task fails."""
        if self._notify_callback:
            await self._notify_callback(
                f"Task failed: {task.command} - {task.error}"
            )

    async def _on_condition_met(self, task: Task):
        """Called when a task's condition is met."""
        if self._notify_callback:
            await self._notify_callback(
                f"Condition met, starting: {task.command}"
            )

    # =========================================================================
    # Status and Info
    # =========================================================================

    def get_status(self) -> Dict:
        """Get full status of task manager."""
        return {
            "queue": self.queue.get_status(),
            "capabilities": {
                "total": len(self.registry.list_all()),
                "categories": self.registry.list_categories()
            }
        }

    def list_capabilities(self,
                          category: str = None,
                          keyword: str = None) -> List[Dict]:
        """List available capabilities."""
        cat = CommandCategory[category.upper()] if category else None
        caps = self.registry.find(category=cat, keyword=keyword)

        return [
            {
                "name": c.name,
                "category": c.category.value,
                "abstraction": c.abstraction.value,
                "description": c.description,
                "example": c.example
            }
            for c in caps
        ]

    def help_command(self, command: str) -> Optional[Dict]:
        """Get help for a specific command."""
        cap = self.registry.get(command)
        if not cap:
            return None

        return {
            "name": cap.name,
            "category": cap.category.value,
            "description": cap.description,
            "parameters": cap.parameters,
            "required": cap.required_params,
            "example": cap.example
        }


# =========================================================================
# Natural Language Parsing Helpers
# =========================================================================

def parse_level_condition(text: str) -> Optional[Condition]:
    """
    Parse level conditions from natural language.

    Examples:
        "when strength reaches 40" -> when_level("strength", 40)
        "after attack level up" -> after_level_up("attack")
        "at level 50 defence" -> when_level("defence", 50)
    """
    import re

    # "when X reaches N" or "at level N X"
    match = re.search(r'(?:when|at)\s+(\w+)\s+(?:reaches?|hits?|is)\s+(\d+)', text.lower())
    if match:
        skill = match.group(1)
        level = int(match.group(2))
        return when_level(skill, level)

    match = re.search(r'(?:at|when)\s+level\s+(\d+)\s+(\w+)', text.lower())
    if match:
        level = int(match.group(1))
        skill = match.group(2)
        return when_level(skill, level)

    # "after X level up"
    match = re.search(r'after\s+(\w+)\s+level\s*up', text.lower())
    if match:
        skill = match.group(1)
        return after_level_up(skill)

    return None


def parse_task_request(text: str, registry: CapabilityRegistry) -> Optional[Dict]:
    """
    Parse a natural language task request.

    Returns:
        {
            "command": "KILL_LOOP",
            "params": {"npc": "Giant_frog", "food": "none"},
            "condition": Condition or None
        }
    """
    text_lower = text.lower()

    # Check for conditional phrases
    condition = parse_level_condition(text)

    # Try to extract command
    # Look for known command patterns
    if "kill" in text_lower and "loop" in text_lower:
        # Extract NPC name
        import re
        match = re.search(r'kill\s*(?:loop)?\s+(\w+)', text_lower)
        if match:
            npc = match.group(1).replace(" ", "_").title()
            return {
                "command": "KILL_LOOP",
                "params": {"npc": npc, "food": "none", "count": 100},
                "condition": condition
            }

    if "fish" in text_lower:
        if "draynor" in text_lower:
            return {
                "command": "FISH_DRAYNOR_LOOP",
                "params": {},
                "condition": condition
            }

    if "attack style" in text_lower or "combat style" in text_lower:
        # Extract style
        styles = ["accurate", "aggressive", "defensive", "controlled", "strength"]
        for style in styles:
            if style in text_lower:
                return {
                    "command": "SET_ATTACK_STYLE",
                    "params": {"style": style},
                    "condition": condition
                }

    return None
