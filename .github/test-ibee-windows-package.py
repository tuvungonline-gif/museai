import hashlib
import http.client
import importlib.util
import json
import os
import re
import tempfile
import threading
from pathlib import Path
from zipfile import ZipFile
from install_account_assets import install
from member_auth import MemberStore


with tempfile.TemporaryDirectory(prefix="ibee-release-") as directory:
    root = Path(directory).resolve()
    default = root / "canvas" / "dist"
    default.mkdir(parents=True)
    (default / "index.html").write_bytes(b"Default directory")
    custom = root / "Custom Canvas files"
    custom.mkdir()
    (custom / "index.html").write_bytes(b"Old version")
    config = b"CANVAS_ROOT=Custom Canvas files\nCANVAS_MEMBERS_ENABLED=1\n"
    (root / ".env").write_bytes(config)
    backup = root / "backup"
    install("account-ui.zip", root, backup=backup)
    assert (root / ".env").read_bytes() == config
    assert (default / "index.html").read_bytes() == b"Default directory"
    assert (backup / "canvas-index.html").read_bytes() == b"Old version"
    with ZipFile("account-ui.zip") as bundle:
        index = bundle.read("index.html")
    assert (custom / "index.html").read_bytes() == index
    fingerprint = hashlib.sha256(index).hexdigest()
    asset_path = re.search(rb'/assets/index-[\w-]+\.js', index).group().decode()
    os.environ.update(CANVAS_ROOT=str(custom), CANVAS_MEMBERS_ENABLED="1", CANVAS_PUBLIC="1",
                      MUSE_API_KEY="fixture-secret")
    import canvas_server
    canvas_server.MEMBER_STORE = MemberStore(root / "members.sqlite3", "0900000000", "fixture-password")
    site = canvas_server.ThreadingHTTPServer(("127.0.0.1", 0), canvas_server.Handler)
    thread = threading.Thread(target=site.serve_forever, daemon=True)
    thread.start()

    def get(path, cookie=None, payload=None):
        conn = http.client.HTTPConnection("127.0.0.1", site.server_port, timeout=7)
        headers = {"Content-Type": "application/json"}
        if cookie:
            headers["Cookie"] = cookie
        conn.request("POST" if payload else "GET", path, json.dumps(payload) if payload else None, headers)
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return result

    try:
        assert get("/video")[0] == 303
        assert get("/employee-api/v1/models")[0] == 401
        status, headers, body = get("/ibee-build.json")
        assert status == 200 and headers["Cache-Control"] == "no-store"
        assert json.loads(body) == {"index_sha256": fingerprint}
        status, headers, _ = get("/member-api/login", payload={"phone": "0900000000", "password": "fixture-password"})
        assert status == 200
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        for path in ("/", "/video", "/image", "/canvas", "/assets"):
            status, headers, body = get(path, cookie)
            assert status == 200 and headers["Cache-Control"] == "no-store" and asset_path.encode() in body, path
        for path in ("/login", "/register", "/account", "/prompts", "/members", "/manifest.webmanifest", "/brand/favicon.svg", asset_path):
            assert get(path, cookie)[0] == 200, path
        assert get("/assets/unavailable.js", cookie)[0] == 404
        print("PASS Windows package: verified served build, custom path, backup, protected routes, account UI and PWA files")
        print("IBEE build", fingerprint)
    finally:
        site.shutdown()
        site.server_close()
        thread.join(timeout=5)
