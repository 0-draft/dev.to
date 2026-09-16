---
title: 'Mandatum: Making an AI Agent''s Authority a Chain You Can Verify'
published: true
description: 'Agents inherit credentials, so you cannot say who is responsible, cannot revoke one agent, and cannot constrain a sequence of calls. I built a Go library that turns an agent''s authority into a signed chain rooted in a named human.'
tags:
  - showdev
  - go
  - security
  - authorization
series: Authorization
id: 4667299
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/mandatum-verifiable-delegation/cover.png'
---

## Introduction

Almost every AI agent acting for a person does it by inheriting a credential: a service account, an API key, a shared token, the user's own session.

Three things break the moment you do that. Two surveys put a rough number on the first of them: 28% of organizations can reliably trace agent actions to a human or system across all environments (Cloud Security Alliance and Strata Identity, *Securing Autonomous AI Agents*, February 2026; n=285), and 68% cannot clearly distinguish AI agent activity from human activity (Cloud Security Alliance and Aembit, *Identity and Access Gaps in the Age of Autonomous AI*, March 2026; n=228). Both are vendor-commissioned and self-reported, and neither says "human sponsor" — the first says "human or system".

So I built `mandatum`.

Repo: [https://github.com/kanywst/mandatum](https://github.com/kanywst/mandatum)

---

## The three things

**You cannot say who is responsible.** The audit log has a service account in it. Which human was that?

**You cannot revoke one agent.** Everything shares the credential, so cutting off the misbehaving agent cuts off everything else. Nobody pulls that lever, so the agent keeps its access.

**You cannot constrain a sequence.** Authorization is decided one call at a time. An agent reads untrusted external content, then writes to an internal system. Both calls are legitimately authorized. The pair is the exfiltration.

MCP's authorization specification covers the transport: how a client gets a token for a server. It says nothing about which tool that token may call, which agent holds it, or who delegated to whom, and MCP's authorization interest group has open work on per-tool scopes and on consent across chains of agents. The Enterprise-Managed Authorization extension, stable since June 2026, gets an access token from an enterprise identity assertion, so what it produces is scoped to a server rather than to a call.

---

## What mandatum does

An agent's authority becomes a signed chain rooted in a named human.

![Delegation, then enforcement](./assets/mandatum-verifiable-delegation/diagrams/01-delegation-and-enforcement.png?v=f1355ef4)

Each link commits to its parent by hash, so links are not interchangeable. Capabilities can only narrow going down. The human at the root is carried unchanged to every leaf, so attribution survives arbitrary sub-delegation. Revoke any link and everything below it dies with it. Nothing else does.

The library never decides authorization itself. It establishes that an agent holds authority a human delegated, then hands that to an OpenID AuthZEN PDP (OPA, Cedar, OpenFGA, whatever you already run). The request follows the AuthZEN COAZ-MCP binding's default mapping rather than a parallel one I invented — so far for `tools/call` only, without the binding's declared mappings or CEL, and with additions of my own that the [conformance document](https://github.com/kanywst/mandatum/blob/main/docs/spec/coaz-mcp-conformance.md) lists as divergences.

---

## The sequence part

The bottom block of that diagram is the bit I actually wanted to build, because per-call authorization structurally cannot do it:

```bash
go test -run Example ./pkg/sequence/ -v
```

```text
write first:       allowed
read external:     allowed
write after read:  denied by no-write-after-external-read
sub-agent writes:  denied by no-write-after-external-read
```

The last line matters. State is keyed by the chain root, not by whoever is acting, so an agent cannot escape an inherited constraint by delegating to a sub-agent it just minted.

A constraint compiles to one bit (has the trigger fired) plus a counter. The state a chain accumulates is fixed-size however long it runs.

---

## Three places I'd actually use it

**A coding agent that can open pull requests.** It reads a dependency's README, an issue comment, a diff from a fork: all attacker-writable. Then it pushes. Tag the reads `external-content` and the push `mutating`, and the second one stops after the first.

```json
{ "id": "no-push-after-third-party-read",
  "forbid": { "resource.tags": ["mutating"] },
  "after":  { "resource.tags": ["external-content"] } }
```

**A support agent that can issue credits.** The customer's message is attacker-controlled text, and the refund tool moves money. Same shape, and the sponsor is the support engineer who approved the session, so the audit record names a person rather than `svc-support-bot`.

**A research agent someone left running.** `max_invocations` on the sponsor's grant caps the whole chain, and because state is keyed by the root, spawning ten sub-agents spends the same budget rather than ten of them.

None of these need a new policy engine. They need the tool call to know what happened earlier under the same authority.

---

## What isn't built

There is no audit log yet. The sequence store is in-process only, which means one enforcement point. Two PEPs with separate memories give an agent two histories to spend. Nothing has had a third-party security review.

All of that is in the [threat model](https://github.com/kanywst/mandatum/blob/main/docs/security/threat-model.md), which lists what is not covered rather than only what is.

---

## Where I'd like to be wrong

The design leans on a chain rather than a flat list of prior actors. A list answers "who was upstream". A chain also answers "did any hop widen its authority", but that is a lot of machinery, and if the first question turns out to be enough, most of it isn't earning its place.

Where a chain belongs in an AuthZEN request is open too. The binding carries the acting client in `context.agent` and says nothing about the hops above it: it does not rule a chain out of that field and it does not name a place for one, so mandatum keeps the hops under a vendor-prefixed key rather than taking a name inside the binding's namespace. That question is live in [openid/authzen#612](https://github.com/openid/authzen/issues/612), a thread on whether `context.agent` should be trust-anchored when it comes from the validated token — and where the working group corrected an earlier reading of mine. If you have run agent systems in production and think the chain is overkill, I'd rather hear it now.

The [specification](https://github.com/kanywst/mandatum/blob/main/docs/spec/delegation-assertion.md) has an open-questions section that is genuinely open.
