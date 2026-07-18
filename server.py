"""
yt-ripper - self-hosted YouTube downloader (Docker/NAS edition).

Env vars:
    DOWNLOAD_DIR    where files land (default /downloads in the container)
    PORT            listen port (default 8000)
    MAX_CONCURRENT  simultaneous downloads (default 3)

Endpoints:
    GET  /                    web UI
    GET  /health              JSON health check (playbook Step 6 verification)
    POST /api/download        {url, quality} -> {id}
    GET  /api/status/<id>     job progress

Note: Only download videos you own, that are Creative Commons licensed,
or that you have permission to download.
"""

import json
import os
import shutil
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    import yt_dlp
except ImportError:
    raise SystemExit("Missing dependency. Run:  pip install yt-dlp")

DOWNLOAD_DIR = os.environ.get(
    "DOWNLOAD_DIR",
    "/downloads" if os.path.isdir("/downloads")
    else os.path.join(os.path.expanduser("~"), "Downloads", "YouTube"))
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
PORT = int(os.environ.get("PORT", "8000"))
MAX_CONCURRENT = int(os.environ.get("MAX_CONCURRENT", "3"))
HAS_FFMPEG = shutil.which("ffmpeg") is not None

jobs = {}  # id -> {status, percent, title, speed, error}
slots = threading.Semaphore(MAX_CONCURRENT)
APP_VERSION = "v0.4.0"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHANGELOG_PATH = os.path.join(BASE_DIR, "CHANGELOG.md")
LOGO_PATH = os.path.join(BASE_DIR, "logo.png")
PAGES_DIR = os.path.join(BASE_DIR, "pages")
STATIC_PAGES = {"/about": "about.html", "/contact": "contact.html",
                "/privacy": "privacy.html", "/terms": "terms.html"}

