# Viewing the headless RuneLite client (Xvfb `:2`)

How to watch the bot's RuneLite window — which runs on `Xvfb :2 -screen 0
1600x1000x24` on **taxi** (Arch, GNOME/Wayland, user `wil`) — both locally on
the laptop and remotely over Tailscale (desktop **diort**, **pixel-6** phone).

**Hard constraint:** the bot injects synthetic AWT events into the game canvas,
so viewer input must NOT reach `:2`. Any solution is view-only by default, or
input is clearly gated off.

**Verified environment (2026-07-17)**
- `Xvfb :2` PID 90864, RuneLite java PID 94049 (~43% of one core, CPU renderer).
- Tailscale up, taxi = `100.83.247.91`, tailscale 1.98.2 (`serve` supported).
- Frame grab from `:2` works: `DISPLAY=:2 import -window root out.png`.
- No root: cannot `pacman -S`. Install commands below are for the user to run.

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

### Use right now (already running, zero install)
The python MJPEG streamer — **option 4**. It is live on taxi:

- Local: **http://127.0.0.1:8787/**
- Any tailnet device (diort, phone): **http://100.83.247.91:8787/**
- Overhead: **~6.6% of one core** at 1.5 fps, pauses to 0 when no one is watching.
- Script: `/home/wil/Desktop/manny_mcp/scripts/mjpeg_viewer.py`
- Log: `/tmp/manny_viewer.log`

The **pixel-6 can just open the URL in its mobile browser** — an `<img>` MJPEG
stream renders natively, no app needed.

To restart it after a reboot:
```bash
cd /home/wil/Desktop/manny_mcp/scripts
setsid python3 mjpeg_viewer.py </dev/null >/dev/null 2>&1 &
```
Env overrides: `MJPEG_PORT`, `MJPEG_FPS`, `MJPEG_QUALITY`, `MJPEG_DISPLAY`.

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

Scaling to several bot accounts = one headless display per account, one viewer
port per account:

| Account | Display | Xvfb | Viewer port | Tailnet URL |
|---|---|---|---|---|
| 1 | `:2` | running | 8787 | `http://100.83.247.91:8787/` |
| 2 | `:3` | `Xvfb :3 -screen 0 1600x1000x24` | 8788 | `…:8788/` |
| 3 | `:4` | `Xvfb :4 -screen 0 1600x1000x24` | 8789 | `…:8789/` |

The MJPEG script already parameterizes display and port via env, so per-account
instances are trivial:
```bash
MJPEG_DISPLAY=:3 MJPEG_PORT=8788 setsid python3 mjpeg_viewer.py </dev/null >/dev/null 2>&1 &
```
For x11vnc, run one per display on distinct `-rfbport`s (5900, 5901, …). A single
`tailscale serve` config can map several paths to the several ports if you want
one hostname with `/acct2`, `/acct3` routes.
