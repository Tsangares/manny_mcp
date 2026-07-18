#!/usr/bin/env python3
"""
Zero-install MJPEG viewer for headless X displays (default :2).

Serves live displays as multipart/x-mixed-replace (motion JPEG) so any
browser on the tailnet — including a phone — can watch the RuneLite game
client(s). View-only by construction: no viewer input is ever sent back
into any X display; there is no code path capable of it.

Design notes:
  - stdlib only (http.server + threading + subprocess).
  - One shared grabber thread PER DISPLAY captures a frame every INTERVAL
    seconds and hands the same JPEG bytes to every connected client of that
    display. Never one grab per client. Grabbers are created lazily on first
    request and pause entirely (0 CPU) when nobody is watching that display.
  - Frames are captured with `DISPLAY=<d> import -window root -quality Q jpg:-`
    (ImageMagick). Benchmarked at ~0.04s/grab vs ~0.11s for an ffmpeg one-shot,
    so `import` is the cheaper grabber.
  - Multiple displays supported via ?display=:N query param (allow-list
    below). FPS adjustable per-stream via ?fps=N (clamped). Because a
    display's grabber is shared, the FPS in effect is whichever value was
    most recently requested for that display — fine for the expected
    single-viewer-per-display use case.
  - CROP-TO-GAME-WINDOW (default on): the RuneLite client only occupies part
    of the 1600x1000 Xvfb root, so by default the stream is cropped tight to
    the game window. This host has NO X introspection tools installed
    (xwininfo/xdotool/xrandr all absent; xprop is useless because no window
    manager runs on Xvfb, so EWMH _NET_CLIENT_LIST does not exist). Detection
    is therefore done purely with ImageMagick: grab one root frame and take
    the non-black bounding box (`convert ... -fuzz F% -trim`), then feed that
    geometry to `import -window root -crop WxH+X+Y +repage` so the crop happens
    at capture time. Geometry is cached and re-detected every DETECT_INTERVAL
    seconds (or immediately on ?redetect=1) so a moved/resized window is
    followed. If detection ever fails or looks insane, the grabber falls back
    to the full root — never a broken stream. ?crop=off forces the full root.

Usage:
  MJPEG_DISPLAY=:2 MJPEG_PORT=8787 MJPEG_FPS=1.5 python3 mjpeg_viewer.py

Browser usage:
  http://<host>:8787/                     -> picker page (all displays)
  http://<host>:8787/view?display=:2      -> phone-friendly page (cropped)
  http://<host>:8787/stream?display=:2    -> raw MJPEG for :2 (cropped to game)
  http://<host>:8787/stream?display=:2&crop=off   -> full 1600x1000 root
  http://<host>:8787/stream?display=:2&redetect=1 -> re-find the window now
  http://<host>:8787/stream?display=:3&fps=8
"""

import logging
import os
import re
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

DEFAULT_DISPLAY = os.environ.get("MJPEG_DISPLAY", ":2")
PORT            = int(os.environ.get("MJPEG_PORT", "8787"))
DEFAULT_FPS     = float(os.environ.get("MJPEG_FPS", "5"))
QUALITY         = int(os.environ.get("MJPEG_QUALITY", "70"))
LOGFILE         = os.environ.get("MJPEG_LOG", "/tmp/manny_viewer.log")
BOUNDARY        = "mjpegframe"

# Crop-to-game-window tuning. Detection = ImageMagick trim (see module docstring).
DETECT_INTERVAL = float(os.environ.get("MJPEG_DETECT_INTERVAL", "30"))  # re-find window every N s
TRIM_FUZZ       = os.environ.get("MJPEG_TRIM_FUZZ", "8%")               # black-border tolerance
MIN_CROP        = int(os.environ.get("MJPEG_MIN_CROP", "200"))          # reject boxes smaller than this
CROP_DEFAULT    = os.environ.get("MJPEG_CROP", "on").lower() not in ("0", "off", "no", "false")

GEOM_RE = re.compile(r"^(\d+)x(\d+)\+(\d+)\+(\d+)$")

