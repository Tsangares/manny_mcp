"""
Intent-based planning system for LLM-agnostic task execution.

Architecture:
1. IntentExtractor: LLM extracts structured intent (classification, not reasoning)
2. PlanGenerator: Code generates execution plan from intent
3. PlanExecutor: Directly executes steps without LLM

This separates "understanding what the user wants" from "figuring out how to do it",
making it work with smaller/weaker models.
"""
import json
import logging
import re
from typing import Optional, Dict, List, Any, Callable
from pydantic import BaseModel, Field
from dataclasses import dataclass

from enum import Enum

logger = logging.getLogger("intent_planner")


class Intent(Enum):
    """Known intent types that have pre-built execution plans."""
    TRAIN_UNTIL_LEVEL = "train_until_level"  # "kill X until level Y"
    GRIND_COUNT = "grind_count"              # "kill 500 frogs"
    GO_AND_DO = "go_and_do"                  # "go to lumbridge and fish"
    GO_TO = "go_to"                          # "go to varrock"
    CHECK_STATUS = "check_status"            # "what's my level"
    START_LOOP = "start_loop"                # "fish at draynor", "kill cows"
    STOP = "stop"                            # "stop", "cancel"
    UNKNOWN = "unknown"                      # Fallback to raw LLM


class ExtractedIntent(BaseModel):
    """Structured intent extracted from user message, validated by Pydantic."""
    intent: Intent
    target: Optional[str] = None
    location: Optional[str] = None
    goal_level: Optional[int] = None
    goal_count: Optional[int] = None
    skills: List[str] = Field(default_factory=list)
    food: Optional[str] = None
    action: Optional[str] = None
    raw_message: str = ""
    confidence: float = 0.5


# Intent extraction prompt - asks LLM to classify and output structured JSON
INTENT_EXTRACTION_PROMPT = """You are an expert at classifying user intent.
From the user's OSRS request, extract the intent and key entities into a JSON object that strictly follows this schema.
Output ONLY the JSON object.

JSON Schema:
{json_schema}

User Request: {message}

JSON OUTPUT:"""


class IntentExtractor:
    """Extracts structured intent from natural language using Pydantic validation."""

    def __init__(self, llm_chat_func: Callable):
        """
        Args:
            llm_chat_func: Async function that takes a message and returns LLM response.
        """
        self.llm_chat = llm_chat_func
        # Generate the schema once and cache it
        self.intent_schema = ExtractedIntent.model_json_schema()

    async def extract(self, message: str) -> ExtractedIntent:
        """Extract intent from user message using LLM and Pydantic validation."""
        # Include the JSON schema in the prompt to the LLM
        prompt = INTENT_EXTRACTION_PROMPT.format(
            message=message,
            json_schema=json.dumps(self.intent_schema, indent=2)
        )

        try:
            # Call LLM for extraction
            response_str = await self.llm_chat(prompt)

            # Use Pydantic to parse and validate the JSON response directly
            intent_model = ExtractedIntent.model_validate_json(
                response_str,
                context={"raw_message": message}
            )
            # Add the raw message to the validated model, as it's not part of the LLM response
            intent_model.raw_message = message
            return intent_model

        except Exception as e:
            logger.error(f"Intent extraction or Pydantic validation failed: {e}")
            # Fallback to UNKNOWN intent on any failure
            return ExtractedIntent(intent=Intent.UNKNOWN, raw_message=message)


@dataclass
class PlanStep:
    """A single step in an execution plan."""
    tool: str                    # Tool to call: "get_game_state", "send_command", etc.
    args: Dict[str, Any]         # Arguments for the tool
    description: str             # Human-readable description
    store_as: Optional[str] = None  # Key to store result for later steps
    condition: Optional[str] = None  # Optional condition to check before executing


