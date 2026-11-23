import http.client
import importlib.util
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("canvas_server", ROOT / "canvas_server.py")
canvas = importlib.util.module_from_spec(spec)
spec.loader.exec_module(canvas)


class FakeMuse(BaseHTTPRequestHandler):
    requests = []

    def do_GET(self):
        self.reply()

    def do_POST(self):
        self.reply()

    def reply(self):
        self.requests.append((self.command, self.path, self.headers.get("Authorization")))
        data = json.dumps({"ok": True}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class PublicCanvasTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        canvas.ROOT = Path(self.temp.name)
        (canvas.ROOT / "index.html").write_text("<h1>Muse</h1>")
        canvas.PUBLIC_CANVAS = True
        canvas.ACCESS_PASSWORD = "owner-password"
        canvas.API_KEY = "private-api-key"
        self.upstream = ThreadingHTTPServer(("127.0.0.1", 0), FakeMuse)
        canvas.API_PORT = self.upstream.server_port
        self.site = ThreadingHTTPServer(("127.0.0.1", 0), canvas.Handler)
        self.threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in (self.site, self.upstream)]
        for thread in self.threads:
            thread.start()
        FakeMuse.requests.clear()

    def tearDown(self):
        for server in (self.site, self.upstream):
            server.shutdown()
            server.server_close()
        self.temp.cleanup()

    def request(self, method, path, body=None):
        client = http.client.HTTPConnection("127.0.0.1", self.site.server_port, timeout=5)
        client.request(method, path, body=body, headers={"Authorization": "Bearer fake-browser-value"})
        response = client.getresponse()
        result = (response.status, response.read().decode())
        client.close()
        return result

    def test_public_page_uses_private_proxy_without_exposing_secrets(self):
        self.assertEqual(self.request("GET", "/")[0], 200)
        status, config = self.request("GET", "/config.js")
        self.assertEqual(status, 200)
        self.assertIn('window.location.origin + "/employee-api"', config)
        self.assertIn("public-canvas", config)
        self.assertNotIn("private-api-key", config)
        self.assertNotIn("AGENT_TOKEN", config)
        self.assertEqual(self.request("GET", "/employee-api/v1/models")[0], 200)
        self.assertEqual(self.request("POST", "/employee-api/v1/images/generations", b"{}")[0], 200)
        self.assertEqual(FakeMuse.requests, [
            ("GET", "/v1/models", "Bearer private-api-key"),
            ("POST", "/v1/images/generations", "Bearer private-api-key"),
        ])

    def test_admin_and_other_paths_are_not_proxied(self):
        self.assertEqual(self.request("GET", "/employee-api/admin/accounts")[0], 404)
        self.assertEqual(self.request("POST", "/employee-api/v1/models", b"")[0], 405)
        self.assertEqual(self.request("GET", "/employee-api/v1/media/something")[0], 404)
        self.assertEqual(FakeMuse.requests, [])


if __name__ == "__main__":
    unittest.main()
