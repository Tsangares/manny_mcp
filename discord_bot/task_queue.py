"""
Task Queue with conditional execution and state monitoring.

Enables complex task flows like:
- "Kill frogs until level 40, then switch to hill giants"
- "Fish until inventory full, bank, repeat"
- "After strength level up, change to defensive style"
"""
import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Any, Union
from enum import Enum
from datetime import datetime
import json

logger = logging.getLogger("task_queue")


class TaskStatus(Enum):
    PENDING = "pending"
    WAITING = "waiting"      # Waiting for condition
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ConditionType(Enum):
    IMMEDIATE = "immediate"           # Run right away
    LEVEL_REACHED = "level_reached"   # Skill hits target level
    LEVEL_UP = "level_up"            # Any level up in skill
    INVENTORY_FULL = "inventory_full"
    INVENTORY_EMPTY = "inventory_empty"
    INVENTORY_HAS = "inventory_has"   # Has specific item
    INVENTORY_COUNT = "inventory_count"  # Item count condition
    HEALTH_BELOW = "health_below"
    HEALTH_ABOVE = "health_above"
    LOCATION_REACHED = "location_reached"
    TASK_COMPLETED = "task_completed"  # Another task finished
    TIME_ELAPSED = "time_elapsed"      # Seconds since queue start
    IDLE = "idle"                      # Player is idle
    CUSTOM = "custom"                  # Custom condition function


@dataclass
class Condition:
    """A condition that must be met before a task runs."""
    type: ConditionType
    params: Dict[str, Any] = field(default_factory=dict)

    # For readable display
    def __str__(self):
        if self.type == ConditionType.IMMEDIATE:
            return "immediately"
        elif self.type == ConditionType.LEVEL_REACHED:
            return f"when {self.params.get('skill', 'skill')} reaches {self.params.get('level', '?')}"
        elif self.type == ConditionType.LEVEL_UP:
            return f"after {self.params.get('skill', 'any')} level up"
        elif self.type == ConditionType.INVENTORY_FULL:
            return "when inventory is full"
        elif self.type == ConditionType.HEALTH_BELOW:
            return f"when health below {self.params.get('threshold', '?')}%"
        elif self.type == ConditionType.TASK_COMPLETED:
            return f"after task '{self.params.get('task_id', '?')}' completes"
        return f"{self.type.value}: {self.params}"


@dataclass
class Task:
    """A single task in the queue."""
    id: str
    command: str                          # The command to execute
    params: Dict[str, Any] = field(default_factory=dict)
    condition: Condition = field(default_factory=lambda: Condition(ConditionType.IMMEDIATE))
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 0                      # Higher = runs first
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict] = None
    error: Optional[str] = None

    # For chaining
    on_complete: Optional[str] = None      # Task ID to trigger on completion
    on_fail: Optional[str] = None          # Task ID to trigger on failure

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "command": self.command,
            "params": self.params,
            "condition": str(self.condition),
            "status": self.status.value,
            "priority": self.priority
        }


