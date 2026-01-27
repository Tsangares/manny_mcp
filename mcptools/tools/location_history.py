"""
Location History MCP tools.

Provides tools for:
- Reading and analyzing location history from the ring buffer
- Visualizing movement trails on collision maps
- Detecting movement patterns (stuck, oscillation, drift)
- Location labeling using known area definitions
- Waypoint consolidation for cleaner routine generation
"""
import json
import os
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import Counter

from ..registry import registry
from ..config import ServerConfig

# Load config
config = ServerConfig.load()

# Collision data directory (for visualization)
COLLISION_DIR = Path("/home/wil/Desktop/manny/data/collision")
OUTPUT_DIR = Path("/tmp/collision_viz")

# Location knowledge directory
LOCATIONS_DIR = Path("/home/wil/manny-mcp/data/locations")

# Cache for loaded location data
_location_cache: Optional[Dict] = None


def _load_history(account_id: str = None) -> Optional[Dict]:
    """Load location history from JSON file."""
    history_file = config.get_location_history_file(account_id)
    if not os.path.exists(history_file):
        return None

    try:
        with open(history_file) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def _load_location_data() -> Dict:
    """Load all location YAML files and cache them."""
    global _location_cache
    if _location_cache is not None:
        return _location_cache

    _location_cache = {}
    if not LOCATIONS_DIR.exists():
        return _location_cache

    for yaml_file in LOCATIONS_DIR.glob("*.yaml"):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
                if data:
                    _location_cache.update(data)
        except (yaml.YAMLError, IOError):
            pass

    return _location_cache


def _identify_location(x: int, y: int, plane: int, location_data: Dict) -> Optional[Dict]:
    """Identify area and room for given coordinates."""
    for area_name, area_data in location_data.items():
        # Skip non-location entries (like common_routes)
        if not isinstance(area_data, dict):
            continue
        if area_name in ("common_routes",):
            continue

        for room_name, room_data in area_data.items():
            if not isinstance(room_data, dict):
                continue
            if "bounds" not in room_data:
                continue

            bounds = room_data["bounds"]
            room_plane = room_data.get("plane", 0)

            # Check if position is within bounds and on same plane
            # Bounds format: [min_x, min_y, max_x, max_y]
            if len(bounds) == 4 and plane == room_plane:
                min_x, min_y, max_x, max_y = bounds
                if min_x <= x <= max_x and min_y <= y <= max_y:
                    return {
                        "area": area_name,
                        "room": room_name
                    }

    return None


def _add_location_labels(positions: List[Dict]) -> List[Dict]:
    """Add location labels to positions using location knowledge base."""
    location_data = _load_location_data()
    if not location_data:
        return positions

    for pos in positions:
        loc = _identify_location(pos["x"], pos["y"], pos["plane"], location_data)
        if loc:
            pos["area"] = loc["area"]
            pos["room"] = loc["room"]

    return positions


