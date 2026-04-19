---
title: 'Why I Built awesome-authorization: Mapping the World of Auth Engines onto a Single Page'
published: true
description: 'The year is 2026 and authorization engines are everywhere. OPA, Cedar, OpenFGA, SpiceDB, Casbin, Cerbos... There are too many choices and it is hard to see the big picture. The arrival of the standard AuthZEN API is stirring things up even more. Here is the story of why I built awesome-authorization to organize the entire authorization landscape onto one page, and a visual guide to where these engines stand today.'
tags:
  - authorization
  - security
  - opensource
  - showdev
series: Authorization
cover_image: 'https://raw.githubusercontent.com/kanywst/dev.to.kanywst/refs/heads/main/articles/assets/why-i-created-awesome-authorization/cover.png'
id: 3519854
date: '2026-04-18T15:16:48Z'
---

# Introduction

"Which authorization engine should I use?"

Very few people can answer this instantly. OPA, Cedar, OpenFGA, SpiceDB, Casbin, Cerbos... That’s six just off the top of my head. They are based on entirely different access control models (RBAC, ABAC, ReBAC), with different design philosophies and use cases.

I've always been an auth nerd. I wrote an AuthZEN-compatible plugin for OPA, read through the SPIFFE/SPIRE implementations, and deep-dived into the Google Zanzibar paper. Through all of this, I realized something: **There is no single place to get a bird's-eye view of the entire authorization landscape.**

A repository called `awesome-authorization` already existed. However, it was mostly a collection of articles and concepts—it didn't answer the practical question of "What engines actually exist and how do they differ?". With AuthZEN 1.0 officially approved, the authorization space is moving fast, but the information is too scattered to track.

So, I built one.

