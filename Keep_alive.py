"""
keep_alive.py
Render's free tier is only available for "Web Service" type, which
requires listening on a port. This runs a tiny HTTP server in a
background thread just so Render sees the service as "up" -- the
actual bot still runs via Telegram polling, untouched.
"""

import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"crypto bot is running")

    def log_message(self, format, *args):
        pass  # silence default request logging


def start():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[keep_alive] listening on 0.0.0.0:{port}", flush=True)