def _consolidate_movements(positions: List[Dict], idle_threshold_ms: int = 2000) -> List[Dict]:
    """
    Consolidate consecutive movement events into walk segments.

    Instead of every tile, creates walk events:
    {"eventType": "walk", "from": {x, y}, "to": {x, y}, "tiles": N, "duration_ms": M}

    Args:
        positions: List of position entries
        idle_threshold_ms: Minimum idle time (ms) to consider a waypoint (default 2000)

    Returns:
        Consolidated list with walk segments and non-move events preserved
    """
    if len(positions) < 2:
        return positions

    consolidated = []
    walk_start = None
    walk_start_ts = None
    last_pos = None
    last_ts = None
    tiles = 0

    for pos in positions:
        event_type = pos.get("eventType", "move")

        # Non-move events break the walk and are passed through
        if event_type != "move":
            # Emit any pending walk
            if walk_start is not None and last_pos is not None:
                walk_event = {
                    "ts": walk_start_ts,
                    "eventType": "walk",
                    "from": {"x": walk_start["x"], "y": walk_start["y"], "plane": walk_start["plane"]},
                    "to": {"x": last_pos["x"], "y": last_pos["y"], "plane": last_pos["plane"]},
                    "tiles": tiles,
                    "duration_ms": last_ts - walk_start_ts if last_ts else 0
                }
                consolidated.append(walk_event)
                walk_start = None
                tiles = 0

            consolidated.append(pos)
            last_pos = pos
            last_ts = pos.get("ts", 0)
            continue

        # Movement event
        curr_ts = pos.get("ts", 0)

        if walk_start is None:
            # Start a new walk
            walk_start = pos
            walk_start_ts = curr_ts
            last_pos = pos
            last_ts = curr_ts
            tiles = 0
        else:
            # Calculate distance from last position
            dx = abs(pos["x"] - last_pos["x"])
            dy = abs(pos["y"] - last_pos["y"])
            step_tiles = max(dx, dy)  # Chebyshev distance
            tiles += step_tiles

            # Check for significant pause (idle threshold)
            time_since_last = curr_ts - last_ts if last_ts else 0
            if time_since_last >= idle_threshold_ms and tiles > 0:
                # Emit walk segment up to last_pos (the waypoint)
                walk_event = {
                    "ts": walk_start_ts,
                    "eventType": "walk",
                    "from": {"x": walk_start["x"], "y": walk_start["y"], "plane": walk_start["plane"]},
                    "to": {"x": last_pos["x"], "y": last_pos["y"], "plane": last_pos["plane"]},
                    "tiles": tiles - step_tiles,  # Don't include current step
                    "duration_ms": last_ts - walk_start_ts if last_ts else 0
                }
                consolidated.append(walk_event)

                # Start new walk from current position
                walk_start = pos
                walk_start_ts = curr_ts
                tiles = step_tiles

            last_pos = pos
            last_ts = curr_ts

    # Emit any remaining walk
    if walk_start is not None and last_pos is not None and tiles > 0:
        walk_event = {
            "ts": walk_start_ts,
            "eventType": "walk",
            "from": {"x": walk_start["x"], "y": walk_start["y"], "plane": walk_start["plane"]},
            "to": {"x": last_pos["x"], "y": last_pos["y"], "plane": last_pos["plane"]},
            "tiles": tiles,
            "duration_ms": last_ts - walk_start_ts if last_ts else 0
        }
        consolidated.append(walk_event)

    return consolidated


