---
title: 'Identity Chaining Deep Dive: Connecting Identity Across Trust Domains with OAuth'
published: true
description: 'A comprehensive guide to Identity Chaining (draft-ietf-oauth-identity-chaining-08). Learn how to safely propagate identity and authorization information across domains in multi-cloud and microservices architectures, combining RFC 8693 and RFC 7523.'
tags:
  - oauth
  - security
  - identity
  - microservices
series: OAuth
cover_image: 'https://raw.githubusercontent.com/kanywst/dev.to.kanywst/refs/heads/main/articles/assets/identity-chaining-deep-dive/cover.png'
id: 3351989
date: '2026-03-14T15:58:39Z'
---

# Introduction

I've been wondering about distributed systems lately—specifically, multiple microservices across different cloud providers. Say a request starts in Domain A, needs to access Domain B's services, and then Domain C. It seems simple at first glance.

But what actually happens under the hood? Once you cross a trust domain boundary, your access token usually becomes worthless. Domain B won't accept Token A, and Domain C won't accept tokens from either. It makes you wonder: how exactly do you safely move identity across trust boundaries without leaking credentials or creating security holes?

![across domain](./assets/identity-chaining-deep-dive/across-domain.png)

"Just pass Service A's access token directly to Service C"? Absolutely not. The audience is different. The signature issuer is different. The receiving end can't even verify it, and if it somehow accepted it, it would become a critical security vulnerability.

**Identity Chaining** is the answer to this exact problem.

---

## What is Identity Chaining?

The answer is Identity Chaining. Instead of inventing something new, it combines two existing OAuth RFCs in a clever way.

![identity chaining](./assets/identity-chaining-deep-dive/identity-chaining.png)

| Component                       | Role                                                    | Usage in Identity Chaining                                                                                           |
| :------------------------------ | :------------------------------------------------------ | :------------------------------------------------------------------------------------------------------------------- |
| **RFC 8693 (Token Exchange)**   | Exchange a token you have for a different token         | At the authorization server in your domain, exchange for a **JWT authorization grant** for the peer domain           |
| **RFC 7523 (JWT Bearer Grant)** | Present a JWT as an assertion to obtain an access token | Present the obtained JWT authorization grant to the peer domain's authorization server to obtain an **access token** |

"Convert with Token Exchange, present with JWT Bearer Grant." To state the entire Identity Chaining flow in one sentence, that's it.

---

## Why Don't Existing Methods Work?

People ask me all the time: "Why not just use Token Exchange directly?" or "Can't you just pass the token along?" Here's why that doesn't work.

### Method 1: Pass the Access Token Directly

![Existing Methods](./assets/identity-chaining-deep-dive/existing-methods.png)

**Problem**: Token A's `aud` (audience) is intended for Domain A's resources. Domain B's Service B can't verify it even if it receives it. If it somehow accepted it, and Token A were leaked, Domain B would also be compromised.

### Method 2: Use Token Exchange Alone

RFC 8693 alone can "exchange tokens," but **it doesn't define a protocol for exchanges across domain boundaries**. If Domain A's authorization server directly issued a token for Domain B, it would ignore Domain B's authorization policies.

### Method 3: Have Users Go Through OAuth Authorization Flow Every Time

![user every time](./assets/identity-chaining-deep-dive/user-every-time.png)

**Problem**: User interaction required every time. This doesn't work for backend service-to-service communication, batch processing, or CI pipelines.

## Identity Chaining's Approach

Identity Chaining assumes a **trust relationship (Federation)** between domains, where authorization servers trust each other's keys. Domain A's authorization server issues a "JWT authorization grant" that Domain B's authorization server validates by checking the signature. No user interaction is needed, and Domain B's authorization policies still apply.

---

### Prerequisite Knowledge: Trust Domains and Federation

Let me first clarify the prerequisites for Identity Chaining.

#### What is a Trust Domain?

A trust domain is **the range managed by a single authorization server**. Technically, a group of resource servers for which a given OAuth 2.0 authorization server handles access token issuance and validation constitutes one trust domain.

![trust domain](./assets/identity-chaining-deep-dive/trust-domain.png)

Within the same domain, you can move freely with a single access token. The issue arises when crossing this boundary.

#### What is Federation?

For Identity Chaining to work, a **trust relationship (Federation)** must be established between Domain A and Domain B. Specifically, the following must hold:

