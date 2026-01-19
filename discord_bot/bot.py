How """
Discord bot for OSRS automation control.
Receives commands via DM, uses LLM to interpret, calls MCP tools directly.
"""
import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

import discord
from discord.ext import commands

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from discord_bot.llm_client import LLMClient

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord_bot")


class OSRSBot(commands.Bot):
    """Discord bot for controlling OSRS automation."""

    def __init__(self, llm_provider: str = "gemini", account_id: str = "aux"):
        # DM-focused bot - minimal intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.dm_messages = True

        super().__init__(command_prefix="!", intents=intents)

        self.llm = LLMClient(provider=llm_provider)
        self.account_id = account_id
        self.conversation_history: Dict[int, List[Dict]] = {}  # user_id -> history
        self.owner_id: Optional[int] = None  # Set to restrict access

        # MCP tools - imported lazily to avoid circular imports
        self._tools_loaded = False
        self._monitoring = None
        self._commands = None
        self._routine = None

    def _load_tools(self):
        """Lazy load MCP tools."""
        if self._tools_loaded:
            return

        from mcptools.tools import monitoring, commands as cmd_tools, routine
        from mcptools.config import ServerConfig
        from mcptools.runelite_manager import MultiRuneLiteManager

        # Initialize dependencies
        config = ServerConfig.load()
        manager = MultiRuneLiteManager(config)

        # Set up tool dependencies
        monitoring.set_dependencies(manager, config)
        cmd_tools.set_dependencies(manager, config)
        routine.set_dependencies(manager, config)

        self._monitoring = monitoring
        self._commands = cmd_tools
        self._routine = routine
        self._tools_loaded = True
        logger.info("MCP tools loaded")

    async def on_ready(self):
        logger.info(f"Bot ready: {self.user.name} ({self.user.id})")
        logger.info("Send me a DM to control the bot!")

    async def on_message(self, message: discord.Message):
        # Ignore own messages
        if message.author == self.user:
            return

        # Only respond to DMs (or optionally specific channels)
        if not isinstance(message.channel, discord.DMChannel):
            return

        # Optional: restrict to specific user
        if self.owner_id and message.author.id != self.owner_id:
            await message.channel.send("Sorry, you're not authorized to control this bot.")
            return

        # Process commands first (if using prefix commands)
        await self.process_commands(message)

        # If not a command, treat as natural language
        if not message.content.startswith("!"):
            await self.handle_natural_language(message)

    async def handle_natural_language(self, message: discord.Message):
        """Handle natural language messages via LLM."""
        self._load_tools()

        user_id = message.author.id
        content = message.content.strip()

        # Get conversation history for this user
        history = self.conversation_history.get(user_id, [])

        # Get current game state for context
        try:
            state_result = await self._monitoring.handle_get_game_state({
                "account_id": self.account_id,
                "fields": ["location", "inventory", "skills", "health"]
            })
            game_state = state_result.get("state", {})
        except Exception as e:
            logger.error(f"Failed to get game state: {e}")
            game_state = None

        # Get available routines
        routines = self._get_available_routines()

        # Show typing indicator
        async with message.channel.typing():
            try:
                response = await self.llm.chat(
                    message=content,
                    game_state={"player": game_state} if game_state else None,
                    available_routines=routines,
                    conversation_history=history
                )

                # Update history (keep last 10 exchanges)
                history.append({"role": "user", "content": content})
                history.append({"role": "assistant", "content": response})
                self.conversation_history[user_id] = history[-20:]

                # Check if LLM suggested an action we should auto-execute
                action = self._parse_action(response)
                if action:
                    action_result = await self._execute_action(action)
                    if action_result:
                        response += f"\n\n**Executed:** {action_result}"

                await message.channel.send(response[:2000])  # Discord limit

            except Exception as e:
                logger.error(f"LLM error: {e}")
                await message.channel.send(f"Error: {e}")

    def _get_available_routines(self) -> List[str]:
        """Get list of available routine files."""
        routines_dir = Path(__file__).parent.parent / "routines"
        if not routines_dir.exists():
            return []

        routines = []
        for yaml_file in routines_dir.rglob("*.yaml"):
            rel_path = yaml_file.relative_to(routines_dir)
            routines.append(str(rel_path))
        return sorted(routines)

    def _parse_action(self, response: str) -> Optional[Dict]:
        """Parse LLM response for actionable commands."""
        response_lower = response.lower()

        # Look for action patterns
        if "run_routine" in response_lower:
            # Extract routine name
            import re
            match = re.search(r'run_routine\s+([^\s]+)(?:\s+(\d+))?', response_lower)
            if match:
                return {
                    "type": "run_routine",
                    "routine": match.group(1),
                    "loops": int(match.group(2)) if match.group(2) else 1
                }

        if "!stop" in response_lower or "action: stop" in response_lower:
            return {"type": "stop"}

        return None

    async def _execute_action(self, action: Dict) -> Optional[str]:
        """Execute a parsed action."""
        try:
            if action["type"] == "run_routine":
                routine_path = f"routines/{action['routine']}"
                if not routine_path.endswith(".yaml"):
                    routine_path += ".yaml"

                result = await self._routine.handle_execute_routine({
                    "routine_path": routine_path,
                    "max_loops": action.get("loops", 1),
                    "account_id": self.account_id
                })
                return f"Started routine: {action['routine']}"

            elif action["type"] == "stop":
                await self._commands.handle_send_command({
                    "command": "STOP",
                    "account_id": self.account_id
                })
                return "Stopped current activity"

        except Exception as e:
            logger.error(f"Action execution error: {e}")
            return f"Failed: {e}"

        return None


