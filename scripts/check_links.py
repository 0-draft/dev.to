#!/usr/bin/env python3
"""Check outbound links in articles.

dev.to appends a random 3-4 character suffix to every article URL, so a
cross-link written from the slug alone silently 404s. This catches that, plus
ordinary link rot.

Usage:
    python scripts/check_links.py articles/foo.md          # links in one article
    python scripts/check_links.py --all                    # dev.to + own-repo links
    python scripts/check_links.py --all --external         # every http(s) link
    python scripts/check_links.py --all --format=md        # GitHub step summary
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

ARTICLES_DIR = "articles"
REPO = "0-draft/dev.to"
USER_AGENT = "devto-repo-link-check/1.0 (+https://github.com/0-draft/dev.to)"
# Some hosts content-negotiate and 404 a request that does not ask for HTML.
# crates.io is one: /crates/clap is 404 without this header and 200 with it.
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT = 20
WORKERS = 8
RETRIES = 2
HOST_DELAY = 0.3     # seconds between two requests to the same host
RECHECK_DELAY = 3.0  # pause before re-checking a 404, which may just be throttling

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
# Markdown links, bare URLs and HTML hrefs all end up here.
URL_RE = re.compile(r"https?://[^\s)>\"'\]`]+")
TRAILING_PUNCT = ".,;:!?"

# Hosts that reject automated HEAD/GET often enough to be noise rather than signal.
SKIP_HOSTS = {"twitter.com", "x.com", "www.linkedin.com", "linkedin.com"}


def strip_code(body):
    """Blank out fenced blocks and inline code, preserving line numbers."""
    out = []
    fence = None
    for line in body.split("\n"):
        stripped = line.lstrip()
        if fence is None:
            match = re.match(r"(```+|~~~+)", stripped)
            if match:
                fence = match.group(1)[0]
                out.append("")
                continue
        else:
            if re.match(r"(```+|~~~+)\s*$", stripped) and stripped[0] == fence:
                fence = None
            out.append("")
            continue
        out.append(INLINE_CODE_RE.sub(lambda m: " " * len(m.group(0)), line))
    return "\n".join(out)


def collect(paths, external):
    """Return {url: [(path, line), ...]}."""
    found = {}
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            raw = handle.read()
        match = FRONTMATTER_RE.match(raw)
        offset = raw[: match.end()].count("\n") if match else 0
        body = strip_code(raw[match.end():] if match else raw)
        urls = [(m.group(0), m.start()) for m in URL_RE.finditer(body)]
        # cover_image lives in frontmatter, not the body.
        if match:
            for m in re.finditer(r"^cover_image:\s*['\"]?(https?://[^\s'\"]+)", match.group(1), re.MULTILINE):
                urls.append((m.group(1), None))
        for url, index in urls:
            url = url.rstrip(TRAILING_PUNCT)
            if not external and not is_internal(url):
                continue
            if urlhost(url) in SKIP_HOSTS:
                continue
            line = offset + body[:index].count("\n") + 1 if index is not None else None
            found.setdefault(url, []).append((path, line))
    return found


def urlhost(url):
    match = re.match(r"https?://([^/]+)", url)
    return match.group(1).lower() if match else ""


def is_internal(url):
    """dev.to articles by this author, and this repo's own raw assets."""
    return "dev.to/kanywst/" in url or f"raw.githubusercontent.com/{REPO}/" in url


def probe(url):
    """Return (status, note), re-checking a 404 before believing it.

    Throttling is not always signalled honestly. csrc.nist.gov answers a
    request it does not want with 404, not 429, so a single 404 cannot be
    trusted. A real 404 costs one extra request; there are few of those.
    """
    status, note = probe_once(url)
    if status == 404:
        time.sleep(RECHECK_DELAY)
        status, note = probe_once(url)
    return status, note


def probe_once(url):
    """Return (status, note). status is an int, or None when unreachable."""
    last = None
    for attempt in range(RETRIES + 1):
        for method in ("HEAD", "GET"):
            request = urllib.request.Request(url, method=method, headers=HEADERS)
            try:
                with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                    return response.status, ""
            except urllib.error.HTTPError as exc:
                # Some hosts 403/405 HEAD but serve GET fine, so try GET before giving up.
                if method == "HEAD" and exc.code in (403, 405, 501):
                    continue
                last = (exc.code, exc.reason)
                break
            except Exception as exc:  # noqa: BLE001 - network errors are all equivalent here
                last = (None, str(exc))
                break
        if last and last[0] and last[0] < 500:
            break
    return last if last else (None, "unknown")


def probe_host(urls):
    """Probe one host's URLs one at a time.

    csrc.nist.gov answers concurrent requests with 404 rather than 429, which
    is indistinguishable from real link rot: four NIST publications were
    reported dead and every one of them returned 200 when probed serially.
    Hosts still run in parallel with each other, so this costs little.
    """
    results = []
    for index, url in enumerate(urls):
        if index:
            time.sleep(HOST_DELAY)
        results.append((url, probe(url)))
    return results


def probe_all(urls):
    """Return {url: (status, note)}, serialised per host."""
    by_host = defaultdict(list)
    for url in urls:
        by_host[urlhost(url)].append(url)
    results = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for batch in pool.map(probe_host, by_host.values()):
            results.update(batch)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--all", action="store_true", help=f"check every {ARTICLES_DIR}/*.md")
    parser.add_argument("--external", action="store_true", help="also check third-party links")
    parser.add_argument("--format", choices=["text", "md"], default="text")
    args = parser.parse_args()

    paths = sorted(glob.glob(os.path.join(ARTICLES_DIR, "*.md"))) if args.all else sorted(args.paths)
    paths = [p for p in paths if p.endswith(".md")]
    if not paths:
        print("[-] No articles to check.")
        return 0

    links = collect(paths, args.external)
    if not links:
        print("[-] No links to check.")
        return 0

    urls = sorted(links)
    probed = probe_all(urls)

    broken = []
    unreachable = []
    for url in urls:
        status, note = probed[url]
        if status is None:
            unreachable.append((url, note))
        elif status >= 400:
            broken.append((url, status, note))

    # A dead link inside this repo's own content is a bug we control; a dead
    # third-party link is the internet rotting, so it only warrants a warning.
    fatal = [b for b in broken if is_internal(b[0])]

    if args.format == "md":
        print("### Link check\n")
        print(f"Checked **{len(urls)}** unique link(s) across **{len(paths)}** article(s).\n")
        if broken:
            print("#### Broken\n")
            for url, status, note in broken:
                where = ", ".join(f"`{f}:{n}`" if n else f"`{f}`" for f, n in links[url])
                print(f"- `{status}` {url} ({where})")
            print()
        if unreachable:
            print("#### Unreachable\n")
            for url, note in unreachable:
                print(f"- {url} ({note})")
            print()
        if not broken and not unreachable:
            print("All links resolved.\n")
    else:
        for url, status, note in broken:
            for path, line in links[url]:
                where = f"{path}:{line}" if line else path
                level = "error" if is_internal(url) else "warning"
                print(f"{where}: {level}: {status} {url}")
        for url, note in unreachable:
            for path, line in links[url]:
                where = f"{path}:{line}" if line else path
                print(f"{where}: warning: unreachable {url} ({note})")
        print(f"\n[-] {len(urls)} link(s): {len(broken)} broken, {len(unreachable)} unreachable.")

    return 1 if fatal else 0


if __name__ == "__main__":
    sys.exit(main())
