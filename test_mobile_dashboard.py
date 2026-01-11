#!/usr/bin/env python3
"""
Mobile Dashboard Testing Tool

Takes screenshots of the dashboard at various mobile resolutions
and provides visual validation for mobile layouts.
"""

import subprocess
import time
import sys
from pathlib import Path

# Common mobile device resolutions (width x height in CSS pixels)
MOBILE_DEVICES = {
    "pixel_6_portrait": (412, 915),
    "pixel_6_landscape": (915, 412),
    "iphone_14_portrait": (390, 844),
    "iphone_14_landscape": (844, 390),
    "small_phone": (360, 640),  # Small Android
    "tablet_portrait": (768, 1024),  # iPad
}

def take_screenshot(url: str, width: int, height: int, output_path: str, wait_seconds: int = 3) -> bool:
    """
    Take a screenshot using headless Chrome/Chromium.

    Args:
        url: Dashboard URL
        width: Viewport width in pixels
        height: Viewport height in pixels
        output_path: Where to save screenshot
        wait_seconds: Seconds to wait for page load

    Returns:
        True if screenshot was taken successfully
    """
    # Try chromium first, then google-chrome, then firefox
    browsers = [
        ("chromium", [
            "--headless",
            "--disable-gpu",
            "--screenshot={}".format(output_path),
            "--window-size={},{}".format(width, height),
            "--force-device-scale-factor=1",
            "--hide-scrollbars",
        ]),
        ("google-chrome", [
            "--headless",
            "--disable-gpu",
            "--screenshot={}".format(output_path),
            "--window-size={},{}".format(width, height),
            "--force-device-scale-factor=1",
            "--hide-scrollbars",
        ]),
    ]

    for browser, base_args in browsers:
        try:
            # Check if browser exists
            check = subprocess.run(["which", browser], capture_output=True)
            if check.returncode != 0:
                continue

            cmd = [browser] + base_args + [url]
            print(f"  Using {browser}...")

            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=wait_seconds + 5
            )

            if result.returncode == 0 and Path(output_path).exists():
                file_size = Path(output_path).stat().st_size
                print(f"  ✓ Screenshot saved: {output_path} ({file_size} bytes)")
                return True
            else:
                print(f"  ✗ {browser} failed: {result.stderr.decode()[:100]}")

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"  ✗ {browser} error: {e}")
            continue

    return False


def test_all_devices(url: str = "http://localhost:8080", output_dir: str = "/tmp/dashboard_mobile_tests"):
    """Test dashboard on all mobile device resolutions."""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Mobile Dashboard Testing Tool")
    print(f"{'='*60}\n")
    print(f"Testing URL: {url}")
    print(f"Output directory: {output_dir}\n")

    results = {}

    for device_name, (width, height) in MOBILE_DEVICES.items():
        print(f"📱 Testing {device_name} ({width}x{height})...")

        screenshot_path = str(output_path / f"{device_name}.png")
        success = take_screenshot(url, width, height, screenshot_path, wait_seconds=3)

        results[device_name] = {
            "resolution": (width, height),
            "success": success,
            "path": screenshot_path if success else None
        }

        time.sleep(1)  # Brief pause between screenshots

    # Summary
    print(f"\n{'='*60}")
    print("Test Summary")
    print(f"{'='*60}\n")

    successful = sum(1 for r in results.values() if r["success"])
    total = len(results)

    print(f"Successful: {successful}/{total}")
    print("\nScreenshots saved:")

    for device_name, result in results.items():
        if result["success"]:
            print(f"  ✓ {device_name}: {result['path']}")
        else:
            print(f"  ✗ {device_name}: FAILED")

    print(f"\n{'='*60}\n")

    return results


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
    results = test_all_devices(url)

    # Exit code based on success
    successful = sum(1 for r in results.values() if r["success"])
    sys.exit(0 if successful > 0 else 1)