class StateMonitor:
    """Monitors game state and checks conditions."""

    def __init__(self, get_state_func: Callable):
        self._get_state = get_state_func
        self._previous_state: Optional[Dict] = None
        self._level_history: Dict[str, int] = {}  # skill -> last known level

    async def check_condition(self, condition: Condition) -> bool:
        """Check if a condition is met."""
        if condition.type == ConditionType.IMMEDIATE:
            return True

        try:
            state = await self._get_state()
            player = state.get("state", {})

            if condition.type == ConditionType.LEVEL_REACHED:
                skill = condition.params.get("skill", "").lower()
                target = condition.params.get("level", 99)
                skills = player.get("skills", {})
                current = skills.get(skill, {}).get("level", 1)
                return current >= target

            elif condition.type == ConditionType.LEVEL_UP:
                skill = condition.params.get("skill", "").lower()
                skills = player.get("skills", {})

                if skill == "any":
                    # Check if any skill leveled up
                    for s, data in skills.items():
                        current = data.get("level", 1)
                        previous = self._level_history.get(s, current)
                        if current > previous:
                            self._level_history[s] = current
                            return True
                    # Update history
                    for s, data in skills.items():
                        self._level_history[s] = data.get("level", 1)
                    return False
                else:
                    current = skills.get(skill, {}).get("level", 1)
                    previous = self._level_history.get(skill, current)
                    self._level_history[skill] = current
                    return current > previous

            elif condition.type == ConditionType.INVENTORY_FULL:
                inventory = player.get("inventory", {})
                used = inventory.get("used", 0)
                capacity = inventory.get("capacity", 28)
                return used >= capacity

            elif condition.type == ConditionType.INVENTORY_EMPTY:
                inventory = player.get("inventory", {})
                used = inventory.get("used", 0)
                return used == 0

            elif condition.type == ConditionType.INVENTORY_HAS:
                item_name = condition.params.get("item", "").lower()
                inventory = player.get("inventory", {})
                items = inventory.get("items", [])
                return any(item_name in str(item).lower() for item in items if item)

            elif condition.type == ConditionType.INVENTORY_COUNT:
                item_name = condition.params.get("item", "").lower()
                target_count = condition.params.get("count", 1)
                operator = condition.params.get("operator", ">=")
                inventory = player.get("inventory", {})
                items = inventory.get("items", [])

                count = sum(1 for item in items
                           if item and item_name in str(item).lower())

                if operator == ">=":
                    return count >= target_count
                elif operator == "<=":
                    return count <= target_count
                elif operator == "==":
                    return count == target_count
                elif operator == ">":
                    return count > target_count
                elif operator == "<":
                    return count < target_count

            elif condition.type == ConditionType.HEALTH_BELOW:
                threshold = condition.params.get("threshold", 50)
                health = player.get("health", {})
                current = health.get("current", 1)
                max_hp = health.get("max", 1)
                percent = (current / max_hp) * 100
                return percent < threshold

            elif condition.type == ConditionType.HEALTH_ABOVE:
                threshold = condition.params.get("threshold", 50)
                health = player.get("health", {})
                current = health.get("current", 1)
                max_hp = health.get("max", 1)
                percent = (current / max_hp) * 100
                return percent > threshold

            elif condition.type == ConditionType.LOCATION_REACHED:
                target_x = condition.params.get("x", 0)
                target_y = condition.params.get("y", 0)
                tolerance = condition.params.get("tolerance", 5)
                location = player.get("location", {})
                current_x = location.get("x", 0)
                current_y = location.get("y", 0)
                distance = abs(current_x - target_x) + abs(current_y - target_y)
                return distance <= tolerance

            elif condition.type == ConditionType.IDLE:
                scenario = player.get("scenario", {})
                return scenario.get("currentTask") == "Idle"

            return False

        except Exception as e:
            logger.error(f"Error checking condition {condition}: {e}")
            return False

    def update_state(self, state: Dict):
        """Update previous state for comparison."""
        self._previous_state = state


