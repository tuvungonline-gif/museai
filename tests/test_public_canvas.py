import hashlib
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
    video = b"0123456789"

    def do_GET(self):
        self.reply()

    def do_POST(self):
        self.reply()

    def reply(self):
        self.requests.append((self.command, self.path, self.headers.get("Authorization")))
        if self.path == "/v1/media/bd8_test.mp4":
            partial = self.headers.get("Range") == "bytes=0-1"
            self.send_response(206 if partial else 200)
            data = self.video[:2] if partial else self.video
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Accept-Ranges", "bytes")
            if partial:
                self.send_header("Content-Range", "bytes 0-1/10")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        result = {"ok": True}
        if self.path == "/v1/videos/video-123":
            result = {
                "status": "completed",
                "url": "http://127.0.0.1:1314/v1/media/bd8_test.mp4",
                "result": {"url": "/v1/media/bd8_test.mp4"},
                "external": {"url": "https://example.com/video.mp4"},
            }
        data = json.dumps(result).encode()
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
        canvas.ROOT = Path(self.temp.name).resolve()
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

    def fetch(self, method, path, body=None, headers=None):
        client = http.client.HTTPConnection("127.0.0.1", self.site.server_port, timeout=5)
        client.request(method, path, body=body, headers={"Authorization": "Bearer fake-browser-value", **(headers or {})})
        response = client.getresponse()
        result = (response.status, dict(response.getheaders()), response.read())
        client.close()
        return result

    def request(self, method, path, body=None):
        status, _, data = self.fetch(method, path, body)
        return status, data.decode()

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

    def test_build_probe_and_cache_follow_the_served_assets(self):
        index = canvas.ROOT / "index.html"
        assets = canvas.ROOT / "assets"
        assets.mkdir()
        (assets / "index-example.js").write_text("export {}")
        for contents in (b"<h1>old</h1>", b"<h1>updated</h1>"):
            index.write_bytes(contents)
            status, headers, data = self.fetch("GET", "/ibee-build.json?v=verify")
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(data), {"index_sha256": hashlib.sha256(contents).hexdigest()})
            self.assertEqual(headers["Cache-Control"], "no-store")
            status, headers, data = self.fetch("GET", "/video")
            self.assertEqual((status, data), (200, contents))
            self.assertEqual(headers["Cache-Control"], "no-store")

        status, headers, _ = self.fetch("GET", "/assets/index-example.js")
        self.assertEqual(status, 200)
        self.assertIn("immutable", headers["Cache-Control"])
        status, headers, _ = self.fetch("GET", "/assets/missing.js")
        self.assertEqual(status, 404)
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_admin_and_other_paths_are_not_proxied(self):
        self.assertEqual(self.request("GET", "/employee-api/admin/accounts")[0], 404)
        self.assertEqual(self.request("POST", "/employee-api/v1/models", b"")[0], 405)
        self.assertEqual(self.request("GET", "/employee-api/v1/media/something")[0], 404)
        self.assertEqual(FakeMuse.requests, [])

    def test_completed_video_supports_playback_and_download(self):
        status, payload = self.request("GET", "/employee-api/v1/videos/video-123")
        self.assertEqual(status, 200)
        video = json.loads(payload)
        path = "/employee-api/v1/media/bd8_test.mp4"
        self.assertEqual(video["url"], path)
        self.assertEqual(video["result"]["url"], path)
        self.assertEqual(video["external"]["url"], "https://example.com/video.mp4")

        status, headers, data = self.fetch("GET", path, headers={"Range": "bytes=0-1"})
        self.assertEqual((status, data), (206, FakeMuse.video[:2]))
        self.assertEqual(headers["Content-Type"], "video/mp4")
        self.assertEqual(headers["Content-Range"], "bytes 0-1/10")
        self.assertEqual(headers["Accept-Ranges"], "bytes")
        self.assertNotIn("Content-Disposition", headers)
        self.assertEqual(headers["Cache-Control"], "no-store")

        status, headers, data = self.fetch("GET", path + "?download=1")
        self.assertEqual((status, data), (200, FakeMuse.video))
        self.assertEqual(headers["Content-Disposition"], 'attachment; filename="bd8_test.mp4"')
        self.assertEqual(FakeMuse.requests[-1], ("GET", "/v1/media/bd8_test.mp4", "Bearer private-api-key"))
        status, headers, data = self.fetch("HEAD", path)
        self.assertEqual((status, data, headers["Content-Length"]), (200, b"", "10"))

    def test_video_relay_limits_paths_and_methods(self):
        for path in ("folder/bd8_test.mp4", "folder%2Fbd8_test.mp4", "accounts.json", "photo.webp"):
            with self.subTest(path=path):
                self.assertEqual(self.request("GET", "/employee-api/v1/media/" + path)[0], 404)
        self.assertEqual(self.request("POST", "/employee-api/v1/media/bd8_test.mp4", b"{}")[0], 405)
        self.assertEqual(FakeMuse.requests, [])


if __name__ == "__main__":
    unittest.main()
