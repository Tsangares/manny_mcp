"""
Dynamic capability registry that discovers available commands
and their abstraction levels from the MCP/plugin.

Adapts automatically when new commands are added to the plugin.
"""
import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Any
from enum import Enum

logger = logging.getLogger("capability_registry")


class AbstractionLevel(Enum):
    ATOMIC = "atomic"           # Single click, single action
    INTERFACE = "interface"     # Opens/interacts with a game interface
    COMPOSITE = "composite"     # Multiple steps bundled together
    LOOP = "loop"              # Continuous until stopped/complete


class CommandCategory(Enum):
    COMBAT = "combat"
    SKILLING = "skilling"
    BANKING = "banking"
    NAVIGATION = "navigation"
    INTERFACE = "interface"
    SYSTEM = "system"
    GE = "grand_exchange"
    SHOP = "shop"
    INVENTORY = "inventory"
    EQUIPMENT = "equipment"
    DIALOGUE = "dialogue"
    UNKNOWN = "unknown"


@dataclass
class Capability:
    """Describes a single capability/command."""
    name: str
    category: CommandCategory
    abstraction: AbstractionLevel
    description: str = ""
    parameters: Dict[str, str] = field(default_factory=dict)
    required_params: List[str] = field(default_factory=list)

    # For composite commands - what atomics they use
    composed_of: List[str] = field(default_factory=list)

    # What interface must be open (if any)
    requires_interface: Optional[str] = None

    # What state to check after execution
    success_condition: Optional[str] = None

    # Example usage
    example: Optional[str] = None


# Category inference patterns
CATEGORY_PATTERNS = [
    (r"^(KILL|ATTACK|COMBAT|FIGHT)", CommandCategory.COMBAT),
    (r"^(FISH|CHOP|MINE|COOK|CRAFT|SMITH|FLETCH|LIGHT)", CommandCategory.SKILLING),
    (r"^BANK", CommandCategory.BANKING),
    (r"^GE", CommandCategory.GE),
    (r"^SHOP", CommandCategory.SHOP),
    (r"^(GOTO|WALK|RUN|PATH)", CommandCategory.NAVIGATION),
    (r"^(TAB|CLICK_WIDGET|CLICK_DIALOGUE)", CommandCategory.INTERFACE),
    (r"^(EQUIP|UNEQUIP|WEAR|WIELD)", CommandCategory.EQUIPMENT),
    (r"^(USE_ITEM|DROP|PICK_UP)", CommandCategory.INVENTORY),
    (r"^(STOP|KILL|WAIT|LIST)", CommandCategory.SYSTEM),
    (r"^INTERACT", CommandCategory.INTERFACE),
]

# Abstraction level inference
ABSTRACTION_PATTERNS = [
    (r"_LOOP$", AbstractionLevel.LOOP),
    (r"^(CLICK_WIDGET|MOUSE|KEY_PRESS|WAIT)$", AbstractionLevel.ATOMIC),
    (r"^(BANK_OPEN|GE_OPEN|SHOP_OPEN|TAB_OPEN)", AbstractionLevel.INTERFACE),
]


