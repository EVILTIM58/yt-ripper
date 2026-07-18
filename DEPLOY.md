# yt-ripper — NAS deployment guide

Follows the NAS migration playbook (GitHub Actions → GHCR → UGOS pulls → shared Cloudflare tunnel). Single image — no frontend/backend split, no Mongo needed.

**Allocations:** host port **8453** · folder `/volume1/docker/yt-ripper` · image `ghcr.io/eviltim58/yt-ripper:latest` · container `yt-ripper`

> Update the playbook's Section 2 port table after deploying: `yt-ripper | 8453 | 8000 | <domain TBD> | LIVE`.

## Step 1 — Create the GitHub repo

Create repo `EVILTIM58/yt-ripper` (private is fine — the image goes public, not the source). Push these files keeping this layout:

```
yt-ripper/
├── .github/workflows/build.yml
├── Dockerfile
├── server.py
├── CHANGELOG.md
├── logo.png                  (splash-screen logo — replace placeholder with real art)
├── pages/                    (about/contact/privacy/terms, linked from dashboard footer)
│   ├── about.html
│   ├── contact.html
│   ├── privacy.html
│   └── terms.html
└── docker-compose.yml        (not used by CI — it's for UGOS, kept here as reference)
```

> The contact/terms pages reference `contact@`, `dmca@`, and `abuse@yt-ripper.com`. Once the domain exists, set these up with Cloudflare Email Routing (free, DNS-only — same setup as warvid's) so they actually deliver; bouncing addresses are worse than none.

## Step 2 — Verify the build

1. Visit https://github.com/EVILTIM58/yt-ripper/actions — if the push didn't auto-trigger, click "Run workflow"
2. Wait ~3 min for the green check
3. Visit https://github.com/EVILTIM58?tab=packages — confirm `yt-ripper` exists
4. **Make the package PUBLIC** (one-time): package → Package settings → Change visibility → Public

The workflow also rebuilds itself every Monday so the baked-in yt-dlp stays current. When YouTube downloads start failing with extraction errors, the fix is: wait for (or manually run) a rebuild, then redeploy on the NAS with "Pull the latest image" ticked.

## Step 3 — Create the UGOS project

In UGOS File Manager, create:

```
/volume1/docker/yt-ripper/
└── downloads/
```

UGOS Docker → Project → **+ Create Project**: name `yt-ripper`, path `/volume1/docker/yt-ripper`, paste `docker-compose.yml`. Deploy with **"Pull the latest image" ticked**. (No `build:` directives, no cloudflared block — the shared `warvid-cloudflared` handles routing. Do not touch it.)

## Step 4 — Verify on the LAN

- `http://10.0.0.146:8453` from any home device → UI loads
- `http://10.0.0.146:8453/health` → JSON with `"status": "ok"`, `"ffmpeg": true`, and the yt-dlp version
- Queue a test download → file appears in `/volume1/docker/yt-ripper/downloads/`

**You can stop here for a LAN-only setup.** Steps 5–6 are only for public access via the tunnel.

## Step 5 — Cloudflare tunnel route (optional, public access)

1. Pick/register a domain (or use a subdomain of one you own, e.g. `rip.warvid.com`)
2. Cloudflare → Zero Trust → Networks → Tunnels → **warvid-nas** → Published application routes tab
3. First check the zone's DNS Records page for stale A/AAAA/CNAME records on that hostname and delete them (leave MX/TXT alone)
4. **+ Add a published application route**: subdomain as needed, Service Type `HTTP`, URL `10.0.0.146:8453`
5. Repeat for `www.` if using an apex domain

## Step 6 — Cloudflare Access (strongly recommended if public)

A no-auth downloader on the open internet will be found and abused by bots, filling the NAS with strangers' downloads — and a public "download YouTube videos" service is a much bigger ToS/legal exposure than a personal tool. Lock it to your own logins:

1. Zero Trust → Access → Applications → **+ Add an application** → Self-hosted
2. Application domain: the hostname from Step 5
3. Policy: Allow → Include → Emails → add your email + anyone else's you trust
4. Save. Visitors now get a Cloudflare login page; approved emails get a one-time PIN, everyone else is blocked. The app itself needs no changes.

## Ongoing use

- **Redeploy after changes:** push to GitHub → green check → UGOS Redeploy with "Pull the latest image"
- **Watch logs:** `sudo docker logs -f yt-ripper`
- **Downloads location:** `/volume1/docker/yt-ripper/downloads` — reachable via SMB like any NAS share
- **Disk space:** nothing auto-deletes; prune the downloads folder occasionally

## Notes

- Only download videos you own, that are Creative Commons licensed, or that you have permission to download.
- `MAX_CONCURRENT` (compose env) caps simultaneous downloads; queued jobs show "Waiting for a free download slot…"
- The container binds `0.0.0.0:8000` internally; only host port 8453 is exposed, matching the playbook's pattern.