PAGE = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>yt-ripper</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 640px; margin: 40px auto;
         padding: 0 16px; color: #222; }
  h1 { font-size: 22px; font-weight: 600; }
  .row { display: flex; gap: 8px; margin: 16px 0; }
  input[type=text] { flex: 1; padding: 10px; font-size: 14px;
                     border: 1px solid #ccc; border-radius: 6px; }
  select, button { padding: 10px 14px; font-size: 14px; border-radius: 6px;
                   border: 1px solid #ccc; background: #fff; cursor: pointer; }
  button.primary { background: #c00; color: #fff; border-color: #c00; }
  .job { border: 1px solid #e2e2e2; border-radius: 8px; padding: 12px 14px;
         margin: 10px 0; font-size: 14px; }
  .bar { height: 8px; background: #eee; border-radius: 4px; overflow: hidden;
         margin: 8px 0 4px; }
  .fill { height: 100%; background: #c00; width: 0%; transition: width .3s; }
  .muted { color: #777; font-size: 13px; }
  .err { color: #b00020; }
  footer { margin-top: 48px; padding-top: 16px; border-top: 1px solid #e2e2e2;
           font-size: 13px; }
  footer a { color: #777; margin-right: 12px; text-decoration: none; }
  footer a:hover { text-decoration: underline; }
  #splash { position: fixed; inset: 0; background: #000; z-index: 1000;
            display: flex; align-items: center; justify-content: center;
            opacity: 1; transition: opacity .6s ease; }
  #splash img { max-width: min(80vw, 480px); max-height: 80vh; }
</style>
</head>
<body>
<div id="splash"><img src="/logo.png" alt="yt-ripper"
     onerror="document.getElementById('splash').remove()"></div>
<script>
setTimeout(() => {
  const s = document.getElementById('splash');
  if (s) { s.style.opacity = '0'; setTimeout(() => s.remove(), 600); }
}, 4000);
</script>
<h1>yt-ripper</h1>
<p class="muted">Files are saved on the server in __FOLDER__</p>
<div class="row">
  <input type="text" id="url" placeholder="Paste a YouTube URL">
  <select id="quality">
    <option value="best">Best</option>
    <option value="1080">1080p</option>
    <option value="720">720p</option>
    <option value="480">480p</option>
  </select>
  <button class="primary" onclick="start()">Download</button>
</div>
<div id="jobs"></div>
<footer>
  <a href="/about">About</a>
  <a href="/contact">Contact</a>
  <a href="/privacy">Privacy Policy</a>
  <a href="/terms">Terms of Use</a>
  <a href="/changelog">Changelog</a>
  <span class="muted">__VERSION__</span>
</footer>
<script>
const tracked = {};

async function start() {
  const url = document.getElementById('url').value.trim();
  if (!url) return alert('Paste a URL first');
  const quality = document.getElementById('quality').value;
  const r = await fetch('/api/download', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({url, quality})
  });
  const data = await r.json();
  if (data.error) return alert(data.error);
  document.getElementById('url').value = '';
  track(data.id);
}

function track(id) {
  if (tracked[id]) return;
  const div = document.createElement('div');
  div.className = 'job';
  div.innerHTML = '<span class="title">Starting…</span>' +
    '<div class="bar"><div class="fill"></div></div>' +
    '<span class="muted status"></span>';
  document.getElementById('jobs').prepend(div);
  tracked[id] = setInterval(async () => {
    const r = await fetch('/api/status/' + id);
    const s = await r.json();
    div.querySelector('.title').textContent = s.title || 'Fetching info…';
    div.querySelector('.fill').style.width = (s.percent || 0) + '%';
    const st = div.querySelector('.status');
    if (s.status === 'error') {
      st.textContent = 'Failed: ' + s.error;
      st.className = 'err';
      clearInterval(tracked[id]);
    } else if (s.status === 'done') {
      st.textContent = 'Done ✓';
      div.querySelector('.fill').style.width = '100%';
      clearInterval(tracked[id]);
    } else if (s.status === 'queued') {
      st.textContent = 'Waiting for a free download slot…';
    } else {
      st.textContent = Math.round(s.percent || 0) + '%' +
        (s.speed ? ' — ' + s.speed : '');
    }
  }, 1000);
}
</script>
</body>
</html>
"""


def build_format(quality: str) -> str:
    height = {"1080": 1080, "720": 720, "480": 480}.get(quality)
    if HAS_FFMPEG:
        if height:
            return (f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]"
                    f"/best[height<={height}]")
        return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best"
    if height:
        return f"best[height<={height}][ext=mp4]/best[height<={height}]"
    return "best[ext=mp4]/best"


def run_download(job_id: str, url: str, quality: str):
    job = jobs[job_id]
    with slots:
        job["status"] = "downloading"

        def hook(d):
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                if total:
                    job["percent"] = d.get("downloaded_bytes", 0) / total * 100
                speed = d.get("speed")
                if speed:
                    job["speed"] = f"{speed / 1_048_576:.1f} MB/s"

        opts = {
            "format": build_format(quality),
            "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
            "merge_output_format": "mp4",
            "progress_hooks": [hook],
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
            job["title"] = info.get("title", "video")
            job["status"] = "done"
            job["percent"] = 100
        except Exception as e:
            job["status"] = "error"
            job["error"] = str(e)[:300]


class Handler(BaseHTTPRequestHandler):
    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            body = (PAGE.replace("__FOLDER__", DOWNLOAD_DIR)
                        .replace("__VERSION__", APP_VERSION).encode())
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/changelog":
            if os.path.isfile(CHANGELOG_PATH):
                with open(CHANGELOG_PATH, encoding="utf-8") as f:
                    text = f.read()
            else:
                text = "CHANGELOG.md missing from build."
            import html as _html
            body = ("<!doctype html><html><head><meta charset='utf-8'>"
                    "<meta name='viewport' content='width=device-width, "
                    "initial-scale=1'><title>Changelog — yt-ripper</title>"
                    "<style>body{font-family:system-ui,sans-serif;max-width:"
                    "720px;margin:40px auto;padding:0 16px;color:#222}"
                    "pre{white-space:pre-wrap;font-family:inherit;font-size:"
                    "14px;line-height:1.6}a{color:#c00}</style></head><body>"
                    "<p><a href='/'>&larr; Back to yt-ripper</a></p><pre>"
                    + _html.escape(text) + "</pre></body></html>").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path in STATIC_PAGES:
            page_path = os.path.join(PAGES_DIR, STATIC_PAGES[self.path])
            if os.path.isfile(page_path):
                with open(page_path, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self._json({"error": "Page not found in build"}, 404)
        elif self.path == "/logo.png":
            if os.path.isfile(LOGO_PATH):
                with open(LOGO_PATH, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                self.wfile.write(body)
            else:
                self._json({"error": "logo.png not present in build"}, 404)
        elif self.path == "/health":
            self._json({"status": "ok", "version": APP_VERSION,
                        "ffmpeg": HAS_FFMPEG,
                        "yt_dlp": yt_dlp.version.__version__,
                        "active_jobs": sum(1 for j in jobs.values()
                                           if j["status"] == "downloading")})
        elif self.path.startswith("/api/status/"):
            job = jobs.get(self.path.rsplit("/", 1)[-1])
            if job is None:
                self._json({"error": "Unknown job"}, 404)
            else:
                self._json(job)
        else:
            self._json({"error": "Not found"}, 404)

    def do_POST(self):
        if self.path != "/api/download":
            return self._json({"error": "Not found"}, 404)
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            data = {}
        url = (data.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            return self._json({"error": "Invalid URL"}, 400)
        job_id = uuid.uuid4().hex[:12]
        jobs[job_id] = {"status": "queued", "percent": 0,
                        "title": "", "speed": "", "error": ""}
        threading.Thread(target=run_download,
                         args=(job_id, url, data.get("quality", "best")),
                         daemon=True).start()
        self._json({"id": job_id})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print(f"yt-ripper: saving to {DOWNLOAD_DIR}, listening on :{PORT}, "
          f"ffmpeg={'yes' if HAS_FFMPEG else 'NO'}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