# Direct commands (prefix-based, for quick actions)
@commands.command(name="status")
async def status(ctx: commands.Context):
    """Get current bot status."""
    bot: OSRSBot = ctx.bot
    bot._load_tools()

    try:
        health = await bot._monitoring.handle_check_health({
            "account_id": bot.account_id
        })

        state = await bot._monitoring.handle_get_game_state({
            "account_id": bot.account_id,
            "fields": ["location", "health", "inventory"]
        })

        player = state.get("state", {})
        loc = player.get("location", {})
        hp = player.get("health", {})
        inv = player.get("inventory", {})

        msg = f"""**Bot Status**
Account: {bot.account_id}
Alive: {health.get('alive', False)}
Location: ({loc.get('x')}, {loc.get('y')})
Health: {hp.get('current', '?')}/{hp.get('max', '?')}
Inventory: {inv.get('used', '?')}/{inv.get('capacity', 28)} slots"""

        await ctx.send(msg)
    except Exception as e:
        await ctx.send(f"Error getting status: {e}")


@commands.command(name="screenshot")
async def screenshot(ctx: commands.Context):
    """Get a screenshot of the game."""
    bot: OSRSBot = ctx.bot
    bot._load_tools()

    try:
        result = await bot._monitoring.handle_get_screenshot({
            "account_id": bot.account_id
        })

        if "path" in result:
            await ctx.send(file=discord.File(result["path"]))
        else:
            await ctx.send("Failed to capture screenshot")
    except Exception as e:
        await ctx.send(f"Error: {e}")


@commands.command(name="stop")
async def stop(ctx: commands.Context):
    """Stop current bot activity."""
    bot: OSRSBot = ctx.bot
    bot._load_tools()

    try:
        await bot._commands.handle_send_command({
            "command": "STOP",
            "account_id": bot.account_id
        })
        await ctx.send("Stop command sent")
    except Exception as e:
        await ctx.send(f"Error: {e}")


@commands.command(name="run")
async def run_routine(ctx: commands.Context, routine: str, loops: int = 1):
    """Run a routine. Usage: !run combat/hill_giants.yaml 5"""
    bot: OSRSBot = ctx.bot
    bot._load_tools()

    routine_path = f"routines/{routine}"
    if not routine_path.endswith(".yaml"):
        routine_path += ".yaml"

    try:
        await ctx.send(f"Starting routine: {routine} ({loops} loops)")
        result = await bot._routine.handle_execute_routine({
            "routine_path": routine_path,
            "max_loops": loops,
            "account_id": bot.account_id
        })
        await ctx.send(f"Routine completed: {result.get('status', 'unknown')}")
    except Exception as e:
        await ctx.send(f"Error: {e}")


@commands.command(name="routines")
async def list_routines(ctx: commands.Context):
    """List available routines."""
    bot: OSRSBot = ctx.bot
    routines = bot._get_available_routines()

    if routines:
        msg = "**Available Routines:**\n" + "\n".join(f"- {r}" for r in routines[:20])
        if len(routines) > 20:
            msg += f"\n... and {len(routines) - 20} more"
    else:
        msg = "No routines found"

    await ctx.send(msg)


def setup_commands(bot: OSRSBot):
    """Add commands to bot."""
    bot.add_command(status)
    bot.add_command(screenshot)
    bot.add_command(stop)
    bot.add_command(run_routine)
    bot.add_command(list_routines)


def create_bot(
    llm_provider: str = "gemini",
    account_id: str = "main",
    owner_id: Optional[int] = None
) -> OSRSBot:
    """Create and configure the bot."""
    bot = OSRSBot(llm_provider=llm_provider, account_id=account_id)
    bot.owner_id = owner_id
    setup_commands(bot)
    return bot
