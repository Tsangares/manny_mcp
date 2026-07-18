#!/usr/bin/env python3
"""
Zero-install MJPEG viewer for a headless X display (default :2).

Serves the live display as multipart/x-mixed-replace (motion JPEG) so any
browser on the tailnet can watch the RuneLite game client. View-only by
construction: no viewer input is ever sent back into the X display.

Design notes:
  - stdlib only (http.server + threading + subprocess).
  - ONE shared grabber thread captures a frame every INTERVAL seconds and
    hands the same JPEG bytes to every connected client. Never one grab per
    client.
  - Frames are captured with `DISPLAY=:2 import -window root -quality 70 jpg:-`
    (ImageMagick). Benchmarked at ~0.04s/grab vs ~0.11s for an ffmpeg one-shot,
    so `import` is the cheaper grabber.
  - When zero clients are connected the grabber pauses (no CPU spent).

Usage:  DISPLAY-independent; pass env overrides if desired.
  MJPEG_DISPLAY=:2 MJPEG_PORT=8787 MJPEG_FPS=1.5 python3 mjpeg_viewer.py
"""

import os
import sys
import time
import threading
import subprocess
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DISPLAY   = os.environ.get("MJPEG_DISPLAY", ":2")
PORT      = int(os.environ.get("MJPEG_PORT", "8787"))
FPS       = float(os.environ.get("MJPEG_FPS", "1.5"))
QUALITY   = int(os.environ.get("MJPEG_QUALITY", "70"))
INTERVAL  = 1.0 / FPS
LOGFILE   = os.environ.get("MJPEG_LOG", "/tmp/manny_viewer.log")
BOUNDARY  = "mjpegframe"

logging.basicConfig(
    filename=LOGFILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


class FrameHub:
    """Single grabber shared by all clients."""

    def __init__(self):
        self._frame = None
        self._cond = threading.Condition()
        self._seq = 0
        self._clients = 0
        self._wake = threading.Event()

    def add_client(self):
        with self._cond:
            self._clients += 1
            n = self._clients
        self._wake.set()
        logging.info("client connected (now %d)", n)

    def remove_client(self):
        with self._cond:
            self._clients -= 1
            n = self._clients
        logging.info("client disconnected (now %d)", n)

    def _grab(self):
        try:
            p = subprocess.run(
                ["import", "-window", "root", "-quality", str(QUALITY), "jpg:-"],
                env={**os.environ, "DISPLAY": DISPLAY},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
            )
            if p.returncode == 0 and p.stdout:
                return p.stdout
            logging.warning("grab failed rc=%s err=%s", p.returncode, p.stderr[:200])
        except Exception as e:  # noqa: BLE001
            logging.warning("grab exception: %s", e)
        return None

    def run(self):
        logging.info("grabber started DISPLAY=%s fps=%.2f q=%d", DISPLAY, FPS, QUALITY)
        while True:
            # Pause entirely when nobody is watching.
            with self._cond:
                idle = self._clients == 0
            if idle:
                self._wake.wait()
                self._wake.clear()
                continue
            t0 = time.time()
            data = self._grab()
            if data:
                with self._cond:
                    self._frame = data
                    self._seq += 1
                    self._cond.notify_all()
            dt = time.time() - t0
            time.sleep(max(0.0, INTERVAL - dt))

    def wait_frame(self, last_seq, timeout=10.0):
        with self._cond:
            if self._seq == last_seq:
                self._cond.wait(timeout)
            return self._frame, self._seq


HUB = FrameHub()

INDEX_HTML = b"""<!doctype html><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>manny :2 viewer</title>
<style>html,body{margin:0;background:#111;height:100%}
img{max-width:100%;max-height:100vh;display:block;margin:auto}</style>
<body><img src="/stream" alt="game display :2"></body>
"""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        logging.info("%s - %s", self.address_string(), fmt % args)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(INDEX_HTML)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(INDEX_HTML)
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
            self._stream()
            return
        self.send_error(404, "not found")

    def _stream(self):
        self.send_response(200)
        self.send_header(
            "Content-Type",
            "multipart/x-mixed-replace; boundary=%s" % BOUNDARY,
        )
        self.send_header("Cache-Control", "no-cache, private")
        self.send_header("Pragma", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        HUB.add_client()
        last = -1
        try:
            while True:
                frame, seq = HUB.wait_frame(last, timeout=10.0)
                if frame is None:
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
            HUB.remove_client()


def main():
    t = threading.Thread(target=HUB.run, daemon=True)
    t.start()
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    logging.info("serving on 0.0.0.0:%d  (open / for the viewer)", PORT)
    print("MJPEG viewer on http://0.0.0.0:%d/  display=%s" % (PORT, DISPLAY),
          file=sys.stderr)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
