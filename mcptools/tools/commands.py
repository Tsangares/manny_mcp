"""
Command execution tools for sending commands and input to the plugin.
"""
import os
from ..registry import registry


# Dependencies
send_command_with_response = None
config = None


def set_dependencies(send_command_func, server_config):
    """Inject dependencies (called from server.py startup)"""
    global send_command_with_response, config
    send_command_with_response = send_command_func
    config = server_config


@registry.register({
    "name": "send_command",
    "description": "[Commands] Send a command to the manny plugin via /tmp/manny_command.txt",
    "inputSchema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The command to send (e.g., 'GOTO 3200 3200 0', 'BANK_OPEN')"
            }
        },
        "required": ["command"]
    }
})
async def handle_send_command(arguments: dict) -> dict:
    """Send command to plugin."""
    command = arguments.get("command", "")
    command_file = config.command_file

    try:
        with open(command_file, "w") as f:
            f.write(command + "\n")
        return {"sent": True, "command": command}
    except Exception as e:
        return {"sent": False, "error": str(e)}


@registry.register({
    "name": "send_input",
    "description": """[Commands] Send input directly to RuneLite canvas via Java AWT events.

Works regardless of Wayland/X11 setup because it uses the plugin's internal Mouse/Keyboard classes.

Input types:
- click: Click at x,y coordinates (button 1=left, 2=middle, 3=right)
- key: Press a key (e.g., "Return", "Escape", "Space", "a", "1")
- move: Move mouse to x,y without clicking

Use this to:
- Dismiss login/disconnect dialogs
- Click UI elements when game commands don't work
- Send keyboard input to the game""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "input_type": {
                "type": "string",
                "enum": ["click", "key", "move"],
                "description": "Type of input to send"
            },
            "x": {
                "type": "integer",
                "description": "X coordinate (for click/move)"
            },
            "y": {
                "type": "integer",
                "description": "Y coordinate (for click/move)"
            },
            "button": {
                "type": "integer",
                "description": "Mouse button: 1=left, 2=middle, 3=right (default: 1)",
                "default": 1
            },
            "key": {
                "type": "string",
                "description": "Key to press (for key type). E.g., 'Return', 'Escape', 'Space', 'a'"
            }
        },
        "required": ["input_type"]
    }
})
async def handle_send_input(arguments: dict) -> dict:
    """Send input to RuneLite canvas."""
    input_type = arguments.get("input_type")
    command_file = config.command_file

    try:
        if input_type == "click":
            x = arguments.get("x")
            y = arguments.get("y")
            button = arguments.get("button", 1)
            if x is None or y is None:
                return {"sent": False, "error": "click requires x and y coordinates"}

            button_name = {1: "left", 2: "middle", 3: "right"}.get(button, "left")
            command = f"MOUSE_MOVE {x},{y}\nMOUSE_CLICK {button_name}"
            with open(command_file, "w") as f:
                f.write(command + "\n")
            return {"sent": True, "input_type": "click", "x": x, "y": y, "button": button_name}

        elif input_type == "key":
            key = arguments.get("key")
            if not key:
                return {"sent": False, "error": "key type requires 'key' parameter"}

            command = f"KEY_PRESS {key}"
            with open(command_file, "w") as f:
                f.write(command + "\n")
            return {"sent": True, "input_type": "key", "key": key,
                    "note": "KEY_PRESS command may need to be added to plugin"}

        elif input_type == "move":
            x = arguments.get("x")
            y = arguments.get("y")
            if x is None or y is None:
                return {"sent": False, "error": "move requires x and y coordinates"}

            command = f"MOUSE_MOVE {x},{y}"
            with open(command_file, "w") as f:
                f.write(command + "\n")
            return {"sent": True, "input_type": "move", "x": x, "y": y}

        else:
            return {"sent": False, "error": f"Unknown input_type: {input_type}"}

    except Exception as e:
        return {"sent": False, "error": str(e)}
