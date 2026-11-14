#!/usr/bin/env bash
# Reproduces the hands-on section of wimse-workload-creds-03.md.
# Needs python3 with the `cryptography` package (pip install cryptography).
set -euo pipefail
cd "$(dirname "$0")"

# The example WIT is Figure 2 of draft-ietf-wimse-workload-creds-03,
# taken from includes/wit.txt at tag draft-ietf-wimse-workload-creds-03 of
# github.com/ietf-wg-wimse/draft-ietf-wimse-s2s-protocol.
cut -d. -f2 spec-example-wit.txt | python3 -c 'import base64,sys,json;s=sys.stdin.read().strip();print(json.dumps(json.loads(base64.urlsafe_b64decode(s+"="*(-len(s)%4))),indent=2))'

python3 -I validate_wit.py
