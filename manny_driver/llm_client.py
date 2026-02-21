"""Multi-provider LLM client abstraction.

Supports Anthropic (Claude), Google (Gemini), OpenAI, and Ollama.
Each provider's native tool calling is used where available.
Ollama uses its native tool calling API.
"""
import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("manny_driver.llm")


@dataclass
class ToolCall:
    """A tool call from the LLM."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """Unified response from any LLM provider."""
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = ""
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class LLMClient(ABC):
    """Abstract base for LLM providers."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict],
        system: str = "",
    ) -> LLMResponse:
        """Send messages and return a response (may contain tool calls)."""
        ...

    @abstractmethod
    def format_tool_result(self, tool_call_id: str, result: str) -> dict:
        """Format a tool result message for this provider."""
        ...

    @abstractmethod
    def format_assistant_with_tool_calls(self, response: LLMResponse) -> dict:
        """Format the assistant's tool-calling message for history."""
        ...


class AnthropicClient(LLMClient):
    """Claude via Anthropic API with native tool_use."""

    def __init__(self, model: str):
        import anthropic
        self.client = anthropic.AsyncAnthropic()
        self.model = model

    async def chat(self, messages, tools, system=""):
        import anthropic
        kwargs = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
        if system:
            kwargs["system"] = system

        response = await self.client.messages.create(**kwargs)

        llm_resp = LLMResponse(
            stop_reason=response.stop_reason or "",
            input_tokens=getattr(response.usage, "input_tokens", 0),
            output_tokens=getattr(response.usage, "output_tokens", 0),
        )

        for block in response.content:
            if block.type == "text":
                llm_resp.text += block.text
            elif block.type == "tool_use":
                llm_resp.tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input or {},
                ))

        return llm_resp

    def format_tool_result(self, tool_call_id, result):
        return {
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_call_id,
                "content": result,
            }],
        }

    def format_assistant_with_tool_calls(self, response):
        content = []
        if response.text:
            content.append({"type": "text", "text": response.text})
        for tc in response.tool_calls:
            content.append({
                "type": "tool_use",
                "id": tc.id,
                "name": tc.name,
                "input": tc.arguments,
            })
        return {"role": "assistant", "content": content}