def _analyze_patterns(positions: List[Dict]) -> Dict[str, Any]:
    """Analyze movement patterns to detect issues."""
    if len(positions) < 10:
        return {"patterns": [], "healthy": True}

    patterns = []

    # 1. Stuck detection: Same position for extended time
    if len(positions) >= 50:
        recent = positions[-50:]
        unique_positions = set((p["x"], p["y"]) for p in recent)
        if len(unique_positions) == 1:
            patterns.append({
                "type": "stuck",
                "severity": "high",
                "description": f"Player stuck at ({recent[0]['x']}, {recent[0]['y']}) for 50+ ticks (~30 seconds)",
                "position": {"x": recent[0]["x"], "y": recent[0]["y"]}
            })

    # 2. Oscillation detection: Bouncing between 2-3 positions
    if len(positions) >= 20:
        recent = positions[-20:]
        pos_counts = Counter((p["x"], p["y"]) for p in recent)
        top_positions = pos_counts.most_common(3)

        # If 2-3 positions account for >80% of recent history, that's oscillation
        if len(top_positions) <= 3:
            total_in_top = sum(c for _, c in top_positions)
            if total_in_top >= 16:  # 80% of 20
                patterns.append({
                    "type": "oscillation",
                    "severity": "medium",
                    "description": f"Player oscillating between {len(top_positions)} positions",
                    "positions": [{"x": p[0], "y": p[1], "count": c} for p, c in top_positions]
                })

    # 3. Drift detection: Slow consistent movement away from expected area
    if len(positions) >= 100:
        start = positions[0]
        end = positions[-1]
        distance = abs(end["x"] - start["x"]) + abs(end["y"] - start["y"])

        # If moved far without clear purpose (no command changes)
        commands = set(p.get("cmd") for p in positions if p.get("cmd"))
        if distance > 50 and len(commands) <= 1:
            patterns.append({
                "type": "drift",
                "severity": "low",
                "description": f"Player drifted {distance} tiles from start position",
                "start": {"x": start["x"], "y": start["y"]},
                "end": {"x": end["x"], "y": end["y"]},
                "distance": distance
            })

    # 4. Teleport/Jump detection: Large position change in single tick
    for i in range(1, len(positions)):
        prev = positions[i-1]
        curr = positions[i]
        jump = abs(curr["x"] - prev["x"]) + abs(curr["y"] - prev["y"])
        if jump > 30:  # Teleport threshold
            patterns.append({
                "type": "jump",
                "severity": "info",
                "description": f"Large position change ({jump} tiles) - possible teleport/death",
                "from": {"x": prev["x"], "y": prev["y"]},
                "to": {"x": curr["x"], "y": curr["y"]},
                "distance": jump
            })
            break  # Only report first jump

    healthy = not any(p["severity"] in ("high", "medium") for p in patterns)

    return {
        "patterns": patterns,
        "healthy": healthy,
        "pattern_count": len(patterns)
    }


def _calculate_stats(positions: List[Dict]) -> Dict[str, Any]:
    """Calculate movement statistics."""
    if not positions:
        return {}

    unique_positions = set((p["x"], p["y"]) for p in positions)

    # Calculate total distance traveled
    total_distance = 0
    for i in range(1, len(positions)):
        prev = positions[i-1]
        curr = positions[i]
        total_distance += abs(curr["x"] - prev["x"]) + abs(curr["y"] - prev["y"])

    # Calculate bounding box
    xs = [p["x"] for p in positions]
    ys = [p["y"] for p in positions]

    # Time stats
    duration_ms = positions[-1]["ts"] - positions[0]["ts"] if len(positions) > 1 else 0
    duration_seconds = duration_ms / 1000

    # Movement rate
    movement_rate = total_distance / duration_seconds if duration_seconds > 0 else 0

    return {
        "entry_count": len(positions),
        "unique_positions": len(unique_positions),
        "total_distance_tiles": total_distance,
        "duration_seconds": round(duration_seconds, 1),
        "movement_rate_tiles_per_sec": round(movement_rate, 2),
        "bounding_box": {
            "min_x": min(xs),
            "max_x": max(xs),
            "min_y": min(ys),
            "max_y": max(ys),
            "width": max(xs) - min(xs) + 1,
            "height": max(ys) - min(ys) + 1
        },
        "current_position": {
            "x": positions[-1]["x"],
            "y": positions[-1]["y"],
            "plane": positions[-1]["plane"]
        }
    }


