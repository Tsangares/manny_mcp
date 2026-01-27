"""
Screenshot and visual analysis tools.
Supports multi-client via account_id parameter.
"""
import os
import subprocess
import time
import base64
import tempfile
from pathlib import Path
from mcp.types import ImageContent, TextContent
from ..registry import registry
from ..session_manager import session_manager


# Dependencies (MultiRuneLiteManager injected at startup)
runelite_manager = None
config = None
GEMINI_AVAILABLE = False
genai = None


def set_dependencies(manager, server_config, gemini_module=None):
    """Inject dependencies (called from server.py startup)"""
    global runelite_manager, config, GEMINI_AVAILABLE, genai
    runelite_manager = manager
    config = server_config
    if gemini_module:
        GEMINI_AVAILABLE = True
        genai = gemini_module


# Common account_id schema property used across tools
ACCOUNT_ID_SCHEMA = {
    "type": "string",
    "description": "Account ID for multi-client support. Omit for default account."
}


def _take_screenshot(output_path: str = None, mode: str = "viewport", account_id: str = None) -> dict:
    """
    Internal screenshot function.

    Args:
        output_path: Where to save
        mode: "fullscreen" or "viewport"
        account_id: Account ID for multi-client support

    Returns:
        dict with success, path, base64, display, mode, account_id
    """
    # Get display - try session first, then config, then default to :2
    display = ":2"  # Default for VPS
    try:
        session_display = session_manager.get_display_for_account(account_id or config.default_account)
        if session_display:
            display = session_display
        elif config:
            account_config = config.get_account_config(account_id)
            if account_config and hasattr(account_config, 'display'):
                display = account_config.display
    except Exception:
        pass  # Use default :2

    if output_path is None:
        # Include account_id in filename for multi-client
        account_suffix = f"_{account_id}" if account_id and account_id != "default" else ""
        output_path = f"/tmp/runelite_screenshot{account_suffix}_{int(time.time())}.png"

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

        # Prefer window-specific capture with ImageMagick (works better with gamescope)
        # Fall back to scrot for full screen only if no window found
        if window_id:
            try:
                result = subprocess.run(
                    ["import", "-window", window_id, output_path],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=20
                )
            except FileNotFoundError:
                # ImageMagick not installed, try scrot
                result = subprocess.run(
                    ["scrot", "-o", output_path],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=20
                )
        else:
            # No window found, capture full screen with scrot
            try:
                result = subprocess.run(
                    ["scrot", "-o", output_path],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=20
                )
            except FileNotFoundError:
                return {
                    "success": False,
                    "error": "No screenshot tool installed. Install with: sudo pacman -S scrot imagemagick"
                }

        if result.returncode != 0:
            return {"success": False, "error": result.stderr or "Screenshot capture failed"}

        # Crop to viewport if requested
        if mode == "viewport":
            try:
                from PIL import Image
                img = Image.open(output_path)
                # Viewport coordinates: 752x499 at offset (120, 137)
                cropped = img.crop((120, 137, 872, 636))
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
            "mode": mode,
            "account_id": account_id or config.default_account
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
            },
            "account_id": ACCOUNT_ID_SCHEMA
        }
    }
})
async def handle_get_screenshot(arguments: dict):
    """Capture screenshot for specified account."""
    output_path = arguments.get("output_path")
    account_id = arguments.get("account_id")
    result = _take_screenshot(output_path, account_id=account_id)

    if result["success"]:
        # Return both image and metadata
        return [
            ImageContent(type="image", data=result["base64"], mimeType="image/png"),
            TextContent(type="text", text=str({
                "success": True,
                "path": result["path"],
                "display": result["display"],
                "account_id": result["account_id"]
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
            },
            "account_id": ACCOUNT_ID_SCHEMA
        }
    }
})
async def handle_analyze_screenshot(arguments: dict) -> dict:
    """Use Gemini to analyze screenshot for specified account."""
    if not GEMINI_AVAILABLE:
        return {"success": False, "error": "Gemini API not available - install google-generativeai"}

    if not os.environ.get("GEMINI_API_KEY"):
        return {"success": False, "error": "GEMINI_API_KEY not set in environment"}

    prompt = arguments.get("prompt")
    screenshot_path = arguments.get("screenshot_path")
    account_id = arguments.get("account_id")

    # Take screenshot if not provided (fullscreen for better context)
    if screenshot_path is None:
        screenshot_result = _take_screenshot(mode="fullscreen", account_id=account_id)
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


