#!/usr/bin/env python3
"""Fixture good service: binds TCP port passed as sys.argv[1] and serves HTTP until terminated."""

import http.server
import socketserver
import sys

port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765

class GoodServiceHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass

with socketserver.TCPServer(("127.0.0.1", port), GoodServiceHandler) as httpd:
    httpd.serve_forever()
