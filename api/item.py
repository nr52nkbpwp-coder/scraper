import sys
import os
import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from api.scraper import get_item_data


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        name = params.get("name", [""])[0].strip()
        include_subitems = params.get("subitems", ["false"])[0].lower() == "true"

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        if not name:
            self.wfile.write(json.dumps({"error": "Missing query parameter 'name'"}).encode())
            return

        try:
            data = get_item_data(name, include_subitems=include_subitems)
            self.wfile.write(json.dumps(data).encode())
        except Exception as e:
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def log_message(self, format, *args):
        pass