class PlanGenerator:
    """Generates execution plans from extracted intents."""

    # Location aliases for lookup
    LOCATION_ALIASES = {
        "chickens": "lumbridge chickens",
        "chicken": "lumbridge chickens",
        "cows": "lumbridge cows",
        "cow": "lumbridge cows",
        "frogs": "lumbridge swamp frogs",
        "frog": "lumbridge swamp frogs",
        "giant frog": "lumbridge swamp frogs",
        "giant_frog": "lumbridge swamp frogs",
        "goblins": "lumbridge goblins",
        "goblin": "lumbridge goblins",
    }

    def generate(self, intent: ExtractedIntent, context: Dict[str, Any] = None) -> List[PlanStep]:
        """Generate execution plan from intent."""
        context = context or {}

        if intent.intent == Intent.TRAIN_UNTIL_LEVEL:
            return self._plan_train_until_level(intent, context)
        elif intent.intent == Intent.GRIND_COUNT:
            return self._plan_grind_count(intent, context)
        elif intent.intent == Intent.GO_AND_DO:
            return self._plan_go_and_do(intent, context)
        elif intent.intent == Intent.GO_TO:
            return self._plan_go_to(intent, context)
        elif intent.intent == Intent.CHECK_STATUS:
            return self._plan_check_status(intent, context)
        elif intent.intent == Intent.START_LOOP:
            return self._plan_start_loop(intent, context)
        elif intent.intent == Intent.STOP:
            return self._plan_stop(intent, context)
        else:
            return []  # Unknown intent - no plan

    def _plan_train_until_level(self, intent: ExtractedIntent, context: Dict) -> List[PlanStep]:
        """Plan for training until a level is reached."""
        steps = []
        target = intent.target or "chicken"
        goal_level = intent.goal_level or 10
        skills = intent.skills or ["attack", "strength", "defence"]
        food = intent.food or "none"

        # Step 1: Check current levels
        steps.append(PlanStep(
            tool="get_game_state",
            args={"fields": ["skills", "location"]},
            description="Check current skill levels",
            store_as="current_state"
        ))

        # Step 2: Look up target location
        location_query = intent.location or self.LOCATION_ALIASES.get(target.lower(), target)
        steps.append(PlanStep(
            tool="lookup_location",
            args={"location": location_query},
            description=f"Find location of {target}",
            store_as="target_location"
        ))

        # Step 3: Travel to location (if we have coords)
        steps.append(PlanStep(
            tool="send_command",
            args={"command": "GOTO {target_location.x} {target_location.y} {target_location.plane}"},
            description=f"Travel to {target} area",
            condition="target_location.found"
        ))

        # Step 4: Set up combat rotation if multiple skills
        if len(skills) > 1:
            # Queue style switches at level milestones
            style_map = {
                "attack": "Accurate",
                "strength": "Aggressive",
                "defence": "Defensive",
                "controlled": "Controlled"
            }

            for i, skill in enumerate(skills):
                if i < len(skills) - 1:
                    next_skill = skills[i + 1]
                    steps.append(PlanStep(
                        tool="queue_on_level",
                        args={
                            "skill": skill,
                            "level": goal_level,
                            "command": f"SWITCH_COMBAT_STYLE {style_map.get(next_skill, 'Accurate')}"
                        },
                        description=f"Switch to {next_skill} training at {skill} level {goal_level}"
                    ))

            # Start with first skill's style
            first_style = style_map.get(skills[0], "Accurate")
            steps.append(PlanStep(
                tool="send_command",
                args={"command": f"SWITCH_COMBAT_STYLE {first_style}"},
                description=f"Set combat style to train {skills[0]}"
            ))

        # Step 5: Start kill loop
        target_formatted = target.replace(" ", "_").capitalize()
        # Use high count since we're training until level
        steps.append(PlanStep(
            tool="send_command",
            args={"command": f"KILL_LOOP {target_formatted} {food} 5000"},
            description=f"Start killing {target} (will train until level {goal_level})"
        ))

        return steps

    def _plan_grind_count(self, intent: ExtractedIntent, context: Dict) -> List[PlanStep]:
        """Plan for killing/collecting a specific count."""
        steps = []
        target = intent.target or "chicken"
        count = intent.goal_count or 100
        food = intent.food or "none"

        # Look up location
        location_query = intent.location or self.LOCATION_ALIASES.get(target.lower(), target)
        steps.append(PlanStep(
            tool="lookup_location",
            args={"location": location_query},
            description=f"Find location of {target}",
            store_as="target_location"
        ))

        # Travel
        steps.append(PlanStep(
            tool="send_command",
            args={"command": "GOTO {target_location.x} {target_location.y} {target_location.plane}"},
            description=f"Travel to {target} area",
            condition="target_location.found"
        ))

        # Start loop with specific count
        target_formatted = target.replace(" ", "_").capitalize()
        steps.append(PlanStep(
            tool="send_command",
            args={"command": f"KILL_LOOP {target_formatted} {food} {count}"},
            description=f"Kill {count} {target}"
        ))

        return steps

    def _plan_go_and_do(self, intent: ExtractedIntent, context: Dict) -> List[PlanStep]:
        """Plan for traveling and performing an action."""
        steps = []
        location = intent.location or "lumbridge"
        action = intent.action or "fish"
        target = intent.target

        # Look up location
        steps.append(PlanStep(
            tool="lookup_location",
            args={"location": location},
            description=f"Find {location} coordinates",
            store_as="destination"
        ))

        # Travel
        steps.append(PlanStep(
            tool="send_command",
            args={"command": "GOTO {destination.x} {destination.y} {destination.plane}"},
            description=f"Travel to {location}",
            condition="destination.found"
        ))

        # Perform action based on type
        if action in ["fish", "fishing"]:
            if "draynor" in location.lower():
                steps.append(PlanStep(
                    tool="send_command",
                    args={"command": "FISH_DRAYNOR_LOOP"},
                    description="Start fishing loop at Draynor"
                ))
            else:
                steps.append(PlanStep(
                    tool="send_command",
                    args={"command": "FISH"},
                    description="Start fishing"
                ))
        elif action in ["kill", "attack", "fight"]:
            target_formatted = (target or "chicken").replace(" ", "_").capitalize()
            food = intent.food or "none"
            steps.append(PlanStep(
                tool="send_command",
                args={"command": f"KILL_LOOP {target_formatted} {food} 100"},
                description=f"Start killing {target}"
            ))
        elif action in ["chop", "woodcutting", "cut"]:
            steps.append(PlanStep(
                tool="send_command",
                args={"command": "CHOP_TREE"},
                description="Start chopping trees"
            ))

        return steps

    def _plan_go_to(self, intent: ExtractedIntent, context: Dict) -> List[PlanStep]:
        """Plan for just traveling somewhere."""
        location = intent.location or intent.target or "lumbridge"

        # Check if the location string looks like coordinates
        import re
        coord_match = re.match(r'^\s*(\d+)\s+(\d+)\s*$', location.strip())
        if coord_match:
            x, y = coord_match.groups()
            return [
                PlanStep(
                    tool="send_command",
                    args={"command": f"GOTO {x} {y} 0"},
                    description=f"Travel to coordinates {x}, {y}"
                )
            ]

        # If not coordinates, use the lookup-based plan
        return [
            PlanStep(
                tool="lookup_location",
                args={"location": location},
                description=f"Find {location} coordinates",
                store_as="destination"
            ),
            PlanStep(
                tool="send_command",
                args={"command": "GOTO {destination.x} {destination.y} {destination.plane}"},
                description=f"Travel to {location}",
                condition="destination.found"
            )
        ]

    def _plan_check_status(self, intent: ExtractedIntent, context: Dict) -> List[PlanStep]:
        """Plan for checking status/levels."""
        fields = ["location", "health"]

        if intent.skills:
            fields.append("skills")
        if "inventory" in intent.raw_message.lower():
            fields.append("inventory")
        if not intent.skills and "level" in intent.raw_message.lower():
            fields.append("skills")

        return [
            PlanStep(
                tool="get_game_state",
                args={"fields": fields},
                description="Get current game state",
                store_as="status"
            )
        ]

    def _plan_start_loop(self, intent: ExtractedIntent, context: Dict) -> List[PlanStep]:
        """Plan for starting a grinding loop."""
        action = intent.action or "kill"
        target = intent.target
        food = intent.food or "none"

        steps = []

        # Look up location if we have a target
        if target:
            location_query = intent.location or self.LOCATION_ALIASES.get(target.lower(), target)
            steps.append(PlanStep(
                tool="lookup_location",
                args={"location": location_query},
                description=f"Find {target} location",
                store_as="target_location"
            ))
            steps.append(PlanStep(
                tool="send_command",
                args={"command": "GOTO {target_location.x} {target_location.y} {target_location.plane}"},
                description=f"Travel to {target}",
                condition="target_location.found"
            ))

        # Start appropriate loop
        if action in ["fish", "fishing"]:
            if intent.location and "draynor" in intent.location.lower():
                steps.append(PlanStep(
                    tool="send_command",
                    args={"command": "FISH_DRAYNOR_LOOP"},
                    description="Start fishing at Draynor with banking"
                ))
            else:
                steps.append(PlanStep(
                    tool="send_command",
                    args={"command": "FISH"},
                    description="Start fishing"
                ))
        elif action in ["kill", "attack", "fight", "grind"]:
            target_formatted = (target or "chicken").replace(" ", "_").capitalize()
            count = intent.goal_count or 100
            steps.append(PlanStep(
                tool="send_command",
                args={"command": f"KILL_LOOP {target_formatted} {food} {count}"},
                description=f"Start killing {target}"
            ))
        elif action in ["chop", "woodcutting"]:
            steps.append(PlanStep(
                tool="send_command",
                args={"command": "CHOP_TREE"},
                description="Start woodcutting"
            ))

        return steps

    def _plan_stop(self, intent: ExtractedIntent, context: Dict) -> List[PlanStep]:
        """Plan for stopping current activity."""
        return [
            PlanStep(
                tool="send_command",
                args={"command": "STOP"},
                description="Stop current activity"
            )
        ]


