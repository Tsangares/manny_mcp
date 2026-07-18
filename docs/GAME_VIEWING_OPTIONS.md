# Viewing the headless RuneLite client (Xvfb `:2`)

How to watch the bot's RuneLite window — which runs on `Xvfb :2 -screen 0
1600x1000x24` on **taxi** (Arch, GNOME/Wayland, user `wil`) — both locally on
the laptop and remotely over Tailscale (desktop **diort**, **pixel-6** phone).

**Hard constraint:** the bot injects synthetic AWT events into the game canvas,
so viewer input must NOT reach `:2`. Any solution is view-only by default, or
input is clearly gated off.

**Verified environment (2026-07-17, post-crash-reboot)**
- `Xvfb :2` running (1600x1000x24, CPU renderer). Only `:2` exists right now;
  `:3`–`:5` are the reserved pool for future accounts, not yet started.
- Tailscale up, taxi = `100.83.247.91`.
- Frame grab from `:2` works: `DISPLAY=:2 import -window root out.png`.
- **No root, and `sudo` requires an interactive password** (`sudo -n true`
  fails) — cannot `pacman -S` anything unattended. `x11vnc`/`tigervnc` are
  in the `extra` repo (confirmed via `pacman -Si`) but not installed
  (`pacman -Q` reports "not found" for both). Install commands below are
  for the user to run by hand when they choose to.
- **Live status: the polished MJPEG viewer (option 4) is what's running,**
  persisted via a systemd **user** unit (survives reboot — see below).

---

## Package availability (`pacman -Si`)

| Package | In repos? | Version | Notes |
|---|---|---|---|
| `x11vnc` | ✅ extra | 1:0.9.17-1 | attach VNC to existing `:2` |
| `tigervnc` | ✅ extra | 1.16.2-4 | provides `Xvnc` (X server + VNC in one) |
| `xorg-server-xephyr` | ✅ extra | 21.1.24-1 | nested X window (local only) |
| `novnc` | ❌ not in repos | — | **AUR only** (`novnc`) — browser VNC. Do not build unattended. |
| `python-websockify` | ❌ not in repos | — | **AUR only** — noVNC's websocket bridge. |

Implication: the "VNC in a browser" path (noVNC) needs two AUR packages. The
native x11vnc/Xvnc servers are one `pacman` command; a browser view without AUR
is best served by the **pure-python MJPEG streamer** (already running, below).

---

## Options compared

Effort/overhead/latency rated for the monitoring use case (2–5 fps is plenty).

| # | Approach | Setup effort | CPU overhead | Latency | Input isolation | Robustness | Browser? |
|---|---|---|---|---|---|---|---|
| 4 | **Python MJPEG (running now)** | none (built) | ~6.6%/core @1.5fps | ~1s | Safe by construction (no input path) | Good; stdlib only | ✅ any browser |
| 1 | x11vnc on `:2` `-viewonly` + noVNC + `tailscale serve` | med (x11vnc easy; noVNC = AUR) | low–med (delta-encoded) | low (<200ms) | Safe with `-viewonly` | Very good | ✅ via noVNC |
| 1b | x11vnc on `:2` `-viewonly`, native VNC client | low | low–med | low | Safe with `-viewonly` | Very good | ❌ needs VNC app |
| 2 | TigerVNC `Xvnc` replacing Xvfb | med (one-time client relaunch) | low | low | Safe if viewers `ViewOnly`; input possible | Very good | ❌ (noVNC=AUR) |
| 3 | ffmpeg x11grab → MJPEG/HLS | low–med | higher (encoder + per-grab startup) | 1–3s (HLS worse) | Safe (one-way) | Medium | ✅ |
| 5 | Xephyr / Xwayland local / local VNC viewer | low–med | low | n/a local | n/a | Good | n/a |
| 6 | sunshine/moonlight, wayvnc | high | — | — | — | — | Rejected (below) |

### Notes per option
- **4 — Python MJPEG (recommended for *now*):** zero install, view-only because
  there is literally no input code path. One shared grabber thread feeds all
  clients (never one grab per client); pauses when nobody is watching. Measured
  **6.6% of one core** at 1.5 fps with a client attached (python orchestrator
  itself ~0%; cost is the transient `import` grabs). Full-frame JPEG each tick,
  so it uses more bandwidth than VNC but that is irrelevant on a LAN/tailnet.
- **1 — x11vnc on `:2`:** the "proper" upgrade. `-viewonly` guarantees isolation,
  delta encoding is lighter and lower-latency than MJPEG, and it survives client
  reconnects. Browser access needs noVNC+websockify (AUR). Publish over Tailscale
  with `tailscale serve` (HTTPS) or just hit `100.83.247.91:5900` with a VNC app.
- **2 — Xvnc replacing Xvfb:** cleanest single-process design, but requires
  killing Xvfb `:2` and relaunching the client on the new server — a one-time
  disruption. Not worth it while a bot session is live; fold in at next restart.
- **3 — ffmpeg x11grab:** measured **0.11s/one-shot grab vs 0.04s for `import`**
  (ffmpeg pays process-startup cost each frame); continuous encode is cheaper per
  frame but adds encoder CPU and, for HLS, multi-second latency. No advantage
  over option 4 for low-fps monitoring.
- **5 — local viewing:** see the dedicated section below.
- **6 — rejected:** *sunshine/moonlight* target GPU HW-encode + gamepad streaming;
  overkill and heavier on a CPU-renderer laptop with thermals to protect.
  *wayvnc* is wlroots-only — GNOME's Wayland compositor (Mutter) is unsupported,
  and it would capture the Wayland desktop, not `:2`, anyway.

---

## Can Xvfb itself be shown on the laptop screen? — No.

Xvfb is a *virtual, headless framebuffer with no output to any monitor*. There is
no "just show it" toggle. Local viewing options, in order of least effort:

1. **Run a VNC viewer locally against x11vnc on `:2`** (after installing x11vnc):
   start `x11vnc` as below, then `vncviewer -viewonly localhost:5900` in your
   GNOME session. Simplest once x11vnc exists.
2. **Just open the MJPEG stream locally** — `http://127.0.0.1:8787/` in a browser
   on the laptop. Zero install, already running.
