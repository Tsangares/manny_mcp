"""
Spatial awareness tools for indoor navigation.
Provides environment scanning with direction labels and room detection.
"""
import logging
import os
import json
import math
from pathlib import Path
from typing import Optional, Dict, List, Any
from ..registry import registry

logger = logging.getLogger(__name__)


# Dependencies (injected from server.py)
send_command_with_response = None
config = None

# Location knowledge cache
_location_data: Dict[str, Any] = {}


def set_dependencies(send_command_func, server_config):
    """Inject dependencies (called from server.py startup)"""
    global send_command_with_response, config
    send_command_with_response = send_command_func
    config = server_config
    _load_location_knowledge()


def _load_location_knowledge():
    """Load location knowledge from YAML files."""
    global _location_data
    locations_dir = Path(__file__).parent.parent.parent / "data" / "locations"

    if locations_dir.exists():
        import yaml
        for yaml_file in locations_dir.glob("*.yaml"):
            try:
                with open(yaml_file) as f:
                    data = yaml.safe_load(f)
                    if data:
                        _location_data.update(data)
            except Exception as e:
                logger.warning("Failed to load %s: %s", yaml_file, e)


def _get_direction(player_x: int, player_y: int, target_x: int, target_y: int) -> str:
    """
    Get cardinal direction from player to target.
    OSRS: +Y is north, +X is east
    """
    dx = target_x - player_x
    dy = target_y - player_y

    if dx == 0 and dy == 0:
        return "here"

    # Calculate angle (0 = east, 90 = north)
    angle = math.degrees(math.atan2(dy, dx))

    # Convert to compass direction
    if -22.5 <= angle < 22.5:
        return "east"
    elif 22.5 <= angle < 67.5:
        return "northeast"
    elif 67.5 <= angle < 112.5:
        return "north"
    elif 112.5 <= angle < 157.5:
        return "northwest"
    elif angle >= 157.5 or angle < -157.5:
        return "west"
    elif -157.5 <= angle < -112.5:
        return "southwest"
    elif -112.5 <= angle < -67.5:
        return "south"
    else:  # -67.5 <= angle < -22.5
        return "southeast"


def _get_distance(x1: int, y1: int, x2: int, y2: int) -> int:
    """Calculate tile distance (Chebyshev/chessboard distance)."""
    return max(abs(x2 - x1), abs(y2 - y1))


def _identify_room(x: int, y: int, plane: int) -> Optional[Dict[str, Any]]:
    """Try to identify current room from location knowledge."""
    for area_name, area_data in _location_data.items():
        if not isinstance(area_data, dict):
            continue
        for room_name, room_data in area_data.items():
            if not isinstance(room_data, dict):
                continue

            # Check bounds if defined
            bounds = room_data.get("bounds")
            if bounds and len(bounds) == 4:
                min_x, min_y, max_x, max_y = bounds
                room_plane = room_data.get("plane", 0)
                if (min_x <= x <= max_x and
                    min_y <= y <= max_y and
                    room_plane == plane):
                    return {
                        "area": area_name,
                        "room": room_name,
                        "data": room_data
                    }

            # Check center with tolerance
            center = room_data.get("center")
            if center and len(center) >= 2:
                cx, cy = center[0], center[1]
                cplane = center[2] if len(center) > 2 else 0
                tolerance = room_data.get("tolerance", 5)
                if (abs(x - cx) <= tolerance and
                    abs(y - cy) <= tolerance and
                    cplane == plane):
                    return {
                        "area": area_name,
                        "room": room_name,
                        "data": room_data
                    }

    return None


def _categorize_object(name: str, actions: List[str]) -> str:
    """Categorize an object by its name and actions."""
    name_lower = name.lower()
    actions_lower = [a.lower() for a in actions] if actions else []

    # Doors/Gates
    if "door" in name_lower or "gate" in name_lower:
        return "door"
    if "open" in actions_lower or "close" in actions_lower:
        return "door"

    # Stairs/Ladders
    if any(x in name_lower for x in ["stair", "ladder", "trapdoor"]):
        return "vertical_transport"
    if any(x in actions_lower for x in ["climb", "climb-up", "climb-down"]):
        return "vertical_transport"

    # Banks
    if "bank" in name_lower or "bank" in actions_lower:
        return "bank"

    # Cooking
    if any(x in name_lower for x in ["range", "fire", "stove"]):
        return "cooking"

    # Anvils/Furnaces
    if any(x in name_lower for x in ["anvil", "furnace", "forge"]):
        return "smithing"

    return "other"


