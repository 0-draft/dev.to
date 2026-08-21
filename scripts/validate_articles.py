#!/usr/bin/env python3
"""Validate article frontmatter and asset references before they reach dev.to.

Errors block a push (exit 1). Warnings are reported but never block, so legacy
content debt does not wedge CI.

Usage:
    python scripts/validate_articles.py articles/foo.md articles/bar.md
    python scripts/validate_articles.py --all
    python scripts/validate_articles.py --all --strict     # warnings become errors
    python scripts/validate_articles.py --all --format=md  # GitHub step summary
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys
from collections import defaultdict

import yaml

ARTICLES_DIR = "articles"
REPO = "0-draft/dev.to"
# dev.to rejects a 5th tag and lowercases whatever it gets, so anything outside
# [a-z0-9] silently changes meaning once it lands.
MAX_TAGS = 4
TAG_RE = re.compile(r"^[a-z0-9]+$")

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)
# devto-cli only rewrites markdown image syntax; HTML <img> passes through as-is.
MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(\s*([^)\s]+)")
HTML_IMAGE_RE = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def strip_code(body):
    """Blank out fenced blocks and inline code, preserving line numbers.

    Articles quote HTML, URLs and em dashes inside code samples all the time;
    prose rules must not fire on them.
    """
    lines = body.split("\n")
    out = []
    fence = None
    for line in lines:
        stripped = line.lstrip()
        if fence is None:
            match = re.match(r"(```+|~~~+)", stripped)
            if match:
                fence = match.group(1)[0] * 3
                out.append("")
                continue
        else:
            if re.match(r"(```+|~~~+)\s*$", stripped) and stripped[0] == fence[0]:
                fence = None
            out.append("")
            continue
        out.append(INLINE_CODE_RE.sub(lambda m: " " * len(m.group(0)), line))
    return "\n".join(out)


ERROR = "error"
WARNING = "warning"


class Finding:
    def __init__(self, level, path, message, line=None):
        self.level = level
        self.path = path
        self.message = message
        self.line = line

    def __str__(self):
        where = f"{self.path}:{self.line}" if self.line else self.path
        return f"{where}: {self.level}: {self.message}"


def load(path):
    """Return (frontmatter dict or None, body, frontmatter start line offset)."""
    with open(path, encoding="utf-8") as handle:
        raw = handle.read()
    match = FRONTMATTER_RE.match(raw)
    if not match:
        return None, raw, 0, None
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        return None, raw, 0, str(exc)
    if not isinstance(data, dict):
        return None, raw, 0, "frontmatter is not a mapping"
    offset = raw[: match.end()].count("\n")
    return data, raw[match.end():], offset, None


def check_frontmatter(path, fm, findings):
    if not fm.get("title"):
        findings.append(Finding(ERROR, path, "frontmatter is missing `title`"))
    if "published" not in fm:
        findings.append(Finding(ERROR, path, "frontmatter is missing `published`"))

    tags = fm.get("tags")
    if not tags:
        findings.append(Finding(WARNING, path, "frontmatter has no `tags`"))
    elif not isinstance(tags, list):
        findings.append(Finding(ERROR, path, f"`tags` must be a list, got {type(tags).__name__}"))
    else:
        if len(tags) > MAX_TAGS:
            findings.append(
                Finding(
                    ERROR,
                    path,
                    f"{len(tags)} tags, dev.to keeps at most {MAX_TAGS} and silently drops the rest: {tags}",
                )
            )
        for tag in tags:
            if not TAG_RE.match(str(tag)):
                findings.append(
                    Finding(ERROR, path, f"tag {tag!r} must be lowercase alphanumeric with no separators")
                )

    if not fm.get("description"):
        level = ERROR if fm.get("published") is True else WARNING
        findings.append(Finding(level, path, "frontmatter has no `description`"))

    series = fm.get("series")
    if isinstance(series, str) and series != series.strip():
        findings.append(Finding(ERROR, path, f"`series` has surrounding whitespace: {series!r}"))


def check_cover(path, fm, findings):
    cover = fm.get("cover_image")
    if not cover:
        findings.append(Finding(WARNING, path, "no `cover_image`"))
        return
    if not str(cover).startswith("http"):
        findings.append(
            Finding(ERROR, path, "`cover_image` must be an absolute raw URL; devto-cli does not rewrite it")
        )
        return
    if REPO not in cover:
        findings.append(Finding(ERROR, path, f"`cover_image` must point at {REPO}: {cover}"))
        return
    match = re.search(r"/(?:refs/heads/)?[^/]+/(articles/.+)$", cover)
    if not match:
        findings.append(Finding(ERROR, path, f"cannot parse `cover_image` path: {cover}"))
        return
    local = match.group(1).split("?")[0]
    if not os.path.exists(local):
        findings.append(Finding(ERROR, path, f"`cover_image` points at a missing file: {local}"))


def check_images(path, body, offset, findings):
    base = os.path.dirname(path)
    for match in MD_IMAGE_RE.finditer(body):
        url = match.group(1)
        line = offset + body[: match.start()].count("\n") + 1
        if url.startswith("http"):
            if url.split("?")[0].lower().endswith(".svg"):
                findings.append(Finding(ERROR, path, f"SVG image: dev.to's CDN corrupts SVG, use PNG ({url})", line))
            continue
        if url.split("?")[0].lower().endswith(".svg"):
            findings.append(Finding(ERROR, path, f"SVG image: dev.to's CDN corrupts SVG, use PNG ({url})", line))
        target = os.path.normpath(os.path.join(base, url.split("?")[0]))
        if not os.path.exists(target):
            findings.append(Finding(ERROR, path, f"image does not exist: {target}", line))

    for match in HTML_IMAGE_RE.finditer(body):
        url = match.group(1)
        if url.startswith("http") or url.startswith("data:"):
            continue
        line = offset + body[: match.start()].count("\n") + 1
        findings.append(
            Finding(
                ERROR,
                path,
                f"<img> with a relative src ({url}): devto-cli only rewrites markdown image syntax, "
                "so this breaks on dev.to. Use ![](...) or an absolute raw URL.",
                line,
            )
        )


def check_body(path, body, offset, raw_body, findings):
    # Only this repo's own assets are constrained; articles legitimately link to
    # raw files in other repos (the author's projects, upstream OSS).
    for match in re.finditer(r"raw\.githubusercontent\.com/([\w.-]+/[\w.-]+)/\S*?articles/assets/", body):
        if match.group(1) != REPO:
            line = offset + body[: match.start()].count("\n") + 1
            findings.append(Finding(ERROR, path, f"asset URL points at {match.group(1)}, expected {REPO}", line))
    if "```mermaid" in raw_body:
        findings.append(Finding(WARNING, path, "uses Mermaid; new diagrams should be D2 (see CLAUDE.md)"))
    if "—" in body:
        findings.append(Finding(WARNING, path, f"contains {body.count(chr(0x2014))} em dash character(s)"))


def check_corpus(articles, findings):
    """Cross-article checks that only make sense over the whole set."""
    by_id = defaultdict(list)
    series = defaultdict(list)
    for path, fm, _body in articles:
        if fm is None:
            continue
        if fm.get("id"):
            by_id[str(fm["id"])].append(path)
        if fm.get("series"):
            series[str(fm["series"])].append(path)

    for article_id, paths in by_id.items():
        if len(paths) > 1:
            for path in paths:
                findings.append(Finding(ERROR, path, f"dev.to id {article_id} is also claimed by {paths}"))

    for name, paths in series.items():
        if len(paths) == 1:
            findings.append(Finding(WARNING, paths[0], f"series {name!r} has a single article; dev.to renders '1/1'"))

    # Near-duplicate series names end up as two separate sidebars on dev.to.
    normalized = defaultdict(list)
    for name in series:
        normalized[re.sub(r"[^a-z0-9]", "", name.lower())].append(name)
    for variants in normalized.values():
        if len(variants) > 1:
            findings.append(Finding(WARNING, ARTICLES_DIR, f"series names differ only by case/punctuation: {variants}"))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*", help="article paths; defaults to nothing unless --all is given")
    parser.add_argument("--all", action="store_true", help=f"check every {ARTICLES_DIR}/*.md")
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    parser.add_argument("--format", choices=["text", "md"], default="text", help="output format")
    args = parser.parse_args()

    paths = sorted(glob.glob(os.path.join(ARTICLES_DIR, "*.md"))) if args.all else sorted(args.paths)
    paths = [p for p in paths if p.endswith(".md")]
    if not paths:
        print("[-] No articles to validate.")
        return 0

    findings = []
    articles = []
    for path in paths:
        fm, body, offset, error = load(path)
        if error:
            findings.append(Finding(ERROR, path, f"invalid frontmatter: {error}"))
            continue
        if fm is None:
            findings.append(Finding(ERROR, path, "no YAML frontmatter"))
            continue
        prose = strip_code(body)
        articles.append((path, fm, body))
        check_frontmatter(path, fm, findings)
        check_cover(path, fm, findings)
        check_images(path, prose, offset, findings)
        check_body(path, prose, offset, body, findings)

    check_corpus(articles, findings)

    errors = [f for f in findings if f.level == ERROR]
    warnings = [f for f in findings if f.level == WARNING]

    if args.format == "md":
        print("### Article validation\n")
        print(f"Checked **{len(paths)}** article(s): **{len(errors)}** error(s), **{len(warnings)}** warning(s).\n")
        for group, title in ((errors, "Errors"), (warnings, "Warnings")):
            if not group:
                continue
            print(f"#### {title}\n")
            for finding in group:
                where = f"{finding.path}:{finding.line}" if finding.line else finding.path
                print(f"- `{where}` {finding.message}")
            print()
    else:
        for finding in errors + warnings:
            print(finding)
        print(f"\n[-] {len(paths)} article(s): {len(errors)} error(s), {len(warnings)} warning(s).")

    if errors:
        return 1
    if warnings and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
