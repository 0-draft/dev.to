---
title: I Built an OPA Plugin That Turns It Into an AuthZEN-Compatible PDP
published: true
description: 'Building an OPA plugin that implements the AuthZEN Authorization API 1.0. How the OPA community discussion led to a plugin approach, and the design decisions behind it.'
tags:
  - showdev
  - opa
  - authorization
  - go
series: Authorization
id: 3441756
cover_image: "https://raw.githubusercontent.com/kanywst/dev.to.kanywst/refs/heads/main/articles/assets/opa-authzen-plugin/cover.png"
---

# Introduction

In my [previous article](https://dev.to/kanywst/authzen-authorization-api-10-deep-dive-the-standard-api-that-separates-authorization-decisions-1m2a), I did a deep dive into the AuthZEN Authorization API 1.0 spec. It standardizes communication between PEPs and PDPs. You send a JSON request asking "can this subject do this action on this resource?" and get back `{"decision": true/false}`.

So the spec makes sense. But how do you actually use OPA as an AuthZEN-compatible PDP?

OPA already has a REST API (`POST /v1/data/...`), but it doesn't match the AuthZEN API.

- Different path: AuthZEN uses `POST /access/v1/evaluation`
- Different request structure: OPA requires wrapping in `{"input": {...}}`
- Different response structure: OPA returns `{"result": ...}`

There's an [authzen-proxy](https://github.com/open-policy-agent/contrib/tree/main/authzen) in contrib, a Node.js proxy, but it requires a separate process.

So I built a plugin that runs the AuthZEN API directly inside the OPA process using OPA's plugin mechanism.

**Repo**: [github.com/kanywst/opa-authzen-plugin](https://github.com/kanywst/opa-authzen-plugin)

---

## The OPA Community Discussion

Before getting into the code, some context on why this ended up as a plugin.

I opened an issue ([#8449](https://github.com/open-policy-agent/opa/issues/8449)) on the OPA repository and brought it up in the `#contributors` Slack channel.

### The Initial Proposal: Route Aliases

```yaml
server:
  route_aliases:
    /access/v1/evaluation: /v1/data/authzen/allow
```

The idea was to add configurable path mapping to the OPA server. I also put up a PR ([#8451](https://github.com/open-policy-agent/opa/pull/8451)).

But path mapping alone can't handle request/response transformation, so it wouldn't fully satisfy the AuthZEN spec.

### What the Community Said

The conclusion was:

1. **Not in OPA core.** OPA is a general-purpose policy engine used beyond just authorization. Adding use-case-specific features increases the surface area.
2. **Plugin / distribution is the right approach.** Same pattern as opa-envoy-plugin. Single binary, OPA + AuthZEN server.
3. **Evaluation API is enough.** The only REQUIRED endpoint in the well-known metadata is `access_evaluation_endpoint`. Evaluations (batch) and Search APIs are all OPTIONAL.

Nobody was against AuthZEN support itself. The stance was: start as a plugin, and if demand grows, it can move closer to core later.

There aren't many production AuthZEN users yet, so adding it to core didn't have strong justification at this point.

---

## Architecture

Just like opa-envoy-plugin bundles OPA + Envoy External Authorization (gRPC) into a single binary, opa-authzen-plugin bundles OPA + an AuthZEN HTTP server into one.

![Architecture](./assets/opa-authzen-plugin/architecture.png)

Key points:

- The AuthZEN request body (`subject`, `resource`, `action`, `context`) becomes OPA's `input` as-is. No wrapping needed.
- The plugin evaluates `data.<path>.<decision>` (default: `data.authzen.allow`) and returns the bool result as `{"decision": ...}`.
- OPA's REST API (`:8181`) still works. Bundles, decision logs, and all other OPA features are available.

![opa authzen plugin](./assets/opa-authzen-plugin/opa-authzen-plugin.png)

---

## OPA's Plugin Mechanism

OPA lets you register plugins at runtime. Call `runtime.RegisterPlugin` with a Factory, and OPA will instantiate and start your plugin based on the config file.

![OPA Plugin](./assets/opa-authzen-plugin/opa-plugin.png)

The entrypoint is just this:

```go
func main() {
    runtime.RegisterPlugin(plugin.PluginName, plugin.Factory{})

    if err := cmd.RootCommand.Execute(); err != nil {
        os.Exit(1)
    }
}
```

opa-envoy-plugin uses the exact same pattern. `runtime.RegisterPlugin` to register a gRPC server plugin.

---

## How AuthZEN Requests Reach OPA

An AuthZEN Access Evaluation API request looks like this:

```json
{
  "subject": {"type": "user", "id": "alice", "properties": {"role": "admin"}},
  "resource": {"type": "document", "id": "doc-123"},
  "action": {"name": "delete"},
  "context": {"time": "2026-04-01T12:00:00Z"}
}
```

The plugin passes this body directly as OPA's `input`. In Rego, you reference it like:

```rego
package authzen

default allow = false

allow if input.subject.properties.role == "admin"

allow if {
    input.action.name == "read"
    input.subject.id != ""
}
```

With OPA's Data API, you'd need to wrap it as `{"input": {...}}` and `POST /v1/data/authzen/allow`. The plugin handles that conversion internally.

Same for the response. OPA returns `{"result": true}`, and the plugin converts it to `{"decision": true}`.

![Request Reach OPA](./assets/opa-authzen-plugin/request-reach-opa.png)

---

## Policy Dispatch

AuthZEN uses a single endpoint (`/access/v1/evaluation`) for all authorization decisions. If you want to route to different policies per resource type or action, you do that in Rego by checking `input.resource.type` or `input.action.name`.

```rego
package authzen

default allow = false

# anyone can read todolists
allow if {
    input.resource.type == "todolist"
    input.action.name == "read"
}

# only editors can create todolists
allow if {
    input.resource.type == "todolist"
    input.action.name == "create"
    input.subject.properties.role == "editor"
}

# only admins can manage accounts
allow if {
    input.resource.type == "account"
    input.action.name == "manage"
    input.subject.properties.role == "admin"
}
```

As mentioned in the community discussion, PDP-specific hints (like which policy to evaluate) can also be passed via the `context` object:

```json
{
  "subject": {"type": "user", "id": "alice"},
  "action": {"name": "read"},
  "resource": {"type": "todolist", "id": "1"},
  "context": {"policy_hint": "todolist"}
}
```

---

## Well-Known Metadata

The PDP metadata endpoint defined in Section 9 of the spec. PEPs can use it to dynamically discover which endpoints are available.

```bash
$ curl -s http://localhost:9292/.well-known/authzen-configuration | jq .
{
  "policy_decision_point": "http://localhost:9292",
  "access_evaluation_endpoint": "http://localhost:9292/access/v1/evaluation"
}
```

OPTIONAL endpoints (`access_evaluations_endpoint`, `search_*`) aren't returned since they're not implemented. Per the spec, parameters with no value MUST be omitted.

---

## Try It Out

### Build and Run

```bash
git clone https://github.com/kanywst/opa-authzen-plugin.git
cd opa-authzen-plugin
make build
./opa-authzen-plugin run --server \
  --config-file example/config.yaml \
  example/policy.rego
```

Also works with Docker:

```bash
make docker-build
make docker-run
```

### Send Requests

Admin user deleting a document (allowed):

```bash
$ curl -s -X POST http://localhost:9292/access/v1/evaluation \
  -H "Content-Type: application/json" \
  -d '{
    "subject": {"type": "user", "id": "alice", "properties": {"role": "admin"}},
    "resource": {"type": "document", "id": "doc-123"},
    "action": {"name": "delete"}
  }'
{"decision":true}
```

Regular user deleting a document (denied):

```bash
$ curl -s -X POST http://localhost:9292/access/v1/evaluation \
  -H "Content-Type: application/json" \
  -d '{
    "subject": {"type": "user", "id": "bob", "properties": {"role": "viewer"}},
    "resource": {"type": "document", "id": "doc-123"},
    "action": {"name": "delete"}
  }'
{"decision":false}
```

The `X-Request-ID` header is echoed back in the response (Section 10.1.3):

```bash
$ curl -si -X POST http://localhost:9292/access/v1/evaluation \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: req-abc-123" \
  -d '{
    "subject": {"type": "user", "id": "alice", "properties": {"role": "admin"}},
    "resource": {"type": "document", "id": "1"},
    "action": {"name": "read"}
  }'
HTTP/1.1 200 OK
Content-Type: application/json
X-Request-Id: req-abc-123

{"decision":true}
```

---

## What's Next

This is a PoC with just the Evaluation API.

- **Evaluations API (batch)**: OPTIONAL, but there's demand. Topaz has 1000+ edge users asking for it.
- **Search APIs**: Hard to implement generically on top of OPA (ABAC). Partial evaluation might work, but nobody has explored that yet.
- **gRPC**: There's interest in having gRPC alongside REST, but REST comes first.

Depending on how the OPA community responds, this could move to contrib or be integrated with opa-envoy-plugin.

---

## Links

- **Repo**: [github.com/kanywst/opa-authzen-plugin](https://github.com/kanywst/opa-authzen-plugin)
- **OPA Issue**: [open-policy-agent/opa#8449](https://github.com/open-policy-agent/opa/issues/8449)
- **AuthZEN Spec**: [openid.net/specs/authorization-api-1_0.html](https://openid.net/specs/authorization-api-1_0.html)
- **Previous Article (AuthZEN Deep Dive)**: [dev.to/kanywst/authzen-authorization-api-10-deep-dive](https://dev.to/kanywst/authzen-authorization-api-10-deep-dive-the-standard-api-that-separates-authorization-decisions-1m2a)
