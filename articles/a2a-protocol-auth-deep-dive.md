---
title: 'A2A Protocol Auth, Taken Apart: Why the Spec Is Thin and Where That Leaves Holes'
published: true
description: 'A primary-source read of authentication and authorization in the Agent2Agent (A2A) protocol, built by Google and now stewarded by the Linux Foundation. A2A advertises auth requirements in the Agent Card and hands token issuance and validation off to OAuth2 / OIDC / mTLS. It only defines the frame. This walks through why it was built that way, where the holes are, and how signed Agent Cards plus mTLS close them.'
tags:
  - ai
  - agents
  - security
  - oauth
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/a2a-protocol-auth-deep-dive/cover.png'
id: 3892021
date: '2026-06-13T14:26:48Z'
series: AI Agent Identity
---

## How this started: I opened the auth section and it was nearly empty

A2A (Agent2Agent) keeps showing up as the protocol for letting AI agents talk to each other. Google announced it in April 2025, and the Linux Foundation runs it now.

"If one agent calls another, there has to be authn and authz in there," I figured, and opened the auth section of the spec. It was an anticlimax. There is no new authentication mechanism defined anywhere. What it says is: "use OAuth2 or OpenID Connect or mTLS," "send credentials in HTTP headers," "advertise your requirements in the Agent Card." That is it.

My first reaction was "is this just lazy?" But the more I read, the clearer it got that the thinness is intentional. A2A defines only the **frame** for authn and authz and delegates the contents to existing standards. The catch is that the way it delegates creates holes.

Everything I have written before about AI agent auth (WIMSE, SPIFFE, ID-JAG, Identity Chaining, Transaction Tokens) shows up here as A2A's "delegation target."

## Background: just three players to remember

Before the auth details, the minimum cast. A2A is a protocol for one agent to hand a task to another agent. The transport is JSON-RPC over HTTP (there are gRPC and HTTP+JSON bindings too).

| Player | Role |
| --- | --- |
| Client Agent (caller) | The agent handing off a task. The source of the HTTP request |
| Remote Agent / A2A Server (callee) | The agent that receives and works the task. Acts as an HTTP server |
| Agent Card (business card) | JSON where the Remote Agent publishes its capabilities and "auth requirements." Lives at `/.well-known/agent-card.json` |

The Agent Card is the one to internalize. "What credential do I need to call this agent?" is written entirely on this card. The Client reads the card first, sets up the right auth, then sends the real request.

![A2A players and where auth happens](./assets/a2a-protocol-auth-deep-dive/diagrams/01-players-overview.png)

The core of A2A auth is already in this picture. **Tokens are issued outside A2A (by an external IdP)**, and A2A itself only "states requirements in the card" and "receives credentials in headers."

## When is it actually A2A: the difference from a plain API call

Before the auth internals, let's pin down what is A2A and what is not. Read on with these confused and the later design decisions float in midair. Here are the three things that get lumped together.

| What you call | What you pass | What it is called | A2A? |
| --- | --- | --- | --- |
| An LLM (an inference API) | a prompt | just a model API | No. The other side is not an agent |
| A tool / data (DB, external API, files) | a function call | MCP territory (agent to tool) | No |
| Another autonomous agent | a **task** | A2A (agent to agent) | Yes |

Calling an LLM directly is "make the model think." The other side is not an agent. MCP is "use your own hands and feet (tools)," where the other side is subordinate. Only A2A is "**hand work to someone else's agent**."

### What is different from a plain API call

To be honest, A2A is mechanically nothing more than HTTP + JSON-RPC. Nothing magic beyond "a service calls a service" happens. What differs is not the wiring but **who the other side is and how you ask**. The same job, "is this expense (EUR 420, client entertainment) within policy, and convert it to USD while you're at it," looks different written two ways.

The plain-API way (you know the whole contract and wire it tightly yourself):

```text
GET  fx-api.com/rate?from=EUR&to=USD
POST policy-service/check  {amount: 420, category: "entertainment"}
```

The A2A way (you do not know the internals; you read the card at runtime and send intent):

```text
1. At runtime, read the Agent Card of the other side
   (another team's / company's "expense compliance agent")
   -> "I can do policy checks and currency conversion. Auth is Bearer token."
2. Send intent as a structured message:
   "Is this expense (EUR 420, entertainment) within policy? Also convert to USD."
3. The LLM inside that agent decides on its own which internal APIs to hit
   and how to judge, then returns a reasoned answer plus an attachment (artifact).
```

