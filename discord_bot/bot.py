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
from discord_bot.agent_brain import AgentBrain, TaskClassifier, TaskType
from discord_bot.conversation_logger import get_conversation_logger
from discord_bot.training_logger import training_logger
from discord_bot.task_manager import TaskManager
from discord_bot.task_queue import when_level, after_level_up, when_inventory_full, when_health_below, immediately

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

        # Agent brain for intelligent task routing
        self._brain: Optional[AgentBrain] = None
        self._classifier = TaskClassifier()

        # Task manager for queued/conditional tasks
        self._task_manager: Optional[TaskManager] = None
        self._task_manager_started: bool = False
        self._dm_channel: Optional[discord.DMChannel] = None  # For notifications

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

        # Set up the tool executor for LLM function calling (with logging wrapper)
        self._current_request_id: Optional[str] = None
        self.llm.set_tool_executor(self._execute_tool_with_logging)

        # Create agent brain for intelligent routing
        self._brain = AgentBrain(self.llm, self._execute_tool_with_logging)

        # Create task manager for queued/conditional tasks
        async def get_state_func():
            result = await self._monitoring.handle_get_game_state({
                "account_id": self.account_id,
                "fields": ["location", "health", "skills", "inventory"]
            })
            return result.get("state", {})

        self._task_manager = TaskManager(
            send_command_func=send_command_with_response,
            get_state_func=get_state_func
        )

        # Set up notification callback for task manager events
        self._task_manager.set_notify_callback(self._task_notification)

        # Track if task manager queue has been started
        self._task_manager_started = False

        logger.info("MCP tools, agent brain, and task manager loaded")

    async def _ensure_task_manager_started(self):
        """Start the task manager queue if not already running."""
        if self._task_manager and not self._task_manager_started:
            await self._task_manager.initialize()
            self._task_manager_started = True
            logger.info("Task manager initialized and queue started")

    async def _execute_tool_with_logging(self, tool_name: str, arguments: dict) -> dict:
        """Wrapper that logs tool calls before executing."""
        import time
        start_time = time.time()

        result = await self._execute_tool(tool_name, arguments)

        latency_ms = int((time.time() - start_time) * 1000)

        # Log if we have a current request context
        if self._current_request_id:
            conv_logger = get_conversation_logger()
            # Truncate large results for logging
            log_result = result
            if isinstance(result, dict) and len(str(result)) > 500:
                log_result = {"_truncated": True, "keys": list(result.keys())}
            conv_logger.log_tool_call(
                request_id=self._current_request_id,
                tool_name=tool_name,
                arguments=arguments,
                result=log_result
            )

            # Also log to training data
            training_example = training_logger.get_example(self._current_request_id)
            if training_example:
                training_example.add_tool_call(tool_name, arguments, result, latency_ms)

        return result

    async def _task_notification(self, message: str):
        """Send task manager notifications to the user's DM channel."""
        if self._dm_channel:
            try:
                await self._dm_channel.send(f"📋 **Task Update:** {message}")
            except Exception as e:
                logger.error(f"Failed to send task notification: {e}")
        else:
            logger.info(f"Task notification (no DM channel): {message}")

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

        # Store DM channel for task notifications
        self._dm_channel = message.channel

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
        """Handle natural language messages via LLM with intelligent routing."""
        self._load_tools()
        await self._ensure_task_manager_started()

        user_id = message.author.id
        username = str(message.author)
        content = message.content.strip()

        # Get conversation history for this user
        history = self.conversation_history.get(user_id, [])

        # Classify the task for logging/debugging
        task_type = self._classifier.classify(content)
        logger.info(f"Task classified as: {task_type.value} for '{content[:50]}'")

        # Log to conversation logger
        conv_logger = get_conversation_logger()
        request_id = conv_logger.log_request(
            user_id=user_id,
            username=username,
            message=content,
            task_type=task_type.value,
            account_id=self.account_id
        )

        # Set request context for tool logging
        self._current_request_id = request_id

        # Start training data collection
        training_logger.start_example(
            request_id=request_id,
            user_message=content,
            task_type=task_type.value,
            source="discord"
        )

        # Show typing indicator
        async with message.channel.typing():
            try:
                # Use the agent brain for intelligent processing
                response = await self._brain.process_request(
                    message=content,
                    conversation_history=history
                )

                # Handle empty responses - LLM sometimes returns just whitespace after tool calls
                if not response or not response.strip():
                    response = "Done."
                    logger.warning(f"Empty LLM response for request {request_id}, using fallback")

                # Log the response
                conv_logger.log_response(request_id=request_id, response=response)

                # Update history (keep last 10 exchanges)
                history.append({"role": "user", "content": content})
                history.append({"role": "assistant", "content": response})
                self.conversation_history[user_id] = history[-20:]

                # For multi-step tasks, don't auto-parse actions - the brain handles it
                # Only parse for conversation responses that might suggest actions
                if task_type == TaskType.CONVERSATION:
                    action = self._parse_action(response)
                    if action:
                        action_result = await self._execute_action(action)
                        if action_result:
                            response += f"\n\n**Executed:** {action_result}"

                # Try to attach a screenshot with the response (only for status/query tasks)
                screenshot_file = None
                if task_type in [TaskType.STATUS_QUERY, TaskType.SIMPLE_COMMAND]:
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

                # Complete training example
                training_logger.complete_example(
                    request_id=request_id,
                    response=response,
                    success=True  # Assume success if no exception
                )

            except Exception as e:
                logger.error(f"LLM/Brain error: {e}", exc_info=True)
                conv_logger.log_error(request_id=request_id, error=str(e))
                # Complete training example with failure
                training_logger.complete_example(
                    request_id=request_id,
                    response=str(e),
                    success=False
                )
                await message.channel.send(f"Error: {e}")
            finally:
                # Clear request context
                self._current_request_id = None

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

            elif tool_name == "lookup_location":
                from discord_bot.locations import find_location, get_goto_command
                location_query = arguments.get("location", "")
                loc = find_location(location_query)
                if loc:
                    goto_cmd = get_goto_command(location_query)
                    return {
                        "found": True,
                        "name": loc["name"],
                        "x": loc["x"],
                        "y": loc["y"],
                        "plane": loc["plane"],
                        "goto_command": goto_cmd
                    }
                else:
                    return {
                        "found": False,
                        "error": f"Location '{location_query}' not found",
                        "hint": "Try common names like: lumbridge, draynor, varrock, ge, cows, frogs"
                    }

            elif tool_name == "list_plugin_commands":
                # Use manny-cli to list commands
                import subprocess
                category = arguments.get("category", "")
                try:
                    result = subprocess.run(
                        ["/home/wil/manny-mcp/manny/manny-cli", "--list"],
                        capture_output=True, text=True, timeout=5
                    )
                    output = result.stdout
                    # Parse and filter if category provided
                    if category:
                        lines = output.split('\n')
                        filtered = [l for l in lines if category.lower() in l.lower()]
                        return {"commands": filtered, "filter": category}
                    return {"commands": output[:3000]}  # Truncate for token limits
                except Exception as e:
                    return {"error": str(e)}

            elif tool_name == "get_command_help":
                # Use manny-cli to get command help
                import subprocess
                command = arguments.get("command", "").upper()
                try:
                    result = subprocess.run(
                        ["/home/wil/manny-mcp/manny/manny-cli", command, "--help"],
                        capture_output=True, text=True, timeout=5
                    )
                    return {"command": command, "help": result.stdout or result.stderr}
                except Exception as e:
                    return {"error": str(e)}

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

