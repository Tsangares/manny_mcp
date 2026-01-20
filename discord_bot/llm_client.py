"""
LLM client wrapper - supports Gemini (default), Claude, OpenAI.
Gemini is cheapest, so we start there.

Supports function calling for tool execution.
"""
import os
import json
from typing import Optional, Dict, Any, List, Callable


# Tool definitions for Gemini function calling
TOOL_DEFINITIONS = [
    {
        "name": "get_game_state",
        "description": "Get current game state including player location, inventory, health, skills. Use fields parameter to request specific data.",
        "parameters": {
            "type": "object",
            "properties": {
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Fields to include: location, inventory, equipment, skills, health, dialogue, nearby, combat, scenario"
                }
            }
        }
    },
    {
        "name": "get_screenshot",
        "description": "Capture a screenshot of the RuneLite game window.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "check_health",
        "description": "Check if RuneLite client is healthy - verifies process running, state file updating, window exists.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "send_command",
        "description": "Send a command to the manny plugin. Examples: 'GOTO 3200 3200 0', 'BANK_OPEN', 'STOP', 'INTERACT_NPC Cook Talk-to'",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The command to send to the plugin"
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "start_runelite",
        "description": "Start the RuneLite client. Use this when the client is not running.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "stop_runelite",
        "description": "Stop the RuneLite client.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "restart_runelite",
        "description": "Restart the RuneLite client. Stops then starts it again.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "auto_reconnect",
        "description": "Handle disconnection by clicking OK dialog and waiting for reconnect. Use when client is disconnected.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "run_routine",
        "description": "Run a YAML routine file. Routines automate multi-step tasks like quests, skilling, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "routine_path": {
                    "type": "string",
                    "description": "Path to the routine file, e.g., 'combat/hill_giants.yaml' or 'skilling/fishing_shrimps.yaml'"
                },
                "loops": {
                    "type": "integer",
                    "description": "Number of times to run the routine (default: 1)"
                }
            },
            "required": ["routine_path"]
        }
    },
    {
        "name": "list_routines",
        "description": "List all available routine YAML files.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_logs",
        "description": "Get recent logs from the RuneLite plugin. Useful for debugging issues.",
        "parameters": {
            "type": "object",
            "properties": {
                "level": {
                    "type": "string",
                    "description": "Minimum log level: DEBUG, INFO, WARN, ERROR, ALL (default: WARN)"
                },
                "since_seconds": {
                    "type": "integer",
                    "description": "Only logs from last N seconds (default: 30)"
                },
                "grep": {
                    "type": "string",
                    "description": "Filter to lines containing this substring"
                }
            }
        }
    },
    {
        "name": "switch_account",
        "description": "Switch to a different OSRS account.",
        "parameters": {
            "type": "object",
            "properties": {
                "account_id": {
                    "type": "string",
                    "description": "Account ID to switch to (e.g., 'main', 'aux')"
                }
            },
            "required": ["account_id"]
        }
    },
    {
        "name": "list_accounts",
        "description": "List all available OSRS accounts.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
]


def get_gemini_tools():
    """Convert tool definitions to Gemini function declarations format."""
    import google.generativeai as genai

    functions = []
    for tool in TOOL_DEFINITIONS:
        properties = {}
        for k, v in tool["parameters"].get("properties", {}).items():
            prop_type = v.get("type", "string")

            if prop_type == "array":
                # Arrays need items specification
                items_type = v.get("items", {}).get("type", "string")
                properties[k] = genai.protos.Schema(
                    type=genai.protos.Type.ARRAY,
                    items=genai.protos.Schema(type=_get_gemini_type(items_type)),
                    description=v.get("description", "")
                )
            else:
                properties[k] = genai.protos.Schema(
                    type=_get_gemini_type(prop_type),
                    description=v.get("description", "")
                )

        functions.append(genai.protos.FunctionDeclaration(
            name=tool["name"],
            description=tool["description"],
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties=properties,
                required=tool["parameters"].get("required", [])
            )
        ))

    return genai.protos.Tool(function_declarations=functions)


def _get_gemini_type(type_str: str):
    """Convert JSON schema type to Gemini type."""
    import google.generativeai as genai

    type_map = {
        "string": genai.protos.Type.STRING,
        "integer": genai.protos.Type.INTEGER,
        "number": genai.protos.Type.NUMBER,
        "boolean": genai.protos.Type.BOOLEAN,
        "array": genai.protos.Type.ARRAY,
        "object": genai.protos.Type.OBJECT
    }
    return type_map.get(type_str, genai.protos.Type.STRING)


