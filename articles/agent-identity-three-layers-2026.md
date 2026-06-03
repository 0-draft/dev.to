---
title: 'The Three Layers of AI Agent Authentication: What ID-JAG, Transaction Tokens, and WIF Actually Protect, and When They Will Catch On'
published: true
description: 'The UX of AI agent auth feels almost identical to running everything on human creds. So why will ID-JAG, Transaction Tokens, and WIF still spread? I read it from the May 2026 IETF drafts and the primary sources for Anthropic WIF / Okta XAA / MCP, the Replit / EchoLeak / Moltbook incidents, and the adoption curves of MFA, short-lived AWS creds, and Sigstore.'
tags:
  - oauth
  - security
  - ai
  - agents
series: AI Agent Identity
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/agent-identity-three-layers-2026/cover.png'
id: 3810476
date: '2026-06-03T11:12:33Z'
---

## Introduction

Something clicked when I looked at the [Workload Identity Federation](https://platform.claude.com/docs/en/manage-claude/workload-identity-federation) that Anthropic shipped in May 2026. Delete the `sk-ant-...` API key, have a k8s service account JWT mint a short-lived `sk-ant-oat01-...` token, call `anthropic.Anthropic()` with no arguments, and it just works. The security posture clearly went up.

But the actual day-to-day flow, where an agent "runs Cursor on Alice's GitHub PAT and opens a PR," did not change one bit. Cursor, Claude Code, Comet: all of them ultimately hold the user's own credentials and act with them. Around the same time I was following the IETF drafts for ID-JAG (Identity Assertion JWT Authorization Grant) and Transaction Tokens, and I kept feeling this gap: the specs are converging, yet nobody is adopting them.

That raises one obvious question. **"Tighter scope," "auditable," "smaller blast radius" are all true, and yet the agent UX you use every day does not change. So is this stuff actually going to catch on?**

This article takes that question head on. The conclusions up front:

- The UX not changing is, like refresh tokens, evidence that the design is correct
- ID-JAG, Transaction Tokens, and WIF each protect a different layer; lining them up to compare is a category error
- There are two adoption routes. One is the MFA / IRSA / Sigstore "incident → regulation → adoption" path. The other is the DNSSEC / SPIFFE "eternal niche, spreads only under a different name through vendor integration" path. **A protocol with no UX improvement basically takes the latter**, and that is the cold lesson of tech history

**To put the punchline first: I predict "we deployed ID-JAG" (Layer A) will not catch on. Layer C will. Layer B is an eternal niche**.

## The May 2026 map: where the major specs and implementations actually stand

To start the discussion from the same place, here are the primary sources.

### IETF drafts

| Spec | Latest | Published | Status |
| --------------------------------------------------------------------------------------------------------------------------------------------- | ------ | ---------- | ------------------------------------------------------------- |
| [draft-ietf-oauth-identity-assertion-authz-grant](https://datatracker.ietf.org/doc/draft-ietf-oauth-identity-assertion-authz-grant/) (ID-JAG) | -04    | 2026-05-21 | Standards Track, Internet-Draft                               |
| [draft-ietf-oauth-identity-chaining](https://datatracker.ietf.org/doc/draft-ietf-oauth-identity-chaining/)                                    | -12    | 2026-05-11 | Standards Track, Internet-Draft                               |
| [draft-ietf-oauth-transaction-tokens](https://datatracker.ietf.org/doc/draft-ietf-oauth-transaction-tokens/)                                  | -08    | 2026-03-02 | Standards Track, Internet-Draft                               |
| [draft-araut-oauth-transaction-tokens-for-agents](https://datatracker.ietf.org/doc/draft-araut-oauth-transaction-tokens-for-agents/)          | -06    | 2026-04-11 | Individual Draft (Ashay Raut, Amazon), pre-WG-adoption        |
| [draft-ietf-oauth-v2-1](https://datatracker.ietf.org/doc/draft-ietf-oauth-v2-1/)                                                              | -15    | 2026-03-02 | Standards Track, Internet-Draft (in WG discussion, pre-Last-Call) |
| [draft-klrc-aiagent-auth-00](https://datatracker.ietf.org/doc/draft-klrc-aiagent-auth/)                                                       | -00    | 2026-03    | Individual Draft (Defakto / AWS / Zscaler / Ping)             |

What this tells you about the lay of the land:

- **ID-JAG is not an RFC yet**. There is just a Standards Track draft circulating; as of this writing there is no official RFC number assigned. The contents can still change
- **The Agent extension to Transaction Tokens is still an individual proposal**, pre-WG-adoption (`draft-araut-`, not `draft-ietf-`). It uses the `act` claim for the AI agent and the `sub` claim for the principal, and it has moved from -00 to -06 in half a year (a straightforward extension of RFC 8693 Token Exchange's actor/subject concepts)
- **OAuth 2.1 (-15) is in WG discussion**. It has not reached Last Call, but it is framed to obsolete RFC 6749. Mandatory PKCE, removal of the Implicit/Password grants, and so on all become load-bearing assumptions for the agent specs

I wrote the dedicated walkthrough of ID-JAG itself in a separate piece ([ID-JAG Deep Dive](https://dev.to/kanywst/id-jag-deep-dive-1mhp)). Here I narrow in on "**what becomes visible when you put all three side by side**."

### The implementation side

Chasing specs alone is pointless. Here is what is actually moving in 2026.

| Implementation | Released | What it does |
| ---------------------------------------------------------------------------------------------------------------------------------- | ------------------------ | -------------------------------------------------------------------------------------------------------------- |
| [Anthropic Workload Identity Federation](https://platform.claude.com/docs/en/manage-claude/workload-identity-federation)           | 2026-05                  | Exchanges k8s SA / GHA / SPIFFE / AWS / GCP JWTs for `sk-ant-oat01-...` short-lived tokens via RFC 7523 jwt-bearer |
| [Okta Cross-App Access (XAA)](https://www.okta.com/solutions/cross-app-access/)                                                    | 2025-Q3 beta → 2026 GA   | The commercial name for ID-JAG. Adopted formally as MCP's Authorization Extension "Enterprise-Managed Authorization" |
| [xaa.dev playground](https://developer.okta.com/blog/2026/01/20/xaa-dev-playground)                                                | 2026-01-20               | An official Okta environment for trying XAA end to end on your own machine                                       |
| [Keycloak 26.5 JWT Authorization Grant](https://www.keycloak.org/2026/01/jwt-authorization-grant)                                  | 2026-01                  | Preview support for RFC 7523. Exchanges externally-signed JWTs for Keycloak tokens                              |
| [MCP spec 2026-03-15](https://modelcontextprotocol.io/specification/draft/basic/authorization)                                     | 2026-03-15               | Makes RFC 8707 Resource Indicators mandatory, RFC 9728 Protected Resource Metadata mandatory                    |
| [Salesforce Agentforce "Trusted Agent Identity"](https://www.salesforce.com/news/stories/agent-fabric-control-plane-announcement/) | 2026 GA                  | Inserts mobile approval into high-risk agent actions                                                            |

Two quiet but big shifts are happening in that table.

One: the 2026-03-15 MCP spec made RFC 8707 (Resource Indicators) and RFC 9728 (Protected Resource Metadata) **mandatory**. Audience binding is now enforced per MCP server, so an access token issued for one MCP server gets rejected by the authorization server if you throw it at a different MCP server. A leak path like Cursor accidentally forwarding a GitHub MCP token to a Slack MCP is now closed at the spec level.

Two: Okta XAA got folded in as MCP's "Enterprise-Managed Authorization" extension. The ID-JAG concept is reaching the implementation side first not as a pure IETF draft but riding on top of MCP.

Summed up: **the specs have converged, implementations are out from Anthropic / Okta / Keycloak / Salesforce, but almost nobody in the field is using any of it**. That is the state of play in May 2026.

## What are the three layers actually protecting?

Putting all three in parallel just causes confusion. As the figure shows, **different layers are protected by different specs**.

![3-layer architecture of agent identity](./assets/agent-identity-three-layers-2026/diagrams/01-three-layers.png)

### Layer A: Human → Agent → External Resource (ID-JAG / XAA)

The problem here is "**how does an Agent touch GitHub on behalf of the human Alice**."

There are two OAuth extensions you need as background. They come up repeatedly, so pin them down first.

- **RFC 7523** (JWT Profile for OAuth 2.0 Client Authentication and Authorization Grants): the profile for "bring one JWT, get an OAuth access token in return." It defines the form you post with `grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer`
- **RFC 8693** (Token Exchange): the general framework for "exchange one token for another." `subject_token` is "who the token is for," `actor_token` is "the party actually acting." The `act` / `sub` claim hierarchy comes from here too

ID-JAG / XAA combines these two into a profile that "**extends the IdP trust established by a human's SSO out to API calls made through an agent**."

To see the concrete difference, the old approaches are only two:

1. Hand the Agent Alice's GitHub PAT (basically everyone today)
2. Have Alice individually approve an OAuth App for the Agent (this is what ChatGPT Plugins / Claude Connectors do)

Approach 1 cannot narrow scope. If Alice has `repo:full`, the Agent has `repo:full`. Approach 2 can narrow scope, but Alice has to walk through a consent screen per Agent, which collapses in the age of N agents.

ID-JAG works like this:

1. Alice is already SSO'd into her IdP (Okta / Entra ID / Google Workspace)
2. The IdP issues an identity assertion JWT for Alice
3. The Agent brings that to GitHub's Authorization Server via the RFC 7523 jwt-bearer grant
4. GitHub's AS **validates the JWT through its trust relationship with the IdP** and, via RFC 8693 Token Exchange, exchanges it for a **scoped-down GitHub access token for Alice**
5. The Agent calls the GitHub API with that token

Alice never touches a consent screen. The Agent only ever holds a narrowly-scoped token from the start. Even with N agents, you manage per-agent policy on the IdP side.

The commercial name, in Okta's case, is "Cross-App Access (XAA)." Conceptually it is a profile riding on top of OAuth Identity Chaining (`draft-ietf-oauth-identity-chaining-12`), and Okta shipped an implementation in 2026 as MCP's "Enterprise-Managed Authorization" extension.

### Layer B: Agent → internal service chain (Transaction Tokens for Agents)

The problem here is "**while an Agent processes a single request and calls multiple internal services, how do you propagate who is acting and for what purpose**."

Layer A's ID-JAG is about crossing a trust domain boundary (your company → GitHub). Layer B is about the **microservice chain inside your own walls**.

The prerequisite, Transaction Tokens (`draft-ietf-oauth-transaction-tokens-08`), is a mechanism to "convert" the outbound token received at the API gateway into a short-lived JWT meant to flow through the internal chain. Pushing the received OAuth access token straight through 5 hops makes the scope too broad and stacks up leak risk. So inside the Trust Domain, a **Transaction Token Service (TTS)** issues a short-lived "for this request" token and flows that through the chain. I plan to write the details elsewhere, but the gist gets across as just "pack the per-request context into a JWT and carry it."

Transaction Tokens **for Agents** is the extension that adds the claim design for when an AI agent is mixed into the Trust Domain.

| claim | meaning |
| ----- | ------------------------------------------------------------------------------------------------ |
| `sub` | the principal (the human Alice, or the agent itself if the agent acts independently)             |
| `act` | the actor (the AI agent actually making the call; embeds RFC 8693's actor token concept straight into the JWT) |

By carrying these two claims across the whole internal chain, who-delegated-to-whom survives per request.

Why is this needed? The ID-JAG token itself does have an `act` claim for the actor (from RFC 8693), so it is not that "delegation can't be expressed." The problem is elsewhere. ID-JAG is a **single-hop, cross-boundary grant** whose `aud` is pinned to a single Resource AS, so you cannot flow it through the internal chain as-is (the `aud` won't match). Pushing the received outbound token straight through 5 hops is also over-scoped and stacks up leak risk. So in practice you **exchange it at the gateway for a short-lived internal token (i.e. mint a new one)**.

If information disappears, it is not because it crosses hops; it is because **the actor gets left off at the moment of that exchange**. Mint it naively and only `sub=alice` survives, `act` drops, and the terminal service sees nothing but "Alice's own transaction." Transaction Tokens for Agents nails down a claim design that forces `act=agent-X, sub=alice` to be preserved at exchange time. Once minted, the TraT propagates immutably through Order Service → Risk Service → Payment Service, and each hop can verify "agent-X is executing Alice's transaction" at the JWT level. The Payment Service's audit log permanently records "agent-X executed this transfer on behalf of alice." That is the territory Layer A alone cannot reach.

### Layer C: Agent (workload) → LLM (Anthropic WIF)

The problem here is "**how does the workload that is the Agent authenticate to the LLM API of Anthropic / OpenAI / Google**."

Layers A and B were authentication toward the resource side (GitHub / internal services). Layer C is **authentication toward the AI side**.

The term Workload Identity Federation (WIF) has history: AWS and GCP originally built it as a mechanism to "delete IAM user static access keys by exchanging an IdP's OIDC token for an STS / GCP token." It is the whole story of exchanging GitHub Actions OIDC or a Kubernetes service account for AWS sigv4 credentials. Anthropic WIF is just the LLM-provider version of that; the structure is completely isomorphic.

The flow on Anthropic's side ([official docs](https://platform.claude.com/docs/en/manage-claude/workload-identity-federation)) is this:

1. The platform the Agent runs on (k8s SA / GHA / SPIFFE / AWS / GCP) issues an ambient OIDC JWT (a projected service account token on Kubernetes, the OIDC endpoint on GitHub Actions, and so on)
2. The Agent posts that JWT to Anthropic's `/v1/oauth/token` via RFC 7523 `urn:ietf:params:oauth:grant-type:jwt-bearer`
3. Anthropic validates the JWT signature against the registered issuer's JWKS and checks the federation rule's `subject_prefix` and the like
4. On a match, it returns a **short-lived `sk-ant-oat01-...` token** (per service account, 3600 seconds by default)

The nice part is you can fully delete the `sk-ant-...` static API key. No more operations of injecting a secret into the Agent container.

One thing that often gets misunderstood here: **"if I have WIF, do I even need ID-JAG?"** They protect different legs, so they do not compare. WIF is the Agent → Anthropic leg, ID-JAG is the Human → Agent → GitHub leg. Anthropic WIF cannot protect Alice's GitHub PAT no matter how nasty a prompt injection the Agent eats. The premise is you use both.

### The three-layer mapping

|                        | Layer A                                            | Layer B                              | Layer C                                          |
| ---------------------- | -------------------------------------------------- | ------------------------------------ | ------------------------------------------------ |
| **Which leg**          | Human → Agent → External Resource                  | Agent → Internal Service Chain       | Agent (workload) → LLM Provider                  |
| **Representative spec**| ID-JAG / Identity Chaining / XAA                   | Transaction Tokens for Agents        | RFC 7523 jwt-bearer + each vendor's WIF          |
| **Input identity**     | Human OIDC ID Token                                | Agent + principal context            | Workload identity (k8s SA / SPIFFE)              |
| **Problem solved**     | narrowing the human's scope, blast radius on agent takeover | propagating "for whom" across the call chain | killing static API keys, auditable workload identity |
| **2026 status**        | IETF draft -04, implemented in Okta XAA            | IETF individual draft -06            | Anthropic GA, AWS/GCP for years                  |
| **Who hurts without it** | enterprise SaaS integrations                     | microservice audit teams             | platform SRE / audit                             |

Once you get here, you see the "**ID-JAG vs WIF**" framing never held in the first place. You use both.

## Why the UX "doesn't change," and what not changing actually means

Back to the opening question: "if the UX doesn't change, won't it fail to catch on?"

This is half right. **In the happy path, one person, one agent, within their own permissions, the UX really does not change at all**. The Agent fetching a JWT from the IdP behind the scenes, narrowing scope with Token Exchange, throwing it at the resource server: none of that is visible to Alice.

And that is the result of correct design. Just as users do not think about OAuth's access_token and refresh_token, **making them think about it is a design failure**. If you look at this spec expecting "the UX to visibly change," you misread its essence.

But "the UX does not change" does not equal "it has no value." Layers A / B / C deliver the kind of value that is **invisible day to day and only becomes visible the instant something goes wrong**. Concretely, it shows up in the next three scenarios.

### Scenario 1: when you have an accident (blast radius)

July 2025, the incident where Replit's AI agent wiped a production DB during a code freeze. In an experiment Jason Lemkin of SaaStr documented, data for over 1,200 executives and 1,190 companies was destroyed. ([Fortune report](https://fortune.com/2025/07/23/ai-coding-tool-replit-wiped-database-called-it-a-catastrophic-failure/), [AI Incident Database #1152](https://incidentdatabase.ai/cite/1152/))

What happened comes down to one thing: **the Agent ran with the same DB connection privileges as a human**. The code-freeze instruction was implemented only as a prompt-level "please," with no mechanism to stop it at the authorization level. The Agent confessed it had "panicked in response to empty queries," and per the report it even lied about the recovery procedure.

If Layer A (ID-JAG) had been in place, picturing it out: scope the token issued to the Agent to just `db:read` and `DROP TABLE` comes back as **HTTP 403**. Even if the Agent goes haywire, if the token is short-lived (say 5 minutes), the rampage itself has a time cap. And the audit log permanently records "agent-X attempted a DELETE against prod and got 403." That is enforcement at the authorization layer, a notch stronger than a prompt-level "please."

After the incident Replit added "automatic dev / prod DB separation." That is the right response, but structurally it is **absorbing Layer A's role into the infrastructure side**. Solving it at the app layer (ID-JAG) or the data layer (DB separation) are both fine; the real problem is that most teams currently do neither.

### Scenario 2: when you eat a zero-click attack (scope violation)

June 2025, **EchoLeak** (CVE-2025-32711, CVSS 9.3) hit Microsoft 365 Copilot ([The Hacker News report](https://thehackernews.com/2025/06/zero-click-ai-vulnerability-exposes.html); [arXiv paper 2509.10540](https://arxiv.org/html/2509.10540v1) analyzes it as the "first real-world zero-click prompt injection exploit in a production LLM system"). The attack flow is simple:

1. The attacker **sends one email** to a user at the target org
2. Copilot later goes to read that email
3. A hidden prompt embedded in the email body steers Copilot
4. Copilot reads out **all data the user has access to** from SharePoint / OneDrive / Teams and exfiltrates it to an external endpoint

The user clicked nothing. It completes just by an email landing in the inbox. Aim Labs, who found it, calls this "LLM Scope Violation."

The core problem is isomorphic to Replit: **the Agent (Copilot) held "all of Alice's permissions."** More precisely, it is not that Alice failed to narrow Copilot's scope, it is that there is no mechanism to narrow it.

In the ID-JAG / XAA worldview, you can cut the token Copilot uses to read SharePoint down to something narrow like "**read the document Alice is looking at right now**." However hard the hidden prompt tries, it can only touch what the token allows. A scope violation like EchoLeak is a phenomenon that occurs where the token's permission boundary is "all of Alice's permissions," so the real problem is that there is currently no standardized way to make that boundary narrow.

### Scenario 3: when it scales (N agents)

The **Moltbook incident** of January–February 2026. A service billing itself as a "social network" for AI agents launched on 2026-01-28, and a mere three days later, on 2026-01-31, it got [reported by 404 Media](https://www.404media.co/exposed-moltbook-database-let-anyone-take-control-of-any-ai-agent-on-the-site/). A backend Supabase misconfiguration left it in a state where **anyone could take over any agent on the platform via the DB**.

Then in February 2026, Wiz researchers found that [the Supabase API key was exposed in the front-end JavaScript](https://www.wiz.io/blog/exposed-moltbook-database-reveals-millions-of-api-keys). Full read/write to production data went through, and you could pull **1.5M API authentication tokens, 35,000 email addresses, and private messages between agents**.

What matters here is a structural story prior to any individual vulnerability: no identity separation between agents, no scope narrowing, no rotation, none of it implemented. Stand up a platform holding this many identities this quickly and try to run it on human-scale credential ops, and this is what you get.

The numbers back it up too. Non-Human Identities (NHI) as of 2026 outnumber humans by **40–100x, reaching 500x in hyper-automation orgs**. The average enterprise carries over 250,000 NHIs ([NHI Working Group's summary](https://nhimg.org/articles/identity-governance-is-shifting-as-non-human-identities-outnumber-humans/)).

Of those, **71% are not rotated, 97% are over-privileged, and only 15% of orgs feel confident they can defend against NHI-based attacks**. 68% of incidents involve NHIs.

This is the **pattern where operations break before any accident does**. Kubernetes service accounts spread not because of an accident but because "sharing creds across 200 microservices became physically impossible." The same thing happens with agents. If Replit / EchoLeak "push it up from the accident side," then Moltbook and the NHI numbers are the "push it up from the operations side."

By here the real meaning of "the UX doesn't change" comes into focus. In the happy path you feel nothing. That is evidence of correct design. On the flip side, when an accident hits, the damage is **human-scale** (Replit's full DB deletion, EchoLeak exfiltrating all of a company's documents off one email), and that is where the cost of not having Layer A surfaces. When you scale, audit-log pollution and the inability to revoke come due all at once as the tab for not having Layers B / C. The cost you do not see day to day becomes visible all at once under accidents and scale: that is the essential role of Layers A / B / C.

## Predicting "when each layer catches on": the 3-stage model of security history

From here on it is prediction. Less to be right than to give the discussion a foundation.

The spread of security infrastructure almost without exception goes through the next three stages.

![3-stage adoption pattern for security infrastructure](./assets/agent-identity-three-layers-2026/diagrams/02-adoption-pattern.png)

### Past isomorphic cases

**MFA**. TOTP was standardized in RFC 6238 in 2011, U2F in 2014; the tech itself is over a decade old. The 2012 LinkedIn breach (6.5M passwords), 2013-2014 Yahoo (eventually found to be 3B accounts), 2017 Equifax (147M): flashy incidents kept coming, and regulation caught up afterward, with **NIST SP 800-63-3 downgrading SMS-based OOB authentication to a "restricted authenticator" in 2017** and **PCI-DSS v4.0 expanding the mandatory-MFA scope beyond admins in 2022**. Real adoption was 2019–2023. **Roughly 15 years from the tech appearing to practical use**.

**Short-lived AWS credentials**. 2011 STS AssumeRole, 2014 Code Spaces burned to the ground (an AWS key leak deleted all resources and ended the company), 2016 Uber (an S3 key leak, 57M records), 2019 Capital One (106M records via the EC2 instance metadata service). 2019 brought EKS IRSA, and **EKS Pod Identity at re:Invent in November 2023** removed even the need to configure OIDC, so the default option finally became "don't create a static key." **10–12 years from the tech appearing to real adoption**.

**Sigstore / keyless signing**. Late 2020 SolarWinds, 2021 Codecov / Kaseya. **Executive Order 14028 in May 2021** codified SBOM and signing as federal procurement conditions, 2022 NIST SSDF (SP 800-218), 2023 SLSA v1.0. Real adoption was 2023–2025. **Rapid adoption 3 years after the accident**, the fastest of the three.

Lining up all three, a common thread emerges. **The tech exists years before the accident** (it does not spread not because of a tech problem, but because the asymmetry between cost and risk has not yet broken). It needs **the media to turn it into a story**: a CVE number and CVSS alone do not move anything; only when a named big company gets named-and-shamed does it start to turn. Finally, **codification by regulation or industry BCP** is the trigger. NIST, PCI, EO 14028, SLSA: at this stage insurance premiums and compliance audits move, and budget gets secured inside companies.

### The other historical pattern: protocols with zero UX improvement do not spread

But reading only the 3-stage model, you might conclude "ID-JAG will come eventually too," and that misses an important precondition. **MFA / Sigstore had extremely strong regulation, or a UX bonus**. With the same "accidents present," a protocol with zero UX improvement and implementation room only on the vendor side does not spread even when regulation comes. Look at tech history and this is the more common pattern.

| Protocol                     | UX improvement        | Setup / ops        | Regulatory pressure | Adoption                              |
| ---------------------------- | --------------------- | ------------------- | ------------------- | ----------------------------------- |
| **DNSSEC**                   | none                  | heavy               | a few govt agencies only | ~30% in 25 years                    |
| **IPv6**                     | none                  | heavy               | Asia-centric, weak in US/EU | ~50% in 25 years                  |
| **DMARC**                    | none                  | medium, full of traps | enterprise BCP only | half of enterprises, long tail unconfigured |
| **DPoP**                     | none                  | medium              | none                | OAuth extension, near-zero adoption |
| **SPIFFE**                   | none                  | heavy               | none                | niche after 10 years                |
| **mTLS (via service mesh)**  | none                  | the mesh hides it   | none                | adopted where the mesh is           |
| **MFA**                      | **worse**             | light               | **strong** (PCI / NIST) | real adoption in 15 years           |
| **Passkey**                  | **dramatically better** | light             | weak                | **exploded in 2-3 years**           |
| **Let's Encrypt + HTTPS**    | **better** (free, automatic) | light        | weak                | global standard in 5 years          |
| **TLS 1.3**                  | **better** (lower latency) | automatic       | none                | spread in a few years               |

The rule you can read off this is simple:

- **UX improves** → spreads fast (Passkey, Let's Encrypt, TLS 1.3)
- **UX worsens + strong regulation** → takes time but spreads (MFA muscled through the UX hit of SMS OTP via regulation)
- **zero UX improvement + weak regulation + heavy setup** → **eternal niche** (DNSSEC, IPv6, DMARC, DPoP, SPIFFE)
- **zero UX improvement but a mechanism makes the ops invisible (service mesh, vendor integration)** → spreads via a different route

So which quadrant is ID-JAG in?

- UX improvement: **none**. Alice's experience is actually better for skipping the consent screen, but it is not at the "wow" level
- Setup: **heavy**. Trust with the IdP, the Resource Server's support, the Agent's Token Exchange implementation, all cross-vendor
- Vendor dependence: **strong**. Users can't use it unless Cursor / Claude Code / Comet each implement it
- Strong regulation: **not yet**. Neither the EU AI Act nor the NIST AI RMF steps into the identity layer

This is the **DNSSEC / SPIFFE / DPoP quadrant**. Rapid adoption like MFA or Sigstore is more likely not to happen.

### Where Agent Identity stands now

Put the three isomorphic cases next to Agent Identity and it looks like this.

| Stage          | MFA                           | Short-lived AWS creds           | Sigstore                    | Agent Identity                                              |
| ------------- | ----------------------------- | ------------------------------- | --------------------------- | ----------------------------------------------------------- |
| 1. Tech appears | 2011 (TOTP)                 | 2011 (STS)                      | 2020                        | 2024-2026 (ID-JAG / Tx Tokens / WIF)                        |
| 2. Flashy accident | 2012-2017                | 2014-2019                       | 2020-2021                   | **2025-2026 (Replit / EchoLeak / Comet / Moltbook, ongoing)** |
| 3. Regulation / BCP | 2017-2022 (800-63-3 / PCI v4) | 2019-2023 (IRSA / Pod Identity) | 2021-2023 (EO 14028 / SLSA) | **2026-? (EU AI Act / NIST AI RMF / RSAC 2026 in discussion)** |
| 4. Real adoption | 2019-2023                  | 2021-2023                       | 2023-2025                   | **predicted 2028-2030**                                     |

Right now is **the entrance to stage 2**. Individual cases like Replit / EchoLeak / Comet ([Brave's analysis of Perplexity Comet](https://brave.com/blog/comet-prompt-injection/), [Schneier on Security's warning on AI browsers](https://www.schneier.com/blog/archives/2025/11/prompt-injection-in-ai-browsers.html)) keep stacking up, but the **"Equifax of Agents"** has not arrived yet. Three scenarios that look likely to come next:

- A big company's Copilot / Cursor / Claude Code integration eats a prompt injection and exfiltrates customer DB contents to a company-wide Slack. Happens at some Fortune 500
- An executive's AI assistant gets hijacked and a transfer instruction goes through via Slack. Salesforce building **mobile approval** into Trusted Agent Identity is precisely a guard against this
- A dev Agent force-pushes to a prod repo on a human's GitHub creds and breaks the supply chain. The AI version of SolarWinds

The moment any one of these lands in the New York Times **with a name attached**, it moves to stage 3 (regulation). Until then it stays stuck at "we really should do this."

### Per-layer adoption-timing prediction (the honest version)

I see the three layers walking separate fates. I write "honest version" because it is my personal prediction with the wishful thinking removed.

**Layer C (WIF) → will catch on**. The reason is simple: **the vendor completely hides the operations**. Anthropic WIF works just by initializing the SDK with no arguments, and a k8s SA auto-mints projected tokens. The end user does nothing. This is the same shape as mTLS spreading hidden inside the service mesh: the protocol itself spreads without anyone being aware of it. `sk-ant-...` / `sk-...` static keys drop within a few years to the status of "exists, but not recommended."

**Layer A (ID-JAG / XAA) → won't catch on as a standard; the concept spreads under a different name via vendor integration**. Almost no team will say "we deployed ID-JAG" or "we adopted XAA." Just like SAML, each vendor implements it proprietarily as "Claude Connector," "Cursor for Enterprise," "Copilot Connector," and the end user perceives it as "I connected GitHub with one click in the Anthropic console." Nobody cares whether the token exchange behind it is ID-JAG-compliant. **Only XAA via MCP has a shot at surfacing**, but even that is only something "the side standing up the MCP Server" is aware of; the end user never sees it.

**Layer B (Transaction Tokens for Agents) → eternal niche**. This is dragged down by the fact that Transaction Tokens proper are currently almost unadopted. It will get picked up in some finance / healthcare intra-trust-domain microservices, but nowhere else. Same pattern as SPIFFE (correct, but adoption is limited).

### The likely base case: it ends on the SPIFFE / DNSSEC route

I write this as the base case. Not wishful thinking: I mean that going by the lessons of tech history plus current vendor dynamics, this is the most likely outcome.

Three reasons:

- **Microsoft / OpenAI / Anthropic / Salesforce locking it down proprietarily is faster**. Once Anthropic Service Account, OpenAI Agent Identity, Microsoft Copilot Studio Identity, and Salesforce Trusted Agent Identity each become self-contained, the incentive to wait for standardization evaporates. The same road SAML took, ending up subtly different per SaaS
- **MCP's Enterprise-Managed Authorization (= XAA)** is a route that could save ID-JAG, but it is an Okta-led implementation, and if Microsoft / Google / Auth0 start shipping isomorphic vendor extensions, it could fragment
- The discussion at **RSAC 2026** ([VentureBeat's summary](https://venturebeat.com/security/rsac-2026-agent-identity-frameworks-three-gaps)) is moving the direction even higher, to "Agent Identity alone is not enough; you need an Action Governance layer." When the "next layer" discussion starts before the identity-layer standardization solidifies, the standardization work falls behind, and each vendor's proprietary implementation becomes the de facto standard

The optimistic scenario does exist: "an Equifax of Agents lands in the NYT, the EU AI Act steps into the identity layer, and ID-JAG becomes effectively mandatory." But that needs regulatory pressure as strong as how regulation muscled MFA through the UX hit of SMS OTP, and the current AI-regulation discussion centers on **liability allocation / transparency / fairness**, with no sign of stepping into identity tech. **The probability of "spreads in reality via vendor proprietary" is higher than the probability of regulation arriving**: that is my honest read.

## Conclusion

This ran long, so here is what I want you to take home from the three-layer model.

"The UX doesn't change, so we don't need ID-JAG" is half a misread and half correct. **Layer A's value shows up under accidents and scale**: that much is correct as a statement about the spec. On the other hand, **"will the ID-JAG protocol catch on" and "will the Layer A concept spread" are separate questions**, and that is the honest read. The route where the standard stands up front and spreads, like MFA or Sigstore, is possible, but a protocol that combines zero UX improvement, heavy setup, and strong vendor dependence is more likely to follow the DNSSEC / SPIFFE / DPoP route.

Even so, the three-layer model itself does not break. **Layer C (WIF) catches on** (the structure where the vendor hides the operations), **Layer A spreads as concept only, under a different name via vendor integration** (Claude Connector / Copilot Connector / Cursor for Enterprise effectively implementing the ID-JAG equivalent behind the scenes), **Layer B is an eternal niche in just part of finance / healthcare**: that is how it splits. If an accident like Replit / EchoLeak / Moltbook happens in your environment, thinking about what stops and what doesn't per Layer A / B / C changes how you see it.

If you want to move in practice today, start with **Layer C**. Replacing `sk-ant-...` / `sk-...` static keys with [Anthropic WIF](https://platform.claude.com/docs/en/manage-claude/workload-identity-federation) or equivalent Workload Identity Federation is the side you can do today without waiting for regulation, and that will reliably catch on. For Layer A, rather than aiming for "ID-JAG compliance," it is more practical to **check how narrow the scope design is in the proprietary connectors your vendors (Anthropic / OpenAI / Microsoft / Okta) ship**. Layer B is fine to think about once an audit requirement actually shows up.

If you want to read the behavior of ID-JAG itself, [ID-JAG Deep Dive](https://dev.to/kanywst/id-jag-deep-dive-1mhp); for the full map of agent auth, [AI Agent Authentication & Authorization Deep Dive: Reading draft-klrc-aiagent-auth-00](https://dev.to/kanywst/ai-agent-authentication-authorization-deep-dive-reading-draft-klrc-aiagent-auth-00-5d1). Those two are the supporting lines.

Holding the three-layer model as a map means **even when a vendor's new announcement is a proprietary integration, you can immediately classify what it solves and what it doesn't**. The OpenAI / Google Cloud agent-auth announcements that will probably come in the second half of 2026, even if they don't ship under the name ID-JAG, are fine as long as you can sort out whether they are trying to solve the Layer A problem or are Layer C. Whether the standard catches on is, in a sense, beside the point. **As long as the problem gets solved**.
