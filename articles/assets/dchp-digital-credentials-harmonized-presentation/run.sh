#!/usr/bin/env bash
# Reproduces the hands-on section: encodes a DCHP request (openid/dchp @ 4ddd238),
# both ChannelBinding numberings, and the response envelope before and after PR #77.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
venv="${TMPDIR:-/tmp}/dchp-venv"
python3 -m venv "$venv"
"$venv/bin/pip" install -q cbor2==6.3.0
"$venv/bin/python" -I -B "$here/dchp_demo.py"
"$venv/bin/python" -I -B "$here/check_encoding.py" "$here/dchp_demo.py"