class LLMClient:
    """Wrapper for LLM API calls with tool/function support."""

    def __init__(self, provider: str = "gemini"):
        self.provider = provider
        self.tool_executor: Optional[Callable] = None

        if provider == "gemini":
            import google.generativeai as genai
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY environment variable not set")
            genai.configure(api_key=api_key)

            # Create model with tools
            self._genai = genai
            self._tools = get_gemini_tools()
            self.model = genai.GenerativeModel(
                'gemini-2.5-flash-lite',
                tools=[self._tools]
            )

        elif provider == "claude":
            from anthropic import Anthropic
            self.client = Anthropic()  # Uses ANTHROPIC_API_KEY env var
            self.model_name = "claude-sonnet-4-20250514"

        elif provider == "openai":
            from openai import OpenAI
            self.client = OpenAI()  # Uses OPENAI_API_KEY env var
            self.model_name = "gpt-4o-mini"

        else:
            raise ValueError(f"Unknown provider: {provider}")

    def set_tool_executor(self, executor: Callable):
        """Set the function that executes tool calls.

        The executor should accept (tool_name: str, arguments: dict) and return a result dict.
        """
        self.tool_executor = executor

    def get_system_prompt(self, available_routines: List[str]) -> str:
        """Generate system prompt from CONTEXT.md and available routines."""
        from pathlib import Path

        # Load context from file
        context_file = Path(__file__).parent / "CONTEXT.md"
        try:
            context = context_file.read_text()
        except FileNotFoundError:
            context = "You are an OSRS bot controller assistant."

        # Append available routines
        if available_routines:
            routines_list = "\n".join(f"  - {r}" for r in available_routines[:30])
            context += f"\n\n## Available Routines\n\n{routines_list}"

        return context

    async def chat(
        self,
        message: str,
        game_state: Optional[Dict[str, Any]] = None,
        available_routines: List[str] = None,
        conversation_history: List[Dict] = None
    ) -> str:
        """
        Send a message to the LLM and get a response.
        Handles tool calls automatically if tool_executor is set.
        """
        available_routines = available_routines or []
        conversation_history = conversation_history or []

        # Build context
        context_parts = []
        if game_state:
            summary = self._summarize_state(game_state)
            context_parts.append(f"Current game state:\n{summary}")

        context = "\n\n".join(context_parts) if context_parts else ""
        full_message = f"{context}\n\nUser: {message}" if context else message

        if self.provider == "gemini":
            return await self._chat_gemini(full_message, available_routines, conversation_history)
        elif self.provider == "claude":
            return await self._chat_claude(full_message, available_routines, conversation_history)
        elif self.provider == "openai":
            return await self._chat_openai(full_message, available_routines, conversation_history)

    def _summarize_state(self, state: Dict[str, Any]) -> str:
        """Create a compact summary of game state."""
        lines = []

        if "player" in state:
            p = state["player"]
            if "location" in p:
                loc = p["location"]
                lines.append(f"Location: ({loc.get('x')}, {loc.get('y')}, plane {loc.get('plane')})")
            if "health" in p:
                h = p["health"]
                lines.append(f"Health: {h.get('current')}/{h.get('max')}")
            if "inventory" in p:
                inv = p["inventory"]
                lines.append(f"Inventory: {inv.get('used', 0)}/{inv.get('capacity', 28)} slots")
            if "skills" in p:
                skills = p["skills"]
                combat_skills = ["attack", "strength", "defence", "hitpoints", "ranged", "magic", "prayer"]
                skill_strs = []
                for skill in combat_skills:
                    if skill in skills:
                        skill_strs.append(f"{skill[:3].title()}: {skills[skill].get('level', '?')}")
                if skill_strs:
                    lines.append(f"Combat: {', '.join(skill_strs)}")

        if "scenario" in state:
            s = state["scenario"]
            lines.append(f"Task: {s.get('currentTask', 'Idle')}")
            if s.get("running"):
                lines.append(f"Progress: {s.get('progress', {}).get('percentage', 0):.0f}%")

        return "\n".join(lines) if lines else "No state available"

    async def _chat_gemini(self, message: str, routines: List[str], history: List[Dict]) -> str:
        """Gemini-specific chat with function calling support."""
        system_prompt = self.get_system_prompt(routines)

        # Build the full message with system context
        if not history:
            full_message = f"{system_prompt}\n\n---\n\n{message}"
        else:
            full_message = message

        # Start a chat session
        chat = self.model.start_chat(history=[])

        # Send message and handle potential tool calls
        response = chat.send_message(full_message)

        # Handle function calls in a loop
        max_tool_calls = 5  # Prevent infinite loops
        tool_calls_made = 0

        while response.candidates[0].content.parts:
            # Check if there are function calls
            function_calls = [
                part.function_call
                for part in response.candidates[0].content.parts
                if hasattr(part, 'function_call') and part.function_call.name
            ]

            if not function_calls:
                # No function calls, extract text response
                break

            if tool_calls_made >= max_tool_calls:
                break

            if not self.tool_executor:
                # No executor set, can't handle tool calls
                break

            # Execute each function call
            function_responses = []
            for fc in function_calls:
                tool_calls_made += 1
                tool_name = fc.name
                tool_args = dict(fc.args) if fc.args else {}

                try:
                    result = await self.tool_executor(tool_name, tool_args)
                    # Convert result to string for Gemini
                    result_str = json.dumps(result, indent=2) if isinstance(result, dict) else str(result)
                except Exception as e:
                    result_str = json.dumps({"error": str(e)})

                function_responses.append(
                    self._genai.protos.Part(
                        function_response=self._genai.protos.FunctionResponse(
                            name=tool_name,
                            response={"result": result_str}
                        )
                    )
                )

            # Send function responses back to model
            response = chat.send_message(function_responses)

        # Extract final text response
        text_parts = [
            part.text
            for part in response.candidates[0].content.parts
            if hasattr(part, 'text') and part.text
        ]

        return "\n".join(text_parts) if text_parts else "Action completed."

    async def _chat_claude(self, message: str, routines: List[str], history: List[Dict]) -> str:
        """Claude-specific chat."""
        system_prompt = self.get_system_prompt(routines)

        messages = history + [{"role": "user", "content": message}]

        response = self.client.messages.create(
            model=self.model_name,
            max_tokens=1024,
            system=system_prompt,
            messages=messages
        )

        return response.content[0].text

    async def _chat_openai(self, message: str, routines: List[str], history: List[Dict]) -> str:
        """OpenAI-specific chat."""
        system_prompt = self.get_system_prompt(routines)

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            max_tokens=1024
        )

        return response.choices[0].message.content