3. **Xephyr** (`xorg-server-xephyr`, in repos): a nested X *window* on your
   Wayland desktop. But the game is already bound to `:2`; Xephyr would create a
   *new* display (e.g. `:5`) — you cannot retarget the running client into it
   without relaunching. Useful only for a future client started fresh on the
   Xephyr display. Not a way to view the *current* `:2`.
4. **Rootful Xwayland** (`Xwayland :5 ...`): same limitation as Xephyr — it is a
   new server, not a window onto `:2`.

**GNOME built-in "Remote Desktop" (RDP/VNC): useless here.** GNOME's Settings →
Sharing → Remote Desktop shares the **Wayland session** (`wayland-0`, your actual
desktop), not `:2`. It cannot target an arbitrary X display. Confirmed
inapplicable — do not use it for this.

---

## RECOMMENDATION

### Use right now — running as a systemd user service (survives reboot)
The python MJPEG streamer — **option 4** — was polished (multi-display picker,
adjustable FPS, auto-reconnect) and is installed as a **systemd --user** unit
so it comes back automatically after any crash/reboot, no manual restart step
needed.

**Pixel phone URL (just open in the mobile browser):**
```
http://100.83.247.91:8787/
```
That's a picker page — tap "Display :2" + an fps (5/8/10) to get the live view
at `/view?display=:2&fps=5`, which wraps the raw stream in a page with a
status banner and JS auto-reconnect. To skip the picker and go straight to the
view: **http://100.83.247.91:8787/view?display=:2&fps=5**

Other endpoints:
- Raw `<img>`-embeddable MJPEG: `http://100.83.247.91:8787/stream?display=:2&fps=5`
- Health check: `http://100.83.247.91:8787/healthz`
- Local (on taxi itself): `http://127.0.0.1:8787/`