class PlanExecutor:
    """Executes plan steps directly without LLM."""

    def __init__(self, tool_executor: Callable):
        """
        Args:
            tool_executor: Async function that executes tools.
                          Signature: (tool_name: str, args: dict) -> dict
        """
        self.tool_executor = tool_executor

    async def execute(self, steps: List[PlanStep]) -> Dict[str, Any]:
        """Execute all steps in the plan, collecting results."""
        context = {}
        results = []

        for i, step in enumerate(steps):
            logger.info(f"Executing step {i+1}/{len(steps)}: {step.description}")

            # Check condition if present
            if step.condition and not self._check_condition(step.condition, context):
                logger.info(f"Skipping step (condition not met): {step.condition}")
                results.append({
                    "step": step.description,
                    "skipped": True,
                    "reason": f"Condition not met: {step.condition}"
                })
                continue

            # Interpolate args with context
            args = self._interpolate_args(step.args, context)

            # Execute the tool
            try:
                result = await self.tool_executor(step.tool, args)

                # Store result if requested
                if step.store_as:
                    context[step.store_as] = result

                results.append({
                    "step": step.description,
                    "success": True,
                    "result": result
                })

            except Exception as e:
                logger.error(f"Step failed: {step.description} - {e}")
                results.append({
                    "step": step.description,
                    "success": False,
                    "error": str(e)
                })
                # Continue with other steps even if one fails

        return {
            "completed": True,
            "steps_executed": len([r for r in results if not r.get("skipped")]),
            "steps_total": len(steps),
            "context": context,
            "results": results
        }

    def _check_condition(self, condition: str, context: Dict) -> bool:
        """Check if a condition is met based on context."""
        # Parse condition like "target_location.found"
        parts = condition.split(".")

        value = context
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return False

            if value is None:
                return False

        return bool(value)

    def _interpolate_args(self, args: Dict, context: Dict) -> Dict:
        """Replace {context.key} placeholders in args with actual values."""
        result = {}

        for key, value in args.items():
            if isinstance(value, str) and "{" in value:
                # Find all placeholders
                result[key] = self._interpolate_string(value, context)
            else:
                result[key] = value

        return result

    def _interpolate_string(self, template: str, context: Dict) -> str:
        """Interpolate a string template with context values."""
        import re

        def replace_match(match):
            path = match.group(1)
            parts = path.split(".")

            value = context
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    return match.group(0)  # Keep original if can't resolve

                if value is None:
                    return match.group(0)

            return str(value)

        return re.sub(r'\{([^}]+)\}', replace_match, template)