The differences are these three:

1. **You send "intent," not an exact command.** You do not spell out steps like `?from=EUR&to=USD`. You hand over a goal and the other side works out the steps (because it has an LLM).
2. **You do not know the internals / you do not pre-wire.** You do not build against the other side's API contract. You read the Agent Card at runtime to learn "what it can do and how to auth" on the spot.
3. **The other side is someone else's property.** You cannot `import` it into your code. It is another team's agent running somewhere else.

### The one reason it exists: killing the N×N wiring

If the other side is your own service, you do not need A2A. Just call the API. That can be said plainly. The one reason A2A earns its keep is **avoiding the N×N problem**.

![Plain APIs N by N wiring versus the A2A common socket](./assets/a2a-protocol-auth-deep-dive/diagrams/02-nxn-wiring.png)

When companies each have agents and want to hand work to each other, plain APIs need wiring per pair (the combinations blow up as the count grows). If everyone aligns on A2A's one card format and one calling convention, you can hand a task to an agent you have never met before, with no pre-wiring. It is like USB-C: the standard itself is not new technology, the value is that **everyone aligned on the same socket**. There is also a business angle: vendors do not want to expose raw APIs, but they will open up as an "agent."

### Reality: still pre-adoption

Honestly, as of 2026 there are still few sharp "this is the A2A use case" examples. Production adoption is past 150 organizations and shows up in supply chain, financial services, insurance, and IT operations, but the public material stops at adoption counts and verticals, and concrete workflow case studies are thin. The canonical demos are cross-vendor delegation: travel booking (a planner delegates to airline, hotel, and rental-car agents from different companies) and hiring (a manager delegates to sourcing and scheduling agents). Most "multi-agent" today is in-process sub-agents, and for that you do not need A2A. A2A pays off when "make agents across org boundaries talk" becomes real, and it is a standard betting on that.

That covers "what A2A is and when to use it." Now the real subject: authn and authz. The auth design takes the shape it does precisely because crossing boundaries is the premise.

## The design philosophy: "treat agents as ordinary apps"

A2A's auth design follows from a single principle.

> Treat agents not as something special but as **ordinary enterprise applications**.

How do ordinary web apps authenticate when they call each other's APIs? Put an OAuth token in the `Authorization: Bearer` header, put an API key in a header, present a client cert with mTLS. A2A just applies that to agents as-is. It invents nothing new.

From this principle, four concrete design decisions fall out. This is the whole shape of A2A auth. Going through them in order:

