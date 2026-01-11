# Improve Dashboard Skill

**Trigger:** User wants to improve the web dashboard appearance, functionality, or robustness.

**Purpose:** Provide a structured workflow for developing and testing dashboard improvements with live preview capabilities.

## When to Use

- User wants to make the dashboard "look better"
- User wants to add features to the dashboard
- User wants to test dashboard on mobile devices
- User needs to debug visual/layout issues
- User wants to improve responsive design

## Workflow

### 1. Setup Development Environment

**Start hot-reload mode:**
```bash
./start_dashboard_dev.sh
```

This provides:
- ✅ Automatic reload on file changes
- ✅ Access from phone: `http://10.0.0.185:8080`
- ✅ Local browser: `http://localhost:8080`

### 2. Access Points

**Desktop Browser:**
- `http://localhost:8080`

**Mobile Device (same WiFi):**
- `http://10.0.0.185:8080`

**Check current IP:**
```bash
ip addr show | grep "inet " | grep -v "127.0.0.1"
```

### 3. Development Cycle

1. **Edit** `dashboard.py` (CSS/HTML in the file)
2. **Save** - changes reload automatically
3. **View** on phone/browser - refresh to see changes
4. **Test** mobile layouts:
   ```bash
   ./venv/bin/python test_mobile_dashboard_playwright.py http://localhost:8080
   ```
5. **Review** screenshots in `/tmp/dashboard_mobile_tests/`

### 4. Key Files

- **dashboard.py**: Main dashboard code (HTML/CSS embedded)
- **DASHBOARD_MOBILE_TESTING.md**: Testing guide
- **test_mobile_dashboard_playwright.py**: Automated mobile testing

### 5. Testing Devices

Mobile test tool validates:
- Pixel 6 (Portrait/Landscape)
- iPhone 14 (Portrait/Landscape)
- Small Phone (360x640)
- Tablet (768x1024)
- Desktop (1920x1080)

### 6. Common Improvements

**Visual Enhancements:**
- Colors, gradients, shadows
- Typography and spacing
- Animations and transitions
- Dark mode support

**Layout Improvements:**
- Responsive breakpoints
- Grid/flexbox adjustments
- Mobile-first design
- Touch target sizes

**Functionality:**
- Real-time data updates
- Interactive controls
- Error handling
- Loading states

**Robustness:**
- WebSocket reconnection
- Error boundaries
- Graceful degradation
- Performance optimization

## Safety Considerations

- Dashboard runs on `0.0.0.0:8080` (accessible on network)
- Read-only interface (no control of game client)
- Uses WebSocket for video stream
- FFmpeg process handles video encoding

## Validation

Before considering changes complete:

1. **Visual check** on desktop browser
2. **Mobile check** on real device
3. **Automated tests** pass for all device sizes
4. **Performance** check (page load, video latency)
5. **Cross-browser** test (Chrome, Firefox, Safari)

## Troubleshooting

**Can't see changes:**
- Save the file (hot-reload triggers on save)
- Hard refresh browser (Ctrl+Shift+R)
- Check terminal for reload logs

**Phone can't connect:**
- Verify same WiFi network
- Check firewall: `sudo ufw allow 8080`
- Verify IP: `ip addr show`

**Video doesn't load:**
- Check RuneLite is running: `DISPLAY=:2 xdotool search --name "RuneLite"`
- Check FFmpeg process: `ps aux | grep ffmpeg`
- View logs: `tail -f /tmp/manny_dashboard.log`

## Example Session

```bash
# 1. Start development server
./start_dashboard_dev.sh

# 2. Open on phone: http://10.0.0.185:8080
# 3. Edit dashboard.py - change CSS colors
# 4. Save file - observe auto-reload in terminal
# 5. Refresh phone browser - see changes
# 6. Run mobile tests
./venv/bin/python test_mobile_dashboard_playwright.py

# 7. Review screenshots
ls -lh /tmp/dashboard_mobile_tests/
```

## Resources

- **Uvicorn docs**: https://www.uvicorn.org/
- **FastAPI docs**: https://fastapi.tiangolo.com/
- **CSS Grid**: https://css-tricks.com/snippets/css/complete-guide-grid/
- **Responsive design**: https://web.dev/responsive-web-design-basics/