**Task Queue**
`/queue` - Show queued tasks
`/queue_task <command>` - Queue a command
`/queue_on_level <skill> <level> <command>` - Queue for level condition
`/queue_rotation` - Set up combat rotation
`/clear_queue` - Clear pending tasks

**Natural Language**
Just type normally in DMs! The bot uses AI to understand requests like:
- "go fish at draynor"
- "what's in my inventory?"
- "when I hit 40 strength, switch to defence"
"""
        await interaction.response.send_message(help_text)

    # =========================================================================
    # Task Queue Commands
    # =========================================================================

    @bot.tree.command(name="queue", description="Show queued tasks and their status")
    async def queue_status(interaction: discord.Interaction):
        bot._load_tools()
        await bot._ensure_task_manager_started()

        if not bot._task_manager:
            await interaction.response.send_message("Task manager not initialized")
            return

        status = bot._task_manager.get_status()
        queue_status = status.get("queue", {})

        # Parse task list by status
        tasks = queue_status.get("tasks", [])
        pending_tasks = [t for t in tasks if t.get("status") in ("pending", "waiting")]
        running_task_id = queue_status.get("current_task")
        by_status = queue_status.get("by_status", {})

        lines = ["**Task Queue Status**"]

        if running_task_id:
            running_task = next((t for t in tasks if t.get("id") == running_task_id), None)
            if running_task:
                lines.append(f"\n🔄 **Running:** {running_task.get('command', 'unknown')}")

        if pending_tasks:
            lines.append(f"\n📋 **Pending ({len(pending_tasks)}):**")
            for task in pending_tasks[:5]:
                cond = task.get("condition", "immediately")
                lines.append(f"  - `{task.get('command')}` ({cond})")
            if len(pending_tasks) > 5:
                lines.append(f"  ... and {len(pending_tasks) - 5} more")
        else:
            lines.append("\n📋 No pending tasks")

        completed = by_status.get("completed", 0)
        failed = by_status.get("failed", 0)
        lines.append(f"\n✅ Completed: {completed}")
        if failed:
            lines.append(f"❌ Failed: {failed}")

        await interaction.response.send_message("\n".join(lines))

    @bot.tree.command(name="queue_task", description="Queue a command for execution")
    @app_commands.describe(
        command="The command to queue (e.g., KILL_LOOP Giant_frog none)",
        priority="Priority (higher = runs first)"
    )
    async def queue_task(interaction: discord.Interaction, command: str, priority: int = 0):
        bot._load_tools()
        await bot._ensure_task_manager_started()

        if not bot._task_manager:
            await interaction.response.send_message("Task manager not initialized")
            return

        task_id = bot._task_manager.queue_task(
            command=command,
            condition=immediately(),
            priority=priority
        )
        await interaction.response.send_message(f"Queued task: `{command}` (ID: {task_id[:8]})")

    @bot.tree.command(name="queue_on_level", description="Queue a command to run when a skill reaches a level")
    @app_commands.describe(
        skill="Skill name (e.g., strength, attack, defence)",
        level="Target level",
        command="Command to run when level is reached"
    )
    async def queue_on_level(interaction: discord.Interaction, skill: str, level: int, command: str):
        bot._load_tools()
        await bot._ensure_task_manager_started()

        if not bot._task_manager:
            await interaction.response.send_message("Task manager not initialized")
            return

        task_id = bot._task_manager.queue_on_level(
            skill=skill.lower(),
            level=level,
            command=command
        )
        await interaction.response.send_message(
            f"Queued: `{command}` when {skill.title()} reaches {level} (ID: {task_id[:8]})"
        )

    @bot.tree.command(name="queue_rotation", description="Set up combat style rotation based on levels")
    @app_commands.describe(
        str_until="Train Strength until this level",
        att_until="Train Attack until this level",
        def_until="Train Defence until this level"
    )
    async def queue_rotation(
        interaction: discord.Interaction,
        str_until: int = 40,
        att_until: int = 40,
        def_until: int = 40
    ):
        bot._load_tools()
        await bot._ensure_task_manager_started()

        if not bot._task_manager:
            await interaction.response.send_message("Task manager not initialized")
            return

        rotations = [
            {"skill": "strength", "until_level": str_until, "style": "aggressive"},
            {"skill": "attack", "until_level": att_until, "style": "accurate"},
            {"skill": "defence", "until_level": def_until, "style": "defensive"},
        ]

        task_ids = bot._task_manager.setup_combat_rotation(rotations)

        msg = f"""**Combat Rotation Set Up**
