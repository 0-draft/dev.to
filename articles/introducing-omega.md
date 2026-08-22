---
title: 'Introducing Omega: SPIFFE Workload Identity + AuthZEN Authorization in a Single Binary'
published: true
description: Omega is a v0 control plane that ships SPIFFE-compatible workload identity and an OpenID AuthZEN 1.0 PDP (Cedar) in one Apache-2.0 binary.
tags:
  - spiffe
  - authzen
  - security
  - opensource
series: ShowDev
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/introducing-omega/cover.png'
id: 3596636
date: '2026-05-01T15:22:55Z'
---

Standing up workload identity in a real cluster usually means running
four projects: SPIRE for SVID issuance, OPA or Cedar for authorization,
an OIDC provider for federation, and a separate audit pipeline.

The standards finally caught up. OpenID AuthZEN Authorization API 1.0
was [approved as a Final Specification on 2026-01-12](https://openid.net/authorization-api-1-0-final-specification-approved/).
Cedar [joined CNCF Sandbox on 2025-10-08](https://aws.amazon.com/blogs/opensource/cedar-joins-cncf-as-a-sandbox-project/)
and is in production at Cloudflare, MongoDB, StrongDM, and AWS Bedrock
AgentCore. SPIFFE is the de-facto workload identity model.

[Omega](https://github.com/kanywst/omega) is my attempt at wiring those
pieces into one Apache-2.0 binary.

## A few terms first

If any of these are unfamiliar, the rest of the article assumes them.

| Term             | One-line definition                                                                 |
| ---------------- | ----------------------------------------------------------------------------------- |
| **SPIFFE**       | A spec for workload identity. Defines `spiffe://trust-domain/path` IDs.             |
| **SVID**         | SPIFFE Verifiable Identity Document. Either an X.509 cert or a JWT.                 |
| **Workload API** | A local gRPC endpoint a workload calls to fetch its current SVID.                   |
| **PDP / PEP**    | Policy Decision Point answers "allow?". Policy Enforcement Point asks the question. |
| **AuthZEN**      | An OpenID spec for the HTTP+JSON wire format between a PEP and a PDP.               |
| **Cedar**        | A small, analyzable policy language from AWS, now CNCF Sandbox.                     |

## What Omega is

One binary with three subcommands:

- `omega server` runs the control plane: a CA that issues SPIFFE
  X.509-SVIDs and JWT-SVIDs, an AuthZEN 1.0 PDP backed by Cedar, an
  audit log, and SPIFFE federation.
- `omega agent` runs the SPIFFE Workload API on a Unix domain socket
  and attests workloads by their UID via `peercred`.
- `omega <CRUD>` is the CLI for domains, policies, and SVIDs.

## What ships today

Repo: <https://github.com/kanywst/omega>. Items marked `tracked` are
GitHub issues, not features in the source tree.

| Layer                   | Status      |
| ----------------------- | ----------- |
| SPIFFE X.509-SVID       | implemented |
| SPIFFE JWT-SVID (JWKS)  | implemented |
| AuthZEN 1.0 PDP (Cedar) | implemented |
| SPIFFE federation       | implemented |
| Tamper-evident audit    | implemented |
| Postgres backend (HA)   | implemented |
| Kubernetes operator     | implemented |
| cert-manager Issuer     | implemented |
| Observability           | implemented |
| Admin UI                | implemented |
| AI agent delegation     | example     |
| OIDC IdP federation hub | tracked     |
| CSI driver              | tracked     |
| PQC (ML-DSA / ML-KEM)   | tracked     |

## 60-second hands-on

```bash
git clone https://github.com/kanywst/omega
cd omega
make docker-up
```

That brings up the control plane on `:8080`, two node agents (giving
the same UID two distinct SPIFFE IDs over separate sockets), the
`hello-svid` server and client (which mTLS-handshakes and prints the
verified peer SPIFFE ID), and the admin dashboard on `:3000`.

Hit the AuthZEN endpoint:

```bash
curl -sS -X POST http://127.0.0.1:8080/access/v1/evaluation \
  -H 'Content-Type: application/json' \
  -d '{"subject":{"type":"Spiffe","id":"spiffe://omega.local/example/web"},
       "action":{"name":"GET"},
       "resource":{"type":"HttpPath","id":"/api/foo"}}'
# {"decision":false}
```

Drop a Cedar policy in `policies/` and pass `--policy-dir policies` to
the server:

```cedar
permit (
  principal == Spiffe::"spiffe://omega.local/example/web",
  action    == Action::"GET",
  resource  == HttpPath::"/api/foo"
);
```

Re-run the curl and the response flips to
`{"decision":true,"reasons":["policy0"]}`. Tear it down with `make
docker-down`.

## How the audit log stays tamper-evident

Every write goes through one append path that computes a row hash from
the previous row's hash plus this row's content
(`internal/server/storage/audit.go`):

```go
// hash = sha256(seq | ts_nano | kind | actor | subject | decision | payload | prev_hash)
h := sha256.New()
fmt.Fprintf(h, "%d|%d|%s|%s|%s|%s|", ev.Seq, ev.Ts.UnixNano(),
    ev.Kind, ev.Actor, ev.Subject, ev.Decision)
h.Write([]byte(ev.Payload))
h.Write([]byte("|"))
h.Write([]byte(ev.PrevHash))
```

`AppendAudit` is serialized through a single mutex so the
`prev_hash` lookup and the INSERT cannot interleave. A `Verify` walk
re-computes every row and reports the first mismatched `seq`, so any
deletion or in-place edit shows up the next time you scan.

## AI agent delegation example

The `examples/mcp-a2a-delegation/` directory shows how a human, a
coordinator agent, and a sub-agent chain through Omega. Each hop calls
`POST /v1/token/exchange`, which mints a new JWT-SVID whose `act` claim
is the previous token's subject. After two hops the leaf token looks
like:

```json
{
  "sub": "spiffe://omega.local/agents/claude-code/github-tool",
  "act": {
    "sub": "spiffe://omega.local/agents/claude-code",
    "act": {
      "sub": "spiffe://omega.local/humans/alice"
    }
  }
}
```

The tool-server verifies the leaf with the omega JWKS, checks the
audience, and walks the `act` chain. With
`--enforce-token-exchange-policy` the Cedar policy gets the final say
on whether each exchange is allowed, and every decision lands in the
audit log.

This is a reference example today, not an in-tree library.

## What comes next

Three things have to land before the project moves off `v0.0.x`:

1. `OmegaIdentity` CRD plus operator-to-control-plane mTLS.
2. SPIFFE federation bundle authenticity (peer mTLS plus first-time pin) and JWKS federation.
3. An OIDC IdP federation adapter, AWS first.

PQC (ML-DSA / ML-KEM) and a CSI driver are deliberately later. CRL and
OCSP are not on the list at all; short-lived SVIDs plus rotation is
the revocation story. Detailed non-goals (secrets storage, end-user
login UI, service-mesh data plane, SIEM, agent runtime) live in
[`docs/non-goals.md`](https://github.com/kanywst/omega/blob/main/docs/non-goals.md).

## Try it

If you have spent an evening stitching SPIRE to OPA to Keycloak to
Loki, please clone it, run `make docker-up`, and tell me where it
breaks.

- Repo: <https://github.com/kanywst/omega>
- Issues: <https://github.com/kanywst/omega/issues>