![Federation](./assets/identity-chaining-deep-dive/federation.png)

- **Authorization Server A publishes its public key** (e.g., via JWKS URI)
- **Authorization Server B is configured to trust A's public key**

This "key trust" is the foundation of Federation. It's essentially the same thing we do with OpenID Connect SSO. Identity Chaining extends this SSO-style trust relationship **to API integration as well**.

---

### Identity Chaining's Complete Flow

Now for the main event. Let me show you the overall flow first, then dive into each step.

#### Complete Sequence Diagram

![identity chaining flow](./assets/identity-chaining-deep-dive/identity-chaining-flow.png)

The flow consists of six steps (A through F). Let's examine each one.

---

#### Step A: Authorization Server Discovery

For a Client (Domain A) to access a resource in Domain B, it must first know "where is Domain B's authorization server?"

Identity Chaining itself doesn't prescribe how discovery happens. Use one of the following:

| Method                                     | Description                                                                         |
| :----------------------------------------- | :---------------------------------------------------------------------------------- |
| **Static Configuration**                   | Hard-code AS B's URL in config or code. Simplest approach                           |
| **RFC 9728 (Protected Resource Metadata)** | Dynamically discover AS from the resource server's `authorization_servers` property |
| **Other Methods**                          | DNS, directory services, etc. (implementation-dependent)                            |

![Discovery](./assets/identity-chaining-deep-dive/discovery.png)

For scenarios like AI agents that dynamically discover resources, RFC 9728 is particularly important.

---

#### Step B/C: Token Exchange (Obtaining JWT Authorization Grant)

This is the first half of Identity Chaining. You ask your domain's authorization server for "give me a JWT authorization grant for Domain B." The protocol used is RFC 8693 (Token Exchange).

##### Request

```http
POST /auth/token HTTP/1.1
Host: as.a.org
Content-Type: application/x-www-form-urlencoded

grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Atoken-exchange
&resource=https%3A%2F%2Fas.b.org%2Fauth
&subject_token=ey...
&subject_token_type=urn%3Aietf%3Aparams%3Aoauth%3Atoken-type%3Aaccess_token
```

Here's what each parameter does:

| Parameter            | Required | Value                 | Description                                                 |
| :------------------- | :------- | :-------------------- | :---------------------------------------------------------- |
| `grant_type`         | ✅        | `token-exchange`      | RFC 8693 Token Exchange                                     |
| `subject_token`      | ✅        | Your current token    | The token you currently hold (access token, ID token, etc.) |
| `subject_token_type` | ✅        | Token type URI        | URI indicating the type of subject_token                    |
| `resource`           | ※        | AS B's URI            | Destination of the token (`audience` is exclusive)          |
| `audience`           | ※        | Logical name for AS B | Destination of the token (`resource` is exclusive)          |
| `scope`              |          | Scope value           | Scopes to include in the JWT authorization grant            |

※ Either `resource` or `audience` must be provided.

###### Authorization Server A's Processing

![token exchange](./assets/identity-chaining-deep-dive/token-exchange.png)

What actually matters is **policy evaluation**. Authorization Server A evaluates whether "this client is allowed to obtain an authorization grant for Domain B" based on its own policy. The RFC 8693 specification itself doesn't define the policy details, but in the Identity Chaining context, checks like "is Federation established?" and "can we issue an AT to this client?" are performed.

