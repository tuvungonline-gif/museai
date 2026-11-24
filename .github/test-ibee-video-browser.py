"""Exercise the built IBEE UI with a controlled Muse response."""
import functools
import http.server
import re
import subprocess
import tempfile
import threading
from collections import Counter
from pathlib import Path
from zipfile import ZipFile
from imageio_ffmpeg import get_ffmpeg_exe
from playwright.sync_api import sync_playwright, expect


class Site(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/video", "/image", "/canvas", "/assets"):
            self.path = "/index.html"
        super().do_GET()

    def log_message(self, *_):
        pass


with tempfile.TemporaryDirectory() as directory, ZipFile("account-ui.zip") as bundle:
    root = Path(directory)
    bundle.extractall(root)
    video = root / "mock.mp4"
    subprocess.run([get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", "color=c=blue:s=96x96:r=10:d=1", "-c:v", "libx264",
                    "-movflags", "+faststart", str(video)], check=True)
    sample = video.read_bytes()
    media_url = "/employee-api/v1/media/mock-result.mp4"
    site = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Site, directory=root))
    threading.Thread(target=site.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{site.server_port}"
    requests = Counter()
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda error: errors.append(str(error)))

        def relay(route):
            method = route.request.method
            endpoint = route.request.url.split("?")[0].removeprefix(base)
            requests[(method, endpoint)] += 1
            count = requests[(method, endpoint)]
            if endpoint == media_url:
                route.fulfill(content_type="video/mp4", body=sample, headers={"Accept-Ranges": "bytes"})
            elif endpoint.endswith("/videos/legacy-slow"):
                if count == 2:
                    route.fulfill(status=502, json={"error": "Temporary fixture fault"})
                elif count == 3:
                    route.abort("internetdisconnected")
                elif count < 146:
                    route.fulfill(json={"id": "legacy-slow", "status": "queued" if count == 1 else "processing"})
                else:
                    route.fulfill(json={"id": "legacy-slow", "status": "completed", "url": media_url})
            elif endpoint.endswith("/videos/legacy-expired"):
                route.fulfill(status=401, json={"error": "Vui lòng đăng nhập."})
            elif endpoint.endswith("/models"):
                route.fulfill(json={"data": [{"id": "muse-video"}]})
            else:
                route.fulfill(status=400, json={"error": "Unexpected fixture request"})

        page.route("**/config.js", lambda route: route.fulfill(content_type="application/javascript",
            body='window.__RUNTIME_CONFIG__ = {MUSE_API_BASE: "/employee-api/v1", MUSE_API_KEY: "fixture-only"};'))
        page.route("**/employee-api/**", relay)
        page.add_init_script("""(() => {
            const schedule = window.setTimeout;
            window.setTimeout = (fn, ms, ...args) => schedule(fn, ms === 2500 ? 10 : ms, ...args);
        })()""")
        page.goto(base + "/video")
        expect(page.get_by_role("heading", name="Trạm tạo video")).to_be_visible()
        page.evaluate("""async () => {
            const db = await new Promise((resolve, reject) => {
                const request = indexedDB.open("infinite-canvas");
                request.onsuccess = () => resolve(request.result);
                request.onerror = () => reject(request.error);
            });
            const tx = db.transaction("video_generation_logs", "readwrite");
            const store = tx.objectStore("video_generation_logs");
            for (const [id, title] of [["legacy-slow", "Video 30s kiểm tra"], ["legacy-expired", "Video phiên hết hạn"]]) {
                store.put({id, createdAt: Date.now()-353000, title, prompt:title,
                    model:"muse::muse-video", config:{model:"muse::muse-video", videoModel:"muse::muse-video",
                    videoSeconds:"30", vquality:"720", size:"720x720"},
                    references:[], durationMs:353000, status:"failed", error:"Tạo video quá thời gian. Hãy thử lại sau.",
                    task:{id, provider:"openai", model:"muse::muse-video"}}, id);
            }
            await new Promise((resolve,reject) => {tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);});
            db.close();
        }""")
        page.reload()
        check = page.get_by_role("button", name="Kiểm tra lại tác vụ cũ")
        old = page.get_by_role("button", name=re.compile("Video 30s kiểm tra"))
        old.click()
        expect(check).to_be_visible()
        assert requests[("GET", "/employee-api/v1/videos/legacy-slow")] == 0
        check.click()
        expect(page.locator("video")).to_have_attribute("src", media_url, timeout=45000)
        page.wait_for_function("document.querySelector('video').readyState >= 1")
        assert page.locator("video").evaluate("(video) => video.duration") == 1
        assert requests[("GET", "/employee-api/v1/videos/legacy-slow")] == 146
        expect(old).to_contain_text("Thành công")
        download = page.locator('a[href="' + media_url + '?download=1"]')
        expect(download).to_be_visible()
        print("PASS: old task recovered after HTTP 502 and network interruption, 146 queries and playable MP4")

        page.set_viewport_size({"width":390, "height":844})
        page.get_by_role("button", name="Lịch sử", exact=True).click()
        page.get_by_role("button", name=re.compile("Video phiên hết hạn")).click()
        check.click()
        expect(page.get_by_text("Phiên đăng nhập IBEE đã hết hạn. Đăng nhập lại rồi kiểm tra tác vụ cũ.")).to_be_visible()
        assert requests[("GET", "/employee-api/v1/videos/legacy-expired")] == 1
        print("PASS: mobile history retains the correct task when the session expires")
        assert not any(method == "POST" for method, _ in requests)
        for path in ("/", "/image", "/canvas", "/assets"):
            page.goto(base + path)
            expect(page.locator("#root")).to_be_visible()
            expect(page.locator(".ibee-loading")).to_have_count(0)
        assert not errors, errors
        print("PASS: image, canvas, assets and home render; no duplicate video submission or uncaught browser errors")
        browser.close()
    site.shutdown()
