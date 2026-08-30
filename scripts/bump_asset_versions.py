#!/usr/bin/env python3
"""Cache-bust image references whose backing asset file changed.

Two problems stack up when a diagram gets re-rendered in place:

1. dev.to's Bunny CDN serves every image with `cache-control: public,
   max-age=31536000, immutable`. Overwriting the PNG at the same URL never
   reaches a reader whose browser already has it.
2. devto-cli only re-pushes an article whose markdown differs from what is
   live. Re-rendering a diagram does not touch the markdown at all, so the
   push is a no-op even if the CDN would have refetched.

Rewriting `?v=<token>` on every reference to the changed asset fixes both: the
URL is new (so the CDN misses) and the markdown changed (so devto-cli pushes).
The token is a content hash of the asset, so reruns are idempotent and the
query changes exactly when the image does.

Ownership is resolved by *reference*, not by directory name: 40 of this repo's
asset directories do not have a same-named article, and some images are shared.
Every top-level article is scanned for a reference to each changed asset.

Usage:
    python scripts/bump_asset_versions.py articles/assets/foo/diagrams/01-bar.png
    python scripts/bump_asset_versions.py --dry-run articles/assets/foo/cover.png

Prints the article paths it rewrote to stdout, one per line, for the publish
workflow to fold into its push batch. An asset nobody references is a warning
on stderr, never an error.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import os
import re
import sys

ARTICLES_DIR = "articles"
REPO = "0-draft/dev.to"
TOKEN_LENGTH = 8

# Deliberately the same patterns validate_articles.py uses, so the two scripts
# agree on what counts as an image reference. Each match ends right after the
# URL, which keeps the span arithmetic in _rewrite trivial and leaves any
# trailing title text (`![](url "title")`) untouched.
MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(\s*(?P<url>[^)\s]+)")
HTML_IMAGE_RE = re.compile(r"<img[^>]+src=[\"'](?P<url>[^\"']+)[\"']")
COVER_IMAGE_RE = re.compile(r"^cover_image:\s*[\"']?(?P<url>[^\"'\s]+)", re.MULTILINE)

FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n?", re.DOTALL)
FENCE_OPEN_RE = re.compile(r"(```+|~~~+)")
FENCE_CLOSE_RE = re.compile(r"(```+|~~~+)\s*$")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
# https://raw.githubusercontent.com/<owner>/<repo>/refs/heads/main/articles/...
RAW_URL_RE = re.compile(r"/(?:refs/heads/)?[^/]+/(articles/.+)$")


def content_token(path: str) -> str:
    """Short content hash of the asset, stable across runs and machines."""
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()[:TOKEN_LENGTH]


def code_mask(text: str) -> bytearray:
    """Mark every character that sits inside a fenced block or inline code span.

    Mirrors validate_articles.py's strip_code line-by-line fence tracking rather
    than a `.*?` regex over the whole document, so `~~~` fences and four-backtick
    fences are handled the same way in both scripts.
    """
    mask = bytearray(len(text))
    position = 0
    fence = None
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        if fence is None:
            opening = FENCE_OPEN_RE.match(stripped)
            if opening:
                fence = opening.group(1)[0]
                mask[position : position + len(line)] = b"\x01" * len(line)
            else:
                for match in INLINE_CODE_RE.finditer(line):
                    start, end = position + match.start(), position + match.end()
                    mask[start:end] = b"\x01" * (end - start)
        else:
            mask[position : position + len(line)] = b"\x01" * len(line)
            if stripped[:1] == fence and FENCE_CLOSE_RE.match(stripped):
                fence = None
        position += len(line)
    return mask


def resolve(url: str, article: str) -> str | None:
    """Map an image reference to a repo-relative path, or None if it is not ours."""
    clean = url.split("?", 1)[0]
    if clean.startswith("data:") or clean.startswith("#"):
        return None
    if clean.startswith("http"):
        # Articles legitimately link to raw files in other repos; only this
        # repo's own assets can be cache-busted from here.
        if REPO not in clean:
            return None
        match = RAW_URL_RE.search(clean)
        return os.path.normpath(match.group(1)) if match else None
    return os.path.normpath(os.path.join(os.path.dirname(article), clean))


def _bump(url: str, token: str) -> str:
    # Everything after '?' is dropped. No image reference in this repo carries a
    # query other than the version token this script owns.
    return f"{url.split('?', 1)[0]}?v={token}"


def _rewrite(text: str, mask: bytearray, patterns, article: str, tokens, hits) -> str:
    """Rewrite every reference to a changed asset in one pass.

    Collect first, splice second. Running `pattern.sub` per pattern would let
    the first pattern's insertions shift `text` out from under `mask`, which is
    indexed against the original: the second pattern then reads the wrong mask
    byte and, once the text has grown past the mask, raises IndexError.
    """
    edits = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            if mask[match.start()]:
                continue
            url = match.group("url")
            target = resolve(url, article)
            token = tokens.get(target)
            if token is None:
                continue
            hits.add(target)
            start, end = match.span("url")
            edits.append((start, end, _bump(url, token)))

    if not edits:
        return text

    pieces = []
    cursor = 0
    for start, end, replacement in sorted(edits):
        # The two body patterns cannot claim the same URL span, but an overlap
        # would duplicate text, so drop anything that starts behind the cursor.
        if start < cursor:
            continue
        pieces.append(text[cursor:start])
        pieces.append(replacement)
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces)


def rewrite_article(article: str, tokens, hits) -> str | None:
    """Return the article's new text, or None when nothing referenced a changed asset."""
    with open(article, encoding="utf-8") as handle:
        text = handle.read()

    # cover_image only ever lives in frontmatter. Restricting its substitution to
    # that span stops a fenced YAML sample in the body (an article documenting
    # this very pipeline, say) from being rewritten as if it were the real key.
    match = FRONTMATTER_RE.match(text)
    split = match.end() if match else 0
    head, body = text[:split], text[split:]

    new_head = _rewrite(head, bytearray(len(head)), [COVER_IMAGE_RE], article, tokens, hits)
    new_body = _rewrite(body, code_mask(body), [MD_IMAGE_RE, HTML_IMAGE_RE], article, tokens, hits)

    updated = new_head + new_body
    return updated if updated != text else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("asset_paths", nargs="+", help="changed asset paths, repo-relative")
    parser.add_argument("--dry-run", action="store_true", help="report what would change, write nothing")
    args = parser.parse_args()

    tokens = {}
    for raw in args.asset_paths:
        path = os.path.normpath(raw)
        if not os.path.isfile(path):
            print(f"warning: {path} is not a file; skipping", file=sys.stderr)
            continue
        tokens[path] = content_token(path)
    if not tokens:
        return 0

    hits = set()
    touched = []
    for article in sorted(glob.glob(os.path.join(ARTICLES_DIR, "*.md"))):
        updated = rewrite_article(article, tokens, hits)
        if updated is None:
            continue
        if not args.dry_run:
            with open(article, "w", encoding="utf-8") as handle:
                handle.write(updated)
        touched.append(article)

    for path in sorted(set(tokens) - hits):
        print(f"warning: no article references {path}; it will not be republished", file=sys.stderr)

    for article in touched:
        print(article)
    return 0


if __name__ == "__main__":
    sys.exit(main())