##### Response

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJo
   dHRwczovL2FzLmEub3JnL2F1dGgiLCJleHAiOjE2OTUyODQwOTIsImlhdCI6MTY5N
   TI4NzY5Miwic3ViIjoiam9obl9kb2VAYS5vcmciLCJhdWQiOiJodHRwczovL2FzLm
   Iub3JnL2F1dGgifQ.304Pv9e6PnzcQPzz14z-k2ZyZvDtP5WIRkYPScwdHW4",
  "token_type": "N_A",
  "issued_token_type": "urn:ietf:params:oauth:token-type:jwt",
  "expires_in": 60
}
```

This is where it gets interesting:

- **`token_type` is "N_A"**: Because this is not an OAuth access token but an "authorization grant." It's not something you present directly to a resource as a Bearer token.
- **`issued_token_type` is "jwt"**: Indicates it's returned in JWT format.
- **`expires_in` is 60**: JWT authorization grants should be short-lived. In this example, 60 seconds.
- **It's in the `access_token` field**: This naming is confusing, but per RFC 8693 spec constraints. The content is actually a JWT authorization grant.

##### Contents of the JWT Authorization Grant

The decoded JWT authorization grant looks like this:

```json
{
  "iss": "https://as.a.org/auth",
  "exp": 1695284092,
  "iat": 1695287692,
  "sub": "john_doe@a.org",
  "aud": "https://as.b.org/auth"
}
```

![jwt authorization grant claims](./assets/identity-chaining-deep-dive/jwt-auth-grant-claims.png)

The `aud` claim is particularly critical.

###### What the `aud` Claim Protects

The `aud` (audience) claim restricts "only AS B is authorized to receive and process this JWT." The specification recommends:

> The `aud` claim should be restricted to only the Authorization Server of Trust Domain B.

Why? If the `aud` claim included AS C's URL as well, AS B could pass this authorization grant to AS C to obtain a token for another domain. This restriction prevents that.

![grant](./assets/identity-chaining-deep-dive/grant.png)

---

#### Step D/E: JWT Bearer Grant (Obtaining Access Token)

In the first half, you obtained a JWT authorization grant. In the second half, you take it to Domain B's authorization server and request an access token. The protocol used is RFC 7523 (JWT Bearer Grant).

##### Request

```http
POST /auth/token HTTP/1.1
Host: as.b.org
Content-Type: application/x-www-form-urlencoded

grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Ajwt-bearer
&assertion=ey...
```

It's simple: set `grant_type` to `jwt-bearer` and put the JWT authorization grant in `assertion`. That's it.

Optionally, you can use `scope` or `resource` (RFC 8707) parameters to specify the access target.

###### Authorization Server B's Validation Process

![auth server validation](./assets/identity-chaining-deep-dive/auth-server-validation.png)

Four checks that make or break this:

1. **`aud` verification**: Does the JWT's `aud` match your (AS B's) identifier? RFC 7523 Section 3 / RFC 8414's issuer identifier is used.
2. **Signature verification**: Verify the JWT's signature with AS A's public key (obtained from JWKS endpoint or via AS Metadata).
3. **Subject identification**: Identify the user from the JWT's `sub` claim. If unidentifiable, reject.
4. **Federation policy**: Is the trust relationship with AS A established?

##### Response

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 60
}
```

Now you have a standard OAuth access token. The rest is straightforward API calls.

---

#### Step F: Resource Access

