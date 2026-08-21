#!/usr/bin/env python3
"""Fail only when a change *adds* markdownlint errors.

The corpus predates the linter, so gating on "zero errors" would block every
edit to an old article until the whole backlog is rewritten. Gating on the delta
against the base revision keeps new work clean and lets the backlog shrink on
its own schedule.

Usage:
    python scripts/lint_ratchet.py --base origin/main articles/foo.md
    python scripts/lint_ratchet.py --base origin/main --changed
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter

CONFIG = os.path.expanduser("~/.markdownlint-cli2.jsonc")
LINT_CMD = ["npx", "--yes", "markdownlint-cli2"]
# e.g. "articles/foo.md:16 error MD025/single-title/single-h1 Multiple top-level..."
FINDING_RE = re.compile(r"^\S+\.md:\d+(?::\d+)?\s+\w+\s+(MD\d+)/")


def run_lint(paths, cwd=None):
    """Return Counter of rule -> occurrences across the given files."""
    if not paths:
        return Counter()
    cmd = list(LINT_CMD)
    if os.path.exists(CONFIG):
        cmd += ["--config", CONFIG]
    cmd += paths
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    counts = Counter()
    for line in (result.stdout + result.stderr).splitlines():
        match = FINDING_RE.match(line.strip())
        if match:
            counts[match.group(1)] += 1
    return counts


def changed_articles(base):
    """Articles added or modified relative to base, plus untracked ones."""
    paths = set()
    for cmd in (
        ["git", "diff", "--name-only", "--diff-filter=d", f"{base}...HEAD", "--", "articles/*.md"],
        ["git", "diff", "--name-only", "--diff-filter=d", "--", "articles/*.md"],
        ["git", "ls-files", "--others", "--exclude-standard", "--", "articles/*.md"],
    ):
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            paths.update(p for p in result.stdout.split() if p.endswith(".md"))
    return sorted(p for p in paths if os.path.exists(p))


def baseline_counts(base, paths, workdir):
    """Lint each path as it exists at base. Files absent at base score zero."""
    staged = []
    for path in paths:
        blob = subprocess.run(["git", "show", f"{base}:{path}"], capture_output=True, text=True)
        if blob.returncode != 0:
            continue  # new article: baseline is an empty, error-free file
        target = os.path.join(workdir, path)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(blob.stdout)
        staged.append(path)
    return run_lint(staged, cwd=workdir), set(staged)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--base", default="origin/main", help="revision to compare against")
    parser.add_argument("--changed", action="store_true", help="derive the file list from git")
    args = parser.parse_args()

    if shutil.which("npx") is None:
        print("[!] npx not found; cannot run markdownlint.", file=sys.stderr)
        return 1

    paths = changed_articles(args.base) if args.changed else sorted(p for p in args.paths if p.endswith(".md"))
    if not paths:
        print("[-] No changed articles to lint.")
        return 0

    print(f"[-] Linting {len(paths)} changed article(s) against {args.base}.")
    current = run_lint(paths)

    with tempfile.TemporaryDirectory() as workdir:
        base, existed = baseline_counts(args.base, paths, workdir)

    new_files = [p for p in paths if p not in existed]
    if new_files:
        print(f"[-] {len(new_files)} new article(s) must be lint clean: {', '.join(new_files)}")

    rules = sorted(set(current) | set(base))
    regressions = {rule: (base[rule], current[rule]) for rule in rules if current[rule] > base[rule]}

    total_base, total_current = sum(base.values()), sum(current.values())
    print(f"[-] markdownlint errors: {total_base} at base -> {total_current} now.")
    for rule in rules:
        if current[rule] != base[rule]:
            arrow = "+" if current[rule] > base[rule] else "-"
            print(f"    {arrow} {rule}: {base[rule]} -> {current[rule]}")

    if regressions:
        print("\n[!] This change adds markdownlint errors. Full output:\n")
        cmd = list(LINT_CMD) + (["--config", CONFIG] if os.path.exists(CONFIG) else []) + paths
        subprocess.run(cmd)
        return 1

    if total_current < total_base:
        print("[+] Net improvement. Nice.")
    else:
        print("[+] No new markdownlint errors.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
