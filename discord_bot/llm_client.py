"""
LLM client wrapper - supports Gemini (default), Claude, OpenAI.
Gemini is cheapest, so we start there.
"""
import os
import json
from typing import Optional, Dict, Any, List


class LLMClient:
    """Wrapper for LLM API calls with tool/function support."""

    def __init__(self, provider: str = "gemini"):
        self.provider = provider

        if provider == "gemini":
            import google.generativeai as genai
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY environment variable not set")
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
            self._genai = genai

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

    def get_system_prompt(self, available_routines: List[str]) -> str:
        """Generate system prompt with available routines."""
        routines_list = "\n".join(f"  - {r}" for r in available_routines)

        return f"""You are an OSRS (Old School RuneScape) bot controller. You help the user manage their bot by:
1. Understanding their goals (e.g., "make money", "train fishing", "do a quest")
2. Checking the current game state
3. Selecting and running appropriate routines
4. Monitoring progress and reporting status

Available routines:
{routines_list}

Available actions you can recommend:
- run_routine <routine_name> [loops] - Execute a YAML routine
- stop - Stop current activity
- status - Get current game state
- screenshot - Get a screenshot

When the user asks you to do something:
1. First assess if you need more info about game state
2. Recommend specific actions
3. Explain your reasoning briefly

Keep responses concise - this is a chat interface, not a document."""

    async def chat(
        self,
        message: str,
        game_state: Optional[Dict[str, Any]] = None,
        available_routines: List[str] = None,
        conversation_history: List[Dict] = None
    ) -> str:
        """
        Send a message to the LLM and get a response.

        Args:
            message: User's message
            game_state: Current game state (optional context)
            available_routines: List of available routine names
            conversation_history: Previous messages for context

        Returns:
            LLM response text
        """
        available_routines = available_routines or []
        conversation_history = conversation_history or []

        # Build context
        context_parts = []
        if game_state:
            # Compact summary
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
        """Gemini-specific chat."""
        system_prompt = self.get_system_prompt(routines)

        # Gemini uses a chat session
        chat = self.model.start_chat(history=[])

        # Send system context as first message if no history
        if not history:
            # Gemini doesn't have a system role, so we prepend to first message
            full_message = f"{system_prompt}\n\n---\n\n{message}"
        else:
            full_message = message

        response = chat.send_message(full_message)
        return response.text

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
