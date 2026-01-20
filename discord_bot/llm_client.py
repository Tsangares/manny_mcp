"""
LLM client wrapper - supports Ollama (primary), Gemini (fallback), Claude, OpenAI.
Ollama with qwen2.5:14b-multi is the primary provider for local inference.
Falls back to Gemini if Ollama is unavailable.

Supports function calling for tool execution.
"""
import os
import json
import asyncio
import logging
import httpx
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any, List, Callable

logger = logging.getLogger("llm_client")

# Thread pool for running blocking API calls
_executor = ThreadPoolExecutor(max_workers=2)

# Ollama configuration
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:14b-multi")


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
    """Wrapper for LLM API calls with tool/function support.

    Supports 'ollama' as primary provider with automatic fallback to 'gemini'.
    """

    def __init__(self, provider: str = "ollama", fallback_provider: str = "gemini"):
        self.provider = provider
        self.fallback_provider = fallback_provider
        self.tool_executor: Optional[Callable] = None
        self._fallback_client: Optional['LLMClient'] = None

        if provider == "ollama":
            # Ollama uses HTTP API - no special initialization needed
            self.ollama_host = OLLAMA_HOST
            self.ollama_model = OLLAMA_MODEL
            logger.info(f"Ollama client initialized: {self.ollama_host} model={self.ollama_model}")

            # Initialize fallback provider (lazy)
            self._fallback_provider_name = fallback_provider

        elif provider == "gemini":
            self._init_gemini()

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

    def _init_gemini(self):
        """Initialize Gemini provider."""
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

    def _get_fallback_client(self) -> 'LLMClient':
        """Get or create the fallback LLM client."""
        if self._fallback_client is None:
            logger.info(f"Initializing fallback provider: {self._fallback_provider_name}")
            self._fallback_client = LLMClient(
                provider=self._fallback_provider_name,
                fallback_provider=None  # No nested fallback
            )
            # Share the tool executor
            if self.tool_executor:
                self._fallback_client.set_tool_executor(self.tool_executor)
        return self._fallback_client

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
        Falls back to secondary provider if primary fails.
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

        # Try primary provider
        try:
            if self.provider == "ollama":
                return await self._chat_ollama(full_message, available_routines, conversation_history)
            elif self.provider == "gemini":
                return await self._chat_gemini(full_message, available_routines, conversation_history)
            elif self.provider == "claude":
                return await self._chat_claude(full_message, available_routines, conversation_history)
            elif self.provider == "openai":
                return await self._chat_openai(full_message, available_routines, conversation_history)
        except Exception as e:
            # If we have a fallback, try it
            if self.provider == "ollama" and self._fallback_provider_name:
                logger.warning(f"Ollama failed ({e}), falling back to {self._fallback_provider_name}")
                fallback = self._get_fallback_client()
                return await fallback.chat(message, game_state, available_routines, conversation_history)
            else:
                raise

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

    async def _chat_ollama(self, message: str, routines: List[str], history: List[Dict]) -> str:
        """Ollama-specific chat with tool calling support."""
        system_prompt = self.get_system_prompt(routines)

        # Convert history to Ollama format
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        messages.append({"role": "user", "content": message})

        # Build request with tools
        tools = self._get_ollama_tools() if self.tool_executor else None

        max_tool_calls = 5
        tool_calls_made = 0

        async with httpx.AsyncClient(timeout=120.0) as client:
            while tool_calls_made < max_tool_calls:
                request_body = {
                    "model": self.ollama_model,
                    "messages": messages,
                    "stream": False,
                }
                if tools:
                    request_body["tools"] = tools

                response = await client.post(
                    f"{self.ollama_host}/api/chat",
                    json=request_body
                )
                response.raise_for_status()
                result = response.json()

                assistant_message = result.get("message", {})
                tool_calls = assistant_message.get("tool_calls", [])

                if not tool_calls:
                    # No tool calls, return the response
                    return assistant_message.get("content", "No response generated")

                # Process tool calls
                messages.append(assistant_message)

                for tool_call in tool_calls:
                    tool_calls_made += 1
                    func = tool_call.get("function", {})
                    tool_name = func.get("name", "")
                    tool_args = func.get("arguments", {})

                    # Handle arguments - could be string or dict
                    if isinstance(tool_args, str):
                        try:
                            tool_args = json.loads(tool_args)
                        except json.JSONDecodeError:
                            tool_args = {}

                    logger.info(f"Ollama tool call: {tool_name}({tool_args})")

                    try:
                        result = await self.tool_executor(tool_name, tool_args)
                        result_str = json.dumps(result) if isinstance(result, dict) else str(result)
                    except Exception as e:
                        result_str = json.dumps({"error": str(e)})

                    # Add tool response
                    messages.append({
                        "role": "tool",
                        "content": result_str
                    })

            # Max tool calls reached
            return "Max tool calls reached. Please try a simpler request."

    def _get_ollama_tools(self) -> List[Dict]:
        """Convert tool definitions to Ollama format."""
        tools = []
        for tool in TOOL_DEFINITIONS:
            tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"]
                }
            })
        return tools

    async def _chat_gemini(self, message: str, routines: List[str], history: List[Dict]) -> str:
        """Gemini-specific chat with function calling support."""
        system_prompt = self.get_system_prompt(routines)

        # Convert history to Gemini format
        gemini_history = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            gemini_history.append({
                "role": role,
                "parts": [msg["content"]]
            })

        # Start a chat session with history
        chat = self.model.start_chat(history=gemini_history)

        # Build the full message with system context (only on first message)
        if not history:
            full_message = f"{system_prompt}\n\n---\n\n{message}"
        else:
            full_message = message

        # Send message in thread pool to avoid blocking Discord event loop
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(_executor, chat.send_message, full_message)

        # Handle function calls in a loop
        max_tool_calls = 5  # Prevent infinite loops
        tool_calls_made = 0
        tools_used = []  # Track what tools were called
        last_tool_result = None

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
                tools_used.append(tool_name)

                try:
                    result = await self.tool_executor(tool_name, tool_args)
                    last_tool_result = result
                    # Convert result to string for Gemini
                    result_str = json.dumps(result, indent=2) if isinstance(result, dict) else str(result)
                except Exception as e:
                    result_str = json.dumps({"error": str(e)})
                    last_tool_result = {"error": str(e)}

                function_responses.append(
                    self._genai.protos.Part(
                        function_response=self._genai.protos.FunctionResponse(
                            name=tool_name,
                            response={"result": result_str}
                        )
                    )
                )

            # Send function responses back to model with instruction to respond
            # Add a nudge to make sure the model responds with text
            function_responses.append(
                self._genai.protos.Part(text="Now please summarize the results and answer my question in plain English.")
            )
            # Run in thread pool to avoid blocking Discord
            response = await loop.run_in_executor(_executor, chat.send_message, function_responses)

        # Extract final text response
        text_parts = [
            part.text
            for part in response.candidates[0].content.parts
            if hasattr(part, 'text') and part.text
        ]

        if text_parts:
            return "\n".join(text_parts)

        # Fallback: generate a basic response from tool results
        if tools_used and last_tool_result:
            if "error" in last_tool_result:
                return f"I tried to check using {tools_used[-1]} but got an error: {last_tool_result['error']}"
            elif "alive" in last_tool_result:
                alive = last_tool_result.get("alive", False)
                return f"The client is {'running' if alive else 'not running'}."
            elif "state" in last_tool_result:
                return f"Got game state. Tools used: {', '.join(tools_used)}"
            else:
                return f"Completed. Used: {', '.join(tools_used)}"

        return "I processed your request but couldn't generate a response. Try asking again?"

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
