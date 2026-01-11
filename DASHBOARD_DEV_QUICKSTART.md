# Dashboard Development - Quick Start

## 🚀 Start Development Mode

```bash
./start_dashboard_dev.sh
```

This starts the dashboard with **hot-reload** - any changes to `dashboard.py` automatically reload!

## 📱 Access the Dashboard

**On your phone (same WiFi):**
```
http://10.0.0.185:8080
```

**On this computer:**
```
http://localhost:8080
```

## ✏️ Make Changes

1. **Edit** `dashboard.py`
2. **Save** the file
3. **Refresh** browser - changes appear instantly!

## 🧪 Test Mobile Layouts

```bash
./venv/bin/python test_mobile_dashboard_playwright.py
```

View results:
```bash
ls -lh /tmp/dashboard_mobile_tests/
```

## 🎨 What You Can Change

**In dashboard.py, look for the `<style>` section:**

- **Colors:** Change hex codes like `#1e1e1e`, `#2a2a2a`
- **Fonts:** Modify `font-size`, `font-family`
- **Layout:** Adjust grid, flexbox, margins, padding
- **Animations:** Add CSS transitions, transforms
- **Responsive:** Edit `@media` breakpoints

**Example - Change background color:**
```css
/* Find this in dashboard.py */
body {
    background: #1e1e1e;  /* Change to #000000 for black */
}
```

## 📊 Current Dashboard Features

- **Live Video Stream**: H.264 WebSocket from RuneLite
- **Game State**: Position, scenario, inventory
- **Player Stats**: HP, Prayer, Run Energy with progress bars
- **MCP Activity**: Recent tool calls from Claude Code
- **Health Indicator**: Green (healthy) / Red (issues)

## 🔧 Troubleshooting

**Changes not appearing?**
- Make sure you saved `dashboard.py`
- Hard refresh: `Ctrl+Shift+R` (Chrome) or `Cmd+Shift+R` (Mac)

**Phone can't connect?**
- Check you're on the same WiFi network
- Verify firewall: `sudo ufw allow 8080`

**Video not loading?**
- Ensure RuneLite is running: `mcp__runelite-debug__check_health()`
- Check display: `DISPLAY=:2 xdotool search --name "RuneLite"`

## 💡 Development Tips

1. **Keep browser dev tools open** (F12) to see console errors
2. **Test on real phone** for accurate mobile experience
3. **Use Playwright tests** to validate all device sizes
4. **Commit working versions** before major changes
5. **Check logs** if something breaks: `tail -f /tmp/manny_dashboard.log`

## 📚 Related Files

- `dashboard.py` - Main dashboard code
- `DASHBOARD_MOBILE_TESTING.md` - Comprehensive testing guide
- `.claude/skills/improve-dashboard/skill.md` - Skill for Claude Code
- `test_mobile_dashboard_playwright.py` - Automated testing tool

## 🎯 Common Tasks

**Make it look better:**
- Update color scheme
- Add gradients/shadows
- Improve typography
- Add animations

**Make it more robust:**
- Better error handling
- Loading states
- Offline indicators
- Auto-reconnect improvements

**Add features:**
- Command input
- Screenshot capture
- Session history
- Export data
