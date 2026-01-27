"""
Routine Generator MCP tool.

Generates YAML routines from recorded event history.
Vision: "Play a quest once -> Generate a replayable routine"
"""
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import yaml

from ..registry import registry
from ..config import ServerConfig

# Load config
config = ServerConfig.load()


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


def _collapse_movements(positions: List[Dict]) -> List[Dict]:
    """
    Collapse consecutive movement entries into single GOTO steps.

    Returns list of significant position changes (destinations).
    """
    if not positions:
        return []

    destinations = []
    current_dest = None
    idle_threshold_ms = 2000  # 2 seconds of standing = destination

    for i, pos in enumerate(positions):
        # Skip event entries (they're handled separately)
        if pos.get("eventType") and pos.get("eventType") != "move":
            continue

        if current_dest is None:
            current_dest = pos
            continue

        # Check if position changed
        same_pos = (
            pos["x"] == current_dest["x"] and
            pos["y"] == current_dest["y"] and
            pos["plane"] == current_dest["plane"]
        )

        if same_pos:
            # Update timestamp to track how long we've been here
            current_dest["end_ts"] = pos["ts"]
        else:
            # Position changed - was the previous position significant?
            if current_dest.get("end_ts"):
                duration = current_dest["end_ts"] - current_dest["ts"]
                if duration >= idle_threshold_ms:
                    # Stood here for a while - it's a destination
                    destinations.append({
                        "x": current_dest["x"],
                        "y": current_dest["y"],
                        "plane": current_dest["plane"],
                        "ts": current_dest["ts"],
                        "duration_ms": duration
                    })
            current_dest = pos

    # Don't forget the last position
    if current_dest:
        destinations.append({
            "x": current_dest["x"],
            "y": current_dest["y"],
            "plane": current_dest["plane"],
            "ts": current_dest["ts"],
            "duration_ms": current_dest.get("end_ts", current_dest["ts"]) - current_dest["ts"]
        })

    return destinations


def _extract_events(positions: List[Dict]) -> List[Dict]:
    """Extract non-movement events from position history."""
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
            # Add optional fields
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


def _detect_phases(events: List[Dict], positions: List[Dict]) -> List[Tuple[str, int]]:
    """
    Detect phase boundaries from significant gaps or location clusters.

    Returns list of (phase_name, start_event_index) tuples.
    """
    phases = []

    if not events:
        return [("main", 0)]

    # Simple heuristic: new phase on 30+ second gap between events
    gap_threshold_ms = 30000

    current_phase = "phase_1"
    phase_num = 1
    phases.append((current_phase, 0))

    for i in range(1, len(events)):
        gap = events[i]["ts"] - events[i-1]["ts"]
        if gap >= gap_threshold_ms:
            phase_num += 1
            current_phase = f"phase_{phase_num}"
            phases.append((current_phase, i))

    return phases


def _infer_await_condition(event: Dict, next_event: Optional[Dict]) -> Optional[str]:
    """Infer appropriate await_condition for an event."""
    event_type = event.get("type", "")
    action = event.get("action", "").lower()
    target = event.get("target", "")

    if event_type == "interact":
        if action in ("talk-to", "talk"):
            return "dialogue_open"
        elif action in ("climb-up", "climb-down", "climb"):
            # Check if next event is on different plane
            if next_event and next_event.get("plane") != event.get("plane"):
                return f"plane:{next_event.get('plane', 0)}"
            return "idle"
        elif action in ("open", "close"):
            return "idle"
        elif action in ("bank", "use"):
            return "idle"
        elif action == "shear":
            return "has_item:Wool"

    elif event_type == "dialogue":
        return None  # Dialogues don't need await - they block

    elif event_type == "inventory":
        delta = event.get("inventoryDelta", "")
        if delta.startswith("+"):
            item = delta[1:]
            return f"has_item:{item}"
        elif delta.startswith("-"):
            item = delta[1:]
            return f"no_item:{item}"

    elif event_type == "door":
        return "idle"

    return None