1. Strength (aggressive) until level {str_until}
2. Attack (accurate) until level {att_until}
3. Defence (defensive) until level {def_until}

Queued {len(task_ids)} style switches."""

        await interaction.response.send_message(msg)

    @bot.tree.command(name="clear_queue", description="Clear all pending tasks")
    async def clear_queue(interaction: discord.Interaction):
        bot._load_tools()
        await bot._ensure_task_manager_started()

        if not bot._task_manager:
            await interaction.response.send_message("Task manager not initialized")
            return

        # Clear the queue
        bot._task_manager.queue.clear()
        await interaction.response.send_message("Task queue cleared")

    @bot.tree.command(name="capabilities", description="List available commands by category")
    @app_commands.describe(
        category="Filter by category (combat, skilling, banking, navigation, etc.)",
        keyword="Search by keyword"
    )
    async def list_capabilities(
        interaction: discord.Interaction,
        category: str = None,
        keyword: str = None
    ):
        bot._load_tools()
        await bot._ensure_task_manager_started()

        if not bot._task_manager:
            await interaction.response.send_message("Task manager not initialized")
            return

        caps = bot._task_manager.list_capabilities(category=category, keyword=keyword)

        if not caps:
            await interaction.response.send_message("No capabilities found matching that criteria")
            return

        lines = ["**Available Commands**"]
        if category:
            lines[0] += f" ({category})"
        if keyword:
            lines[0] += f" matching '{keyword}'"

        for cap in caps[:15]:
            lines.append(f"- **{cap['name']}** ({cap['category']}): {cap['description'][:50]}")

        if len(caps) > 15:
            lines.append(f"\n... and {len(caps) - 15} more")

        await interaction.response.send_message("\n".join(lines))


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