@registry.register({
    "name": "get_location_history",
    "description": """[Monitoring] Get player location history from the ring buffer.

Returns movement trail data with optional analysis:
- positions: List of (timestamp, x, y, plane, command) entries
- stats: Movement statistics (distance traveled, unique positions, etc.)
- patterns: Detected movement issues (stuck, oscillation, drift)

Use last_n to limit entries returned. Use include_analysis for pattern detection.
Use add_location_labels to add area/room labels from location knowledge base.
Use consolidate_movements to collapse move events into walk segments.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client support. Omit for default account."
            },
            "last_n": {
                "type": "integer",
                "description": "Return only the last N entries (default: all, max: 900)",
                "default": 0
            },
            "include_positions": {
                "type": "boolean",
                "description": "Include raw position data (default: true). Set false for stats-only.",
                "default": True
            },
            "include_analysis": {
                "type": "boolean",
                "description": "Include pattern analysis (stuck, oscillation, drift detection)",
                "default": True
            },
            "add_location_labels": {
                "type": "boolean",
                "description": "Add area/room labels from location knowledge base (default: false)",
                "default": False
            },
            "consolidate_movements": {
                "type": "boolean",
                "description": "Collapse consecutive moves into walk segments (default: false)",
                "default": False
            }
        }
    }
})
async def handle_get_location_history(arguments: dict) -> dict:
    """Get location history with analysis."""
    account_id = arguments.get("account_id")
    last_n = arguments.get("last_n", 0)
    include_positions = arguments.get("include_positions", True)
    include_analysis = arguments.get("include_analysis", True)
    add_labels = arguments.get("add_location_labels", False)
    consolidate = arguments.get("consolidate_movements", False)

    history = _load_history(account_id)
    if not history:
        return {
            "success": False,
            "account_id": account_id or config.default_account,
            "error": "Location history file not found - is the plugin running?"
        }

    positions = history.get("positions", [])

    # Limit entries if requested
    if last_n > 0 and len(positions) > last_n:
        positions = positions[-last_n:]

    # Apply location labels if requested
    if add_labels:
        positions = _add_location_labels(positions)

    # Consolidate movements if requested
    if consolidate:
        positions = _consolidate_movements(positions)

    result = {
        "success": True,
        "account_id": account_id or config.default_account,
        "buffer_size": history.get("bufferSize", 900),
        "entry_count": history.get("entryCount", len(positions)),
        "duration_seconds": history.get("durationSeconds", 0)
    }

    # Add stats (use original positions for accurate stats)
    original_positions = history.get("positions", [])
    if last_n > 0 and len(original_positions) > last_n:
        original_positions = original_positions[-last_n:]
    result["stats"] = _calculate_stats(original_positions)

    # Add pattern analysis
    if include_analysis:
        result["analysis"] = _analyze_patterns(original_positions)

    # Add processed positions
    if include_positions:
        if consolidate:
            # Include full event data for consolidated output
            result["positions"] = positions
        else:
            # Compact format: just the essential fields
            result["positions"] = [
                {
                    "x": p["x"],
                    "y": p["y"],
                    "plane": p["plane"],
                    "cmd": p.get("cmd"),
                    **({"area": p["area"], "room": p["room"]} if "area" in p else {})
                }
                for p in positions
            ]

    return result


@registry.register({
    "name": "visualize_trail",
    "description": """[Monitoring] Generate a PNG visualization of the player's movement trail.

Overlays the location history on a collision map showing:
- Green: Walkable tiles
- Gray: Blocked tiles
- Blue line: Movement trail (faded = older, bright = recent)
- White dot: Current position
- Red dots: Positions where issues were detected (stuck, oscillation)

Returns path to the generated PNG file.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client support. Omit for default account."
            },
            "last_minutes": {
                "type": "number",
                "description": "Only show trail from last N minutes (default: 5)",
                "default": 5
            },
            "output_path": {
                "type": "string",
                "description": "Custom output path for PNG (default: /tmp/collision_viz/trail_<timestamp>.png)"
            }
        }
    }
})
async def handle_visualize_trail(arguments: dict) -> dict:
    """Generate trail visualization."""
    account_id = arguments.get("account_id")
    last_minutes = arguments.get("last_minutes", 5)
    output_path = arguments.get("output_path")

    history = _load_history(account_id)
    if not history:
        return {
            "success": False,
            "error": "Location history file not found"
        }

    positions = history.get("positions", [])
    if not positions:
        return {
            "success": False,
            "error": "No position data in history"
        }

    # Filter to last N minutes
    cutoff_ms = positions[-1]["ts"] - (last_minutes * 60 * 1000)
    positions = [p for p in positions if p["ts"] >= cutoff_ms]

    if not positions:
        return {
            "success": False,
            "error": f"No positions in last {last_minutes} minutes"
        }

    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return {
            "success": False,
            "error": "PIL/Pillow not installed - run: pip install Pillow"
        }

    # Calculate bounding box with padding
    xs = [p["x"] for p in positions]
    ys = [p["y"] for p in positions]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    # Add padding
    padding = 10
    min_x -= padding
    max_x += padding
    min_y -= padding
    max_y += padding

    width = max_x - min_x + 1
    height = max_y - min_y + 1

    # Scale for visibility (at least 400px)
    scale = max(1, 400 // max(width, height))
    scale = min(scale, 8)  # Cap at 8x

    img_width = width * scale
    img_height = height * scale

    # Create image with dark background
    img = Image.new('RGB', (img_width, img_height), (30, 30, 30))
    draw = ImageDraw.Draw(img)

    # Helper to convert world coords to image coords
    def to_img(x, y):
        ix = (x - min_x) * scale + scale // 2
        iy = (height - 1 - (y - min_y)) * scale + scale // 2  # Flip Y
        return ix, iy

    # Draw trail as connected line segments with gradient
    total = len(positions)
    for i in range(1, total):
        # Color gradient: older = dimmer blue, newer = brighter cyan
        progress = i / total
        r = int(50 * (1 - progress))
        g = int(150 + 100 * progress)
        b = int(200 + 55 * progress)
        color = (r, g, b)

        x1, y1 = to_img(positions[i-1]["x"], positions[i-1]["y"])
        x2, y2 = to_img(positions[i]["x"], positions[i]["y"])

        # Draw line segment
        line_width = max(1, scale // 2)
        draw.line([(x1, y1), (x2, y2)], fill=color, width=line_width)

    # Draw current position as white dot
    if positions:
        cx, cy = to_img(positions[-1]["x"], positions[-1]["y"])
        radius = max(3, scale)
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
                     fill=(255, 255, 255), outline=(0, 0, 0))

    # Draw start position as green dot
    if len(positions) > 1:
        sx, sy = to_img(positions[0]["x"], positions[0]["y"])
        radius = max(2, scale - 1)
        draw.ellipse([sx - radius, sy - radius, sx + radius, sy + radius],
                     fill=(100, 255, 100), outline=(0, 100, 0))

    # Analyze patterns and mark problem areas
    analysis = _analyze_patterns(positions)
    for pattern in analysis.get("patterns", []):
        if pattern["type"] == "stuck" and "position" in pattern:
            px, py = to_img(pattern["position"]["x"], pattern["position"]["y"])
            radius = max(4, scale + 1)
            draw.ellipse([px - radius, py - radius, px + radius, py + radius],
                         fill=None, outline=(255, 0, 0), width=2)

    # Add info text
    stats = _calculate_stats(positions)
    info_lines = [
        f"Positions: {len(positions)}",
        f"Duration: {stats.get('duration_seconds', 0):.0f}s",
        f"Distance: {stats.get('total_distance_tiles', 0)} tiles",
        f"Unique: {stats.get('unique_positions', 0)} positions"
    ]

    # Draw info box
    y_offset = 5
    for line in info_lines:
        draw.text((5, y_offset), line, fill=(200, 200, 200))
        y_offset += 12

    # Save image
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not output_path:
        import time
        output_path = OUTPUT_DIR / f"trail_{int(time.time())}.png"
    else:
        output_path = Path(output_path)

    img.save(output_path)

    return {
        "success": True,
        "path": str(output_path),
        "dimensions": f"{img_width}x{img_height}",
        "positions_shown": len(positions),
        "duration_seconds": stats.get("duration_seconds", 0),
        "analysis": analysis
    }


@registry.register({
    "name": "detect_movement_patterns",
    "description": """[Monitoring] Analyze location history for movement issues.

Detects:
- stuck: Player at same position for extended time
- oscillation: Bouncing between 2-3 positions repeatedly
- drift: Gradual movement away from task area
- jump: Large position changes (teleport, death, disconnect)

Returns severity levels: high, medium, low, info""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client support. Omit for default account."
            }
        }
    }
})
async def handle_detect_movement_patterns(arguments: dict) -> dict:
    """Detect movement patterns/issues."""
    account_id = arguments.get("account_id")

    history = _load_history(account_id)
    if not history:
        return {
            "success": False,
            "account_id": account_id or config.default_account,
            "error": "Location history file not found"
        }

    positions = history.get("positions", [])
    analysis = _analyze_patterns(positions)
    stats = _calculate_stats(positions)

    return {
        "success": True,
        "account_id": account_id or config.default_account,
        "entry_count": len(positions),
        "duration_seconds": stats.get("duration_seconds", 0),
        "current_position": stats.get("current_position"),
        "healthy": analysis["healthy"],
        "patterns": analysis["patterns"],
        "summary": _generate_summary(analysis, stats)
    }


def _generate_summary(analysis: Dict, stats: Dict) -> str:
    """Generate human-readable summary of movement analysis."""
    patterns = analysis.get("patterns", [])

    if not patterns:
        return f"Movement healthy. {stats.get('unique_positions', 0)} unique positions visited in {stats.get('duration_seconds', 0):.0f}s."

    high = [p for p in patterns if p["severity"] == "high"]
    medium = [p for p in patterns if p["severity"] == "medium"]

    if high:
        return f"ISSUE DETECTED: {high[0]['description']}"
    elif medium:
        return f"Warning: {medium[0]['description']}"
    else:
        return f"Minor patterns detected: {len(patterns)} issues (info level)"


def _extract_events(positions: List[Dict]) -> List[Dict]:
    """Extract events (non-movement entries) from position history."""
    events = []
    for p in positions:
        event_type = p.get("eventType")
        if event_type and event_type != "move":
            event = {
                "ts": p["ts"],
                "type": event_type,
                "x": p["x"],
                "y": p["y"],
                "plane": p["plane"],
            }
            # Add optional fields if present
            if p.get("command"):
                event["command"] = p["command"]
            if p.get("target"):
                event["target"] = p["target"]
            if p.get("action"):
                event["action"] = p["action"]
            if p.get("targetX") is not None:
                event["targetX"] = p["targetX"]
            if p.get("targetY") is not None:
                event["targetY"] = p["targetY"]
            if p.get("dialogueOption"):
                event["dialogueOption"] = p["dialogueOption"]
            if p.get("inventoryDelta"):
                event["inventoryDelta"] = p["inventoryDelta"]
            events.append(event)
    return events


def _group_events_by_type(events: List[Dict]) -> Dict[str, List[Dict]]:
    """Group events by their type for easier analysis."""
    grouped = {
        "interactions": [],
        "dialogues": [],
        "inventory_changes": [],
        "doors": [],
    }
    for event in events:
        event_type = event.get("type", "")
        if event_type == "interact":
            grouped["interactions"].append(event)
        elif event_type == "dialogue":
            grouped["dialogues"].append(event)
        elif event_type == "inventory":
            grouped["inventory_changes"].append(event)
        elif event_type == "door":
            grouped["doors"].append(event)
    return grouped


def _suggest_await_conditions(events: List[Dict]) -> List[Dict]:
    """Suggest await_conditions based on event patterns."""
    suggestions = []

    for i, event in enumerate(events):
        suggestion = {
            "event_index": i,
            "command": event.get("command", ""),
            "conditions": []
        }

        event_type = event.get("type", "")
        target = event.get("target", "")
        action = event.get("action", "")

        if event_type == "interact":
            if action.lower() in ("talk-to", "talk"):
                suggestion["conditions"].append("dialogue_open")
            elif action.lower() in ("climb-up", "climb-down", "climb"):
                # Suggest plane change if target location differs
                suggestion["conditions"].append(f"plane:{event.get('plane', 0)}")
            elif action.lower() in ("open", "close"):
                suggestion["conditions"].append("idle")

        elif event_type == "dialogue":
            suggestion["conditions"].append("dialogue_continue")

        elif event_type == "inventory":
            delta = event.get("inventoryDelta", "")
            if delta.startswith("+"):
                item = delta[1:]
                suggestion["conditions"].append(f"has_item:{item}")
            elif delta.startswith("-"):
                item = delta[1:]
                suggestion["conditions"].append(f"no_item:{item}")

        elif event_type == "door":
            suggestion["conditions"].append("idle")

        if suggestion["conditions"]:
            suggestions.append(suggestion)

    return suggestions


@registry.register({
    "name": "get_event_history",
    "description": """[Routine Generation] Get enriched event history with interactions, dialogues, and inventory changes.

This tool extracts non-movement events from the location history ring buffer, grouped by type:
- interactions: NPC and object interactions (Talk-to, Open, Shear, etc.)
- dialogues: Dialogue selections (continue, option clicks)
- inventory_changes: Item gains/losses (+Wool, -Grain)
- doors: Door/gate interactions

Also suggests appropriate await_conditions for each event to help generate robust routines.

Use this as input for generate_routine to create YAML routines from recorded gameplay.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client support. Omit for default account."
            },
            "last_n": {
                "type": "integer",
                "description": "Return only the last N entries from history (default: all)",
                "default": 0
            },
            "last_minutes": {
                "type": "number",
                "description": "Return only events from last N minutes (default: 15)",
                "default": 15
            },
            "include_suggestions": {
                "type": "boolean",
                "description": "Include suggested await_conditions for routine generation (default: true)",
                "default": True
            }
        }
    }
})
async def handle_get_event_history(arguments: dict) -> dict:
    """Get enriched event history for routine generation."""
    account_id = arguments.get("account_id")
    last_n = arguments.get("last_n", 0)
    last_minutes = arguments.get("last_minutes", 15)
    include_suggestions = arguments.get("include_suggestions", True)

    history = _load_history(account_id)
    if not history:
        return {
            "success": False,
            "account_id": account_id or config.default_account,
            "error": "Location history file not found - is the plugin running?"
        }

    positions = history.get("positions", [])

    if not positions:
        return {
            "success": False,
            "account_id": account_id or config.default_account,
            "error": "No position data in history"
        }

    # Filter by time if requested
    if last_minutes > 0:
        cutoff_ms = positions[-1]["ts"] - (last_minutes * 60 * 1000)
        positions = [p for p in positions if p["ts"] >= cutoff_ms]

    # Limit entries if requested
    if last_n > 0 and len(positions) > last_n:
        positions = positions[-last_n:]

    # Extract events
    events = _extract_events(positions)
    grouped = _group_events_by_type(events)

    result = {
        "success": True,
        "account_id": account_id or config.default_account,
        "time_range_minutes": last_minutes,
        "total_positions": len(positions),
        "event_count": len(events),
        "events_by_type": {
            k: len(v) for k, v in grouped.items()
        },
        "events": grouped,
    }

    # Add await_condition suggestions
    if include_suggestions and events:
        result["await_suggestions"] = _suggest_await_conditions(events)

    # Add summary
    if events:
        first_ts = events[0]["ts"]
        last_ts = events[-1]["ts"]
        duration_sec = (last_ts - first_ts) / 1000
        result["summary"] = (
            f"{len(events)} events over {duration_sec:.0f}s: "
            f"{len(grouped['interactions'])} interactions, "
            f"{len(grouped['dialogues'])} dialogues, "
            f"{len(grouped['inventory_changes'])} inventory changes, "
            f"{len(grouped['doors'])} door ops"
        )
    else:
        result["summary"] = "No events recorded in the specified time range"

    return result