# Known/allowed displays (the task's headless pool is :2..:5). Anything not
# matching this shape is rejected before it ever reaches subprocess/env.
DISPLAY_RE = re.compile(r"^:[0-9]$")
KNOWN_DISPLAYS = [":2", ":3", ":4", ":5"]

MIN_FPS, MAX_FPS = 1.0, 15.0

logging.basicConfig(
    filename=LOGFILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


def clamp_fps(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        v = DEFAULT_FPS
    return max(MIN_FPS, min(MAX_FPS, v))


def detect_geometry(display):
    """Find the RuneLite game window's bounding box on ``display``.

    No X introspection tools exist on this host, so this grabs one root frame
    and returns the bounding box of everything that isn't the (black) Xvfb
    background, via ImageMagick's trim. Returns a "WxH+X+Y" string, or None if
    the grab/trim fails or the result is implausibly small (e.g. a transient
    all-black loading screen) — callers keep their last good geometry or fall
    back to the full root on None.
    """
    try:
        cap = subprocess.run(
            ["import", "-window", "root", "png:-"],
            env={**os.environ, "DISPLAY": display},
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5,
        )
        if cap.returncode != 0 or not cap.stdout:
            return None
        tr = subprocess.run(
            ["convert", "png:-", "-fuzz", TRIM_FUZZ, "-format", "%@", "info:"],
            input=cap.stdout,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5,
        )
        if tr.returncode != 0 or not tr.stdout:
            return None
        m = GEOM_RE.match(tr.stdout.decode("ascii", "ignore").strip())
        if not m:
            return None
        w, h, x, y = (int(g) for g in m.groups())
        if w < MIN_CROP or h < MIN_CROP:
            return None
        return "%dx%d+%d+%d" % (w, h, x, y)
    except Exception as e:  # noqa: BLE001
        logging.warning("%s: geometry detect failed: %s", display, e)
        return None


class FrameHub:
    """Single grabber shared by all clients of ONE display."""

    def __init__(self, display, fps, crop=CROP_DEFAULT):
        self.display = display
        self.fps = fps
        self.crop = crop            # crop tight to game window?
        self.geom = None            # last good "WxH+X+Y", or None -> full root
        self._last_detect = 0.0
        self._redetect = True       # force a detect on first grab
        self._frame = None
        self._error_frame = None
        self._cond = threading.Condition()
        self._seq = 0
        self._clients = 0
        self._wake = threading.Event()
        self._consecutive_fail = 0
        t = threading.Thread(target=self.run, daemon=True, name=f"grab{display}")
        t.start()

    def add_client(self, fps=None, crop=None, redetect=False):
        with self._cond:
            self._clients += 1
            n = self._clients
            if fps:
                self.fps = clamp_fps(fps)
            if crop is not None:
                self.crop = crop
            if redetect:
                self._redetect = True
        self._wake.set()
        logging.info(
            "%s: client connected (now %d, fps=%.1f, crop=%s)",
            self.display, n, self.fps, "on" if self.crop else "off",
        )

    def remove_client(self):
        with self._cond:
            self._clients -= 1
            n = self._clients
        logging.info("%s: client disconnected (now %d)", self.display, n)

    def _maybe_detect(self):
        """Re-find the game window when cropping and the cache is stale/forced."""
        if not self.crop:
            return
        now = time.time()
        if not (self._redetect or self.geom is None
                or (now - self._last_detect) >= DETECT_INTERVAL):
            return
        g = detect_geometry(self.display)
        self._last_detect = now
        self._redetect = False
        if g:
            if g != self.geom:
                logging.info("%s: crop geometry -> %s", self.display, g)
            self.geom = g
        elif self.geom is None:
            logging.info("%s: window not detected; streaming full root", self.display)
        # On a failed re-detect with a prior geometry, keep the old one (a
        # transient all-black frame shouldn't blow the crop away).

    def _grab(self):
        args = ["import", "-window", "root"]
        if self.crop and self.geom:
            args += ["-crop", self.geom, "+repage"]
        args += ["-quality", str(QUALITY), "jpg:-"]
        try:
            p = subprocess.run(
                args,
                env={**os.environ, "DISPLAY": self.display},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
            )
            if p.returncode == 0 and p.stdout:
                self._consecutive_fail = 0
                return p.stdout
            self._consecutive_fail += 1
            logging.warning("%s: grab failed rc=%s err=%s", self.display, p.returncode, p.stderr[:200])
        except Exception as e:  # noqa: BLE001
            self._consecutive_fail += 1
            logging.warning("%s: grab exception: %s", self.display, e)
        return None

    def run(self):
        logging.info("grabber started display=%s fps=%.2f q=%d", self.display, self.fps, QUALITY)
        while True:
            with self._cond:
                idle = self._clients == 0
            if idle:
                self._wake.wait()
                self._wake.clear()
                continue
            t0 = time.time()
            self._maybe_detect()
            data = self._grab()
            if data:
                with self._cond:
                    self._frame = data
                    self._seq += 1
                    self._cond.notify_all()
            elif self._consecutive_fail in (1, 5, 30):
                # Nudge waiters occasionally so the browser can show a
                # "no signal" state instead of hanging forever.
                with self._cond:
                    self._seq += 1
                    self._cond.notify_all()
            interval = 1.0 / max(self.fps, MIN_FPS)
            dt = time.time() - t0
            time.sleep(max(0.0, interval - dt))

    def wait_frame(self, last_seq, timeout=10.0):
        with self._cond:
            if self._seq == last_seq:
                self._cond.wait(timeout)
            return self._frame, self._seq, self._consecutive_fail


HUBS = {}
HUBS_LOCK = threading.Lock()


def get_hub(display, fps):
    with HUBS_LOCK:
        hub = HUBS.get(display)
        if hub is None:
            hub = FrameHub(display, fps)
            HUBS[display] = hub
        return hub


def picker_html():
    rows = []
    for d in KNOWN_DISPLAYS:
        tag = " (default)" if d == DEFAULT_DISPLAY else ""
        rows.append(f"""
        <div class="disp">
          <div class="dname">Display {d}{tag}</div>
          <div class="fpsrow">
            {"".join(f'<a href="/view?display={d}&fps={f}">{f} fps</a>' for f in (5, 8, 10))}
          </div>
        </div>""")
    return f"""<!doctype html><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1,maximum-scale=1">
<title>manny game viewer</title>
<style>
  html,body{{margin:0;background:#111;color:#ddd;font-family:system-ui,sans-serif;
    min-height:100%}}
  h1{{font-size:1.1rem;padding:1rem 1rem 0}}
  .disp{{margin:1rem;padding:.75rem 1rem;background:#1c1c1c;border-radius:10px}}
  .dname{{font-weight:600;margin-bottom:.5rem}}
  .fpsrow a{{display:inline-block;margin:0 .5rem .5rem 0;padding:.4rem .8rem;
    background:#2a5;color:#fff;border-radius:6px;text-decoration:none;font-size:.9rem}}
  .fpsrow a:active{{background:#184}}
  p.note{{margin:1rem;color:#888;font-size:.85rem}}
</style>
<body>
<h1>manny — RuneLite display viewer (view-only)</h1>
{"".join(rows)}
<p class="note">Only :2 is confirmed running right now; :3–:5 will work once a
display exists on this host. Tap a display+fps combo above, or open
<code>/stream?display=:2&amp;fps=5</code> directly for the raw image.</p>
</body>
"""


def view_html(display, fps, crop=CROP_DEFAULT):
    crop_qs = "" if crop else "&crop=off"
    crop_label = "cropped to game" if crop else "full root"
    return f"""<!doctype html><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>manny {display} viewer</title>
<style>
  html,body{{margin:0;background:#111;height:100%;overflow:hidden}}
  #wrap{{position:fixed;inset:0;display:flex;align-items:center;justify-content:center}}
  img{{max-width:100%;max-height:100vh;display:block;margin:auto}}
  #status{{position:fixed;top:0;left:0;right:0;padding:.3rem .6rem;font:12px
    system-ui,sans-serif;color:#9c9;background:rgba(0,0,0,.5);text-align:center}}
  #status.bad{{color:#f88}}
  a.back{{position:fixed;bottom:.5rem;left:.5rem;color:#7af;font:12px
    system-ui,sans-serif;text-decoration:none;background:rgba(0,0,0,.5);
    padding:.3rem .6rem;border-radius:6px}}
</style>
<body>
<div id="status">connecting to {display} @ {fps} fps ({crop_label})…</div>
<div id="wrap"><img id="stream" alt="game display {display}"></div>
<a class="back" href="/">&larr; displays</a>
<a class="back" style="left:auto;right:.5rem" href="/view?display={display}&fps={fps}&crop={"off" if crop else "on"}">{"full frame" if crop else "crop to game"}</a>
<script>
(function() {{
  var img = document.getElementById('stream');
  var status = document.getElementById('status');
  var src = "/stream?display={display}&fps={fps}{crop_qs}&_=" ;
  var backoff = 1000;
  function connect() {{
    status.textContent = "connecting to {display} @ {fps} fps ({crop_label})…";
    status.classList.remove('bad');
    img.onerror = onDrop;
    img.onload = function() {{
      backoff = 1000;
      status.textContent = "{display} live";
    }};
    img.src = src + Date.now();
  }}
  function onDrop() {{
    status.textContent = "stream lost — reconnecting…";
    status.classList.add('bad');
    setTimeout(connect, backoff);
    backoff = Math.min(backoff * 1.5, 15000);
  }}
  // Streams are long-lived MJPEG responses; if the browser silently stalls
  // (no error event, just no new frames) force a reconnect periodically.
  setInterval(function() {{
    if (!img.complete && img.naturalWidth === 0) onDrop();
  }}, 20000);
  connect();
}})();
</script>
</body>
"""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        logging.info("%s - %s", self.address_string(), fmt % args)

    def _parse(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        display = qs.get("display", [DEFAULT_DISPLAY])[0]
        if not DISPLAY_RE.match(display):
            display = DEFAULT_DISPLAY
        fps = clamp_fps(qs.get("fps", [DEFAULT_FPS])[0])
        crop_raw = qs.get("crop", ["on" if CROP_DEFAULT else "off"])[0].lower()
        crop = crop_raw not in ("0", "off", "no", "false")
        redetect = qs.get("redetect", ["0"])[0].lower() in ("1", "on", "yes", "true")
        return parsed.path, display, fps, crop, redetect

    def do_GET(self):
        path, display, fps, crop, redetect = self._parse()
        if path in ("/", "/index.html"):
            body = picker_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/view":
            body = view_html(display, fps, crop).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/healthz":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", "3")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(b"ok\n")
            return
        if path in ("/stream", "/stream.mjpg"):
            self._stream(display, fps, crop, redetect)
            return
        self.send_error(404, "not found")

    def _stream(self, display, fps, crop=CROP_DEFAULT, redetect=False):
        hub = get_hub(display, fps)
        self.send_response(200)
        self.send_header(
            "Content-Type",
            "multipart/x-mixed-replace; boundary=%s" % BOUNDARY,
        )
        self.send_header("Cache-Control", "no-cache, private")
        self.send_header("Pragma", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        hub.add_client(fps, crop=crop, redetect=redetect)
        last = -1
        try:
            while True:
                frame, seq, fails = hub.wait_frame(last, timeout=10.0)
                if frame is None:
                    if fails >= 30:
                        return  # give the browser's onerror/stall path a chance
                    continue
                if seq == last:
                    continue  # spurious wakeup / keepalive
                last = seq
                hdr = (
                    "--%s\r\n"
                    "Content-Type: image/jpeg\r\n"
                    "Content-Length: %d\r\n\r\n" % (BOUNDARY, len(frame))
                ).encode("ascii")
                self.wfile.write(hdr)
                self.wfile.write(frame)
                self.wfile.write(b"\r\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:  # noqa: BLE001
            logging.info("stream ended: %s", e)
        finally:
            hub.remove_client()


def main():
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    logging.info("serving on 0.0.0.0:%d  (default display=%s)", PORT, DEFAULT_DISPLAY)
    print("MJPEG viewer on http://0.0.0.0:%d/  default display=%s" % (PORT, DEFAULT_DISPLAY),
          file=sys.stderr)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