```http
GET /api/data HTTP/1.1
Host: resource.b.org
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

Nothing specific to Identity Chaining here. It's the same as a standard OAuth 2.0 flow.

---

## Claims Transcription: Converting Claims Across Domains

When Identity Chaining crosses domain boundaries, a challenge you can't avoid is **claims transformation**. The specification calls this **Claims Transcription**.

### Why Transformation is Necessary

![claims transcription](./assets/identity-chaining-deep-dive/claims-transcription.png)

The same user might be `johndoe@a.org` in Domain A but `doe.john@b.org` in Domain B. Without transforming the JWT authorization grant's `sub` claim to Domain B's format, Domain B's resource server wonders "who is this?"

### Four Transformation Patterns

The specification lists four patterns. Defined in RFC Section 2.5 and RFC 6 (Privacy Considerations).

| Pattern                    | Example Transformation                             | Timing                                                      | Purpose                                                |
| :------------------------- | :------------------------------------------------- | :---------------------------------------------------------- | :----------------------------------------------------- |
| **1. Subject Identifier**  | `sub: johndoe@a.org` → `sub: doe.john@b.org`       | During Token Exchange (AS A) or Assertion processing (AS B) | User ID normalization across domains                   |
| **2. Data Minimization**   | `{sub, account_type, limit, ssn}` → `{sub, limit}` | During Token Exchange (AS A) or Assertion processing (AS B) | Remove unnecessary personal info (privacy protection)  |
| **3. Scope Control**       | `scope: [read, write, admin]` → `scope: [read]`    | During Token Exchange (`scope` parameter)                   | Least privilege principle. Cannot grant broader rights |
| **4. JWT Claims Transfer** | Include `{amr, auth_time}` in AS B's AT            | During Assertion processing (AS B)                          | Propagate authentication metadata across domains       |

#### Detailed Explanation

**1. Subject Identifier Transformation**

Handling cases where users have different identifiers across domains. For example:

- Domain A: `johndoe@a.org` (email format)
- Domain B: `doe.john@b.org` (first.last format)

Whether AS A transforms during Token Exchange or AS B transforms during Assertion processing depends on Federation setup.

**2. Data Minimization**

A critical concept emphasized in RFC Section 6 (Privacy Considerations). When crossing federation boundaries, don't leak unnecessary personal information.

**Concrete example: Financial institution and payment gateway integration**

- AS A (financial institution) includes in JWT: `account_type: premium`, `transaction_limit: $10,000`, `ssn: 123-45-6789`, `account_balance: $50,000`
- AS B (payment gateway) needs only: `transaction_limit`

AS A removes unnecessary claims before sending to Domain B. This minimizes personal information leakage to Domain B.

**3. Scope Control (Downscoping)**

Clients can explicitly restrict to "read-only for this request." Uses RFC 8693's `scope` parameter.

Critical rule: **AS A must never grant broader rights than the original token**.

Example:
- Original token: `scope: read write delete admin`
- Client request: `scope: read`
- Returned JWT authorization grant: `scope: read` ✅

**4. JWT Authorization Grant Claims Transfer**

AS B can include claims from the received JWT authorization grant (like `amr`: authentication method, `auth_time`: authentication time) in the access token, preserving authentication metadata across domains.

---

## Application Patterns: Who Can Be the Client?

In the basic Identity Chaining flow, the "Client" was the main actor. But in real-world architectures, resource servers or authorization servers can also play the client role.

### Pattern 1: Resource Server as Client

The most common pattern in microservices integration. When Domain A's Service A calls Domain B's Service B, Service A plays the client role in Identity Chaining.

![resource server](./assets/identity-chaining-deep-dive/resource-server.png)

Prerequisite conditions:

- Resource Server A has a way to know Domain B's authorization server location (RFC 9728, etc.)
- Resource Server A can access Domain B's AS B and has proper client authentication capability

### Pattern 2: Authorization Server as Client

More complex, but necessary in these situations:

- Domain A's client doesn't know Domain B's authorization server exists
- Domain A's client cannot reach Domain B's authorization server over the network
- Domain B requires strict access control and cannot manage external client registration

![authorization server](./assets/identity-chaining-deep-dive/authorization-server.png)

In this case, AS A performs the entire sequence internally: "Token Exchange myself → generate JWT authorization grant → present to AS B." From the client's perspective, one request returns a Domain B access token, so you don't need to be aware you're crossing domains.

---

## Security Considerations

Identity Chaining is a powerful mechanism for cross-domain token propagation, but **improper implementation poses serious security risks**. Let me outline the points the specification clearly warns about. Defined in RFC Section 5 (Security Considerations).

### 1. Client Authentication (RFC 5.1)

![client authentication](./assets/identity-chaining-deep-dive/client-authentication.png)

Follow RFC 9700 (OAuth 2.0 Security BCP) best practices. Particularly, insufficient client authentication during Token Exchange risks lateral movement when tokens are compromised.

### 2. Authorization to Use subject_token (RFC 5.3)

**Authorization Server A must verify that the client presenting `subject_token` has the right to use it.**

Why? If a client's token is compromised, an attacker could use that token as `subject_token` and obtain access tokens for completely different domains (lateral movement).

![auth subject_token](./assets/identity-chaining-deep-dive/auth-subject-token.png)

To prevent this, AS A needs an authorization policy to confirm "this client is authorized to perform Token Exchange on behalf of this subject_token's subject."

### 3. Don't Issue Refresh Tokens (RFC 5.4)

The specification is clear: **Domain B's authorization server must never issue Refresh Tokens.**

Reasons:

- When access token expires, just re-present the JWT authorization grant to get a new token
- If JWT authorization grant also expires, re-run Token Exchange
- Issuing Refresh Tokens risks Domain B tokens continuing to refresh even after the Domain A session ends (logout, etc.)

![refresh token](./assets/identity-chaining-deep-dive/refresh-token.png)

### 4. Replay Attacks on JWT Authorization Grant (RFC 5.5)

JWT authorization grants are bearer tokens. If an attacker intercepts one, they can re-present it to AS B to obtain access tokens. The specification recommends these countermeasures:

| Countermeasure            | Effect                                                    |
| :------------------------ | :-------------------------------------------------------- |
| **Short Expiration**      | Minimize the time window for attack                       |
| **Single-Use**            | Prevent reuse of the same JWT authorization grant         |
| **Client Authentication** | The client presenting the grant must authenticate to AS B |

### 5. Sender Constraining (RFC 5.2)

To overcome bearer token limitations, "sender constraining"—tying tokens to specific clients—is also recommended.

The specification's Appendix describes this as **Delegated Key Binding**:

- AS A validates the client's key material (proof of possession key)
- AS A includes that key info as `requested_cnf` claim in the JWT authorization grant
- AS B issues an access token with `cnf` claim
- Client uses that key to generate DPoP proof or establish mTLS session to access the resource

---

## Authorization Server Metadata

Identity Chaining adds one new parameter to AS Metadata.

```json
{
  "issuer": "https://as.example.com",
  "token_endpoint": "https://as.example.com/token",
  "identity_chaining_requested_token_types_supported": [
    "urn:ietf:params:oauth:token-type:jwt",
    "urn:ietf:params:oauth:token-type:access_token"
  ]
}
```

**`identity_chaining_requested_token_types_supported`**: List of token types that can be specified as `requested_token_type` in Token Exchange requests. By publishing this, clients can dynamically confirm "does this authorization server support Identity Chaining?" and "what token types does it support?"

However, due to information leakage concerns, some implementations don't disclose all supported types.

---

## Privacy Considerations: Protecting Privacy Across Domain Boundaries

Privacy considerations when Identity Chaining crosses domains. Defined in RFC Section 6.

### Prevent Excessive Information Leakage

In OAuth federation (multi-domain token exchange), user data can leak unnecessarily if excessive or unnecessary information is included in tokens.

**Warning from RFC:**

> In OAuth federation, tokens and claims are exchanged between disparate trust domains. If excessive or unnecessary user data is included in these tokens, it may lead to unintended privacy consequences.

#### Concrete Example: Financial Institution Integrating with Payment Gateway

**Domain A (financial institution) includes in JWT:**

```
- User identifier
- Account type (premium / standard)
- Transaction limit ($10,000)
- Social Security number (123-45-6789)
- Account balance ($50,000)
```

**Domain B (payment gateway) actually needs:**

```
- User identifier
- Transaction limit ($10,000) ← This only
```

→ AS A must use **Claims Transcription (Data Minimization)** to remove unnecessary information before sending to Domain B.

### Ensure Privacy Policy Consistency Between Domains

Inconsistent privacy practices in federation pose major risks.

#### Pre-Federation Checklist

| Verification Item       | AS A       | AS B     | Resolution                       |
| :---------------------- | :--------- | :------- | :------------------------------- |
| **Data Protection Law** | GDPR       | CCPA     | Configure claims satisfying both |
| **Retention Period**    | 90 days    | 1 year   | Align to stricter (90 days)      |
| **Explicit Consent**    | Required   | Optional | Standardize to AS A's rules      |
| **Third-Party Sale**    | Prohibited | Allowed  | Prohibit in federation contract  |

When Domain A (strict) and Domain B (permissive) federate, the principle is **align to the stricter policy**.

#### Identity Chaining Metadata: What to Share

Deciding what metadata to include in JWTs or Access Tokens is a critical federation design step.

![identity chaining metadata](./assets/identity-chaining-deep-dive/identity-chaining-metadata.png)

In federation contracts, examine whether **each metadata is truly necessary and justified from a data minimization perspective**.

---

## Real-World Use Cases

Let me consolidate the use cases mentioned in the specification's Appendix.

#### 1. Multi-Cloud / Hybrid Environment User Context Preservation

![real world use case](./assets/identity-chaining-deep-dive/real-world.png)

Even in mixed on-premises and cloud environments, the original user's ID and authorization context flow to each workload. Intermediate services maintain the request context (who initiated it, which services it traversed) for authorization decisions.

#### 2. CI/CD Pipeline External Resource Access

![CI/CD](./assets/identity-chaining-deep-dive/ci-cd.png)

When CI pipelines access external resources, build metadata (commit hash, repo name, etc.) can be safely propagated via Identity Chaining. Static API key management becomes unnecessary, and the resource side enables fine-grained access control.

#### 3. SSO to API Integration Extension

![sso](./assets/identity-chaining-deep-dive/sso.png)

For API integration between multiple SaaS apps with SSO relationships through an IdP, no additional user consent is required. Access control is based on IdP policies.

#### 4. Cross-Domain API Authorization

Email client accessing third-party calendar API. The email client and calendar service don't need prior relationships; they can integrate if they share a common IdP.

---

## Relationship to ID-JAG

"What's the difference between Identity Chaining and ID-JAG?" This is an important question.

**ID-JAG (Identity Assertion JWT Authorization Grant, draft-ietf-oauth-identity-assertion-authz-grant)** is the "enterprise SSO-specialized profile" of Identity Chaining.

![id jag](./assets/identity-chaining-deep-dive/id-jag.png)

| Aspect                           | Identity Chaining                   | ID-JAG                      |
| :------------------------------- | :---------------------------------- | :-------------------------- |
| **Scope**                        | Generic. Any domain boundary        | Enterprise SSO (via IdP)    |
| **Foundation**                   | Authorization server federation     | SSO (OIDC/SAML) trust       |
| **subject_token**                | Anything (access token, etc.)       | ID Token or SAML assertion  |
| **JWT Authorization Grant Type** | No specific type                    | `typ: oauth-id-jag+jwt`     |
| **Policy Authority**             | Each authorization server           | Enterprise IdP (IT admin)   |
| **Typical Environment**          | Multi-cloud, CI/CD, API integration | SaaS integration, AI agents |

Identity Chaining is a generic protocol for "how to obtain Domain B's token from Domain A," while ID-JAG is a concrete implementation of "how to use ID Assertions from SSO IdPs for API integration."

---

## Industry Adoption (2026)

### Keycloak

Open-source identity provider Keycloak added preview support for JWT Authorization Grant in version 26.5 (January 2026). Based on RFC 7523, combined with existing RFC 8693 support, Identity Chaining flows can be implemented.

### Okta

Aaron Parecki, co-author of ID-JAG and Okta employee, is leading **Cross App Access (XAA)** initiative for ID-JAG / Identity Chaining implementation.

### IETF

draft-ietf-oauth-identity-chaining-08 was published in February 2026, with an expiration date of August 2026. It has Standards Track status (aiming for standardization rather than informational), and discussions continue toward formal RFC publication.

---

## Summary

Remember these essentials on Identity Chaining (draft-ietf-oauth-identity-chaining-08):

- **RFC 8693 + RFC 7523 combination**. Not a new protocol, but a profile of existing specifications.
- **Token Exchange** obtains JWT authorization grants from your authorization server; **JWT Bearer Grant** requests access tokens from the peer's authorization server. Two-step flow.
- **`aud` claim** restricting the destination is key to preventing forwarding and replay attacks.
- **Claims Transcription** handles ID transformation, data minimization, and scope control across domains.
- **Works for any scenario crossing domain boundaries**: multi-cloud, CI/CD, SaaS integration, AI agents.
- **No Refresh Tokens issued**. JWT authorization grants themselves serve as short-lived, reusable assertions.

Still in IETF draft phase, but with Standards Track status and active RFC publication discussions. If you're designing cross-domain access control in multi-cloud or microservices environments, understanding this specification's principles now will serve you well.

---

---

## References

- [OAuth Identity and Authorization Chaining Across Domains (draft-ietf-oauth-identity-chaining-08)](https://datatracker.ietf.org/doc/draft-ietf-oauth-identity-chaining/)
- [RFC 8693 - OAuth 2.0 Token Exchange](https://www.rfc-editor.org/rfc/rfc8693.html)
- [RFC 7523 - JWT Profile for OAuth 2.0 Client Authentication and Authorization Grants](https://www.rfc-editor.org/rfc/rfc7523.html)
- [RFC 6749 - The OAuth 2.0 Authorization Framework](https://www.rfc-editor.org/rfc/rfc6749)
- [RFC 8414 - OAuth 2.0 Authorization Server Metadata](https://www.rfc-editor.org/rfc/rfc8414.html)
- [RFC 9728 - OAuth 2.0 Protected Resource Metadata](https://www.rfc-editor.org/rfc/rfc9728.html)
- [RFC 9700 - Best Current Practice for OAuth 2.0 Security](https://www.rfc-editor.org/rfc/rfc9700.html)
