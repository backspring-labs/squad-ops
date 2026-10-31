"""Tally's HTTP interface."""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from tally.ledger import Ledger

ASSETS = Path(__file__).resolve().parent.parent / "assets"
COUNTERS = "/counters/"


def make_handler(ledger):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/healthz":
                self._send(200, "text/plain", b"ok\n")
            elif self.path == "/counters":
                self._json(200, ledger.counters())
            elif self.path == "/mark.png":
                self._send(200, "image/png", (ASSETS / "mark.png").read_bytes())
            elif self.path == "/admin":
                self._admin()
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self):
            name = self.path[len(COUNTERS) :] if self.path.startswith(COUNTERS) else ""
            if not name or "/" in name:
                self._json(404, {"error": "not found"})
                return
            self._json(200, {"name": name, "count": ledger.add(name)})

        def _admin(self):
            token = os.environ.get("TALLY_ADMIN_TOKEN")
            if not token:
                self._json(503, {"error": "admin is not configured"})
            elif self.headers.get("Authorization") != f"Bearer {token}":
                self._json(401, {"error": "unauthorized"})
            else:
                self._json(200, {"total": ledger.total()})

        def _json(self, status, body):
            self._send(status, "application/json", json.dumps(body).encode())

        def _send(self, status, content_type, payload):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return Handler


def make_server(host, port, ledger=None):
    return ThreadingHTTPServer(
        (host, port), make_handler(ledger if ledger is not None else Ledger())
    )