**[awesome-authorization](https://github.com/kanywst/awesome-authorization)** : A curated list of tools, frameworks, standards, and learning resources for authorization and access control.

In this post, I want to explain why this list needed to exist and map out the state of authorization engines in 2026.

---

## 1. Setting the Stage: PEP vs. PDP

Before looking at the engines themselves, let's clarify where authorization sits within the architecture and what exactly an authorization engine—or Policy Decision Point (PDP)—does.

![PEP vs PDP](./assets/why-i-created-awesome-authorization/pep-vs-pdp.png)

Authentication (Who are you?) → Token Issuance → Authorization (What can you do?) → Resource Access. In this flow, the authorization engine (PDP) and the AuthZEN API are strictly responsible for step 4: "Query AuthZ Decision."

OAuth 2.0 and AuthZEN operate on different layers. OAuth is about passing tokens between a client and a resource server. AuthZEN is about the application asking a policy engine for a decision. I see articles conflating these two all the time, but they are entirely different beasts.

## 2. The Cambrian Explosion of Authorization Engines

Let’s look at reality. As of April 2026, here is what the major authorization engine landscape looks like.

![Authorization Engines](./assets/why-i-created-awesome-authorization/authorization-engines.png)

That's a lot. And while they might look similar from the outside, their foundational design philosophies are radically different.

---

## 3. You Can't Choose If You Don't Know the Models

The very first thing to understand when picking an authorization engine is the underlying **access control model**. If you skip this, you will inevitably hit a wall where the engine simply cannot express your use case.

### RBAC: Managing by Roles

The simplest approach. Assign roles to users, and bind permissions to those roles.

![RBAC](./assets/why-i-created-awesome-authorization/rbac.png)

Kubernetes RBAC is a perfect example. It's simple, but as conditions grow, you suffer from Role Explosion. Try expressing "Only full-time engineers in the Tokyo office assigned to Project A can access the production environment" in strict RBAC. The number of role permutations becomes unmanageable.

### ABAC: Deciding by Attributes

Decisions are evaluated based on the **attributes** of the user, the resource, and the environment.

![ABAC](./assets/why-i-created-awesome-authorization/abac.png)

This is where OPA (Rego) and Cedar shine. It’s highly flexible, but the policies themselves can get complicated very quickly.

### ReBAC: Deciding by Relationships

Coined by the Google Zanzibar paper. It manages **relationships** as a graph—for example, "alice is a viewer of doc:readme," or "all members of the eng group are viewers."

![ReBac](./assets/why-i-created-awesome-authorization/rebac.png)

SpiceDB, OpenFGA, and Permify implement this model. It operates identically to how sharing works in Google Drive, making it the most natural fit for collaborative apps. However, it struggles with attribute-based conditions like "allow access only during business hours."

### So, Which One Should You Use?

Roughly speaking:

| What you want to do                      | Model     | Candidates                               |
| :--------------------------------------- | :-------- | :--------------------------------------- |
| Simple role management                   | RBAC      | Casbin, Spring Security, Kubernetes RBAC |
| Complex branching logic (Attributes)     | ABAC      | OPA, Cedar, Cerbos                       |
| Google Drive-style sharing / Hierarchies | ReBAC     | SpiceDB, OpenFGA, Permify                |
| Kubernetes policy control                | ABAC/RBAC | OPA Gatekeeper, Kyverno                  |

In reality, you often end up with a hybrid of RBAC + ABAC or a combination of ReBAC + ABAC. Cedar natively supports both RBAC and ABAC, while Aserto's Topaz combines Zanzibar-style ReBAC with an OPA engine for ABAC.

---

## 4. AuthZEN: Standardizing the AuthZ API

All the authorization engines we’ve looked at share a glaring problem: **Their APIs are completely fragmented.**

OPA wants `{"input": {...}}` sent via `POST /v1/data/...`. Cedar uses a different API entirely. SpiceDB expects a gRPC `CheckPermission` call. They are all different.

This means if you ever decide to swap engines, you have to rewrite all of your application code. We successfully separated PDP (decision) from PEP (enforcement), but we never standardized the protocol between them.

![AuthZEN](./assets/why-i-created-awesome-authorization/authzen.png)

In January 2026, the OpenID Foundation officially approved the **AuthZEN Authorization API 1.0** as a Final Specification. It standardizes the communication between the PEP and PDP, allowing you to use the exact same JSON API regardless of which underlying engine is running.

```json
// Request: Can this subject perform this action on this resource?
POST /access/v1/evaluation
{
  "subject": { "type": "user", "id": "alice" },
  "action": { "name": "read" },
  "resource": { "type": "document", "id": "doc-123" }
}

// Response
{
  "decision": true
}
```

Why does this matter? It decouples your engine choice from your application code. Starting with OPA and later swapping it out for Cedar as your use case evolves is suddenly a realistic option.

### Making OPA AuthZEN-Compatible

I built a plugin that makes OPA natively speak AuthZEN.

**[opa-authzen-plugin](https://github.com/kanywst/opa-authzen-plugin)**

OPA is a generic policy engine with its own REST API. Its paths, request structures, and response structures are entirely different from AuthZEN's. There was an `authzen-proxy` built in Node.js sitting in the contrib repo, but running a separate proxy process alongside OPA felt less than ideal for production.

So, I used OPA’s plugin architecture to run an AuthZEN server directly inside the OPA process itself. It’s the exact same pattern used by the `opa-envoy-plugin`.

![opa-authzen-plugin](./assets/why-i-created-awesome-authorization/opa-authzen-plugin.png)

Engines like Cerbos and Topaz have already started natively supporting AuthZEN. As more engines adopt it, the switching costs between them will continue to drop.

---

## 5. Why the Existing awesome-authorization Failed

[warrant-dev/awesome-authorization](https://github.com/warrant-dev/awesome-authorization) has around 420 stars and decent visibility. But looking closely at the content, there are obvious gaps.

**It focuses heavily on articles and concepts, lacking actual tools.** OPA gets exactly one line. Major engines like Cedar, OpenFGA, SpiceDB, Casbin, and Cerbos are entirely absent.

**It completely ignores modern standards.** The authorization spec world doesn’t end with OAuth 2.0. We have AuthZEN, SPIFFE, UMA, and GNAP reshaping the space, but none of them are covered.

**It feels like a vendor proxy.** The repo puts the Warrant company banner right at the very top. It’s hard to call it a vendor-neutral community resource.

So, I decided to build a better one.

---

## 6. Curating awesome-authorization

I designed [kanywst/awesome-authorization](https://github.com/kanywst/awesome-authorization) to cover the entire authorization landscape through the following sections:

![awesome-authorization](./assets/why-i-created-awesome-authorization/awesome-authorization.png)

The biggest differentiator from the old list is the **Policy Engines section**. I explicitly categorized them into General Purpose, Zanzibar-based, Kubernetes Native, and AuthZEN-compatible. I wanted to create a place where anyone looking for an auth engine could instantly understand the entire current market.

The Standards section is just as comprehensive, covering AuthZEN, OAuth/OIDC, SPIFFE/SPIRE, XACML, and GNAP. You can't grasp the "big picture" of authorization by just looking at tools—you need to understand the underlying specifications driving them.

---

## Conclusion

There are too many authorization engines, and no place to make sense of them all. So I fixed that.

**[kanywst/awesome-authorization](https://github.com/kanywst/awesome-authorization)**

Whether you are trying to select a policy engine, research a standard specification, or find that one specific engineering blog post you read months ago, treat this repository as your starting point.

PRs are absolutely welcome. If a good tool or article is missing, please add it.

---

## Related Articles

- [AuthZEN Authorization API 1.0 Deep Dive](https://dev.to/kanywst/authzen-authorization-api-10-deep-dive-the-standard-api-that-separates-authorization-decisions-1m2a) : Deep Dive into the AuthZEN Spec
- [I Built an OPA Plugin That Turns It Into an AuthZEN-Compatible PDP](https://dev.to/kanywst/i-built-an-opa-plugin-that-turns-it-into-an-authzen-compatible-pdp-eac) : Design and Implementation of opa-authzen-plugin
- [Google Zanzibar Deep Dive](https://dev.to/kanywst/google-zanzibar-deep-dive-handling-2-trillion-acls-in-under-10ms-456d) : Explaining the Zanzibar Paper
- [RBAC vs ABAC vs ReBAC](https://dev.to/kanywst/rbac-vs-abac-vs-rebac-how-to-choose-and-implement-access-control-models-3c89) : Comparing Access Control Models