class TaskQueue:
    """
    Manages a queue of tasks with conditional execution.

    Features:
    - Priority-based execution
    - Conditional triggers (level up, inventory full, etc.)
    - Task chaining (on_complete, on_fail)
    - State monitoring
    - Persistence (optional)
    """

    def __init__(self, execute_func: Callable, get_state_func: Callable):
        self._execute = execute_func  # Function to execute commands
        self._get_state = get_state_func
        self._monitor = StateMonitor(get_state_func)

        self._tasks: Dict[str, Task] = {}
        self._task_counter = 0
        self._running = False
        self._current_task: Optional[Task] = None
        self._loop_task: Optional[asyncio.Task] = None

        # Callbacks
        self._on_task_complete: Optional[Callable] = None
        self._on_task_fail: Optional[Callable] = None
        self._on_condition_met: Optional[Callable] = None

    def set_callbacks(self,
                      on_complete: Callable = None,
                      on_fail: Callable = None,
                      on_condition: Callable = None):
        """Set callback functions for task events."""
        self._on_task_complete = on_complete
        self._on_task_fail = on_fail
        self._on_condition_met = on_condition

    def add(self,
            command: str,
            params: Dict = None,
            condition: Condition = None,
            priority: int = 0,
            task_id: str = None,
            on_complete: str = None,
            on_fail: str = None) -> str:
        """
        Add a task to the queue.

        Returns the task ID.
        """
        self._task_counter += 1
        task_id = task_id or f"task_{self._task_counter}"

        task = Task(
            id=task_id,
            command=command,
            params=params or {},
            condition=condition or Condition(ConditionType.IMMEDIATE),
            priority=priority,
            on_complete=on_complete,
            on_fail=on_fail
        )

        self._tasks[task_id] = task
        logger.info(f"Added task {task_id}: {command} ({task.condition})")

        return task_id

    def add_sequence(self, tasks: List[Dict]) -> List[str]:
        """
        Add a sequence of tasks that run in order.

        Each task waits for the previous to complete.
        """
        task_ids = []
        prev_id = None

        for i, task_def in enumerate(tasks):
            # Default condition: wait for previous task
            condition = task_def.get("condition")
            if condition is None and prev_id:
                condition = Condition(
                    ConditionType.TASK_COMPLETED,
                    {"task_id": prev_id}
                )

            task_id = self.add(
                command=task_def["command"],
                params=task_def.get("params", {}),
                condition=condition,
                priority=task_def.get("priority", 0)
            )

            task_ids.append(task_id)
            prev_id = task_id

        return task_ids

    def add_conditional(self,
                        condition_type: str,
                        condition_params: Dict,
                        command: str,
                        params: Dict = None) -> str:
        """
        Convenience method to add a conditional task.

        Examples:
            add_conditional("level_reached", {"skill": "strength", "level": 40},
                           "SET_ATTACK_STYLE", {"style": "defensive"})

            add_conditional("inventory_full", {},
                           "BANK_DEPOSIT_ALL", {})
        """
        cond_type = ConditionType[condition_type.upper()]
        condition = Condition(cond_type, condition_params)

        return self.add(command, params, condition)

    def remove(self, task_id: str) -> bool:
        """Remove a task from the queue."""
        if task_id in self._tasks:
            task = self._tasks[task_id]
            if task.status == TaskStatus.RUNNING:
                task.status = TaskStatus.CANCELLED
            del self._tasks[task_id]
            logger.info(f"Removed task {task_id}")
            return True
        return False

    def clear(self):
        """Clear all pending tasks."""
        to_remove = [tid for tid, t in self._tasks.items()
                     if t.status in (TaskStatus.PENDING, TaskStatus.WAITING)]
        for tid in to_remove:
            del self._tasks[tid]
        logger.info(f"Cleared {len(to_remove)} tasks")

    def get_status(self) -> Dict:
        """Get queue status."""
        by_status = {}
        for task in self._tasks.values():
            status = task.status.value
            by_status[status] = by_status.get(status, 0) + 1

        return {
            "running": self._running,
            "current_task": self._current_task.id if self._current_task else None,
            "total_tasks": len(self._tasks),
            "by_status": by_status,
            "tasks": [t.to_dict() for t in self._tasks.values()]
        }

    def get_pending(self) -> List[Task]:
        """Get all pending/waiting tasks sorted by priority."""
        pending = [t for t in self._tasks.values()
                   if t.status in (TaskStatus.PENDING, TaskStatus.WAITING)]
        return sorted(pending, key=lambda t: -t.priority)

    async def start(self):
        """Start processing the queue."""
        if self._running:
            logger.warning("Queue already running")
            return

        self._running = True
        self._loop_task = asyncio.create_task(self._process_loop())
        logger.info("Task queue started")

    async def stop(self):
        """Stop processing the queue."""
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        logger.info("Task queue stopped")

    async def _process_loop(self):
        """Main processing loop."""
        while self._running:
            try:
                # Check conditions for waiting tasks
                await self._check_waiting_tasks()

                # Get next task to run
                next_task = self._get_next_runnable()

                if next_task:
                    await self._run_task(next_task)
                else:
                    # Nothing to do, wait a bit
                    await asyncio.sleep(1.0)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in process loop: {e}", exc_info=True)
                await asyncio.sleep(1.0)

    async def _check_waiting_tasks(self):
        """Check if any waiting tasks' conditions are now met."""
        for task in self._tasks.values():
            if task.status == TaskStatus.WAITING:
                if await self._monitor.check_condition(task.condition):
                    task.status = TaskStatus.PENDING
                    logger.info(f"Condition met for task {task.id}: {task.condition}")
                    if self._on_condition_met:
                        await self._on_condition_met(task)

            elif task.status == TaskStatus.PENDING:
                # Check if task has a non-immediate condition
                if task.condition.type != ConditionType.IMMEDIATE:
                    if not await self._monitor.check_condition(task.condition):
                        task.status = TaskStatus.WAITING

    def _get_next_runnable(self) -> Optional[Task]:
        """Get the next task that can run."""
        pending = [t for t in self._tasks.values()
                   if t.status == TaskStatus.PENDING]

        if not pending:
            return None

        # Sort by priority (higher first), then by creation time
        pending.sort(key=lambda t: (-t.priority, t.created_at))
        return pending[0]

    async def _run_task(self, task: Task):
        """Execute a single task."""
        self._current_task = task
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()

        logger.info(f"Running task {task.id}: {task.command}")

        try:
            # Build the full command with params
            if task.params:
                param_str = " ".join(str(v) for v in task.params.values())
                full_command = f"{task.command} {param_str}"
            else:
                full_command = task.command

            # Execute
            result = await self._execute(full_command)
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()

            logger.info(f"Task {task.id} completed")

            # Trigger on_complete chain
            if task.on_complete and task.on_complete in self._tasks:
                chained = self._tasks[task.on_complete]
                chained.status = TaskStatus.PENDING
                logger.info(f"Triggered chained task {task.on_complete}")

            if self._on_task_complete:
                await self._on_task_complete(task)

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now()

            logger.error(f"Task {task.id} failed: {e}")

            # Trigger on_fail chain
            if task.on_fail and task.on_fail in self._tasks:
                chained = self._tasks[task.on_fail]
                chained.status = TaskStatus.PENDING
                logger.info(f"Triggered failure handler task {task.on_fail}")

            if self._on_task_fail:
                await self._on_task_fail(task)

        finally:
            self._current_task = None

            # Check if condition was for this task completing
            for other in self._tasks.values():
                if (other.status == TaskStatus.WAITING and
                    other.condition.type == ConditionType.TASK_COMPLETED and
                    other.condition.params.get("task_id") == task.id):
                    other.status = TaskStatus.PENDING


# Convenience functions for creating conditions

def when_level(skill: str, level: int) -> Condition:
    """Create a 'level reached' condition."""
    return Condition(ConditionType.LEVEL_REACHED, {"skill": skill, "level": level})


def after_level_up(skill: str = "any") -> Condition:
    """Create a 'level up' condition."""
    return Condition(ConditionType.LEVEL_UP, {"skill": skill})


def when_inventory_full() -> Condition:
    """Create an 'inventory full' condition."""
    return Condition(ConditionType.INVENTORY_FULL)


def when_health_below(percent: int) -> Condition:
    """Create a 'health below' condition."""
    return Condition(ConditionType.HEALTH_BELOW, {"threshold": percent})


def after_task(task_id: str) -> Condition:
    """Create a 'task completed' condition."""
    return Condition(ConditionType.TASK_COMPLETED, {"task_id": task_id})


def immediately() -> Condition:
    """Create an immediate condition (no waiting)."""
    return Condition(ConditionType.IMMEDIATE)
