---
title: 'mcp-opa-authz: Authorization Answers for Coding Agents, from the Policy Instead of a Guess'
published: true
description: 'An MCP server that evaluates Rego in-process through OPA, or asks an AuthZEN 1.0 PDP. It keeps undefined apart from false and a broken PDP apart from a deny, and it compiles http.send out of model-written policies.'
tags:
  - showdev
  - mcp
  - opa
  - authorization
series: ShowDev
id: 5038054
date: '2026-11-14T21:50:27Z'
---

Paste a Rego policy into a chat, ask whether bob may delete `doc-1`, and the model reads the policy and answers. The answer sounds right and nothing checked it. If the decision really comes from a PDP in production, the model can't see it at all.

I wanted the agent to stop reading policies and start running them. mcp-opa-authz is an MCP server with five tools: one evaluates Rego in-process with OPA, four talk to an [OpenID AuthZEN 1.0](https://dev.to/kanywst/authzen-authorization-api-10-deep-dive-the-standard-api-that-separates-authorization-decisions-1m2a) PDP.

- Source: <https://github.com/kanywst/mcp-opa-authz>
- Install: `brew install kanywst/tap/mcp-opa-authz` or `go install github.com/kanywst/mcp-opa-authz@latest`, then `claude mcp add opa-authz -- mcp-opa-authz`

| Tool | Answers |
| --- | --- |
| `evaluate_policy` | What does this Rego say? Runs in-process. |
| `authzen_evaluate` | What does the PDP that governs the system say? |
| `authzen_evaluate_batch` | The same, for a list of requests. |
| `authzen_search` | Who may, which resources, what actions (AuthZEN Search APIs). |
| `authzen_discover` | Which endpoints does this PDP advertise? |

`evaluate_policy` needs nothing external. The rest need `AUTHZEN_PDP_URL`. A local [opa-authzen-plugin](https://dev.to/kanywst/i-built-an-opa-plugin-that-turns-it-into-an-authzen-compatible-pdp-i81) on `:8181` works as that PDP.

## Why not just give the agent `opa eval`

It can already run `opa eval` through a shell tool. Here is what it gets back for a policy with no `default` and a user who isn't in `roles`:

```rego
package rbac

roles := {"alice": {"editor"}}

allow if {
	some role in roles[input.user]
	role == "editor"
}
```

```text
$ opa eval -d rbac.rego -i in.json 'data.rbac.allow'
{}
```

Exit 0, empty object. A model reads that as a deny. It isn't one: the policy has no opinion. The same query through `evaluate_policy`:

```text
{
  "defined": false,
  "value": null,
  "result_set": null
}
```

Add `default allow := false` and it becomes `"defined": true, "value": false`. Those are two different bugs to fix, and now they look different.

`trace: true` returns OPA's pretty trace, capped at 200 lines, which is usually enough to see where it stopped:

```text
"policy.rego:6     | | Unify \"bob\" = __local3__",
"policy.rego:6     | | Eval role = data.rbac.roles[__local3__][__local0__]",
...
"policy.rego:6     | | Fail role = data.rbac.roles[__local3__][__local0__]",
"query:1           | Fail data.rbac.allow = _"
```

## A PDP that didn't answer is not a deny

AuthZEN makes `decision` required. Decode a response that lacks it into a Go `bool` and you get `false`, so a broken PDP looks like a strict one. The response type here uses `*bool`, and a missing member is an error. I pointed it at a fake PDP that returns `{"context":{"error":"policy not loaded"}}`:

```text
isError: true
PDP response has no `decision` member, which AuthZEN 1.0 requires. Treating this as a failure rather than a deny; endpoint http://127.0.0.1:18282/broken/access/v1/evaluation, request id 6f96e760d517a5c25b7154e52dfe09c0.
```

A 401 gets the same treatment, because it means the MCP server failed to authenticate, not that bob was denied:

```text
isError: true
PDP returned HTTP 401: {"error":"unauthorized"}

note: 401 means this MCP server failed to authenticate to the PDP, not that the subject was denied. Check AUTHZEN_PDP_TOKEN.
```

A real answer carries the `request_id` it sent as `X-Request-ID`, so a decision in a transcript can be found in the PDP's logs:

```text
{
  "decision": false,
  "context": {
    "reason": "no role binding"
  },
  "pdp_url": "http://127.0.0.1:18282/access/v1/evaluation",
  "request_id": "bf0c8da21620a59ad4aa3dfb41721c4d"
}
```

Batch results carry an `index`. With `permit_on_first_permit` the PDP may stop early and return fewer decisions than you sent, and zipping the arrays would pin a decision on the wrong resource. Three requests, a PDP that stops after the second:

```text
{
  "decisions": [
    {
      "index": 0,
      "decision": false
    },
    {
      "index": 1,
      "decision": true
    }
  ],
  "evaluations_semantic": "permit_on_first_permit",
  "truncated": true,
  "pdp_url": "http://127.0.0.1:18283/access/v1/evaluations",
  "request_id": "59abef1b8b9d3ecf07560c9b454066f7",
  "endpoint_source": "pdp_url"
}
```

## The policy is model-written, so it runs sandboxed

The Rego handed to `evaluate_policy` was written by a model, maybe from text it read on a web page, and it runs inside the server process on your laptop. Three built-ins are removed from the OPA capability set: `http.send` (SSRF from wherever the server runs), `net.lookup_ip_addr` (enough to leak `input` one DNS label at a time) and `opa.runtime` (the process environment). Because they are gone at compile time, a policy that uses one fails before it evaluates:

```text
isError: true
rego compile error: bundle activation failed: 1 error occurred: policy.rego:3: rego_type_error: undefined function http.send

note: http.send is disabled in this sandbox because a policy evaluated here is model-supplied and runs inside the MCP server process. Set MCP_OPA_ALLOW_NETWORK_BUILTINS=true to re-enable it, understanding that the policy can then reach the network from wherever this server runs.
```

Time, JWT, UUID and random built-ins stay, since real policies use them. On the PDP side, `pdp_url` has to be an absolute `http(s)` URL without userinfo, redirects are refused rather than followed with the token attached, and endpoints advertised in PDP metadata must stay on the PDP's own origin.

## Checking it

`make smoke` builds the binary, starts a fake PDP, and drives one real stdio MCP session through all five tools:

```text
✓ smoke: tools/list advertises all five tools
✓ smoke: evaluate_policy value=true, defined, print() captured
✓ smoke: http.send rejected inside evaluate_policy
✓ smoke: authzen_evaluate decision=true, correlated by request id
✓ smoke: authzen_evaluate_batch returned 2 aligned decisions from the advertised endpoint
✓ smoke: authzen_discover resolved http://127.0.0.1:18181/access/v1/evaluation
✓ smoke: authzen_search listed 2 permitted resources from the advertised endpoint
✓ smoke: all checks passed
```

Every output above came from a binary built from `main` with OPA v1.22.2 compiled in. Releases ship a cosign-signed checksum file and a CycloneDX SBOM per archive, and there is a container at `ghcr.io/kanywst/mcp-opa-authz`.

The AuthZEN working group's COAZ profile covers the other half: a gateway authorizing `tools/call` itself. This server is for the agent that needs to ask. If you run it against a PDP I haven't tried, an issue saying what broke is the most useful thing you can send.