1. Don't put identity in the payload. Establish it at the HTTP transport layer.
2. Advertise auth requirements in the Agent Card.
3. Acquire credentials out-of-band (outside A2A's scope).
4. Authorization is per-skill scope based. But actual enforcement is left to external infrastructure.

### Decision 1: don't put identity in the payload

The spec says this.

> A2A protocol payloads (JSON-RPC messages) don't carry user or client identity information directly.

"Not in the payload" is easy to misread, so look at the actual HTTP request. A2A traffic is JSON-RPC carried over HTTP, and it splits like this.

```http
POST /a2a HTTP/1.1
Host: remote-agent.example.com
Authorization: Bearer eyJhbGci...     # "who is calling" (identity) goes here
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "method": "message/send",
  "params": { "message": { "text": "Summarize this PDF" } }
}
```

**The payload (the JSON-RPC body) carries only "what you want done." "Who" is carried by the `Authorization` token in the HTTP header (or the mTLS client cert).** That is what "don't put identity in the payload" means.

The contrast with the design A2A **does not** use makes it clear. If you did put identity in the payload, it would look like this.

```json
{
  "jsonrpc": "2.0",
  "method": "message/send",
  "params": {
    "callerId": "agent-A",
    "onBehalfOf": "user-123",
    "message": { "text": "Summarize this PDF" }
  }
}
```

A2A avoided this shape. There are three reasons, and they are what make it a "design decision."

1. **A "who" inside the body is nothing but self-assertion.** Anyone can write `callerId: "admin"`. The header token, on the other hand, is signed by an IdP and cannot be forged. The identity you can actually verify only rides on the header side.
2. **You can offload verification to infrastructure.** Reading the `Authorization` header is the specialty of an API Gateway / reverse proxy / IAM. It does not have to parse the body (app-specific JSON). So the A2A SDK itself never needs to know "who is calling" (it stays identity-agnostic).
3. **No double bookkeeping.** HTTP already has a place for auth (the header). Put it in the body too and you have two places that can disagree.

The "transport layer" here does not mean OSI L4 in the strict sense. It is more like "the HTTP request envelope (headers) that wraps the app message (JSON-RPC)." ID on the envelope, business in the contents.

This separation also feeds the "holes" later. If identity does not ride in the payload, the A2A message itself cannot carry the context "acting on behalf of user-123." So when you delegate in hops, A to B and B to C, the job of conveying "who the original user is" falls outside A2A (Identity Chaining / Transaction Tokens).

### Decision 2: advertise auth requirements in the Agent Card

"To call this agent you need a Bearer token (scope `read:tasks`)" or "no, we use an API key": requirements differ per agent. A2A makes you declare this in the Agent Card's `securitySchemes` and `security` fields. Read the card and you know what to bring. Details below.

### Decision 3: acquire credentials out-of-band

The spec decides how credentials are "used" but not how they are "obtained."

> Credentials for a client agent to connect to a remote agent are obtained by the client agent through an out-of-band process outside the scope of the A2A protocol.

How you get the token (run an OAuth authorization-code flow, or grab one with client credentials) is outside A2A. The agent operates on the premise that it "already has a token."

### Decision 4: per-skill scope authorization, enforced externally

An A2A agent lists its "skills" (what it can do) in the Agent Card. Authorization can be applied per skill.

> Access can be controlled on a per-skill basis ... specific OAuth scopes should grant an authenticated client access to invoke certain skills but not others.

But the implementation that "checks the scope and rejects" is not something A2A does. That too is external work (a Gateway or IAM, or the app's middleware). The A2A spec only says "do it."

## Sorting "what A2A defines" from "what it delegates"

Sort the decisions so far cleanly into "what A2A decides itself" and "what it delegates to external standards," and the essence of A2A auth shows.

![What A2A defines itself versus what it delegates](./assets/a2a-protocol-auth-deep-dive/diagrams/03-define-vs-delegate.png)

Left (green) is A2A's "frame," right (yellow) is the "delegation targets." **Understanding A2A auth is almost entirely about understanding the left frame**, and the right is the very standards covered in other articles (ID-JAG, Identity Chaining, WIMSE, and so on).

From here, take the left frame apart in order.

## Dissecting the Agent Card: 5 SecurityScheme types

Look at a real Agent Card that declares auth requirements. `securitySchemes` defines "what auth methods exist" by name, and the `security` array specifies "which methods are required." This notation is borrowed straight from OpenAPI 3.x Security Schemes.

```json
{
  "name": "Document Processing Agent",
  "description": "An agent that analyzes documents",
  "capabilities": {
    "streaming": true,
    "extendedAgentCard": true
  },
  "securitySchemes": {
    "oauth2": {
      "type": "oauth2",
      "flows": {
        "authorizationCode": {
          "authorizationUrl": "https://auth.example.com/oauth/authorize",
          "tokenUrl": "https://auth.example.com/oauth/token",
          "scopes": {
            "read:tasks": "Read task information",
            "write:tasks": "Modify tasks"
          }
        }
      }
    },
    "apiKey": {
      "type": "apiKey",
      "in": "header",
      "name": "X-API-Key"
    }
  },
  "security": [
    { "oauth2": ["read:tasks", "write:tasks"] },
    { "apiKey": [] }
  ],
  "skills": [
    { "name": "analyze-document", "description": "Analyze document content" }
  ],
  "signatures": [
    {
      "protected": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9",
      "signature": "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    }
  ]
}
```

How to read this card:

- `securitySchemes` defines two methods, `oauth2` and `apiKey`.
- The `security` array is read as **OR**. It means "come in with `oauth2` (with scopes), or come in with `apiKey`."
- `signatures` is for tamper detection on the card itself (more below).

The spec fixes SecurityScheme at **exactly 5 types**. These are the entirety of A2A's auth methods.

| type | what it is | main fields |
| --- | --- | --- |
| `apiKey` | API key | `in` (header/query/cookie), `name` |
| `http` | HTTP auth (Basic/Bearer, etc.) | `scheme` (e.g. "bearer"), `bearerFormat` |
| `oauth2` | OAuth 2.0 | `flows` (table below) |
| `openIdConnect` | OIDC discovery | `openIdConnectUrl` |
| `mtls` | mutual TLS | (no extra fields) |

The flows you can write in `oauth2`'s `flows` are also limited by the spec: the only ones defined are `authorizationCode`, `clientCredentials`, and `deviceCode`, **just these three**. OpenAPI's `implicit` and `password` are not adopted in A2A (both are discouraged flows, so it is a sensible cut). For agent-to-agent traffic (no human in the loop) you pick `clientCredentials`, and for human delegation you pick `authorizationCode`.

Worth noting: **`mtls` is in this list of 5**. Beyond OAuth tokens, certificate-based mutual auth is in the "frame" from the start. That turns out to be the key to closing holes later.

## The auth flow: read the card, then send the real request

With the cast and card understood, walk the actual auth flow end to end. A2A auth is **discovery-driven** (it starts from the card). The client first fetches the card with no auth, reads the requirements written there, then sets up auth.

![A2A discovery-driven auth flow with 401 and 403 branches](./assets/a2a-protocol-auth-deep-dive/diagrams/04-auth-flow-sequence.png)

Three points.

1. **Phase 1 needs no auth.** Anyone can read the card. So you must not write secrets in the card, and the card's authenticity has to be protected by other means (signing).
2. **Phase 2 is outside A2A.** A2A has nothing to do with how the token is obtained. The diagram uses `client_credentials` as an example, but this is entirely the OAuth world.
3. **Credentials always go in HTTP headers.** The spec is blunt: "Credentials MUST be transmitted in standard HTTP headers." Never in the JSON-RPC body. Validation failure is `401`, insufficient permission is `403`.

## Extended Agent Card: authenticate and the card grows

A2A has a neat trick: the **Extended Agent Card**. The public card (readable by anyone) carries only the minimum, and **only authenticated clients get an "extended card" with additional skills and config**.

This helps when you want to hide even the existence of a capability. Show only base skills to the outside, and show management skills to authenticated internal agents.

![Extended Agent Card retrieval flow](./assets/a2a-protocol-auth-deep-dive/diagrams/05-extended-card-flow.png)

Spec rules:

- Usable only if the public card has `capabilities.extendedAgentCard: true`.
- The auth for fetching the extended card uses **a scheme declared in the public card's `security`**. In other words, "the key to see the extended version is told to you properly by the public version."
- A client that gets the extended card **replaces** its cached public card with it (for the duration of the authenticated session, or until the version changes).

What is interesting is that "the visible capabilities change with authentication," a form of authorization, is built into the protocol.

## Signing the Agent Card: the card itself is an attack surface

You may have noticed by now. All the auth requirements are written on the card. So **what happens if the card is tampered with**?

If an attacker rewrites the card's `tokenUrl` to their own server, the client goes to the attacker to fetch a token. Inject a prompt injection into the card's `description` and you can warp the behavior of a victim agent that reads it. The card is the root of trust, yet in Phase 1 it is handed out with no auth. That is the weak point.

For this, A2A provides **Agent Card signing**.

![Agent Card signing on the issuer side and verification on the client side](./assets/a2a-protocol-auth-deep-dive/diagrams/06-card-signing.png)

The mechanism is two stages:

1. **Canonicalize with JCS** (RFC 8785, JSON Canonicalization Scheme): the same JSON content can produce different bytes depending on key order and whitespace. Canonicalize before signing so anyone who processes it gets the same byte string. Skip this and you get the accident where the meaning is identical but signature verification fails.
2. **Sign with JWS** (RFC 7515): sign the canonicalized bytes and put `protected` (the JWS protected header) and `signature` into `signatures[]`.

But in the spec this is **MAY** (optional). It is "you may sign," not "you must sign." That becomes one of the holes discussed next.

## Where the holes are: risks born from A2A's delegation design

A2A's "define only the frame, delegate the contents" design is safe if the implementer fills it in properly, but **forget to fill it and it becomes a hole**. The parts the spec does not bind with MUST become attack surface directly. Here are the main attack surfaces and their roots (how to close them is diagrammed in the next section).

- **Card tampering / impersonation**: the signature (`signatures`) is optional, and the spec does not even mandate "how to verify the card." An implementation that trusts an unsigned card as-is gets lured to the attacker's server by a rewritten card.
- **Replay**: `Authorization: Bearer <token>` is a bearer token. Steal it and the thief acts as the legitimate client. A2A itself has no mechanism to "bind a token to a specific client."
- **Credential leak down the delegation chain**: in a chain where agent A calls B and B calls C, if A's token unintentionally flows to C, permission leaks. The spec says "credentials SHOULD be bound to the agent which originated the request," but with SHOULD, not as a mandate.
- **Scope bypass / confused deputy**: per-skill authorization is also up to the app/Gateway to enforce. Forget the "can this token call this skill" check and authentication passes while authorization sails through. And when an agent executes someone else's request with "its own strong permissions," you get a textbook confused deputy.

In short, whether A2A auth ends up safe hinges on **whether the implementer can promote the parts the spec let off with MAY / SHOULD up to MUST**.

## Closing the holes: mTLS + signed cards + existing identity standards

So how do you fill it concretely. OAuth bearer tokens alone cannot close the holes above. The combination that comes up over and over in practice is the three-piece set "mutual TLS + signed Agent Card + PKI-backed machine identity." These three supply the "proof of the sender" and "authenticity of the card" that a bearer token structurally cannot hold. Mapping this onto A2A's frame and the existing standards covered in other articles looks like this.

![Holes mapped to fixes and the delegated standards that back them](./assets/a2a-protocol-auth-deep-dive/diagrams/07-holes-fixes-standards.png)

Brought down to concrete implementation policy:

1. **Always sign the card. Do not accept an unsigned card.** Promote the spec's MAY to MUST in your own system. Put issuer verification on PKI (a trusted CA, or a SPIFFE trust domain).
2. **Use mTLS for agent-to-agent paths with no human in the loop.** A2A has the `mtls` SecurityScheme from the start. With client certs, a stolen token alone cannot impersonate. Even when using OAuth, kill bearer replay with sender-constrained tokens. This is a mechanism that binds the token to "a specific client's key or cert," so stealing only the token is useless without the matching key. The two implementation styles are mTLS binding (RFC 8705) and DPoP (RFC 9449).
3. **Leave chain propagation to standards outside A2A.** Bind the credential to the originator, and for crossing domains use ID-JAG / Identity Chaining, for safe propagation within a chain use Transaction Tokens. A2A is only the "frame" to carry these, so bring the contents in from standards.
4. **Always enforce per-skill authorization at a Gateway / IAM.** "Authentication passed" and "has permission to call that skill" are different things. Always place a layer that does not let the latter through unchecked.

This is where the "delegation targets" (the blue on the right) all connect to existing standards covered in other articles. A2A is the **plumbing (frame)** of AI agent auth, and the water flowing through it (the identity contents) is the very standards I have been writing about. That structure becomes clear.

## See it for real: turn a coding CLI into an A2A server and the holes appear

The "holes" so far may look abstract, but stand up one existing OSS project and they show up right in front of you. A Remote Agent is not a special product. It is **just an HTTP server that wraps an agent you have on hand as an A2A server**. There are several OSS projects you can actually try.

- [a2aproject/a2a-samples](https://github.com/a2aproject/a2a-samples): the official hello-world Remote Agent (5 languages). The minimal server that handles `message/send`
- [hybroai/a2a-adapter](https://github.com/hybroai/a2a-adapter): a Python SDK that converts n8n / LangGraph / CrewAI / **Claude Code** / Codex / Ollama and more into A2A servers (published on PyPI)
- [firstintent/a2a-bridge](https://github.com/firstintent/a2a-bridge): connects CLI agents like Claude Code / Codex / Gemini CLI / Zed to each other through a daemon

For example, turning Claude Code into an A2A server with `a2a-adapter` is just this.

```python
from a2a_adapter import ClaudeCodeAdapter, serve_agent

adapter = ClaudeCodeAdapter(working_dir="/path/to/project")
serve_agent(adapter)  # Claude Code comes up as an A2A server
```

This stands up a server where "throw a task over the network and Claude Code reads/writes files and runs commands and returns." The problem starts here. The `a2a-adapter` README says this.

> Without a pre-configured Claude Code permissions file, tool-use is blocked. You can bypass it with `skip_permissions=True` (or the env var `A2A_CLAUDE_SKIP_PERMISSIONS=1`).

```python
adapter = ClaudeCodeAdapter(working_dir="...", skip_permissions=True)
```

The moment you add `skip_permissions=True`, **Claude Code runs tools (file edits, command execution) without human confirmation**. And the trigger that launches it is a task coming over A2A. If you have not tightened the front-door auth (who can call this server), anyone who reaches the endpoint gets all the way to command execution. This is exactly the attack surface listed earlier in the article.

- No auth in front -> unauthenticated remote code execution
- Token only, no mTLS -> replay with a stolen token
- Per-skill scope not enforced -> "read only" turns into write and execute (confused deputy)

So the previous section's fixes (limit who can call it with mTLS / signed cards / enforce per-skill scope at a Gateway) are not slogans. They become **mandatory** the moment you ship one such adapter to production. The responsibility A2A "delegated" for auth is ultimately taken on by the human who stood up this server.

## Design-decision cheat sheet

For reference while implementing, here are A2A auth decision points on one page.

| Topic | What A2A specifies | Strength | Recommendation in practice |
| --- | --- | --- | --- |
| Where identity lives | HTTP header / transport layer. Not in the payload | design | Follow as-is. Push verification to Gateway/IAM |
| Conveying auth requirements | Agent Card `securitySchemes` / `security` | defined | Mind the OR semantics. Cut least-privilege scopes |
| Auth methods | apiKey / http / oauth2 / openIdConnect / mtls, 5 types | defined | For M2M paths use `mtls` or client_credentials |
| Credential transmission | HTTP headers required | MUST | Never in the body |
| Transport | HTTPS required in prod, TLS 1.2+ recommended | MUST/SHOULD | Use TLS 1.3, verify the server cert |
| Card signing | JWS (RFC 7515) + JCS (RFC 8785) | MAY | Promote to MUST in your own system |
| Authorization granularity | per-skill scope | SHOULD | Always enforce at Gateway/IAM |
| Binding the credential | bind to the originating agent | SHOULD | Enforce with sender-constrained tokens |
| Cross-domain propagation | unspecified (outside A2A) | none | Bring in ID-JAG / Identity Chaining |
| Replay defense | unspecified | none | Kill bearer theft with mTLS / DPoP |

Where the "Strength" column is MUST, A2A has your back. Where it is MAY / SHOULD / none, **you tighten it yourself**. A2A auth security comes down to how much of the bottom-right of this table you fill.

## Conclusion

A2A auth is "thin." But that is not laziness. It is the result of a clear design decision: "treat agents as ordinary enterprise apps and delegate the auth contents to existing standards."

The three things to hold onto:

- **What A2A defines itself is only the "frame."** Agent Card `securitySchemes` / `security`, the 5 SecurityScheme types, the no-identity-in-payload design, the Extended Agent Card, JWS signing. Token issuance, validation, and propagation are all outside.
- **Holes appear in the parts the spec let off with MAY / SHOULD.** Card signing is optional, replay defense is absent, scope enforcement is external. Unless the implementer promotes these to MUST, they sail through.
- **The way to close them is mTLS + signed cards + existing identity standards.** SPIFFE / WIMSE / ID-JAG / Identity Chaining / Transaction Tokens are the water flowing through the A2A plumbing.

Read A2A as a "new auth protocol" and you get the anticlimax. Read it as a "frame for wiring existing auth standards between AI agents" and the rationale of the design, and the responsibility you have to fill yourself, both come into focus. Next time you stand up an A2A server, change the bottom-right of this article's cheat sheet (MAY / SHOULD / none) into MUST, one row at a time.

## References

- [Agent2Agent (A2A) Protocol Specification](https://a2a-protocol.org/latest/specification/)
- [Enterprise-Ready Features - Agent2Agent Protocol (A2A)](https://a2a-protocol.org/latest/topics/enterprise-ready/)
- [RFC 7515: JSON Web Signature (JWS)](https://www.rfc-editor.org/rfc/rfc7515)
- [RFC 8785: JSON Canonicalization Scheme (JCS)](https://www.rfc-editor.org/rfc/rfc8785)
- [RFC 8705: OAuth 2.0 Mutual-TLS Client Authentication](https://www.rfc-editor.org/rfc/rfc8705)
- [RFC 9449: OAuth 2.0 Demonstrating Proof of Possession (DPoP)](https://www.rfc-editor.org/rfc/rfc9449)