class CapabilityRegistry:
    """
    Dynamic registry of available capabilities.

    Populates from:
    1. MCP list_commands introspection
    2. Command metadata from plugin
    3. Local capability definitions (for scaffolding)
    """

    def __init__(self):
        self._capabilities: Dict[str, Capability] = {}
        self._by_category: Dict[CommandCategory, List[str]] = {}
        self._by_abstraction: Dict[AbstractionLevel, List[str]] = {}
        self._last_refresh = None
        self._mcp_client = None

    def set_mcp_client(self, client):
        """Set the MCP client for capability discovery."""
        self._mcp_client = client

    async def refresh(self):
        """Refresh capabilities from MCP."""
        if not self._mcp_client:
            logger.warning("No MCP client set, using static capabilities")
            self._load_static_capabilities()
            return

        try:
            # Get all commands from plugin via MCP
            result = await self._mcp_client.list_commands()
            commands = result.get("commands", [])

            for cmd in commands:
                cap = self._parse_command(cmd)
                self.register(cap)

            self._last_refresh = asyncio.get_event_loop().time()
            logger.info(f"Refreshed {len(self._capabilities)} capabilities from MCP")

        except Exception as e:
            logger.error(f"Failed to refresh capabilities: {e}")
            self._load_static_capabilities()

    def _load_static_capabilities(self):
        """Load static capability definitions as fallback."""
        static_caps = [
            # Combat
            Capability("KILL_LOOP", CommandCategory.COMBAT, AbstractionLevel.LOOP,
                      "Kill NPCs continuously",
                      {"npc": "NPC name", "food": "Food name or 'none'", "count": "Max kills"},
                      ["npc", "food"],
                      example="KILL_LOOP Giant_frog Tuna 100"),
            Capability("ATTACK_NPC", CommandCategory.COMBAT, AbstractionLevel.COMPOSITE,
                      "Attack an NPC once",
                      {"npc": "NPC name"},
                      ["npc"]),
            Capability("SET_ATTACK_STYLE", CommandCategory.COMBAT, AbstractionLevel.ATOMIC,
                      "Set combat attack style",
                      {"style": "Attack style name"},
                      ["style"]),

            # Navigation
            Capability("GOTO", CommandCategory.NAVIGATION, AbstractionLevel.COMPOSITE,
                      "Walk to coordinates",
                      {"x": "X coordinate", "y": "Y coordinate", "plane": "Plane (0-3)"},
                      ["x", "y", "plane"],
                      example="GOTO 3200 3200 0"),

            # Banking
            Capability("BANK_OPEN", CommandCategory.BANKING, AbstractionLevel.INTERFACE,
                      "Open nearest bank"),
            Capability("BANK_CLOSE", CommandCategory.BANKING, AbstractionLevel.INTERFACE,
                      "Close bank interface"),
            Capability("BANK_DEPOSIT_ALL", CommandCategory.BANKING, AbstractionLevel.COMPOSITE,
                      "Deposit entire inventory"),
            Capability("BANK_WITHDRAW", CommandCategory.BANKING, AbstractionLevel.COMPOSITE,
                      "Withdraw items from bank",
                      {"item": "Item name", "quantity": "Amount"},
                      ["item", "quantity"]),

            # Skilling
            Capability("FISH_DRAYNOR_LOOP", CommandCategory.SKILLING, AbstractionLevel.LOOP,
                      "Fish at Draynor, bank when full"),
            Capability("FISH", CommandCategory.SKILLING, AbstractionLevel.COMPOSITE,
                      "Fish at current spot"),
            Capability("COOK_ALL", CommandCategory.SKILLING, AbstractionLevel.COMPOSITE,
                      "Cook all raw food in inventory"),

            # Interface
            Capability("TAB_OPEN", CommandCategory.INTERFACE, AbstractionLevel.INTERFACE,
                      "Open a game tab",
                      {"tab": "Tab name (combat, skills, inventory, etc.)"},
                      ["tab"]),
            Capability("CLICK_WIDGET", CommandCategory.INTERFACE, AbstractionLevel.ATOMIC,
                      "Click a widget by ID and action",
                      {"widget_id": "Widget ID", "action": "Action text"},
                      ["widget_id", "action"]),
            Capability("CLICK_CONTINUE", CommandCategory.DIALOGUE, AbstractionLevel.ATOMIC,
                      "Click continue in dialogue"),
            Capability("CLICK_DIALOGUE", CommandCategory.DIALOGUE, AbstractionLevel.ATOMIC,
                      "Click a dialogue option",
                      {"option": "Option text"},
                      ["option"]),

            # System
            Capability("STOP", CommandCategory.SYSTEM, AbstractionLevel.ATOMIC,
                      "Stop current activity gracefully"),
            Capability("KILL", CommandCategory.SYSTEM, AbstractionLevel.ATOMIC,
                      "Nuclear stop - halt all automation immediately"),
            Capability("WAIT", CommandCategory.SYSTEM, AbstractionLevel.ATOMIC,
                      "Wait for milliseconds",
                      {"ms": "Milliseconds to wait"},
                      ["ms"]),

            # Interaction
            Capability("INTERACT_NPC", CommandCategory.INTERFACE, AbstractionLevel.COMPOSITE,
                      "Interact with an NPC",
                      {"name": "NPC name", "action": "Action (Talk-to, Trade, etc.)"},
                      ["name", "action"]),
            Capability("INTERACT_OBJECT", CommandCategory.INTERFACE, AbstractionLevel.COMPOSITE,
                      "Interact with a game object",
                      {"name": "Object name (use underscores)", "action": "Action"},
                      ["name", "action"]),
            Capability("PICK_UP_ITEM", CommandCategory.INVENTORY, AbstractionLevel.COMPOSITE,
                      "Pick up a ground item",
                      {"name": "Item name"},
                      ["name"]),
        ]

        for cap in static_caps:
            self.register(cap)

        logger.info(f"Loaded {len(static_caps)} static capabilities")

    def register(self, capability: Capability):
        """Register a capability."""
        self._capabilities[capability.name] = capability

        # Index by category
        if capability.category not in self._by_category:
            self._by_category[capability.category] = []
        if capability.name not in self._by_category[capability.category]:
            self._by_category[capability.category].append(capability.name)

        # Index by abstraction
        if capability.abstraction not in self._by_abstraction:
            self._by_abstraction[capability.abstraction] = []
        if capability.name not in self._by_abstraction[capability.abstraction]:
            self._by_abstraction[capability.abstraction].append(capability.name)

    def get(self, name: str) -> Optional[Capability]:
        """Get a capability by name."""
        return self._capabilities.get(name.upper())

    def find(self,
             category: CommandCategory = None,
             abstraction: AbstractionLevel = None,
             keyword: str = None) -> List[Capability]:
        """Find capabilities matching criteria."""
        results = list(self._capabilities.values())

        if category:
            results = [c for c in results if c.category == category]
        if abstraction:
            results = [c for c in results if c.abstraction == abstraction]
        if keyword:
            keyword = keyword.lower()
            results = [c for c in results
                      if keyword in c.name.lower() or keyword in c.description.lower()]

        return results

    def list_categories(self) -> Dict[str, int]:
        """List all categories with command counts."""
        return {cat.value: len(cmds) for cat, cmds in self._by_category.items()}

    def list_all(self) -> List[str]:
        """List all capability names."""
        return list(self._capabilities.keys())

    def get_for_interface(self, interface: str) -> List[Capability]:
        """Get commands that work with a specific interface."""
        return [c for c in self._capabilities.values()
                if c.requires_interface == interface]

    def _parse_command(self, cmd_info: dict) -> Capability:
        """Parse command info from MCP into Capability."""
        name = cmd_info.get("name", "").upper()
        description = cmd_info.get("description", "")

        # Infer abstraction level
        abstraction = AbstractionLevel.COMPOSITE  # default
        for pattern, level in ABSTRACTION_PATTERNS:
            if re.search(pattern, name):
                abstraction = level
                break

        # Infer category
        category = CommandCategory.UNKNOWN
        for pattern, cat in CATEGORY_PATTERNS:
            if re.search(pattern, name):
                category = cat
                break

        # Parse parameters if provided
        params = cmd_info.get("parameters", {})
        required = cmd_info.get("required", [])

        return Capability(
            name=name,
            category=category,
            abstraction=abstraction,
            description=description,
            parameters=params,
            required_params=required,
            example=cmd_info.get("example")
        )

    def build_command(self, name: str, params: dict) -> str:
        """Build a command string from capability name and params."""
        cap = self.get(name)
        if not cap:
            # Just concatenate name and params
            param_str = " ".join(str(v) for v in params.values())
            return f"{name} {param_str}".strip()

        # Build based on required params order
        parts = [cap.name]
        for param in cap.required_params:
            if param in params:
                parts.append(str(params[param]))

        # Add optional params
        for key, value in params.items():
            if key not in cap.required_params:
                parts.append(str(value))

        return " ".join(parts)


# Global registry instance
registry = CapabilityRegistry()