class IntentPlanner:
    """
    Main coordinator: extracts intent, generates plan, executes it.

    Usage:
        planner = IntentPlanner(llm_chat_func, tool_executor)
        result = await planner.process("kill chickens until 15 in all combat")
    """

    def __init__(self, llm_chat_func: Callable, tool_executor: Callable):
        self.extractor = IntentExtractor(llm_chat_func)
        self.generator = PlanGenerator()
        self.executor = PlanExecutor(tool_executor)

    async def process(self, message: str) -> Dict[str, Any]:
        """
        Process a user message: extract intent, generate plan, execute.

        Returns dict with:
            - intent: The extracted intent
            - plan: List of planned steps
            - execution: Results of execution
            - summary: Human-readable summary
        """
        # Step 1: Extract intent
        logger.info(f"Extracting intent from: {message[:50]}...")
        intent = await self.extractor.extract(message)
        logger.info(f"Extracted intent: {intent.intent.value}, target={intent.target}, goal_level={intent.goal_level}")

        # Step 2: Generate plan
        if intent.intent == Intent.UNKNOWN:
            return {
                "intent": intent,
                "plan": [],
                "execution": None,
                "summary": None,
                "fallback_to_llm": True  # Signal to use raw LLM
            }

        plan = self.generator.generate(intent)
        logger.info(f"Generated plan with {len(plan)} steps")

        if not plan:
            return {
                "intent": intent,
                "plan": [],
                "execution": None,
                "summary": "No plan generated for this intent",
                "fallback_to_llm": True
            }

        # Step 3: Execute plan
        execution = await self.executor.execute(plan)

        # Step 4: Generate summary
        summary = self._generate_summary(intent, plan, execution)

        return {
            "intent": intent,
            "plan": plan,
            "execution": execution,
            "summary": summary,
            "fallback_to_llm": False
        }

    def _generate_summary(self, intent: ExtractedIntent, plan: List[PlanStep], execution: Dict) -> str:
        """Generate human-readable summary of what was done."""
        context = execution.get("context", {})

        if intent.intent == Intent.TRAIN_UNTIL_LEVEL:
            skills_str = ", ".join(intent.skills) if intent.skills else "combat"
            current_levels = ""
            if "current_state" in context:
                state = context["current_state"].get("state", {})
                skills_data = state.get("skills", {})
                if skills_data and intent.skills:
                    levels = []
                    for skill in intent.skills:
                        skill_info = skills_data.get(skill, {})
                        if isinstance(skill_info, dict):
                            levels.append(f"{skill.title()}: {skill_info.get('level', '?')}")
                    if levels:
                        current_levels = f" Current: {', '.join(levels)}."

            return (
                f"Started training {skills_str} to level {intent.goal_level} "
                f"on {intent.target or 'target'}.{current_levels} "
                f"Combat style will rotate automatically."
            )

        elif intent.intent == Intent.GRIND_COUNT:
            return f"Started killing {intent.goal_count} {intent.target or 'targets'}."

        elif intent.intent == Intent.GO_AND_DO:
            return f"Traveling to {intent.location} to {intent.action}."

        elif intent.intent == Intent.GO_TO:
            location = intent.location or intent.target
            return f"Traveling to {location}."

        elif intent.intent == Intent.CHECK_STATUS:
            if "status" in context:
                state = context["status"].get("state", {})
                parts = []
                if "location" in state:
                    loc = state["location"]
                    parts.append(f"Location: ({loc.get('x')}, {loc.get('y')})")
                if "health" in state:
                    hp = state["health"]
                    parts.append(f"HP: {hp.get('current')}/{hp.get('max')}")
                if "skills" in state and intent.skills:
                    skills_data = state["skills"]
                    for skill in intent.skills:
                        skill_info = skills_data.get(skill, {})
                        if isinstance(skill_info, dict):
                            parts.append(f"{skill.title()}: {skill_info.get('level')}")
                return " | ".join(parts) if parts else "Status retrieved."
            return "Status check complete."

        elif intent.intent == Intent.START_LOOP:
            return f"Started {intent.action or 'activity'} loop on {intent.target or 'target'}."

        elif intent.intent == Intent.STOP:
            return "Stopped current activity."

        return f"Executed {len(plan)} steps."
