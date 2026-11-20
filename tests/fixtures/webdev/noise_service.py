#!/usr/bin/env python3
"""Fixture noise service: binds port, prints noise warning, and serves HTTP."""

import http.server
import socketserver
import sys
import time

port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
print("[HMR] Waiting for update...")
print("[Fast Refresh] rebuilding...")
sys.stdout.flush()

class NoiseServiceHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass

with socketserver.TCPServer(("127.0.0.1", port), NoiseServiceHandler) as httpd:
    httpd.serve_forever()
