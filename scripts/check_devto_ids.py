#!/usr/bin/env python3
"""Verify every local dev.to `id` exists on the account behind DEVTO_TOKEN.

devto-cli raises "Cannot find published article on dev.to: <title>" and aborts
the entire batch when one local id is unknown to the token's account, without
naming the file. The usual cause is a fork that kept the upstream `id` values.

Exits 0 when there is nothing to complain about, including when no token is
available, so this is safe to run as a pre-flight check.

Usage:
    DEVTO_TOKEN=... python scripts/check_devto_ids.py articles/foo.md ...
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request

API = "https://dev.to/api"
USER_AGENT = "devto-repo-id-check/1.0"
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
ID_RE = re.compile(r"^id:\s*(\d+)\s*$", re.MULTILINE)


def remote_ids(token):
    ids = set()
    page = 1
    while True:
        request = urllib.request.Request(
            f"{API}/articles/me/all?per_page=1000&page={page}",
            headers={"User-Agent": USER_AGENT, "api-key": token},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            batch = json.load(response)
        ids.update(article["id"] for article in batch)
        if len(batch) < 1000:
            return ids
        page += 1


def main(paths):
    token = os.environ.get("DEVTO_TOKEN") or os.environ.get("DEVTO_API_KEY")
    if not token:
        print("[-] No dev.to token available; skipping the id pre-flight check.")
        return 0

    local = {}
    for path in paths:
        if not path.endswith(".md"):
            continue
        with open(path, encoding="utf-8") as handle:
            match = FRONTMATTER_RE.match(handle.read())
        if not match:
            continue
        found = ID_RE.search(match.group(1))
        if found:
            local[path] = int(found.group(1))

    if not local:
        print("[-] No local dev.to ids to verify.")
        return 0

    try:
        known = remote_ids(token)
    except urllib.error.HTTPError as exc:
        # A bad token is devto-cli's problem to report; do not block on it here.
        print(f"[!] Could not list remote articles ({exc.code}); skipping the check.", file=sys.stderr)
        return 0

    orphans = {path: article_id for path, article_id in local.items() if article_id not in known}
    if not orphans:
        print(f"[-] All {len(local)} local dev.to id(s) exist on this account.")
        return 0

    for path, article_id in sorted(orphans.items()):
        print(f"::error file={path}::id {article_id} does not exist on this dev.to account")
    print(
        f"\n[!] {len(orphans)} article(s) carry a dev.to id this token cannot see. "
        "devto-cli would abort the whole batch on the first one.\n"
        "    If this is a fork, delete the `id:` and `date:` lines so the articles "
        "are created fresh under your own account.\n"
        "    If the articles do exist under a different title, re-run this workflow "
        "with the 'reconcile' input enabled to adopt them by title.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