**Service management:**
```bash
systemctl --user status  mjpeg-viewer.service   # check it's up
systemctl --user restart mjpeg-viewer.service   # manual restart if ever needed
systemctl --user stop    mjpeg-viewer.service    # stop watching entirely
journalctl --user -u mjpeg-viewer.service -e     # service-level logs
tail -f /tmp/manny_viewer.log                    # app-level logs (per-client connect/disconnect)
```
Unit file: `/home/wil/.config/systemd/user/mjpeg-viewer.service`
(`enabled` + `WantedBy=default.target`; `loginctl show-user wil` confirms
`Linger=yes`, so it starts at boot even with nobody logged in — genuinely
reboot-persistent, not just session-persistent).

Script: `/home/wil/Desktop/manny_mcp/scripts/mjpeg_viewer.py`
Env overrides (set in the unit file, or export before running manually):
`MJPEG_PORT` (8787), `MJPEG_FPS` (default 5), `MJPEG_QUALITY` (70, JPEG %),
`MJPEG_DISPLAY` (`:2`, used when no `?display=` query param is given),
`MJPEG_CROP` (`on`/`off`, default on), `MJPEG_DETECT_INTERVAL` (30 s),
`MJPEG_TRIM_FUZZ` (`8%`), `MJPEG_MIN_CROP` (200 px).

#### Crop-to-game-window (default ON)

The RuneLite client only fills part of the 1600x1000 Xvfb root (on `:2` it sits
at `796x504+804+496`, the classic fixed-mode window flush to the bottom-right),
so the phone previously saw the game shoved into a corner. The stream now
**crops tight to the game window by default**.