@registry.register({
    "name": "scan_environment",
    "description": """[Spatial] Comprehensive environment scan for indoor navigation.

Combines game state, tile object scanning, and nearby queries into a structured
spatial model with direction labels.

Returns:
- player: Current position (x, y, plane)
- room: Identified room from location knowledge (if known)
- doors: All doors/gates with direction labels and actions
- objects_of_interest: Notable objects (ranges, banks, ladders, etc.)
- npcs: Nearby NPCs with direction labels
- environment_type: "indoor" or "outdoor" (estimated from wall density)

Use this BEFORE any indoor navigation to understand the surroundings.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "radius": {
                "type": "integer",
                "description": "Search radius in tiles (default: 15)",
                "default": 15
            },
            "timeout_ms": {
                "type": "integer",
                "description": "Timeout in milliseconds (default: 5000)",
                "default": 5000
            },
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client (optional, defaults to 'default')"
            }
        }
    }
})
async def handle_scan_environment(arguments: dict) -> dict:
    """
    Comprehensive environment scan with spatial analysis.
    """
    radius = arguments.get("radius", 15)
    timeout_ms = arguments.get("timeout_ms", 5000)
    account_id = arguments.get("account_id")

    # Read game state for player position
    state_file = config.get_state_file(account_id)
    try:
        with open(state_file) as f:
            game_state = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        return {
            "success": False,
            "error": f"Failed to read game state: {e}"
        }

    # Extract player position
    player = game_state.get("player", {})
    player_loc = player.get("location", {})
    player_x = player_loc.get("x", 0)
    player_y = player_loc.get("y", 0)
    player_plane = player_loc.get("plane", 0)

    # Identify room from knowledge base
    room_info = _identify_room(player_x, player_y, player_plane)

    # Scan for doors/gates (WallObjects)
    doors = []
    door_types = ["door", "gate", "large_door"]
    for door_type in door_types:
        response = await send_command_with_response(
            f"SCAN_TILEOBJECTS {door_type} {radius}",
            timeout_ms,
            account_id
        )
        if response.get("status") == "success":
            result = response.get("result", {})
            objects = result.get("objects", [result] if "location" in result else [])
            for obj in objects:
                loc = obj.get("location", {})
                obj_x = loc.get("x", player_x)
                obj_y = loc.get("y", player_y)

                # Add direction and format for output
                doors.append({
                    "name": obj.get("name", door_type).replace(" ", "_"),
                    "location": [obj_x, obj_y],
                    "distance": _get_distance(player_x, player_y, obj_x, obj_y),
                    "direction": _get_direction(player_x, player_y, obj_x, obj_y),
                    "actions": obj.get("actions", []),
                    "type": obj.get("type", "WallObject")
                })

    # Deduplicate doors by location
    seen_locations = set()
    unique_doors = []
    for door in sorted(doors, key=lambda d: d["distance"]):
        loc_key = (door["location"][0], door["location"][1])
        if loc_key not in seen_locations:
            seen_locations.add(loc_key)
            unique_doors.append(door)

    # Scan for objects of interest
    objects_of_interest = []
    interest_objects = ["range", "bank", "ladder", "stair", "anvil", "furnace", "hopper", "flour"]
    for obj_type in interest_objects:
        response = await send_command_with_response(
            f"SCAN_TILEOBJECTS {obj_type} {radius}",
            timeout_ms,
            account_id
        )
        if response.get("status") == "success":
            result = response.get("result", {})
            objects = result.get("objects", [result] if "location" in result else [])
            for obj in objects:
                loc = obj.get("location", {})
                obj_x = loc.get("x", player_x)
                obj_y = loc.get("y", player_y)
                name = obj.get("name", obj_type)
                actions = obj.get("actions", [])

                objects_of_interest.append({
                    "name": name.replace(" ", "_"),
                    "location": [obj_x, obj_y],
                    "distance": _get_distance(player_x, player_y, obj_x, obj_y),
                    "direction": _get_direction(player_x, player_y, obj_x, obj_y),
                    "actions": actions,
                    "category": _categorize_object(name, actions)
                })

    # Deduplicate objects by location
    seen_obj_locations = set()
    unique_objects = []
    for obj in sorted(objects_of_interest, key=lambda o: o["distance"]):
        loc_key = (obj["location"][0], obj["location"][1])
        if loc_key not in seen_obj_locations:
            seen_obj_locations.add(loc_key)
            unique_objects.append(obj)

    # Get NPCs from game state (already in nearby)
    npcs = []
    nearby_npcs = player.get("nearby", {}).get("npcs", [])
    for npc in nearby_npcs:
        npc_loc = npc.get("location", {})
        npc_x = npc_loc.get("x", player_x)
        npc_y = npc_loc.get("y", player_y)

        npcs.append({
            "name": npc.get("name", "Unknown"),
            "location": [npc_x, npc_y],
            "distance": npc.get("distance", _get_distance(player_x, player_y, npc_x, npc_y)),
            "direction": _get_direction(player_x, player_y, npc_x, npc_y),
            "combat_level": npc.get("combatLevel"),
            "actions": npc.get("actions", [])
        })

    # Estimate environment type based on wall/door density
    wall_count = len(unique_doors)
    environment_type = "indoor" if wall_count >= 2 else "outdoor"

    # Build response
    result = {
        "success": True,
        "player": {
            "x": player_x,
            "y": player_y,
            "plane": player_plane
        },
        "environment_type": environment_type,
        "doors": unique_doors[:10],  # Limit to 10 nearest
        "objects_of_interest": unique_objects[:15],  # Limit to 15 nearest
        "npcs": npcs[:10]  # Limit to 10 nearest
    }

    # Add room info if identified
    if room_info:
        result["room"] = {
            "area": room_info["area"],
            "name": room_info["room"],
            "key_objects": room_info["data"].get("key_objects", []),
            "nearby_doors": room_info["data"].get("nearby_doors", []),
            "connections": room_info["data"].get("connections", [])
        }

    # Add account_id if specified
    if account_id:
        result["account_id"] = account_id

    return result


@registry.register({
    "name": "get_transitions",
    "description": """[Spatial] Find all navigable transitions (doors, stairs, ladders, etc.) nearby.

Returns transitions SORTED BY DISTANCE (nearest first) with state info and direction.
This is the preferred tool for indoor navigation.

Output structure:
- nearest: Quick reference list - one per category, sorted by distance. USE THIS FIRST!
- transitions: Full details by category (doors, stairs, ladders, etc.), each sorted by distance
- summary: Actionable text like "Nearest: Large_door (closed) 2 tiles north, Staircase 5 tiles east"

The "nearest" array is designed for quick decision-making:
```json
{"nearest": [
  {"type": "door", "name": "Large_door", "distance": 2, "direction": "north", "state": "closed", "actions": ["Open"]},
  {"type": "stair", "name": "Staircase", "distance": 5, "direction": "east", "actions": ["Climb-up"]}
]}
```

Each transition includes:
- name, distance (tiles), direction ("north", "southwest", etc.)
- state ("open", "closed", or null for non-doors)
- actions (e.g., ["Open"], ["Climb-up", "Climb-down"])

Use this BEFORE indoor navigation to find the nearest transition to interact with.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "radius": {
                "type": "integer",
                "description": "Search radius in tiles (default: 15)",
                "default": 15
            },
            "timeout_ms": {
                "type": "integer",
                "description": "Timeout in milliseconds (default: 5000)",
                "default": 5000
            },
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client (optional, defaults to 'default')"
            }
        }
    }
})
async def handle_get_transitions(arguments: dict) -> dict:
    """
    Find all navigable transitions nearby using the plugin's QUERY_TRANSITIONS command.
    """
    radius = arguments.get("radius", 15)
    timeout_ms = arguments.get("timeout_ms", 5000)
    account_id = arguments.get("account_id")

    # Call plugin command
    response = await send_command_with_response(
        f"QUERY_TRANSITIONS {radius}",
        timeout_ms,
        account_id
    )

    if response.get("status") != "success":
        return {
            "success": False,
            "error": response.get("error", "Failed to query transitions")
        }

    result = response.get("result", {})
    transitions = result.get("transitions", {})

    # Sort each category by distance (nearest first)
    sorted_transitions = {}
    for category, items in transitions.items():
        if isinstance(items, list):
            sorted_transitions[category] = sorted(items, key=lambda x: x.get("distance", 999))

    # Build "nearest" quick reference - one from each category, sorted by distance
    nearest = []
    for category, items in sorted_transitions.items():
        if items:
            item = items[0]
            nearest.append({
                "type": category.rstrip("s"),  # "doors" -> "door"
                "name": item.get("name", "Unknown"),
                "distance": item.get("distance", 0),
                "direction": item.get("direction", ""),
                "state": item.get("state"),
                "actions": item.get("actions", [])
            })
    nearest.sort(key=lambda x: x.get("distance", 999))

    # Build actionable summary
    summary_parts = []
    for item in nearest[:3]:  # Top 3 nearest
        state_str = f" ({item['state']})" if item.get("state") else ""
        summary_parts.append(f"{item['name']}{state_str} {item['distance']} tiles {item['direction']}")

    actionable_summary = "Nearest: " + ", ".join(summary_parts) if summary_parts else "No transitions found"

    output = {
        "success": True,
        "player_location": result.get("player_location"),
        "nearest": nearest,  # Quick reference sorted by distance
        "transitions": sorted_transitions,  # Full details, each category sorted by distance
        "summary": actionable_summary,
        "total_count": result.get("total_count", 0)
    }

    if account_id:
        output["account_id"] = account_id

    return output