def _event_to_step(event: Dict, step_id: int, phase: str, next_event: Optional[Dict]) -> Dict:
    """Convert a single event to a routine step."""
    event_type = event.get("type", "")

    step = {
        "id": step_id,
        "phase": phase,
    }

    if event_type == "interact":
        target = event.get("target", "Unknown")
        action = event.get("action", "")

        # Determine if NPC or object interaction
        # Heuristic: NPCs have Talk-to, Attack, etc. Objects have Open, Use, etc.
        npc_actions = {"talk-to", "talk", "attack", "pickpocket", "trade", "shear"}
        if action.lower() in npc_actions:
            step["action"] = "INTERACT_NPC"
            # Replace spaces with underscores for multi-word names
            npc_name = target.replace(" ", "_")
            step["args"] = f"{npc_name} {action}"
        else:
            step["action"] = "INTERACT_OBJECT"
            object_name = target.replace(" ", "_")
            step["args"] = f"{object_name} {action}"

        step["description"] = f"{action} {target}"

    elif event_type == "dialogue":
        option = event.get("dialogueOption", "")
        if option == "continue":
            step["action"] = "CLICK_CONTINUE"
            step["description"] = "Continue dialogue"
        else:
            step["action"] = "CLICK_DIALOGUE"
            step["args"] = option
            step["description"] = f"Select dialogue: {option}"

    elif event_type == "door":
        door_name = event.get("target", "Door").replace(" ", "_")
        action = event.get("action", "Open")
        step["action"] = "INTERACT_OBJECT"
        step["args"] = f"{door_name} {action}"
        step["description"] = f"{action} {door_name}"

    elif event_type == "inventory":
        delta = event.get("inventoryDelta", "")
        # Inventory events are typically side effects, not direct actions
        # We might skip these or convert to verification steps
        step["action"] = "VERIFY"
        step["args"] = delta
        step["description"] = f"Inventory: {delta}"

    else:
        # Unknown event type
        step["action"] = "UNKNOWN"
        step["args"] = event.get("command", "")
        step["description"] = f"Unknown event: {event_type}"

    # Add await_condition if inferrable
    await_cond = _infer_await_condition(event, next_event)
    if await_cond:
        step["await_condition"] = await_cond

    return step


def _generate_locations_dict(events: List[Dict], destinations: List[Dict]) -> Dict[str, Dict]:
    """Generate locations dictionary from events and destinations."""
    locations = {}

    # Add locations from events (interaction targets)
    for event in events:
        if event.get("targetX") is not None and event.get("target"):
            loc_name = event["target"].lower().replace(" ", "_")
            if loc_name not in locations:
                locations[loc_name] = {
                    "x": event["targetX"],
                    "y": event["targetY"],
                    "plane": event.get("plane", 0),
                    "description": f"Location of {event['target']}",
                    "validated": False
                }

    # Add significant destinations
    for i, dest in enumerate(destinations):
        if dest.get("duration_ms", 0) >= 5000:  # Stood here 5+ seconds
            loc_name = f"waypoint_{i+1}"
            locations[loc_name] = {
                "x": dest["x"],
                "y": dest["y"],
                "plane": dest["plane"],
                "description": f"Waypoint (stood {dest['duration_ms']/1000:.0f}s)",
                "validated": False
            }

    return locations


def _generate_routine(
    routine_name: str,
    events: List[Dict],
    positions: List[Dict],
    source_file: str
) -> Dict[str, Any]:
    """Generate complete routine YAML structure from events."""

    # Collapse movements to destinations
    destinations = _collapse_movements(positions)

    # Detect phases
    phases = _detect_phases(events, positions)

    # Build steps
    steps = []
    step_id = 1
    current_phase_idx = 0

    # Interleave GOTO steps and event steps based on timestamps
    event_idx = 0
    dest_idx = 0

    while event_idx < len(events) or dest_idx < len(destinations):
        # Determine which comes next (by timestamp)
        event_ts = events[event_idx]["ts"] if event_idx < len(events) else float('inf')
        dest_ts = destinations[dest_idx]["ts"] if dest_idx < len(destinations) else float('inf')

        # Update current phase
        while (current_phase_idx + 1 < len(phases) and
               event_idx >= phases[current_phase_idx + 1][1]):
            current_phase_idx += 1
        current_phase = phases[current_phase_idx][0]

        if dest_ts <= event_ts and dest_idx < len(destinations):
            # Add GOTO step for destination
            dest = destinations[dest_idx]
            if dest.get("duration_ms", 0) >= 2000:  # Only significant pauses
                step = {
                    "id": step_id,
                    "phase": current_phase,
                    "action": "GOTO",
                    "args": f"{dest['x']} {dest['y']} {dest['plane']}",
                    "description": f"Walk to ({dest['x']}, {dest['y']})"
                }
                steps.append(step)
                step_id += 1
            dest_idx += 1
        else:
            # Add event step
            event = events[event_idx]
            next_event = events[event_idx + 1] if event_idx + 1 < len(events) else None
            step = _event_to_step(event, step_id, current_phase, next_event)

            # Skip VERIFY steps (inventory events are side effects)
            if step["action"] != "VERIFY":
                steps.append(step)
                step_id += 1
            event_idx += 1

    # Generate locations dictionary
    locations = _generate_locations_dict(events, destinations)

    # Build routine structure
    routine = {
        "name": routine_name,
        "type": "generated",
        "generated_at": datetime.now().isoformat(),
        "source": source_file,
        "description": f"Auto-generated routine from {len(events)} events",
    }

    if locations:
        routine["locations"] = locations

    routine["steps"] = steps

    # Add metadata
    routine["_metadata"] = {
        "event_count": len(events),
        "step_count": len(steps),
        "phase_count": len(phases),
        "generation_note": "Review and validate before use. Check object names use underscores."
    }

    return routine


