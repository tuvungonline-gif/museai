#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""无限画布静态站点服务器（零第三方依赖，Python 3.8+）。

- 托管 canvas/dist，所有前端路由回退到 index.html（React Router）。
- 动态生成 /config.js：把 .env 里的 Muse 地址/Key 和
  agent/.infinite-canvas/canvas-agent.json 里的 Agent 地址/Token 注入浏览器配置。
  Agent 的地址和 Token 只认这个 JSON 文件，不读环境变量。
"""
from __future__ import annotations

import json
import base64
import hmac
import http.client
import mimetypes
import os
import re
import signal
import stat
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

BASE_DIR = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("CANVAS_ROOT") or BASE_DIR / "canvas" / "dist").resolve()
AGENT_CONFIG = Path(os.environ.get("AGENT_CONFIG_FILE") or BASE_DIR / "agent" / ".infinite-canvas" / "canvas-agent.json")
HOST = os.environ.get("CANVAS_HOST", "0.0.0.0")
PORT = int(os.environ.get("CANVAS_PORT", "1521"))
ACCESS_USER = os.environ.get("CANVAS_ACCESS_USER", "")
ACCESS_PASSWORD = os.environ.get("CANVAS_ACCESS_PASSWORD", "")
PUBLIC_CANVAS = os.environ.get("CANVAS_PUBLIC", "").lower() in ("1", "true", "yes")
MEMBERS_ENABLED = os.environ.get("CANVAS_MEMBERS_ENABLED", "0") == "1"
MEMBER_STORE = None
API_KEY = os.environ.get("MUSE_API_KEY", "").strip()
API_PORT = int(os.environ.get("MUSE2API_PORT", "1314"))
PUBLIC_PREFIX = "/employee-api/v1/"
PUBLIC_API_PATH = re.compile(
    r"^/v1/(?:models|chat/completions|images/(?:generations|edits)|"
    r"videos(?:/[A-Za-z0-9_-]+(?:/content)?)?)$"
)
MAX_REQUEST_BYTES = 100 * 1024 * 1024
MEDIA_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".mp4", ".webm", ".mov"}

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/javascript", ".mjs")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/webp", ".webp")
mimetypes.add_type("image/avif", ".avif")
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("application/wasm", ".wasm")
mimetypes.add_type("video/mp4", ".mp4")
mimetypes.add_type("application/manifest+json", ".webmanifest")


def _remove_expired_media(directory: Path, hours: int, now: float | None = None) -> tuple[int, int]:
    """Remove only expired finished media, never directories, links or account files."""
    if hours <= 0:
        raise ValueError("Retention must be greater than zero")
    if (not directory.is_dir() or directory.is_symlink()
            or getattr(directory, "is_junction", lambda: False)()):
        return 0, 0
    cutoff = (time.time() if now is None else now) - hours * 3600
    removed, freed = 0, 0
    for file in directory.iterdir():
        if file.suffix.lower() not in MEDIA_EXTENSIONS:
            continue
        try:
            before = file.lstat()
            if (not stat.S_ISREG(before.st_mode)
                    or getattr(before, "st_file_attributes", 0) & 0x400
                    or before.st_mtime >= cutoff):
                continue
            # Keep files that have changed while this cleanup pass was running.
            current = file.lstat()
            if ((before.st_ino, before.st_size, before.st_mtime_ns)
                    != (current.st_ino, current.st_size, current.st_mtime_ns)):
                continue
            file.unlink()
            removed += 1
            freed += before.st_size
        except OSError:
            # Windows may lock a video while it is being downloaded; retry next hour.
            continue
    return removed, freed


def _start_media_cleanup(stop_event: threading.Event) -> None:
    try:
        hours = int(os.environ.get("CANVAS_MEDIA_RETENTION_HOURS", "0"))
        if hours < 0:
            raise ValueError
    except ValueError:
        print("[media-cleanup] Invalid retention setting; cleanup disabled", flush=True)
        return
    if not hours:
        return
    home = Path(os.environ.get("MUSE2API_HOME") or BASE_DIR / "muse2api")
    if not home.is_absolute():
        home = BASE_DIR / "muse2api" / home
    directory = home / "data" / "media"
    print(f"[media-cleanup] Keep {hours} hours; check hourly: {directory}", flush=True)

    def work() -> None:
        while not stop_event.is_set():
            try:
                count, size = _remove_expired_media(directory, hours)
                if count:
                    print(f"[media-cleanup] Deleted {count} files, freed {size} bytes", flush=True)
            except OSError:
                print("[media-cleanup] Media folder temporarily unavailable; retry next hour", flush=True)
            stop_event.wait(3600)

    threading.Thread(target=work, name="media-cleanup", daemon=True).start()


def _agent_runtime() -> dict[str, str]:
    """Agent 地址/Token 的唯一来源：agent/.infinite-canvas/canvas-agent.json。"""
    try:
        data = json.loads(AGENT_CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    url = str(data.get("publicUrl") or data.get("public_url") or data.get("url") or "").strip().rstrip("/")
    token = str(data.get("token") or "").strip()
    payload: dict[str, str] = {}
    if url:
        payload["AGENT_URL"] = url
    if token:
        payload["AGENT_TOKEN"] = token
    return payload


def _runtime_config() -> str:
    payload: dict[str, str] = {}
    for key in ("ANALYTICS_GA4_ID", "ANALYTICS_BAIDU_ID", "MUSE_CHANNEL_NAME"):
        value = os.environ.get(key, "").strip()
        if value:
            payload[key] = value
    if not PUBLIC_CANVAS and not MEMBERS_ENABLED:
        payload.update(_agent_runtime())
    base = ("/employee-api" if PUBLIC_CANVAS or MEMBERS_ENABLED else os.environ.get("MUSE_API_BASE", "").strip().rstrip("/"))
    if base:
        payload["MUSE_API_BASE"] = base
    # Public visitors receive a non-secret placeholder. The server adds the real key
    # only for the allowlisted generation endpoints below.
    key = "public-canvas" if PUBLIC_CANVAS or MEMBERS_ENABLED else API_KEY
    if key:
        payload["MUSE_API_KEY"] = key
    script = (
        "window.__RUNTIME_CONFIG__ = Object.assign({}, window.__RUNTIME_CONFIG__, "
        + json.dumps(payload, ensure_ascii=False)
        + ");\n"
    )
    if PUBLIC_CANVAS or MEMBERS_ENABLED:
        script += 'window.__RUNTIME_CONFIG__.MUSE_API_BASE = window.location.origin + "/employee-api";\n'
    return script


class Handler(BaseHTTPRequestHandler):
    server_version = "MuseCanvas/1.0"
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802
        self._serve(head_only=False)

    def do_HEAD(self) -> None:  # noqa: N802
        self._serve(head_only=True)

    def do_POST(self) -> None:  # noqa: N802
        self._serve(head_only=False)

    def log_message(self, fmt: str, *args) -> None:
        sys.stdout.write("%s - %s\n" % (self.log_date_time_string(), fmt % args))
        sys.stdout.flush()

    def _send(self, status: int, body: bytes, content_type: str, cache: str, head_only: bool) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def _serve(self, head_only: bool) -> None:
        path = unquote(urlsplit(self.path).path)
        if MEMBERS_ENABLED:
            if MEMBER_STORE is None:
                self._send(503, b"Member service unavailable", "text/plain", "no-store", head_only)
                return
            if MEMBER_STORE.route(self, path):
                return
            if path in ("/login", "/register") and self.command in ("GET", "HEAD"):
                from member_pages import PAGE
                self._send(200, PAGE.encode(), "text/html; charset=utf-8", "no-store", head_only)
                return
            user = MEMBER_STORE.user(self)
            if not user:
                if path.startswith("/employee-api/") or self.command == "POST":
                    MEMBER_STORE.reply(self, 401, {"error": "Vui lòng đăng nhập."})
                else:
                    self.send_response(303)
                    self.send_header("Location", "/login")
                    self.send_header("Content-Length", "0")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                return
            if self.command == "POST":
                origin = self.headers.get("Origin")
                if origin and urlsplit(origin).netloc != self.headers.get("Host"):
                    MEMBER_STORE.reply(self, 403, {"error": "Yêu cầu không hợp lệ."})
                    return
            if path in ("/prompts", "/members") and self.command in ("GET", "HEAD"):
                if path == "/members" and user["role"] != "admin":
                    self._send(403, b"Admin only", "text/plain", "no-store", head_only)
                    return
                from member_pages import PAGE
                self._send(200, PAGE.encode(), "text/html; charset=utf-8", "no-store", head_only)
                return
            if path == "/member-widget.js":
                from member_pages import WIDGET
                self._send(200, WIDGET.encode(), "application/javascript; charset=utf-8", "no-store", head_only)
                return
        if ACCESS_PASSWORD and not PUBLIC_CANVAS and not MEMBERS_ENABLED:
            supplied = self.headers.get("Authorization", "")
            expected = "Basic " + base64.b64encode(
                f"{ACCESS_USER or 'admin'}:{ACCESS_PASSWORD}".encode("utf-8")
            ).decode("ascii")
            if not hmac.compare_digest(supplied, expected):
                self.send_response(401)
                self.send_header("WWW-Authenticate", 'Basic realm="Muse Canvas", charset="UTF-8"')
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
        try:
            if path.startswith("/employee-api/"):
                self._public_api(path, head_only)
                return
            if self.command == "POST":
                self._send(405, b"method not allowed\n", "text/plain", "no-store", False)
                return
            if path == "/healthz":
                self._send(200, b"ok\n", "text/plain; charset=utf-8", "no-store", head_only)
                return
            if path == "/config.js":
                body = _runtime_config().encode("utf-8")
                self._send(200, body, "application/javascript; charset=utf-8", "no-store", head_only)
                return

            candidate = (ROOT / path.lstrip("/")).resolve()
            if candidate != ROOT and ROOT not in candidate.parents:
                self._send(403, b"forbidden\n", "text/plain; charset=utf-8", "no-store", head_only)
                return
            if candidate.is_dir():
                candidate = candidate / "index.html"
            if not candidate.is_file():
                # SPA 回退：/canvas/xxx、/image 等前端路由都交给 index.html
                candidate = ROOT / "index.html"
            if not candidate.is_file():
                self._send(503, "前端未构建：缺少 canvas/dist/index.html\n".encode("utf-8"),
                           "text/plain; charset=utf-8", "no-store", head_only)
                return

            body = candidate.read_bytes()
            if MEMBERS_ENABLED and candidate == ROOT / "index.html":
                body = body.replace(b"</body>", b'<script src="/member-widget.js"></script></body>')
            content_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
            if content_type.startswith("text/") or content_type in (
                "application/javascript", "application/json", "application/manifest+json",
            ):
                content_type += "; charset=utf-8"
            immutable = path.startswith("/assets/")
            cache = "public, max-age=31536000, immutable" if immutable else "no-cache"
            self._send(200, body, content_type, cache, head_only)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except OSError as exc:
            self._send(500, f"读取文件失败：{exc}\n".encode("utf-8"),
                       "text/plain; charset=utf-8", "no-store", head_only)

    def _public_api(self, path: str, head_only: bool) -> None:
        if not (PUBLIC_CANVAS or MEMBERS_ENABLED) or not API_KEY or self.command not in ("GET", "POST") or head_only:
            self._send(404, b"not found\n", "text/plain", "no-store", head_only)
            return
        if not path.startswith(PUBLIC_PREFIX):
            self._send(404, b"not found\n", "text/plain", "no-store", False)
            return
        upstream_path = "/v1/" + path[len(PUBLIC_PREFIX):]
        if not PUBLIC_API_PATH.fullmatch(upstream_path):
            self._send(404, b"not found\n", "text/plain", "no-store", False)
            return
        if self.command == "POST" and upstream_path not in (
            "/v1/chat/completions", "/v1/images/generations", "/v1/images/edits", "/v1/videos"
        ):
            self._send(405, b"method not allowed\n", "text/plain", "no-store", False)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if length < 0 or length > MAX_REQUEST_BYTES or self.headers.get("Transfer-Encoding"):
            self._send(413, b"request too large\n", "text/plain", "no-store", False)
            return
        body = self.rfile.read(length) if length else None
        headers = {"Authorization": "Bearer " + API_KEY, "Accept": self.headers.get("Accept", "*/*")}
        if body is not None:
            headers["Content-Type"] = self.headers.get("Content-Type", "application/json")
        query = urlsplit(self.path).query
        target = upstream_path + ("?" + query if query else "")
        # Muse image/chat requests can run for several minutes; video polls
        # return sooner, but keep the relay timeout above upstream defaults.
        connection = http.client.HTTPConnection("127.0.0.1", API_PORT, timeout=660)
        started_response = False
        try:
            connection.request(self.command, target, body=body, headers=headers)
            response = connection.getresponse()
            self.send_response(response.status)
            self.send_header("Content-Type", response.getheader("Content-Type", "application/octet-stream"))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if response.getheader("Content-Length"):
                self.send_header("Content-Length", response.getheader("Content-Length"))
            else:
                self.send_header("Connection", "close")
                self.close_connection = True
            self.end_headers()
            started_response = True
            while chunk := response.read(64 * 1024):
                self.wfile.write(chunk)
        except (OSError, http.client.HTTPException) as exc:
            self.log_message("Muse API proxy error: %s", exc)
            if not started_response:
                self._send(502, b"Muse API unavailable\n", "text/plain", "no-store", False)
            self.close_connection = True
        finally:
            connection.close()


def main() -> None:
    global MEMBER_STORE
    if MEMBERS_ENABLED:
        from member_auth import MemberStore
        MEMBER_STORE = MemberStore(BASE_DIR / "data" / "members.sqlite3",
                                   os.environ.get("CANVAS_ADMIN_PHONE", ""), ACCESS_PASSWORD)
    if PUBLIC_CANVAS and (HOST not in ("127.0.0.1", "::1", "localhost") or not API_KEY):
        raise SystemExit("Public canvas requires CANVAS_HOST=127.0.0.1 and MUSE_API_KEY")
    if HOST not in ("127.0.0.1", "::1", "localhost") and not ACCESS_PASSWORD:
        raise SystemExit("Set CANVAS_ACCESS_PASSWORD before binding the canvas to a public interface")
    if not (ROOT / "index.html").is_file():
        sys.stderr.write(f"[warn] {ROOT / 'index.html'} 不存在，请先构建前端或设置 CANVAS_ROOT\n")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.daemon_threads = True
    cleanup_stop = threading.Event()

    def stop(_signum, _frame) -> None:
        cleanup_stop.set()
        # shutdown() 会等待 serve_forever 退出，必须放到别的线程里调用。
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print(f"[canvas] serving {ROOT} on http://{HOST}:{PORT}", flush=True)
    _start_media_cleanup(cleanup_stop)
    try:
        server.serve_forever()
    finally:
        cleanup_stop.set()
        server.server_close()


if __name__ == "__main__":
    main()
