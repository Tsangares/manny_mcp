# Mobile Dashboard Testing Guide

This document describes the mobile testing tools and validation process for the Manny MCP Dashboard.

## Quick Start

### Run Mobile Tests

```bash
./venv/bin/python test_mobile_dashboard_playwright.py http://localhost:8080
```

Screenshots will be saved to `/tmp/dashboard_mobile_tests/`

### Supported Devices

The testing tool validates the dashboard on these resolutions:

| Device | Resolution (CSS pixels) | Aspect Ratio |
|--------|------------------------|--------------|
| Pixel 6 Portrait | 412 x 915 | 9:20 |
| Pixel 6 Landscape | 915 x 412 | 20:9 |
| iPhone 14 Portrait | 390 x 844 | 9:19.4 |
| iPhone 14 Landscape | 844 x 390 | 19.4:9 |
| Small Phone | 360 x 640 | 9:16 |
| Tablet Portrait | 768 x 1024 | 3:4 |
| Desktop | 1920 x 1080 | 16:9 |

## Mobile Optimizations

### Responsive Layout

**Desktop (>900px width):**
- Grid layout: Video (left) | Stats + MCP (right stacked)
- Video fills left column
- 400px sidebar for stats and activity

**Mobile (<=900px width):**
- Vertical stack: Video → Stats → MCP Activity
- Video limited to 35vh max height
- Stats panel up to 40vh
- MCP Activity fills remaining space

**Small Mobile (<=480px width):**
- Reduced padding (4px vs 8px)
- Smaller font sizes
- Larger touch targets (28px min height)
- Optimized spacing

### Key CSS Features

```css
/* Video container */
.video-panel {
    max-height: 35vh;     /* Mobile: don't dominate screen */
    min-height: 200px;    /* Ensure usable size */
}

/* Video element */
video {
    object-fit: contain;  /* Maintain aspect ratio */
    max-height: 100%;     /* Fit within container */
}

/* Smooth mobile scrolling */
.stats-panel, .mcp-panel {
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
}
```

## Access from Mobile Device

### Same WiFi Network

1. Find your local IP:
   ```bash
   ip addr show | grep "inet " | grep -v "127.0.0.1"
   ```

2. On your phone's browser, navigate to:
   ```
   http://<YOUR_IP>:8080
   ```

   Example: `http://10.0.0.185:8080`

### Features

- **Live Video Stream**: H.264 WebSocket stream (auto-reconnects)
- **Real-time Stats**: Updates every 500ms
- **Player Info**: HP, Prayer, Run Energy with gradient progress bars
- **Current Action**: Shows what the bot is doing
- **MCP Activity**: Recent tool calls from Claude Code
- **Health Indicator**: Green (healthy) / Red (issues)

## Testing Tool Details

### Installation

The testing tool uses Playwright with Chromium:

```bash
# Already done if you followed the setup
./venv/bin/pip install playwright
./venv/bin/playwright install chromium
```

### How It Works

1. **Launches headless Chromium**
2. **Sets viewport** to each device resolution
3. **Navigates** to dashboard URL
4. **Waits** for DOM content loaded (3 seconds)
5. **Captures screenshot** at exact viewport size
6. **Saves** as PNG in output directory

### Custom Usage

```python
from test_mobile_dashboard_playwright import test_all_devices
import asyncio

# Test custom URL
results = asyncio.run(test_all_devices(
    url="http://192.168.1.100:8080",
    output_dir="/tmp/my_tests"
))

# Check results
for device, info in results.items():
    if info["success"]:
        print(f"{device}: {info['path']}")
```

### Adding New Device Resolutions

Edit `test_mobile_dashboard_playwright.py`:

```python
MOBILE_DEVICES = {
    # ... existing devices ...
    "custom_device": {
        "width": 480,
        "height": 800,
        "device_scale_factor": 2
    },
}
```

## Validation Checklist

When testing mobile layout, verify:

- [ ] Video stream loads and plays
- [ ] Video doesn't dominate the viewport (max 35-40% height)
- [ ] All player stats are visible without scrolling
- [ ] Progress bars display correctly
- [ ] MCP Activity section is accessible
- [ ] Text is readable (minimum 11-13px font size)
- [ ] Touch targets are adequate (28px+ height)
- [ ] No horizontal scrolling
- [ ] Smooth scrolling in stats/MCP panels
- [ ] Layout adapts correctly on rotation (portrait/landscape)

## Known Issues

### Video Stream

- **Black bars**: Video maintains 16:9 aspect ratio with `object-fit: contain`
- **First load**: May take 2-3 seconds to start streaming
- **Auto-reconnect**: WebSocket reconnects every 2s if disconnected

### Browser Compatibility

- ✅ **Chrome/Chromium**: Full support (recommended)
- ✅ **Firefox**: Full support
- ✅ **Safari**: H.264 MSE support (iOS 11+)
- ⚠️ **Edge**: Usually works (Chromium-based)

## Performance

- **Page Load**: < 2 seconds on local network
- **Video Latency**: ~500ms to 1s
- **State Updates**: Every 500ms
- **WebSocket Bandwidth**: ~200-500 KB/s (depending on video complexity)

## Troubleshooting

### Screenshots Fail

```bash
# Check Playwright installation
./venv/bin/playwright install chromium

# Verify dashboard is running
curl http://localhost:8080
```

### Mobile Can't Connect

```bash
# Check firewall allows port 8080
sudo ufw allow 8080

# Ensure dashboard binds to 0.0.0.0 (not localhost)
# In dashboard.py: uvicorn.run(app, host="0.0.0.0", port=8080)
```

### Video Doesn't Play

1. **Check FFmpeg process**: `ps aux | grep ffmpeg`
2. **View logs**: `tail -f /tmp/manny_dashboard.log`
3. **Test display**: `DISPLAY=:2 xdotool search --name "RuneLite"`
4. **Restart dashboard**: `./start_dashboard.sh`

## Development Workflow

1. **Make CSS changes** in `dashboard.py`
2. **Restart dashboard**: `./start_dashboard.sh`
3. **Run tests**: `./venv/bin/python test_mobile_dashboard_playwright.py`
4. **View screenshots**: `ls -lh /tmp/dashboard_mobile_tests/`
5. **Validate**: Check Pixel 6 and small phone screenshots
6. **Iterate** until layout looks good

## Future Improvements

- [ ] Add touch gestures (pinch-to-zoom on video)
- [ ] Save screenshots with timestamp for comparison
- [ ] Add visual diff tool to compare before/after
- [ ] Generate HTML report with all screenshots
- [ ] Add performance metrics (page load time, video startup time)
- [ ] Test on real devices via BrowserStack/Sauce Labs
- [ ] Add accessibility testing (color contrast, font sizes)
