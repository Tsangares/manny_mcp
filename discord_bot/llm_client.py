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


def _normalize_args(obj: Any) -> Any:
    """Recursively normalize arguments to standard Python types.

    Converts protobuf types, iterables, etc. to standard Python dict/list/str.
    """
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: _normalize_args(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_normalize_args(item) for item in obj]
    # Handle protobuf RepeatedComposite and similar iterables
    if hasattr(obj, '__iter__'):
        try:
            return [_normalize_args(item) for item in obj]
        except:
            pass
    # Fallback: convert to string
    return str(obj)


def _safe_json_dumps(obj: Any) -> str:
    """Safely serialize object to JSON, converting non-serializable types to strings.

    Handles protobuf types (like RepeatedComposite) and other exotic types
    that might leak through from Google's SDK.
    """
    def default_handler(o):
        # Handle any non-serializable type by converting to string
        try:
            # Try to convert to list (for iterable protobuf types)
            if hasattr(o, '__iter__') and not isinstance(o, (str, bytes, dict)):
                return list(o)
        except:
            pass
        # Fallback to string representation
        return str(o)

    try:
        return json.dumps(obj, default=default_handler)
    except Exception as e:
        # Ultimate fallback
        return json.dumps({"serialization_error": str(e), "type": str(type(obj))})

# Ollama configuration
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "hermes3:8b-llama3.1-q4_K_M")


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
    },
    {
        "name": "lookup_location",
        "description": "Look up OSRS coordinates for a location. Use this when you need to GOTO somewhere but don't know the coordinates. Returns x, y, plane for the location.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "Location name to look up (e.g., 'lumbridge swamp', 'draynor fishing', 'varrock bank', 'ge', 'cows')"
                }
            },
            "required": ["location"]
        }
    },
    {
        "name": "list_plugin_commands",
        "description": "List all available plugin commands with their syntax. Use this when you're unsure about command format or want to discover available commands. Can filter by category.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Optional category filter (e.g., 'combat', 'skilling', 'banking', 'movement')"
                }
            }
        }
    },
    {
        "name": "get_command_help",
        "description": "Get detailed help for a specific command including usage and examples.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Command name to get help for (e.g., 'KILL_LOOP', 'GOTO', 'BANK_WITHDRAW')"
                }
            },
            "required": ["command"]
        }
    }
]


def get_gemini_tools():
    """Convert tool definitions to Gemini function declarations format for new SDK."""
    from google.genai import types

    tools = []
    for tool in TOOL_DEFINITIONS:
        # Build parameter schema dict
        properties = {}
        for k, v in tool["parameters"].get("properties", {}).items():
            prop_schema = {"type": v.get("type", "string").upper()}
            if v.get("description"):
                prop_schema["description"] = v["description"]
            if v.get("type") == "array" and "items" in v:
                prop_schema["items"] = {"type": v["items"].get("type", "string").upper()}
            if v.get("enum"):
                prop_schema["enum"] = v["enum"]
            properties[k] = prop_schema

        func_decl = types.FunctionDeclaration(
            name=tool["name"],
            description=tool["description"],
            parameters=types.Schema(
                type="OBJECT",
                properties=properties,
                required=tool["parameters"].get("required", [])
            )
        )
        tools.append(func_decl)

    return tools


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
        """Initialize Gemini provider using the new google.genai SDK."""
        from google import genai
        from google.genai import types

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")

        # Create client with the new SDK
        self._genai_client = genai.Client(api_key=api_key)
        self._genai_types = types
        self._tools = get_gemini_tools()
        self._gemini_model = "gemini-2.0-flash-lite"
        logger.info(f"Gemini client initialized with model {self._gemini_model}")

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

        # Log which provider/model is handling this request
        if self.provider == "ollama":
            logger.info(f"Processing request with Ollama ({self.ollama_model})")
        elif self.provider == "gemini":
            logger.info(f"Processing request with Gemini (gemini-2.0-flash-lite)")
        else:
            logger.info(f"Processing request with {self.provider}")

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

        max_tool_calls = 10  # Allow more for multi-step tasks
        tool_calls_made = 0
        llm_turns = 0  # Track LLM API round-trips

        async with httpx.AsyncClient(timeout=120.0) as client:
            while tool_calls_made < max_tool_calls:
                llm_turns += 1
                logger.info(f"Ollama turn {llm_turns} (tools so far: {tool_calls_made})")

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
                    logger.info(f"Ollama completed: {llm_turns} turns, {tool_calls_made} tool calls")
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

                    # Ensure tool_args are standard Python types (not protobuf)
                    tool_args = _normalize_args(tool_args)

                    logger.info(f"Ollama tool call: {tool_name}({tool_args})")

                    try:
                        result = await self.tool_executor(tool_name, tool_args)
                        # Use safe serialization to handle any non-JSON types (like protobuf)
                        result_str = _safe_json_dumps(result)
                    except Exception as e:
                        result_str = json.dumps({"error": str(e)})

                    # Add tool response
                    messages.append({
                        "role": "tool",
                        "content": result_str
                    })

            # Max tool calls reached
            logger.warning(f"Ollama hit limit: {llm_turns} turns, {tool_calls_made} tool calls")
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
        """Gemini-specific chat with function calling support using new google.genai SDK."""
        types = self._genai_types
        system_prompt = self.get_system_prompt(routines)

        # Build contents list with history
        contents = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(types.Content(
                role=role,
                parts=[types.Part.from_text(msg["content"])]
            ))

        # Add current message with system context on first message
        if not history:
            full_message = f"{system_prompt}\n\n---\n\n{message}"
        else:
            full_message = message

        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(full_message)]
        ))

        # Configure with tools
        config = types.GenerateContentConfig(
            tools=self._tools,
            temperature=0.7
        )

        # Handle function calls in a loop
        max_tool_calls = 5
        tool_calls_made = 0
        llm_turns = 0  # Track LLM API round-trips
        tools_used = []
        last_tool_result = None

        while tool_calls_made < max_tool_calls:
            llm_turns += 1
            logger.info(f"Gemini turn {llm_turns} (tools so far: {tool_calls_made})")

            # Generate response
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                _executor,
                lambda: self._genai_client.models.generate_content(
                    model=self._gemini_model,
                    contents=contents,
                    config=config
                )
            )

            # Check for function calls
            if not response.candidates or not response.candidates[0].content.parts:
                break

            function_calls = []
            text_parts = []
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    function_calls.append(part.function_call)
                if hasattr(part, 'text') and part.text:
                    text_parts.append(part.text)

            if not function_calls:
                # No function calls, return text response
                logger.info(f"Gemini completed: {llm_turns} turns, {tool_calls_made} tool calls")
                if text_parts:
                    return "\n".join(text_parts)
                break

            if not self.tool_executor:
                break

            # Add model's response to contents
            contents.append(response.candidates[0].content)

            # Execute function calls and build responses
            function_response_parts = []
            for fc in function_calls:
                tool_calls_made += 1
                tool_name = fc.name
                tool_args = dict(fc.args) if fc.args else {}
                tools_used.append(tool_name)

                try:
                    result = await self.tool_executor(tool_name, tool_args)
                    last_tool_result = result
                    result_data = result if isinstance(result, dict) else {"result": str(result)}
                except Exception as e:
                    result_data = {"error": str(e)}
                    last_tool_result = result_data

                function_response_parts.append(
                    types.Part.from_function_response(
                        name=tool_name,
                        response=result_data
                    )
                )

            # Add function responses to contents
            contents.append(types.Content(
                role="user",
                parts=function_response_parts
            ))

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