class GeminiClient(LLMClient):
    """Google Gemini with native function calling."""

    def __init__(self, model: str):
        from google import genai
        from google.genai import types
        self._genai = genai
        self._types = types
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set")
        self._client = genai.Client(api_key=api_key)
        self.model = model
        self._call_counter = 0

    async def chat(self, messages, tools, system=""):
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        types = self._types

        # Build contents
        contents = []
        for msg in messages:
            if msg["role"] == "user":
                # Check if this is a tool result message
                if isinstance(msg.get("content"), list):
                    parts = []
                    for item in msg["content"]:
                        if item.get("type") == "tool_result":
                            parts.append(types.Part.from_function_response(
                                name=item.get("_tool_name", "unknown"),
                                response={"result": item["content"]},
                            ))
                        else:
                            parts.append(types.Part.from_text(text=str(item.get("content", item.get("text", "")))))
                    contents.append(types.Content(role="user", parts=parts))
                else:
                    text = msg["content"]
                    contents.append(types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=text)],
                    ))
            elif msg["role"] == "assistant" or msg["role"] == "model":
                parts = []
                if isinstance(msg.get("content"), list):
                    for item in msg["content"]:
                        if item.get("type") == "tool_use":
                            parts.append(types.Part.from_function_call(
                                name=item["name"],
                                args=item.get("input", {}),
                            ))
                        elif item.get("type") == "text" and item.get("text"):
                            parts.append(types.Part.from_text(text=item["text"]))
                elif msg.get("content"):
                    parts.append(types.Part.from_text(text=msg["content"]))
                if parts:
                    contents.append(types.Content(role="model", parts=parts))

        # Build Gemini tool declarations wrapped in a Tool object
        def _to_gemini_schema(schema_dict: dict) -> dict:
            """Convert a JSON Schema property to Gemini Schema dict."""
            result = {"type": schema_dict.get("type", "STRING").upper()}
            if schema_dict.get("description"):
                result["description"] = schema_dict["description"]
            if schema_dict.get("enum"):
                result["enum"] = schema_dict["enum"]
            if result["type"] == "ARRAY" and "items" in schema_dict:
                result["items"] = _to_gemini_schema(schema_dict["items"])
            if result["type"] == "OBJECT" and "properties" in schema_dict:
                result["properties"] = {
                    k: _to_gemini_schema(v)
                    for k, v in schema_dict["properties"].items()
                }
            return result

        func_decls = []
        for t in tools:
            params = t.get("parameters", {})
            props = {}
            for k, v in params.get("properties", {}).items():
                props[k] = _to_gemini_schema(v)
            func_decls.append(types.FunctionDeclaration(
                name=t["name"],
                description=t.get("description", ""),
                parameters=types.Schema(
                    type="OBJECT",
                    properties=props,
                    required=params.get("required", []),
                ) if props else None,
            ))

        gemini_tools = [types.Tool(function_declarations=func_decls)] if func_decls else None

        config = types.GenerateContentConfig(
            tools=gemini_tools,
            temperature=0.3,
            system_instruction=system if system else None,
        )

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            ),
        )

        llm_resp = LLMResponse()

        # Track token usage from Gemini response metadata
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            llm_resp.input_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0) or 0
            llm_resp.output_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0) or 0

        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    self._call_counter += 1
                    llm_resp.tool_calls.append(ToolCall(
                        id=f"gemini_{self._call_counter}",
                        name=fc.name,
                        arguments=dict(fc.args) if fc.args else {},
                    ))
                if hasattr(part, "text") and part.text:
                    llm_resp.text += part.text

        return llm_resp

    def format_tool_result(self, tool_call_id, result):
        # For Gemini we store the tool name in the result for later reconstruction
        name = tool_call_id.replace("gemini_", "tool_")
        return {
            "role": "user",
            "content": [{"type": "tool_result", "content": result, "_tool_name": name}],
        }

    def format_assistant_with_tool_calls(self, response):
        content = []
        if response.text:
            content.append({"type": "text", "text": response.text})
        for tc in response.tool_calls:
            content.append({
                "type": "tool_use",
                "id": tc.id,
                "name": tc.name,
                "input": tc.arguments,
            })
        return {"role": "assistant", "content": content}


class OpenAIClient(LLMClient):
    """OpenAI with native function calling."""

    def __init__(self, model: str):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI()
        self.model = model

    async def chat(self, messages, tools, system=""):
        oai_messages = []
        if system:
            oai_messages.append({"role": "system", "content": system})

        for msg in messages:
            if msg["role"] == "assistant" and isinstance(msg.get("content"), list):
                # Reconstruct OpenAI assistant message with tool_calls
                oai_msg = {"role": "assistant", "content": None, "tool_calls": []}
                for item in msg["content"]:
                    if item.get("type") == "text":
                        oai_msg["content"] = item.get("text", "")
                    elif item.get("type") == "tool_use":
                        oai_msg["tool_calls"].append({
                            "id": item["id"],
                            "type": "function",
                            "function": {
                                "name": item["name"],
                                "arguments": json.dumps(item.get("input", {})),
                            },
                        })
                if not oai_msg["tool_calls"]:
                    del oai_msg["tool_calls"]
                oai_messages.append(oai_msg)
            elif msg["role"] == "user" and isinstance(msg.get("content"), list):
                # Tool results
                for item in msg["content"]:
                    if item.get("type") == "tool_result":
                        oai_messages.append({
                            "role": "tool",
                            "tool_call_id": item.get("tool_use_id", ""),
                            "content": item["content"],
                        })
            else:
                oai_messages.append(msg)

        oai_tools = tools if tools else None

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=oai_messages,
            tools=oai_tools,
            max_completion_tokens=4096,
        )

        choice = response.choices[0]
        llm_resp = LLMResponse(
            text=choice.message.content or "",
            stop_reason=choice.finish_reason or "",
            input_tokens=getattr(response.usage, "prompt_tokens", 0),
            output_tokens=getattr(response.usage, "completion_tokens", 0),
        )

        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                llm_resp.tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments) if tc.function.arguments else {},
                ))

        return llm_resp

    def format_tool_result(self, tool_call_id, result):
        return {
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_call_id,
                "content": result,
            }],
        }

    def format_assistant_with_tool_calls(self, response):
        content = []
        if response.text:
            content.append({"type": "text", "text": response.text})
        for tc in response.tool_calls:
            content.append({
                "type": "tool_use",
                "id": tc.id,
                "name": tc.name,
                "input": tc.arguments,
            })
        return {"role": "assistant", "content": content}


