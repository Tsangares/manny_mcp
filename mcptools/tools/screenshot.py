"""
Screenshot and visual analysis tools.
"""
import os
import subprocess
import time
import base64
from pathlib import Path
from mcp.types import ImageContent, TextContent
from ..registry import registry


# Dependencies
config = None
GEMINI_AVAILABLE = False
genai = None


def set_dependencies(server_config, gemini_module=None):
    """Inject dependencies (called from server.py startup)"""
    global config, GEMINI_AVAILABLE, genai
    config = server_config
    if gemini_module:
        GEMINI_AVAILABLE = True
        genai = gemini_module


def _take_screenshot(output_path: str = None, mode: str = "fullscreen") -> dict:
    """
    Internal screenshot function.

    Args:
        output_path: Where to save
        mode: "fullscreen" or "viewport"

    Returns:
        dict with success, path, base64, display, mode
    """
    display = config.display

    if output_path is None:
        output_path = f"/tmp/runelite_screenshot_{int(time.time())}.png"

    env = os.environ.copy()
    env["DISPLAY"] = display

    try:
        # Find RuneLite window
        window_result = subprocess.run(
            ["xdotool", "search", "--name", "RuneLite"],
            env=env,
            capture_output=True,
            text=True,
            timeout=5
        )

        window_id = None
        if window_result.returncode == 0 and window_result.stdout.strip():
            window_id = window_result.stdout.strip().split('\n')[0]

        if window_id:
            # Use ImageMagick to capture window
            result = subprocess.run(
                ["import", "-window", window_id, output_path],
                env=env,
                capture_output=True,
                text=True,
                timeout=10
            )
        else:
            # Fallback to scrot
            result = subprocess.run(
                ["scrot", "-o", output_path],
                env=env,
                capture_output=True,
                text=True,
                timeout=10
            )

        if result.returncode != 0:
            return {"success": False, "error": result.stderr or "Screenshot capture failed"}

        # Crop to viewport if requested
        if mode == "viewport":
            try:
                from PIL import Image
                img = Image.open(output_path)
                # Viewport coordinates: 1020x666 at offset 200,8
                cropped = img.crop((200, 8, 1220, 674))
                cropped.save(output_path)
            except ImportError:
                pass  # PIL not available
            except Exception:
                pass  # Cropping failed

        # Read and encode
        with open(output_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        return {
            "success": True,
            "path": output_path,
            "base64": image_data,
            "display": display,
            "mode": mode
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Screenshot timed out"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@registry.register({
    "name": "get_screenshot",
    "description": "[Screenshot] Capture a screenshot of the RuneLite window on display :2. Returns the image as base64 and saves to a file.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "output_path": {
                "type": "string",
                "description": "Optional path to save the screenshot (default: /tmp/runelite_screenshot_<timestamp>.png)"
            }
        }
    }
})
async def handle_get_screenshot(arguments: dict):
    """Capture screenshot."""
    output_path = arguments.get("output_path")
    result = _take_screenshot(output_path)

    if result["success"]:
        # Return both image and metadata
        return [
            ImageContent(type="image", data=result["base64"], mimeType="image/png"),
            TextContent(type="text", text=str({
                "success": True,
                "path": result["path"],
                "display": result["display"]
            }))
        ]
    else:
        return result


@registry.register({
    "name": "analyze_screenshot",
    "description": "[Screenshot] Use Gemini AI to visually analyze a screenshot of the game. Can answer questions about what's on screen.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Custom prompt for analysis (default: general OSRS state analysis)"
            },
            "screenshot_path": {
                "type": "string",
                "description": "Path to existing screenshot (default: takes new screenshot)"
            }
        }
    }
})
async def handle_analyze_screenshot(arguments: dict) -> dict:
    """Use Gemini to analyze screenshot."""
    if not GEMINI_AVAILABLE:
        return {"success": False, "error": "Gemini API not available - install google-generativeai"}

    if not os.environ.get("GEMINI_API_KEY"):
        return {"success": False, "error": "GEMINI_API_KEY not set in environment"}

    prompt = arguments.get("prompt")
    screenshot_path = arguments.get("screenshot_path")

    # Take screenshot if not provided (fullscreen for better context)
    if screenshot_path is None:
        screenshot_result = _take_screenshot(mode="fullscreen")
        if not screenshot_result["success"]:
            return {"success": False, "error": f"Failed to take screenshot: {screenshot_result.get('error')}"}
        screenshot_path = screenshot_result["path"]

    # Default OSRS analysis prompt
    if prompt is None:
        prompt = """Analyze this Old School RuneScape screenshot. Please tell me:
1. Player location (be specific - town name, area)
2. What is the player currently doing or hovering over?
3. Inventory contents - list all visible items
4. Equipment visible (if any panel is open)
5. Health/Prayer/Run energy status
6. Any important observations for automation (NPCs, objects, obstacles)

Be concise and accurate - this is used for game automation."""

    try:
        with open(screenshot_path, "rb") as f:
            image_data = f.read()

        model = genai.GenerativeModel('gemini-2.5-flash-lite')
        image_part = {"mime_type": "image/png", "data": image_data}

        response = model.generate_content([prompt, image_part])

        return {
            "success": True,
            "analysis": response.text,
            "screenshot_path": screenshot_path,
            "model": "gemini-2.5-flash-lite"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
