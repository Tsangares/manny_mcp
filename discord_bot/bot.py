"""
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
from discord import app_commands
from discord.ext import commands
import yaml

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from discord_bot.llm_client import LLMClient

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord_bot")


class OSRSBot(commands.Bot):
    """Discord bot for controlling OSRS automation."""

    def __init__(self, llm_provider: str = "ollama", account_id: str = "aux"):
        # DM-focused bot - minimal intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.dm_messages = True

        super().__init__(command_prefix="!", intents=intents, help_command=None)

        self.llm = LLMClient(provider=llm_provider)
        self.account_id = account_id
        self.conversation_history: Dict[int, List[Dict]] = {}  # user_id -> history
        self.owner_id: Optional[int] = None  # Set to restrict access

        # MCP tools - imported lazily to avoid circular imports
        self._tools_loaded = False
        self._monitoring = None
        self._commands = None
        self._routine = None
        self._screenshot = None

    def _load_tools(self):
        """Lazy load MCP tools."""
        if self._tools_loaded:
            return

        from mcptools.tools import monitoring, commands as cmd_tools, routine, screenshot
        from mcptools.config import ServerConfig
        from mcptools.runelite_manager import MultiRuneLiteManager

        # Initialize dependencies
        config = ServerConfig.load()
        manager = MultiRuneLiteManager(config)

        # Create a simple send_command_with_response wrapper for tools that need it
        async def send_command_with_response(command: str, timeout_ms: int = 10000, account_id: str = None):
            """Simple command sender - writes to file and polls for response."""
            import json
            import time
            import asyncio

            command_file = config.get_command_file(account_id)
            response_file = config.get_response_file(account_id)

            # Get current response timestamp
            old_ts = 0
            try:
                with open(response_file) as f:
                    old_response = json.load(f)
                    old_ts = old_response.get("timestamp", 0)
            except:
                pass

            # Send command
            with open(command_file, "w") as f:
                f.write(command + "\n")

            # Poll for response
            start = time.time()
            while (time.time() - start) < (timeout_ms / 1000.0):
                try:
                    with open(response_file) as f:
                        response = json.load(f)
                    if response.get("timestamp", 0) > old_ts:
                        return response
                except:
                    pass
                await asyncio.sleep(0.3)

            return {"status": "timeout", "error": "No response received"}

        # Set up tool dependencies
        monitoring.set_dependencies(manager, config)
        cmd_tools.set_dependencies(send_command_with_response, config)
        routine.set_dependencies(send_command_with_response, config)
        screenshot.set_dependencies(manager, config)

        self._monitoring = monitoring
        self._commands = cmd_tools
        self._routine = routine
        self._screenshot = screenshot
        self._manager = manager
        self._config = config
        self._tools_loaded = True

        # Set up the tool executor for LLM function calling
        self.llm.set_tool_executor(self._execute_tool)
        logger.info("MCP tools loaded")

    async def on_ready(self):
        logger.info(f"Bot ready: {self.user.name} ({self.user.id})")

        # Sync slash commands
        try:
            # Check for guild-specific sync (instant) via env var
            guild_id = os.environ.get("DISCORD_GUILD_ID")
            if guild_id:
                guild = discord.Object(id=int(guild_id))
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                logger.info(f"Synced {len(synced)} slash commands to guild {guild_id} (instant)")
            else:
                # Global sync (can take up to 1 hour)
                synced = await self.tree.sync()
                logger.info(f"Synced {len(synced)} slash commands globally (may take up to 1 hour)")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

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

                # Try to attach a screenshot with the response
                screenshot_file = None
                try:
                    ss_result = self._screenshot._take_screenshot(account_id=self.account_id)
                    if ss_result.get("success") and "path" in ss_result:
                        screenshot_file = discord.File(ss_result["path"])
                except Exception as e:
                    logger.debug(f"Auto-screenshot failed: {e}")

                if screenshot_file:
                    await message.channel.send(response[:2000], file=screenshot_file)
                else:
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

    def _get_available_accounts(self) -> Dict[str, str]:
        """Get available accounts from credentials file.

        Returns dict of alias -> display_name.
        """
        creds_path = Path.home() / ".manny" / "credentials.yaml"
        if not creds_path.exists():
            return {}

        try:
            with open(creds_path) as f:
                creds = yaml.safe_load(f) or {}

            accounts = {}
            for alias, data in creds.get("accounts", {}).items():
                display_name = data.get("display_name", alias)
                accounts[alias] = display_name
            return accounts
        except Exception as e:
            logger.error(f"Failed to load credentials: {e}")
            return {}

    def switch_account(self, account_id: str) -> bool:
        """Switch to a different account.

        Returns True if successful, False if account doesn't exist.
        """
        available = self._get_available_accounts()
        if account_id not in available:
            return False

        self.account_id = account_id
        # Clear conversation history on account switch
        self.conversation_history.clear()
        logger.info(f"Switched to account: {account_id}")
        return True

    async def _execute_tool(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool call from the LLM.

        Routes tool calls to the appropriate MCP handlers.
        """
        logger.info(f"LLM tool call: {tool_name}({arguments})")

        try:
            if tool_name == "get_game_state":
                return await self._monitoring.handle_get_game_state({
                    "account_id": self.account_id,
                    "fields": arguments.get("fields")
                })

            elif tool_name == "get_screenshot":
                result = self._screenshot._take_screenshot(account_id=self.account_id)
                # Don't return base64 to LLM - too large
                if result.get("success"):
                    return {"success": True, "path": result.get("path"), "message": "Screenshot captured"}
                return result

            elif tool_name == "check_health":
                return await self._monitoring.handle_check_health({
                    "account_id": self.account_id
                })

            elif tool_name == "send_command":
                return await self._commands.handle_send_command({
                    "command": arguments.get("command", ""),
                    "account_id": self.account_id
                })

            elif tool_name == "start_runelite":
                result = self._manager.start_instance(self.account_id)
                return result

            elif tool_name == "stop_runelite":
                result = self._manager.stop_instance(self.account_id)
                return result

            elif tool_name == "restart_runelite":
                self._manager.stop_instance(self.account_id)
                import asyncio
                await asyncio.sleep(2)
                result = self._manager.start_instance(self.account_id)
                return {"restarted": True, "start_result": result}

            elif tool_name == "auto_reconnect":
                return await self._monitoring.handle_auto_reconnect({
                    "account_id": self.account_id
                })

            elif tool_name == "run_routine":
                routine_path = arguments.get("routine_path", "")
                if not routine_path.startswith("routines/"):
                    routine_path = f"routines/{routine_path}"
                if not routine_path.endswith(".yaml"):
                    routine_path += ".yaml"

                # For now, just dispatch the command - routine execution is complex
                return await self._commands.handle_send_command({
                    "command": f"RUN_ROUTINE {routine_path}",
                    "account_id": self.account_id
                })

            elif tool_name == "list_routines":
                routines = self._get_available_routines()
                return {"routines": routines, "count": len(routines)}

            elif tool_name == "get_logs":
                return await self._monitoring.handle_get_logs({
                    "account_id": self.account_id,
                    "level": arguments.get("level", "WARN"),
                    "since_seconds": arguments.get("since_seconds", 30),
                    "grep": arguments.get("grep"),
                    "max_lines": 50
                })

            elif tool_name == "switch_account":
                new_account = arguments.get("account_id", "")
                if self.switch_account(new_account):
                    return {"success": True, "account_id": new_account, "message": f"Switched to {new_account}"}
                else:
                    available = list(self._get_available_accounts().keys())
                    return {"success": False, "error": f"Account not found. Available: {available}"}

            elif tool_name == "list_accounts":
                accounts = self._get_available_accounts()
                return {
                    "accounts": accounts,
                    "current": self.account_id,
                    "count": len(accounts)
                }

            else:
                return {"error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            logger.error(f"Tool execution error: {tool_name} - {e}")
            return {"error": str(e)}

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


def setup_slash_commands(bot: OSRSBot):
    """Register slash commands with the bot's command tree."""

    @bot.tree.command(name="status", description="Get current bot status")
    async def status(interaction: discord.Interaction):
        bot._load_tools()
        await interaction.response.defer()

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

            await interaction.followup.send(msg)
        except Exception as e:
            logger.error(f"/status error: {e}")
            await interaction.followup.send(f"Error getting status: {e}")

    @bot.tree.command(name="screenshot", description="Get a screenshot of the game")
    async def screenshot(interaction: discord.Interaction):
        bot._load_tools()
        await interaction.response.defer()

        try:
            result = bot._screenshot._take_screenshot(account_id=bot.account_id)

            if result.get("success") and "path" in result:
                await interaction.followup.send(file=discord.File(result["path"]))
            else:
                error_msg = result.get('error', 'unknown error')
                logger.error(f"/screenshot failed: {error_msg}")
                await interaction.followup.send(f"Failed to capture screenshot: {error_msg}")
        except Exception as e:
            logger.error(f"/screenshot error: {e}")
            await interaction.followup.send(f"Error: {e}")

    @bot.tree.command(name="gif", description="Record a short GIF of the game")
    @app_commands.describe(
        duration="Recording duration in seconds (default: 5, max: 15)"
    )
    async def gif(interaction: discord.Interaction, duration: int = 5):
        bot._load_tools()
        await interaction.response.defer()

        try:
            await interaction.followup.send(f"Recording {duration}s GIF...")
            result = bot._screenshot._capture_gif(duration=min(duration, 15), account_id=bot.account_id)

            if result.get("success") and "path" in result:
                size = result.get("size_kb", 0)
                await interaction.followup.send(
                    content=f"GIF recorded ({size}KB)",
                    file=discord.File(result["path"])
                )
            else:
                error_msg = result.get('error', 'unknown error')
                logger.error(f"/gif failed: {error_msg}")
                await interaction.followup.send(f"Failed to record GIF: {error_msg}")
        except Exception as e:
            logger.error(f"/gif error: {e}")
            await interaction.followup.send(f"Error: {e}")

    @bot.tree.command(name="stop", description="Stop current bot activity")
    async def stop(interaction: discord.Interaction):
        bot._load_tools()
        await interaction.response.defer()

        try:
            await bot._commands.handle_send_command({
                "command": "STOP",
                "account_id": bot.account_id
            })
            await interaction.followup.send("Stop command sent")
        except Exception as e:
            logger.error(f"/stop error: {e}")
            await interaction.followup.send(f"Error: {e}")

    @bot.tree.command(name="restart", description="Kill all RuneLite instances and restart")
    async def restart(interaction: discord.Interaction):
        import subprocess
        bot._load_tools()
        await interaction.response.defer()

        try:
            # Kill all RuneLite/java processes
            await interaction.followup.send("Killing all RuneLite instances...")
            subprocess.run(["pkill", "-9", "-f", "runelite"], capture_output=True)
            subprocess.run(["pkill", "-9", "-f", "RuneLite"], capture_output=True)

            # Wait for processes to die
            await asyncio.sleep(2)

            # Start RuneLite
            await interaction.followup.send("Starting RuneLite...")
            result = bot._manager.start_instance(bot.account_id)

            if result.get("success") or result.get("pid"):
                await interaction.followup.send(f"RuneLite started (PID: {result.get('pid', 'unknown')})")
            else:
                await interaction.followup.send(f"Start result: {result}")
        except Exception as e:
            logger.error(f"/restart error: {e}")
            await interaction.followup.send(f"Error: {e}")

    @bot.tree.command(name="kill", description="Kill all RuneLite instances")
    async def kill(interaction: discord.Interaction):
        import subprocess
        await interaction.response.defer()

        try:
            # Kill all RuneLite/java processes
            subprocess.run(["pkill", "-9", "-f", "runelite"], capture_output=True)
            subprocess.run(["pkill", "-9", "-f", "RuneLite"], capture_output=True)

            await asyncio.sleep(1)

            # Check if any remain
            result = subprocess.run(["pgrep", "-f", "runelite"], capture_output=True)
            if result.returncode == 0:
                await interaction.followup.send("Killed RuneLite (some processes may remain)")
            else:
                await interaction.followup.send("All RuneLite instances killed")
        except Exception as e:
            logger.error(f"/kill error: {e}")
            await interaction.followup.send(f"Error: {e}")

    @bot.tree.command(name="run", description="Run a routine")
    @app_commands.describe(
        routine="Path to routine (e.g., combat/hill_giants.yaml)",
        loops="Number of loops to run (default: 1)"
    )
    async def run_routine(interaction: discord.Interaction, routine: str, loops: int = 1):
        bot._load_tools()
        await interaction.response.defer()

        routine_path = f"routines/{routine}"
        if not routine_path.endswith(".yaml"):
            routine_path += ".yaml"

        try:
            await interaction.followup.send(f"Starting routine: {routine} ({loops} loops)")
            result = await bot._routine.handle_execute_routine({
                "routine_path": routine_path,
                "max_loops": loops,
                "account_id": bot.account_id
            })
            await interaction.followup.send(f"Routine completed: {result.get('status', 'unknown')}")
        except Exception as e:
            logger.error(f"/run error for {routine}: {e}")
            await interaction.followup.send(f"Error: {e}")

    @bot.tree.command(name="routines", description="List available routines")
    async def list_routines(interaction: discord.Interaction):
        routines = bot._get_available_routines()

        if routines:
            msg = "**Available Routines:**\n" + "\n".join(f"- {r}" for r in routines[:20])
            if len(routines) > 20:
                msg += f"\n... and {len(routines) - 20} more"
        else:
            msg = "No routines found"

        await interaction.response.send_message(msg)

    @bot.tree.command(name="switch", description="Switch to a different account")
    @app_commands.describe(account="Account alias to switch to (e.g., main, aux)")
    async def switch_account(interaction: discord.Interaction, account: str):
        account = account.lower()
        available = bot._get_available_accounts()

        if bot.switch_account(account):
            display_name = available.get(account, account)
            await interaction.response.send_message(f"Switched to **{account}** ({display_name})")
        else:
            account_list = ", ".join(available.keys()) if available else "none found"
            logger.warning(f"/switch failed: account '{account}' not found. Available: {account_list}")
            await interaction.response.send_message(f"Account '{account}' not found. Available: {account_list}")

    @bot.tree.command(name="accounts", description="List available accounts")
    async def list_accounts(interaction: discord.Interaction):
        accounts = bot._get_available_accounts()

        if accounts:
            lines = []
            for alias, display_name in accounts.items():
                marker = " (active)" if alias == bot.account_id else ""
                lines.append(f"- **{alias}**: {display_name}{marker}")
            msg = "**Available Accounts:**\n" + "\n".join(lines)
        else:
            logger.warning("/accounts: No accounts configured in ~/.manny/credentials.yaml")
            msg = "No accounts configured. Check `~/.manny/credentials.yaml`"

        await interaction.response.send_message(msg)

    @bot.tree.command(name="help", description="Show all available commands")
    async def help_command(interaction: discord.Interaction):
        help_text = """**OSRS Bot Commands**

**Status & Info**
`/status` - Get bot status (location, health, inventory)
`/screenshot` - Get a screenshot of the game
`/gif [duration]` - Record a GIF (default 5s, max 15s)
`/accounts` - List available accounts
`/help` - Show this help message

**Control**
`/stop` - Stop current bot activity
`/switch <account>` - Switch to a different account
`/run <routine> [loops]` - Run a routine
`/routines` - List available routines

**Natural Language**
Just type normally in DMs! The bot uses AI to understand requests like:
- "go fish at draynor"
- "what's in my inventory?"
- "stop what you're doing"
"""
        await interaction.response.send_message(help_text)


def create_bot(
    llm_provider: str = "ollama",
    account_id: str = "aux",
    owner_id: Optional[int] = None
) -> OSRSBot:
    """Create and configure the bot.

    Default provider is 'ollama' (local qwen2.5:14b-multi) with automatic fallback to 'gemini'.
    """
    bot = OSRSBot(llm_provider=llm_provider, account_id=account_id)
    bot.owner_id = owner_id
    setup_slash_commands(bot)
    return bot