class OllamaClient(LLMClient):
    """Ollama with native tool calling via HTTP API."""

    def __init__(self, model: str):
        self.model = model
        self.host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self._call_counter = 0

    async def chat(self, messages, tools, system=""):
        import httpx

        # Convert messages to Ollama format
        ollama_msgs = []
        if system:
            ollama_msgs.append({"role": "system", "content": system})

        for msg in messages:
            if msg["role"] == "assistant" and isinstance(msg.get("content"), list):
                # Reconstruct assistant message with tool_calls for Ollama
                text_parts = []
                tool_calls = []
                for item in msg["content"]:
                    if item.get("type") == "text" and item.get("text"):
                        text_parts.append(item["text"])
                    elif item.get("type") == "tool_use":
                        tool_calls.append({
                            "function": {
                                "name": item["name"],
                                "arguments": item.get("input", {}),
                            }
                        })
                ollama_msg = {"role": "assistant", "content": "\n".join(text_parts)}
                if tool_calls:
                    ollama_msg["tool_calls"] = tool_calls
                ollama_msgs.append(ollama_msg)
            elif msg["role"] == "user" and isinstance(msg.get("content"), list):
                # Tool results
                for item in msg["content"]:
                    if item.get("type") == "tool_result":
                        ollama_msgs.append({
                            "role": "tool",
                            "content": item["content"],
                        })
            else:
                ollama_msgs.append({
                    "role": msg["role"],
                    "content": msg.get("content", ""),
                })

        # Convert tools to Ollama format (OpenAI-compatible)
        ollama_tools = None
        if tools:
            ollama_tools = [{
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema") or t.get("parameters", {}),
                },
            } for t in tools]

        body = {
            "model": self.model,
            "messages": ollama_msgs,
            "stream": False,
            "options": {"temperature": 0.3},
        }
        if ollama_tools:
            body["tools"] = ollama_tools

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{self.host}/api/chat", json=body)
            resp.raise_for_status()
            data = resp.json()

        assistant_msg = data.get("message", {})
        llm_resp = LLMResponse(
            text=assistant_msg.get("content", ""),
            input_tokens=data.get("prompt_eval_count", 0) or 0,
            output_tokens=data.get("eval_count", 0) or 0,
        )

        for tc in assistant_msg.get("tool_calls", []):
            func = tc.get("function", {})
            self._call_counter += 1
            args = func.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            llm_resp.tool_calls.append(ToolCall(
                id=f"ollama_{self._call_counter}",
                name=func.get("name", ""),
                arguments=args,
            ))

        return llm_resp

    def format_tool_result(self, tool_call_id, result):
        return {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": tool_call_id, "content": result}],
        }

    def format_assistant_with_tool_calls(self, response):
        content = []
        if response.text:
            content.append({"type": "text", "text": response.text})
        for tc in response.tool_calls:
            content.append({
                "type": "tool_use",
                "id": tc.id,
                "name": tc.name,
                "input": tc.arguments,
            })
        return {"role": "assistant", "content": content}


def create_client(provider: str, model: str) -> LLMClient:
    """Factory: create the appropriate LLM client."""
    if provider == "anthropic":
        return AnthropicClient(model)
    elif provider == "gemini":
        return GeminiClient(model)
    elif provider == "openai":
        return OpenAIClient(model)
    elif provider == "ollama":
        return OllamaClient(model)
    else:
        raise ValueError(f"Unknown provider: {provider}")
