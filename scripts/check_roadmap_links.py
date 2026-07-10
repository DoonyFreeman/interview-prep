#!/usr/bin/env python3
"""Liveness check for every external URL in content/roadmap.json.

Network-bound and deliberately NOT part of pytest — run manually before a
merge (and occasionally after, YouTube links rot):

    python3 scripts/check_roadmap_links.py

YouTube URLs go through the oEmbed endpoint (200 = alive, 401 = alive but
embed-disabled — fine, we link rather than embed; 404/400 = dead). Everything
else gets a browser-UA HEAD (GET retry on 405). 403 is reported as a warning —
Habr/Cloudflare cut bots but serve browsers — check those by hand.
Exits 1 if any URL is dead.
"""
from __future__ import annotations

import json
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# macOS framework Python ships without CA certs wired up; prefer certifi when
# available (it's in backend/.venv), else fall back to unverified — we only
# read status codes here, nothing sensitive rides on this connection.
try:
    import certifi

    SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:  # pragma: no cover
    SSL_CTX = ssl._create_unverified_context()

ROADMAP = Path(__file__).resolve().parent.parent / "content" / "roadmap.json"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
TIMEOUT = 15


def iter_urls(data: dict):
    """Yield (where, url) for every resource in the roadmap."""
    for stage in data["stages"]:
        for course in stage.get("courses", []):
            for res in course.get("resources", []):
                yield f"{course['slug']}", res["url"]
            for lesson, resources in (course.get("lesson_resources") or {}).items():
                for res in resources:
                    yield f"{course['slug']}/{lesson}", res["url"]
        for node in stage.get("extra_nodes", []):
            for res in node.get("resources", []):
                yield f"extra:{node['slug']}", res["url"]


def http_status(url: str, method: str = "HEAD") -> int:
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=SSL_CTX) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return -1  # network error / timeout


def check_youtube(url: str) -> tuple[str, str]:
    oembed = (
        "https://www.youtube.com/oembed?url="
        + urllib.parse.quote(url, safe="")
        + "&format=json"
    )
    code = http_status(oembed, method="GET")
    if code == 200:
        return "ok", "oembed 200"
    if code == 401:  # embed disabled but the video exists
        return "ok", "oembed 401 (embed-disabled)"
    return "dead", f"oembed {code}"


def check_generic(url: str) -> tuple[str, str]:
    code = http_status(url, method="HEAD")
    if code == 405:
        code = http_status(url, method="GET")
    if code in (200, 301, 302):
        return "ok", f"http {code}"
    if code == 403:
        return "warn", "http 403 (bot wall — check manually)"
    if code == -1:
        return "warn", "network error/timeout — check manually"
    return "dead", f"http {code}"


def main() -> int:
    data = json.loads(ROADMAP.read_text(encoding="utf-8"))
    seen: dict[str, tuple[str, str]] = {}
    dead: list[str] = []
    warns: list[str] = []
    total = 0

    for where, url in iter_urls(data):
        total += 1
        if url not in seen:
            host = urllib.parse.urlparse(url).netloc
            if "youtube.com" in host or "youtu.be" in host:
                seen[url] = check_youtube(url)
            else:
                seen[url] = check_generic(url)
        status, detail = seen[url]
        line = f"{status.upper():5} {detail:35} {where:35} {url}"
        print(line)
        if status == "dead":
            dead.append(line)
        elif status == "warn":
            warns.append(line)

    print(
        f"\n{total} refs, {len(seen)} unique urls: "
        f"{len(seen) - len(dead) - len(warns)} ok, {len(warns)} warn, {len(dead)} dead"
    )
    if warns:
        print("\nWARN (check manually):\n" + "\n".join(warns))
    if dead:
        print("\nDEAD:\n" + "\n".join(dead))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
