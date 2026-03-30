# Killing Floor Turbo Web Server
# Serves session data as JSON over HTTP.
# Distributed under the terms of the GPL-2.0 License.
# For more information see https://github.com/KFPilot/KFTurbo.

import threading
from http.server import HTTPServer, BaseHTTPRequestHandler


class SessionDataHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(self.server.cached_json)

    def log_message(self, format, *args):
        pass


class SessionDataServer(HTTPServer):
    def __init__(self, host: str, port: int):
        super().__init__((host, port), SessionDataHandler)
        self.cached_json = b"{}"

    def update(self, data: str):
        self.cached_json = data.encode("utf-8")

    def start(self):
        thread = threading.Thread(target=self.serve_forever, daemon=True)
        thread.start()
        print(f"Serving session data on {self.server_address[0]}:{self.server_address[1]}...")
