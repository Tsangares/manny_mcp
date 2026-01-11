#!/usr/bin/env python3
"""
Mobile Dashboard Testing Tool using Playwright

Takes screenshots of the dashboard at various mobile resolutions
and provides visual validation for mobile layouts.
"""

import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright

# Common mobile device resolutions (width x height in CSS pixels)
MOBILE_DEVICES = {
    "pixel_6_portrait": {"width": 412, "height": 915, "device_scale_factor": 2.625},
    "pixel_6_landscape": {"width": 915, "height": 412, "device_scale_factor": 2.625},
    "iphone_14_portrait": {"width": 390, "height": 844, "device_scale_factor": 3},
    "iphone_14_landscape": {"width": 844, "height": 390, "device_scale_factor": 3},
    "small_phone": {"width": 360, "height": 640, "device_scale_factor": 2},
    "tablet_portrait": {"width": 768, "height": 1024, "device_scale_factor": 2},
    "desktop": {"width": 1920, "height": 1080, "device_scale_factor": 1},
}


async def take_screenshot(page, url: str, device_name: str, config: dict, output_path: str) -> bool:
    """
    Take a screenshot using Playwright.

    Args:
        page: Playwright page object
        url: Dashboard URL
        device_name: Name of device being tested
        config: Device configuration dict
        output_path: Where to save screenshot

    Returns:
        True if screenshot was taken successfully
    """
    try:
        # Set viewport
        await page.set_viewport_size({
            "width": config["width"],
            "height": config["height"]
        })

        # Navigate to URL (use domcontentloaded instead of networkidle due to streaming)
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)

        # Wait for main content to render
        await page.wait_for_timeout(3000)

        # Take screenshot
        await page.screenshot(path=output_path, full_page=False)

        file_size = Path(output_path).stat().st_size
        print(f"  ✓ Screenshot saved: {output_path} ({file_size:,} bytes)")
        return True

    except Exception as e:
        print(f"  ✗ Failed: {str(e)[:100]}")
        return False


async def test_all_devices(url: str = "http://localhost:8080", output_dir: str = "/tmp/dashboard_mobile_tests"):
    """Test dashboard on all mobile device resolutions."""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Mobile Dashboard Testing Tool (Playwright)")
    print(f"{'='*60}\n")
    print(f"Testing URL: {url}")
    print(f"Output directory: {output_dir}\n")

    results = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
        )
        page = await context.new_page()

        for device_name, config in MOBILE_DEVICES.items():
            print(f"📱 Testing {device_name} ({config['width']}x{config['height']})...")

            screenshot_path = str(output_path / f"{device_name}.png")
            success = await take_screenshot(page, url, device_name, config, screenshot_path)

            results[device_name] = {
                "resolution": (config["width"], config["height"]),
                "success": success,
                "path": screenshot_path if success else None
            }

            await asyncio.sleep(0.5)  # Brief pause between screenshots

        await browser.close()

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
    print("To view screenshots:")
    print(f"  cd {output_dir}")
    print(f"  ls -lh *.png")
    print(f"\n{'='*60}\n")

    return results


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
    results = asyncio.run(test_all_devices(url))

    # Exit code based on success
    successful = sum(1 for r in results.values() if r["success"])
    sys.exit(0 if successful > 0 else 1)