@registry.register({
    "name": "get_location_info",
    "description": """[Spatial] Look up a known location from the location knowledge base.

Returns pre-defined information about a location including:
- Coordinates (center or bounds)
- Key objects in the location
- Connected rooms and doors
- Tips for navigation

Use this to get information about a destination before navigating.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "area": {
                "type": "string",
                "description": "Area name (e.g., 'lumbridge_castle')"
            },
            "room": {
                "type": "string",
                "description": "Room name within the area (e.g., 'kitchen')"
            }
        },
        "required": ["area"]
    }
})
async def handle_get_location_info(arguments: dict) -> dict:
    """Look up a known location."""
    area = arguments.get("area", "").lower().replace(" ", "_")
    room = arguments.get("room", "").lower().replace(" ", "_") if arguments.get("room") else None

    if area not in _location_data:
        # List available areas
        available = list(_location_data.keys())
        return {
            "success": False,
            "error": f"Unknown area: {area}",
            "available_areas": available
        }

    area_data = _location_data[area]

    if room:
        if room not in area_data:
            available_rooms = [k for k in area_data.keys() if isinstance(area_data[k], dict)]
            return {
                "success": False,
                "error": f"Unknown room: {room}",
                "available_rooms": available_rooms
            }

        room_data = area_data[room]
        return {
            "success": True,
            "area": area,
            "room": room,
            "data": room_data
        }
    else:
        # Return area overview
        rooms = {k: v for k, v in area_data.items() if isinstance(v, dict)}
        return {
            "success": True,
            "area": area,
            "rooms": list(rooms.keys()),
            "room_count": len(rooms)
        }


@registry.register({
    "name": "list_known_locations",
    "description": """[Spatial] List all known locations from the location knowledge base.

Returns all areas and rooms that have pre-defined navigation data.""",
    "inputSchema": {
        "type": "object",
        "properties": {}
    }
})
async def handle_list_known_locations(arguments: dict) -> dict:
    """List all known locations."""
    locations = {}

    for area_name, area_data in _location_data.items():
        if isinstance(area_data, dict):
            rooms = [k for k in area_data.keys() if isinstance(area_data[k], dict)]
            locations[area_name] = rooms

    return {
        "success": True,
        "locations": locations,
        "total_areas": len(locations),
        "total_rooms": sum(len(rooms) for rooms in locations.values())
    }