@registry.register({
    "name": "generate_routine",
    "description": """[Routine Generation] Generate a YAML routine from recorded event history.

Converts event history into a replayable routine YAML file:
1. Collapses movements into GOTO steps (destinations where player paused)
2. Converts interactions to INTERACT_NPC/INTERACT_OBJECT steps
3. Captures dialogue flow as CLICK_DIALOGUE/CLICK_CONTINUE steps
4. Infers await_conditions from context
5. Detects phases from time gaps

**Workflow:**
1. Play through a quest/task manually
2. Call generate_routine() to create YAML
3. Review and validate the generated routine
4. Test with execute_routine()

**Note:** Generated routines need manual review:
- Check object names use underscores (Spinning_wheel not Spinning wheel)
- Verify await_conditions are appropriate
- Add skip_if conditions for optional steps
- Test in-game before production use""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client support. Omit for default account."
            },
            "routine_name": {
                "type": "string",
                "description": "Name for the generated routine (e.g., 'Sheep Shearing')"
            },
            "time_range_minutes": {
                "type": "number",
                "description": "Generate from last N minutes of history (default: 15)",
                "default": 15
            },
            "output_path": {
                "type": "string",
                "description": "Path to save YAML file. Default: routines/generated/<name>_<timestamp>.yaml"
            }
        },
        "required": ["routine_name"]
    }
})
async def handle_generate_routine(arguments: dict) -> dict:
    """Generate YAML routine from event history."""
    account_id = arguments.get("account_id")
    routine_name = arguments.get("routine_name", "Generated Routine")
    time_range_minutes = arguments.get("time_range_minutes", 15)
    output_path = arguments.get("output_path")

    # Load history
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
            "error": "No position data in history"
        }

    # Filter to time range
    cutoff_ms = positions[-1]["ts"] - (time_range_minutes * 60 * 1000)
    positions = [p for p in positions if p["ts"] >= cutoff_ms]

    if not positions:
        return {
            "success": False,
            "error": f"No positions in last {time_range_minutes} minutes"
        }

    # Extract events
    events = _extract_events(positions)

    if not events:
        return {
            "success": False,
            "error": "No events (interactions, dialogues, etc.) found in history. "
                     "Events are recorded when you interact with NPCs, objects, or dialogues."
        }

    # Generate routine
    source_file = config.get_location_history_file(account_id)
    routine = _generate_routine(routine_name, events, positions, source_file)

    # Determine output path
    if not output_path:
        safe_name = routine_name.lower().replace(" ", "_").replace("-", "_")
        timestamp = int(time.time())
        output_dir = Path("routines/generated")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{safe_name}_{timestamp}.yaml"
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write YAML
    with open(output_path, "w") as f:
        # Add header comment
        f.write(f"# Generated Routine: {routine_name}\n")
        f.write(f"# Generated: {datetime.now().isoformat()}\n")
        f.write(f"# Source: {time_range_minutes} minutes of gameplay\n")
        f.write(f"#\n")
        f.write(f"# IMPORTANT: Review before use!\n")
        f.write(f"# - Verify object names use underscores (Spinning_wheel, not Spinning wheel)\n")
        f.write(f"# - Check await_conditions are appropriate\n")
        f.write(f"# - Test with execute_routine() before production\n")
        f.write(f"#\n\n")

        # Write YAML content
        yaml.dump(routine, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    return {
        "success": True,
        "account_id": account_id or config.default_account,
        "routine_name": routine_name,
        "output_path": str(output_path),
        "stats": {
            "events_processed": len(events),
            "steps_generated": len(routine.get("steps", [])),
            "phases_detected": routine.get("_metadata", {}).get("phase_count", 1),
            "locations_extracted": len(routine.get("locations", {})),
            "time_range_minutes": time_range_minutes
        },
        "next_steps": [
            f"1. Review: Read {output_path}",
            "2. Edit: Fix any object names, add skip_if conditions",
            f"3. Test: execute_routine(routine_path='{output_path}')"
        ]
    }
