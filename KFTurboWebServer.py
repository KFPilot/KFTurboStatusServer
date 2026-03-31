# Killing Floor Turbo Web Server
# Serves session data as JSON over HTTP.
# Distributed under the terms of the GPL-2.0 License.
# For more information see https://github.com/KFPilot/KFTurbo.

import json
import threading
from dataclasses import dataclass, asdict
from http.server import HTTPServer, BaseHTTPRequestHandler

from KFTurboServerStatusTypes import ServerPayload

@dataclass
class WebServerEntry:
    server: str
    current_players : int
    max_players : int
    current_map : str

try:
    with open('serverportalconfig.json') as f:
        raw_config = json.load(f)
except Exception as e:
    print(f"Error loading config file: {e}")

ServerMapping = raw_config.get('server mapping')

class SessionDataHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(self.server.cached_json)

    def log_message(self, format, *args):
        pass

def find_location_suffix(name: str) -> str | None:
    name = name.lower().rstrip()
    for loc in ServerMapping:
        if loc in name:
            return ServerMapping[loc]
    return None
    
class SessionDataServer(HTTPServer):
    def __init__(self, host: str, port: int):
        super().__init__((host, port), SessionDataHandler)
        self.cached_json = b"{}"
    
    def update(self, data: dict[str, ServerPayload]):
        entries = {}
        for payload in data.values():
            server_name = find_location_suffix(payload.name)
            entries[server_name] = asdict(WebServerEntry(
                server=payload.name or payload.session_id,
                current_players=payload.player_count or 0,
                max_players=payload.player_max or 0,
                current_map=payload.map_name or payload.map_file or "",
            ))
        self.cached_json = json.dumps(entries).encode("utf-8")

    def start(self):
        thread = threading.Thread(target=self.serve_forever, daemon=True)
        thread.start()
        print(f"Serving session data on {self.server_address[0]}:{self.server_address[1]}...")