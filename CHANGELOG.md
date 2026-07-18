# yt-ripper changelog

Every feature and every fix gets an entry here at the time it's made — no
batching. Bump `APP_VERSION` in `server.py` with each entry; the version shows
in the dashboard footer and `/health`.

## v0.4.0 — 2026-07-18
- Added site pages: About, Contact, Privacy Policy, Terms of Use (with DMCA
  notice procedure). Served from `pages/`, honest-content pattern: real city
  only, no invented contact details, not-legal-advice notes.
- Added footer to the main dashboard linking all four pages + changelog;
  every page cross-links every other (no orphaned pages).
- Added `/changelog` route rendering this file in-app.
- Added `APP_VERSION` constant, shown in the dashboard footer and `/health`.

## v0.3.0 — 2026-07-18
- Added logo splash screen: full-black overlay shows `logo.png` centered for
  4 seconds on page load, then fades out (0.6s) to the dashboard.
- Added `/logo.png` route (served from the app folder, 1-day cache header).
- Splash auto-skips (removes itself) if the logo file is missing or fails to
  load, instead of showing a broken image.
- `logo.png` is currently a plain dark placeholder — replace with the real
  yt-ripper art. Dockerfile uses a `logo.png*` glob so the image still builds
  if the file is absent.

## v0.2.0 — 2026-07-18
- NAS/Docker edition, per the NAS migration playbook (GitHub Actions → GHCR →
  UGOS pulls → shared Cloudflare tunnel).
- `DOWNLOAD_DIR`, `PORT`, `MAX_CONCURRENT` now env-configurable; downloads
  default to the `/downloads` volume in the container.
- Added download concurrency cap (default 3) with a queue — queued jobs show
  "Waiting for a free download slot…" in the UI.
- Added `/health` endpoint (status, ffmpeg presence, yt-dlp version, active
  job count) for the playbook's Step 6 verification.
- Added `Dockerfile` (python:3.11-slim + ffmpeg baked in, single image).
- Added GitHub Actions workflow pushing `ghcr.io/eviltim58/yt-ripper`
  (lowercase, per playbook lesson 3) with `latest` + SHA tags, plus a weekly
  scheduled rebuild so the baked-in yt-dlp stays current — a stale yt-dlp is
  this app's #1 expected failure mode.
- Added UGOS `docker-compose.yml`: host port 8453 → container 8000, downloads
  bind mount, no `build:` directives, no cloudflared block.
- Added `DEPLOY.md` runbook: repo → Actions → public GHCR package → UGOS
  project → LAN verify → optional tunnel route → Cloudflare Access
  (recommended if public).

## v0.1.0 — 2026-07-18
- Initial web downloader. Python stdlib only (`http.server`) + yt-dlp — no
  Flask, no other dependencies.
- Paste URL, pick quality (Best/1080p/720p/480p), per-job live progress bars
  with percent and speed, multiple simultaneous users, no accounts.
- URL validation (http/https only), JSON API: `POST /api/download`,
  `GET /api/status/<id>`.
- ffmpeg detection: full-quality merged downloads when present, progressive
  fallback (≤720p) when absent.
- No credential use: deliberately runs without any YouTube/Google login or
  cookies. Premium-cookie sharing was considered and rejected — sharing
  account cookies grants full Google-account access and risks suspension.