Detection is pure ImageMagick — this host has **no X introspection tools**
(`xwininfo`/`xdotool`/`xrandr` are all absent, and `xprop` is useless because no
window manager runs on Xvfb so `_NET_CLIENT_LIST`/EWMH doesn't exist). The
grabber takes one root frame, finds the non-black bounding box
(`convert … -fuzz 8% -trim`), and feeds that geometry to
`import -window root -crop WxH+X+Y +repage` so the crop happens at capture time
(no extra scaling pass). Geometry is cached and **re-detected every 30 s** (env
`MJPEG_DETECT_INTERVAL`), so a window that moves or resizes is followed
automatically within one detect cycle; add `&redetect=1` to force it immediately.

Fallbacks (never a broken stream): if the grab/trim fails or the box is
implausibly small (< `MJPEG_MIN_CROP`, e.g. a transient all-black loading
screen), the grabber keeps the last good geometry, or streams the **full root**
if it never got one. Displays without a client still cost 0 CPU (lazy grabber).

Stream/view params:
- `&crop=off` — stream the full 1600x1000 root instead of the game window.
- `&redetect=1` — re-find the window now (window moved/resized).
- The `/view` page shows the current mode in the status banner and has a
  `full frame` / `crop to game` toggle link in the bottom-right corner.

Caveat: the per-display grabber is shared, so `crop` (like `fps`) is
last-request-wins, and the *first* frame a client receives after a crop-mode
toggle can be the previously-cached frame in the old mode — it self-corrects on
the next captured frame (~0.2 s). Irrelevant for the normal single-viewer,
crop-on-by-default case.

**Multi-display support is now built into one process** — no more one
process-per-account. `?display=:2|:3|:4|:5` selects which Xvfb to grab (regex
allow-listed, so a stray query param can't reach an arbitrary DISPLAY value).
Each display gets its own lazily-started grabber thread that pauses (0 CPU)
when nobody is watching it; `:3`–`:5` will "just work" once those Xvfb
instances exist — no script changes or new services needed for more accounts.

**Measured overhead (2026-07-17, live test running on :2):**
- 0 clients connected: ~0% CPU (grabber thread blocks on a condvar).
- 1 client @ 5 fps: **~21–22% of one core** (dominated by the `import`
  grab subprocess, not the python server itself, which stays <1%).
- Scales roughly linearly with fps (the old 1.5 fps measurement was ~6.6%).
  Recommended phone fps: **5** (good motion, moderate CPU); use 8–10 only if
  you need snappier feedback and can spare the core time.

The **pixel-6 can just open the URL in its mobile browser** — an `<img>` MJPEG
stream renders natively, no app needed. The `/view` page adds a dark
mobile-friendly frame, a live/lost status banner, and automatic reconnect if
the stream drops (browser `onerror` + a 20s stall watchdog), so leaving the
phone on the page unattended is fine.

#### Optional: publish over Tailscale with HTTPS
Plain HTTP over the tailnet is already private (WireGuard-encrypted). If you want
a clean `https://taxi.<tailnet>.ts.net/` URL with a real cert:
```bash
tailscale serve --bg 8787          # maps https://taxi.<tailnet>.ts.net/ -> 127.0.0.1:8787
tailscale serve status             # show the exact URL
tailscale serve reset              # tear down when done
```
Then the phone/desktop open the `https://…ts.net/` URL. (Do **not** use
`tailscale funnel` — that would expose it to the public internet.)

### Install for a "proper" setup (better latency, lower CPU, reconnect-safe)
This needs root, and `sudo` on this box requires an interactive password (no
passwordless sudo configured), so it could not be done unattended — it's a
manual, one-time upgrade for the user to run whenever convenient. Everything
else (systemd persistence, phone-friendly viewer) is already done above and
does **not** depend on this.

**x11vnc attached to the existing `:2`, view-only** — no client restart required:
```bash
sudo pacman -S x11vnc
# attach to the LIVE :2, view-only, loop forever, localhost-bound:
x11vnc -display :2 -viewonly -forever -shared -nopw -localhost -rfbport 5900 &
```
Reach it from the tailnet either way:
- **Native VNC client** (desktop): point it at `100.83.247.91:5900`. For a native
  client drop `-localhost` (tailnet is already private) or keep `-localhost` and
  use `tailscale serve --tcp 5900 tcp://localhost:5900`.
- **Browser (needs AUR):**
  ```bash
  # AUR — build manually, do not auto-build:
  #   git clone https://aur.archlinux.org/novnc.git && makepkg -si
  #   git clone https://aur.archlinux.org/python-websockify.git && makepkg -si
  websockify --web=/usr/share/novnc 6080 localhost:5900 &
  tailscale serve --bg 6080        # https://taxi.<tailnet>.ts.net/vnc.html
  ```

If you ever restart the client anyway, consider **option 2 (Xvnc replacing
Xvfb)** for a single-process X-server-plus-VNC — launch the client on `Xvnc :2
-geometry 1600x1000 -depth 24 -SecurityTypes None -localhost` instead of Xvfb.
Keep viewers in ViewOnly mode to preserve input isolation.

---

## Multi-account future

**Update:** the viewer now handles this with **one running service**, not one
process per account — `mjpeg-viewer.service` already serves every display via
a query param:

| Account | Display | Xvfb | Tailnet URL |
|---|---|---|---|
| 1 (running) | `:2` | running | `http://100.83.247.91:8787/view?display=:2&fps=5` |
| 2 (future) | `:3` | `Xvfb :3 -screen 0 1600x1000x24` | `…/view?display=:3&fps=5` |
| 3 (future) | `:4` | `Xvfb :4 -screen 0 1600x1000x24` | `…/view?display=:4&fps=5` |
| 4 (future) | `:5` | `Xvfb :5 -screen 0 1600x1000x24` | `…/view?display=:5&fps=5` |

Nothing to start or configure when a new account's Xvfb comes up on `:3`–`:5` —
the picker page at `http://100.83.247.91:8787/` already lists all four and the
grabber thread for a display is created lazily on first request. If a display
doesn't exist yet, that display's tile in the picker will just show a "stream
lost / reconnecting" status until it does.

For x11vnc (if installed later), run one instance per display on distinct
`-rfbport`s (5900, 5901, …) — that server doesn't have a query-param
multiplexing concept like the MJPEG one does. A single `tailscale serve`
config can map several paths to the several ports if you want one hostname
with `/acct2`, `/acct3` routes.
