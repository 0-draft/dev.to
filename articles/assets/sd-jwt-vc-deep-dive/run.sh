#!/usr/bin/env bash
# Reproduces every result in articles/sd-jwt-vc-deep-dive.md.
# Needs python3 (3.10+) and the `cryptography` package. No network access.
set -euo pipefail
cd "$(dirname "$0")"
if ! python3 -c 'import cryptography' 2>/dev/null; then
  python3 -m venv "${TMPDIR:-/tmp}/sdjwtvc-venv"
  "${TMPDIR:-/tmp}/sdjwtvc-venv/bin/pip" install -q 'cryptography>=42'
  exec "${TMPDIR:-/tmp}/sdjwtvc-venv/bin/python" -I sdjwtvc.py
fi
python3 -I sdjwtvc.py