def _capture_gif(output_path: str = None, duration: int = 5, fps: int = 10, account_id: str = None) -> dict:
    """
    Capture a GIF of the game screen using ffmpeg.

    Args:
        output_path: Where to save the GIF
        duration: Recording duration in seconds (default: 5)
        fps: Frames per second (default: 10)
        account_id: Account ID for multi-client support

    Returns:
        dict with success, path, duration, size_kb
    """
    # Get display
    session_display = session_manager.get_display_for_account(account_id or config.default_account)
    if session_display:
        display = session_display
    else:
        account_config = config.get_account_config(account_id)
        display = account_config.display

    if output_path is None:
        account_suffix = f"_{account_id}" if account_id and account_id != "default" else ""
        output_path = f"/tmp/runelite_gif{account_suffix}_{int(time.time())}.gif"

    env = os.environ.copy()
    env["DISPLAY"] = display

    # Use a temp file for the raw video, then convert to GIF
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
        tmp_video = tmp.name

    try:
        # Capture video with ffmpeg
        # x11grab captures the X11 display, crop to game viewport
        capture_cmd = [
            "ffmpeg", "-y",
            "-f", "x11grab",
            "-video_size", "1024x768",  # Match Xvfb resolution
            "-framerate", str(fps),
            "-i", display,
            "-t", str(duration),
            "-vf", "crop=752:499:120:137",  # Crop to viewport (w:h:x:y)
            "-c:v", "libx264",
            "-preset", "ultrafast",
            tmp_video
        ]

        result = subprocess.run(
            capture_cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=duration + 10
        )

        if result.returncode != 0:
            return {"success": False, "error": f"ffmpeg capture failed: {result.stderr[:500]}"}

        # Convert to GIF with reasonable quality/size
        # Use palettegen for better colors
        palette_file = tmp_video + "_palette.png"

        # Generate palette (no scaling - already cropped to 752x499)
        palette_cmd = [
            "ffmpeg", "-y",
            "-i", tmp_video,
            "-vf", f"fps={fps},palettegen",
            palette_file
        ]
        subprocess.run(palette_cmd, capture_output=True, timeout=30)

        # Create GIF using palette
        gif_cmd = [
            "ffmpeg", "-y",
            "-i", tmp_video,
            "-i", palette_file,
            "-lavfi", f"fps={fps}[x];[x][1:v]paletteuse",
            output_path
        ]

        result = subprocess.run(
            gif_cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Cleanup temp files
        try:
            os.unlink(tmp_video)
            os.unlink(palette_file)
        except:
            pass

        if result.returncode != 0:
            return {"success": False, "error": f"GIF conversion failed: {result.stderr[:500]}"}

        # Get file size
        size_kb = os.path.getsize(output_path) // 1024

        return {
            "success": True,
            "path": output_path,
            "duration": duration,
            "fps": fps,
            "size_kb": size_kb,
            "display": display,
            "account_id": account_id or config.default_account
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "GIF capture timed out"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        # Cleanup on error
        try:
            if os.path.exists(tmp_video):
                os.unlink(tmp_video)
        except:
            pass


@registry.register({
    "name": "capture_gif",
    "description": "[Screenshot] Record a short GIF of the game screen. Good for showing recent activity.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "duration": {
                "type": "integer",
                "description": "Recording duration in seconds (default: 5, max: 15)"
            },
            "fps": {
                "type": "integer",
                "description": "Frames per second (default: 10)"
            },
            "account_id": ACCOUNT_ID_SCHEMA
        }
    }
})
async def handle_capture_gif(arguments: dict) -> dict:
    """Capture a GIF of the game screen."""
    duration = min(arguments.get("duration", 5), 15)  # Cap at 15 seconds
    fps = arguments.get("fps", 10)
    account_id = arguments.get("account_id")

    result = _capture_gif(duration=duration, fps=fps, account_id=account_id)
    return result
