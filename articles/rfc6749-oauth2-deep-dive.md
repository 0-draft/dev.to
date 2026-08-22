---
title: 'RFC 6749 Deep Dive: Understanding OAuth 2.0 Design Decisions from the Specification'
published: true
description: 'A line-by-line walkthrough of RFC 6749 covering all Grant Types, endpoints, and security design . Also covers the evolution toward OAuth 2.1.'
tags:
  - oauth
  - security
  - authentication
  - oidc
series: OAuth
id: 3277973
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/rfc6749-oauth2-deep-dive/cover.png'
date: '2026-02-23T13:11:37Z'
---

## Introduction

Everyone has heard of OAuth 2.0. If you have ever clicked a "Sign in with Google" button, you are already benefiting from it.

But what if someone asked you these questions?

- "Explain the difference between Authorization Code Grant and Implicit Grant from a security perspective."
- "Why should Client Credentials Grant not issue a Refresh Token?"
- "What exactly does PKCE protect against?"

Surprisingly few people can answer these fluently. Getting by with "it just works somehow" is a recipe for authorization bugs and vulnerabilities down the road.

This article dissects **RFC 6749** (The OAuth 2.0 Authorization Framework) based on the original specification, building a fundamental understanding of OAuth 2.0's design philosophy. By the time you finish reading, the "why" behind each design decision should click into place.

---

## 1. The Problem OAuth 2.0 Solved

Before OAuth 2.0, the only way for a third-party application to access a user's resources was to **hand over the user's password directly**.

![oauth2 resolve](./assets/rfc6749-oauth2-deep-dive/oauth2-resolve.png)

This approach has fatal problems:

| Problem                     | Description                                                                    |
| --------------------------- | ------------------------------------------------------------------------------ |
| **Password Storage**        | Third-party must store the password in plaintext                               |
| **Excessive Access**        | App can access all user resources (no scope restriction)                       |
| **No Selective Revocation** | Cannot revoke access for a single app (password change = all apps invalidated) |
| **Cascading Breach**        | One app's breach → all of the user's data is at risk                           |

OAuth 2.0's approach is dead simple. **Use an "access token" instead of a password.**

![oauth2 resolve2](./assets/rfc6749-oauth2-deep-dive/oauth2-resolve2.png)

The password never touches the third-party. Tokens carry scope (permission boundaries) and an expiration. Each app's token can be revoked individually.

This is the starting point of OAuth 2.0.

---

## 2. The Four Roles

RFC 6749 §1.1 defines the **four roles** in OAuth 2.0. Without a precise understanding of these, the Grant Type discussions that follow will not make sense.

![4 roles](./assets/rfc6749-oauth2-deep-dive/4-roles.png)

| Role                     | RFC Definition                                                                               | Example                        |
| ------------------------ | -------------------------------------------------------------------------------------------- | ------------------------------ |
| **Resource Owner**       | An entity capable of granting access to a protected resource                                 | End user (you)                 |
| **Client**               | An application making protected resource requests on behalf of the resource owner            | Web app, mobile app, CLI tool  |
| **Authorization Server** | The server issuing access tokens after authenticating the client and obtaining authorization | Google OAuth, Ory Hydra, Auth0 |
| **Resource Server**      | The server hosting the protected resources, accepting access tokens                          | Google Drive API, GitHub API   |

> The authorization server and resource server **may be the same server or separate** (RFC 6749 §1.1). A typical pattern is one authorization server (e.g., Google) issuing tokens to multiple APIs (Gmail, Drive, Calendar).

---

## 3. Protocol Endpoints

Before diving into Grant Types, let's nail down the **three endpoints** used in the OAuth 2.0 protocol.

![protocol endpoints](./assets/rfc6749-oauth2-deep-dive/proto-endpoints.png)

| Endpoint                   | Location             | Role                              | HTTP Method            |
| -------------------------- | -------------------- | --------------------------------- | ---------------------- |
| **Authorization Endpoint** | Authorization Server | Interact with user to get consent | GET (MUST), POST (MAY) |
| **Token Endpoint**         | Authorization Server | Exchange grant for access token   | POST (MUST)            |
| **Redirection Endpoint**   | Client               | Receive response from auth server | —                      |

- Authorization Endpoint and Token Endpoint **require TLS** (RFC 6749 §3.1, §3.2)
- Confidential Clients **MUST authenticate** at the Token Endpoint (§3.2.1)

---

## 4. Client Types

RFC 6749 §2.1 classifies clients into two types. This classification directly determines which Grant Type should be used.

![client type](./assets/rfc6749-oauth2-deep-dive/client-type.png)

| Type             | `client_secret` Storage   | Example                             | Recommended Grant Type        |
| ---------------- | ------------------------- | ----------------------------------- | ----------------------------- |
| **Confidential** | ✅ Can store securely      | Rails / Django / Go server-side app | Authorization Code            |
| **Public**       | ❌ Extractable from source | React SPA, iOS/Android app, CLI     | Authorization Code + **PKCE** |

---

## 5. Client Authentication — Who Uses `client_secret` and When?

Before diving into Grant Types, let's bust a common misconception.

> ❌ "Only Client Credentials Grant requires `client_id` and `client_secret`"

Wrong. The correct understanding is:

> ✅ **Whether `client_secret` (client authentication) is required depends on the Client Type, not the Grant Type**

RFC 6749 §3.2.1 states:

> Confidential clients or other clients issued client credentials **MUST authenticate** with the authorization server when making requests to the **token endpoint**.

In other words, **for every Grant Type that uses the Token Endpoint, Confidential Clients must authenticate**.

![client secret usecase](./assets/rfc6749-oauth2-deep-dive/client-secret-usecase.png)

### Client Authentication by Grant Type

| Grant Type                    | `client_id` | `client_secret` (auth)      | Why                                                                                   |
| ----------------------------- | ----------- | --------------------------- | ------------------------------------------------------------------------------------- |
| **Authorization Code**        | ✅ Required  | ✅ Required for Confidential | Authentication when exchanging auth code at Token Endpoint (§4.1.3)                   |
| **Authorization Code + PKCE** | ✅ Required  | ❌ Not required              | Public Client cannot hold a secret → PKCE protects instead                            |
| **Implicit**                  | ✅ Required  | ❌ Not required              | Does not use Token Endpoint, so there is no opportunity to authenticate (§4.2)        |
| **Password**                  | ✅ Required  | ✅ Required for Confidential | Authentication when sending password at Token Endpoint (§4.3.2)                       |
| **Client Credentials**        | ✅ Required  | ✅ **Always required**       | This Grant Type is **Confidential only** (§4.4), so authentication is always required |

Client Credentials Grant appears "special" only because the Grant Type is **exclusive to Confidential Clients** (§4.4). Since only Confidential Clients can use it, `client_secret` is always needed. That's all there is to it.

### Authentication Methods

There are two primary ways to send `client_secret` (§2.3.1):

```http
# Method 1: HTTP Basic Authentication (recommended)
POST /token HTTP/1.1
Authorization: Basic BASE64(client_id:client_secret)

# Method 2: Include in POST body (not recommended, but permitted)
POST /token HTTP/1.1
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code&code=xxx&client_id=ID&client_secret=SECRET
```

---

## 6. Grant Types — Complete Guide

This is the heart of RFC 6749. OAuth 2.0 defines **four Grant Types** (authorization grant methods), each with entirely different use cases and security properties.

### 6.1 Authorization Code Grant

**The most important Grant Type.** Designed for Confidential Clients. It is a redirect-based flow where the access token never passes through the user's browser — its greatest security advantage.

![auth code grant](./assets/rfc6749-oauth2-deep-dive/auth-code-grant.png)

**Security highlights**:

- The `state` parameter is **CSRF protection**. The client generates a random value per request and verifies it matches on callback (§10.12)
- Authorization codes are **single-use**. If a second use is detected, all tokens issued with that code should be revoked (§4.1.2)
- Authorization codes should have a **maximum lifetime of 10 minutes** (§4.1.2)
- The Token Request (④) happens over a **back-channel** (server-to-server), so the access token is never exposed to the browser

#### HTTP Request Example

```http
POST /token HTTP/1.1
Host: auth.example.com
Authorization: Basic czZCaGRSa3F0MzpnWDFmQmF0M2JW
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&code=SplxlOBeZQQYbYS6WxSbIA
&redirect_uri=https%3A%2F%2Fclient.example.com%2Fcallback
```

#### Token Response Example

```json
{
  "access_token": "2YotnFZFEjr1zCsicMWpAA",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "tGzv3JOkF0XG5Qx2TlKWIA"
}
```

---

### 6.2 Implicit Grant ⚠️ Deprecated

A Grant Type formerly designed for SPAs. **It returns the access token directly from the Authorization Endpoint without using the Token Endpoint.**

![implicit flow](./assets/rfc6749-oauth2-deep-dive/implicit-flow.png)

> **⚠️ This Grant Type is officially removed in OAuth 2.1.** Never use it in new implementations.

**Why it was deprecated:**

1. **Access token exposed in URI** — The URL fragment `#access_token=xxx` can leak through browser history and referrer headers. **PKCE cannot fix this problem.** PKCE prevents authorization code interception — it cannot address the structural flaw of an access token being placed directly in the URI
2. **No client authentication** — Public Clients cannot use `client_secret`, making token hijacking undetectable
3. **Cannot issue Refresh Token** — Explicitly prohibited by RFC 6749 §4.2.2. Users must be dragged back through re-authorization every time the token expires

#### Why Was Implicit Needed in the First Place?

SPA (Single Page Application) code runs in the browser. Source code is readable by **anyone** via DevTools or View Source. Embedding a `client_secret` does not make it "secret."

```javascript
// SPA code — downloaded to the user's browser
const CLIENT_SECRET = "super_secret_123";  // ← Visible in DevTools. Not a secret.
```

That is why SPAs are classified as **Public Clients** (clients that cannot securely store a `client_secret`). At the time, Authorization Code Grant required `client_secret` at the Token Request, making it unusable for Public Clients.

```text
2012 (when RFC 6749 was published) — available options:
  SPA needs access to protected resources
  → Authorization Code Grant requires client_secret → cannot use
  → Client Credentials Grant is for M2M (no user) → cannot use
  → Implicit Grant is the only option → access token exposed in URI 💀 (reluctantly accepted)
```

#### PKCE Did Not "Fix" Implicit — It Made Implicit Unnecessary

PKCE (2015, RFC 7636) changed the game. By protecting with a `code_verifier` / `code_challenge` pair instead of `client_secret`, **Public Clients could now use Authorization Code Grant.**

```text
After PKCE — available options:
  SPA needs access to protected resources
  → Authorization Code + PKCE → ✅ secure without client_secret
  → Access token received via back-channel (Token Endpoint)
  → Access token never appears in the URI
  → No reason to use Implicit anymore → deprecated
```

**The access-token-in-URI problem of Implicit was solved by deprecating the entire flow.** It wasn't patched — it was thrown away.

> Note that Implicit Grant is a **browser-required** flow (redirect-based) and cannot be used for M2M (machine-to-machine) communication. M2M has no user and no browser, so Client Credentials Grant is used from the start.

---

### 6.3 Resource Owner Password Credentials Grant ⚠️ Deprecated

A Grant Type where the user **hands their password directly to the client**. Only intended for cases where a high degree of trust exists between the resource owner and the client (e.g., the OS login screen).

![resouce owner password credentials grant](./assets/rfc6749-oauth2-deep-dive/resource-password.png)

> **⚠️ This Grant Type is also removed in OAuth 2.1.** It was defined as a migration path from HTTP Basic/Digest authentication to OAuth and is not recommended for new use.

---

### 6.4 Client Credentials Grant

A Grant Type for machine-to-machine (M2M) communication **where no user is involved**. Used when the client accesses its own resources.

![client credentials grant](./assets/rfc6749-oauth2-deep-dive/client-credentials-grant.png)

**Key points**:

- Confidential Clients **only** (§4.4)
- Refresh Token is **SHOULD NOT** (§4.4.3) — the client can always obtain a new token with its own credentials, so a Refresh Token serves no purpose
- Typical use cases: batch jobs, CI/CD pipelines, inter-microservice communication

#### Why Is `client_secret` Alone Sufficient?

Compared to Authorization Code Grant, Client Credentials Grant requires no authorization code, no login screen — just `client_secret` for a token. Intuitively, you might wonder: "Is that secure enough?"

The answer: **the resources being accessed are different, so the required proof is different.**

![client secret](./assets/rfc6749-oauth2-deep-dive/client_secret.png)

In Client Credentials Grant, **the client IS the Resource Owner** (§4.4). You don't need anyone else's permission to access your own resources. Proving you are who you say you are is sufficient.

In contrast, Authorization Code Grant accesses **someone else's (the user's) resources**. So the resource owner's (user's) approval = the authorization code is additionally required.

|                      | Authorization Code                    | Client Credentials               |
| -------------------- | ------------------------------------- | -------------------------------- |
| **Whose resources?** | The user's                            | The client's own                 |
| **User approval**    | ✅ Required (authorization code)       | ❌ Not needed (no user)           |
| **Client proof**     | ✅ Required (client_secret)            | ✅ Required (client_secret)       |
| **RFC phrasing**     | Client acts **on behalf of** the user | Client **is** the Resource Owner |

In short, `client_secret` is **used in both**. Client Credentials Grant looks simpler because the "user approval" layer is simply not needed — not because security was relaxed.

---

### 6.5 Grant Type Comparison Summary

![grant type comparision](./assets/rfc6749-oauth2-deep-dive/type-comparision.png)

| Grant Type                    | User | Client Type  | Refresh Token | Recommendation |
| ----------------------------- | ---- | ------------ | ------------- | -------------- |
| **Authorization Code**        | ✅    | Confidential | ✅             | ✅ Recommended  |
| **Authorization Code + PKCE** | ✅    | Public       | ✅             | ✅ Recommended  |
| **Implicit**                  | ✅    | Public       | ❌             | ⛔ Deprecated   |
| **Password**                  | ✅    | High-trust   | ✅             | ⛔ Deprecated   |
| **Client Credentials**        | ❌    | Confidential | ❌             | ✅ M2M standard |

---

## 7. Access Tokens and Refresh Tokens

### Access Token

- A credential for accessing protected resources (§1.4)
- **Opaque** to the client — the spec does not prescribe a format
- Represents scope, lifetime, and other access attributes
- RFC 6749 does not define the format. JWT (RFC 9068) or opaque tokens are implementation-dependent

### Refresh Token

- A credential for obtaining new access tokens (§1.5)
- Sent **only to the authorization server** (never to the resource server)
- Issuance is optional

A Refresh Token is issued alongside the access token during Authorization Code Grant. From that point on, new access tokens can be obtained **without any user interaction** — using only the Refresh Token. Think of it as completing the initial "user approval" via Authorization Code Grant, then being able to **repeat token renewal over a back-channel only**, much like Client Credentials Grant.

![refresh token](./assets/rfc6749-oauth2-deep-dive/refresh-token.png)

#### Can You Refresh Infinitely?

**RFC 6749 itself defines no limit on refresh count** (§6). It is left to the discretion of the authorization server.

However, allowing unlimited refresh would make the risk of a leaked Refresh Token permanent. In practice, **limits are almost always applied**:

| Limitation Method          | Description                                                                 |
| -------------------------- | --------------------------------------------------------------------------- |
| **Expiration**             | e.g., Refresh Token expires after 30 or 90 days → user must re-login        |
| **Refresh Token Rotation** | Replaced with a new Refresh Token on every use; old one immediately revoked |
| **Maximum Use Count**      | Expires after N refreshes                                                   |
| **Absolute Lifetime**      | Expires X days from initial issuance, regardless of renewal activity        |

#### Refresh Token Rotation — Detecting Theft

**Refresh Token Rotation** is strongly recommended by RFC 9700 (Security BCP) and OAuth 2.1.

![refresh token rotation](./assets/rfc6749-oauth2-deep-dive/refresh-token-rotation.png)

By making Refresh Tokens **single-use** and replacing them on every refresh:

1. **A stolen old Refresh Token** is already invalidated and cannot be used
2. **If the attacker uses it first**, the legitimate client's next attempt triggers fraud detection, revoking all tokens

#### Rotation and Expiration Should Be Combined

"If you have Rotation, do you still need expiration?" These two have **different threat coverage**, so both are recommended.

Rotation detects theft through collision **when both the attacker and the legitimate client attempt to use the token**. If the user stops using the app, there is no collision from the legitimate side, and the attacker can keep refreshing indefinitely. **An expiration ensures forced invalidation after 30 days, even if the user walks away.**

| Limitation                | Threat Coverage                                        | Sufficient Alone?                              |
| ------------------------- | ------------------------------------------------------ | ---------------------------------------------- |
| **Rotation only**         | Token theft (detected via collision)                   | ❌ Exploitable forever if user stops using app  |
| **Expiration only**       | Long-term unauthorized access                          | ❌ Cannot detect theft within the expiry window |
| **Rotation + Expiration** | Covers both short-term theft and long-term abandonment | ✅ Recommended                                  |

#### Refresh Tokens Are Opaque — Expiration Is Managed in the DB

"Isn't managing expiration while rotating tokens every time complicated?" No, it's not.

Access Tokens are often JWTs (self-contained, with `exp` embedded inside), but **Refresh Tokens are almost always opaque (just random strings)**, with expiration managed **in the authorization server's database**.

```text
Access Token (JWT):  eyJhbGciOiJSUzI1NiIs... (exp embedded inside)
Refresh Token:       tGzv3JOkF0XG5Qx2TlKWIA  (just a random string — no embedded info)
```

Managing this in the DB is straightforward — just INSERT a new row with `expires_at` on each rotation. There are **two patterns** for setting the expiration:

| Pattern      | How `expires_at` Is Set                  | Effect                                                                          |
| ------------ | ---------------------------------------- | ------------------------------------------------------------------------------- |
| **Sliding**  | New token's issue time + 30 days         | Expiration extends on each rotation (active users never need to re-login)       |
| **Absolute** | Inherit `expires_at` from original token | Expires at original deadline regardless of rotations (forces periodic re-login) |

Ory Hydra ships with Refresh Token Rotation enabled by default, and allows setting the expiration via `ttl.refresh_token` (both mechanisms combined).

---

## 8. Scope

Scope defines the range of access permissions the client requests (§3.3).

```text
scope = scope-token *( SP scope-token )
```

- Space-delimited list of strings
- The authorization server may **ignore all or part** of the requested scope
- If the issued token's scope differs from the request, the response MUST include `scope`

```http
GET /authorize?response_type=code
  &client_id=xxx
  &scope=openid%20profile%20email
  &redirect_uri=https://client/callback
  &state=abc123
```

![scope](./assets/rfc6749-oauth2-deep-dive/scope.png)

---

## 9. PKCE — The Savior of Public Clients

PKCE (Proof Key for Code Exchange / RFC 7636) is an extension to prevent **authorization code interception attacks**. It becomes **mandatory for all client types** in OAuth 2.1.

### Attack Scenario (Without PKCE)

1. User initiates authorization flow from a SPA
2. Authorization code is delivered to the `redirect_uri` query
3. **A malicious app registers the same redirect_uri scheme** → intercepts the authorization code
4. Malicious app exchanges the intercepted code at the Token Endpoint → access token stolen

### How PKCE Works

![pkce](./assets/rfc6749-oauth2-deep-dive/pkce.png)

**Why this is secure:**

- `code_challenge` is a SHA-256 hash, so `code_verifier` cannot be reverse-engineered
- Even if the authorization code is intercepted, it cannot be exchanged at the Token Endpoint without the `code_verifier`
- **Only the legitimate client** holds the `code_verifier`

---

## 10. Security Design (Essence of RFC 6749 §10)

Section 10 of RFC 6749 is arguably the most critical section in the 76-page specification. Here is a summary of the key threats and countermeasures.

![security design](./assets/rfc6749-oauth2-deep-dive/security-design.png)

| Threat                     | RFC Section  | Countermeasure                                       |
| -------------------------- | ------------ | ---------------------------------------------------- |
| **CSRF**                   | §10.12       | Bind random value to `state` parameter               |
| **Auth code interception** | §10.5, §10.6 | PKCE, strict `redirect_uri` matching                 |
| **Token leakage**          | §10.3        | TLS required, short token lifetimes                  |
| **Client impersonation**   | §10.2        | Client authentication, pre-registered `redirect_uri` |
| **Open redirector**        | §10.15       | Exact `redirect_uri` matching                        |
| **Refresh Token theft**    | §10.4        | Refresh Token Rotation, sender-constrained tokens    |

---

## 11. RFC 6749 → OAuth 2.1 Evolution

RFC 6749 was published in 2012. Drawing on over a decade of real-world deployment experience, OAuth 2.1 (draft-ietf-oauth-v2-1) is being developed.

![oauth 2.1](./assets/rfc6749-oauth2-deep-dive/oauth21.png)

### Key Changes

| Item                    | RFC 6749                | OAuth 2.1                       |
| ----------------------- | ----------------------- | ------------------------------- |
| **Implicit Grant**      | Defined                 | ❌ **Removed**                   |
| **Password Grant**      | Defined                 | ❌ **Removed**                   |
| **PKCE**                | Optional (separate RFC) | ✅ **Mandatory for all clients** |
| **Redirect URI**        | Partial match OK        | ✅ **Exact match required**      |
| **Refresh Token**       | Rotation optional       | ✅ **Rotation recommended**      |
| **Bearer Token in URL** | Allowed                 | ❌ **Prohibited**                |

---

## 12. Related RFC Map

RFC 6749 does not stand alone. A practical authorization infrastructure requires the surrounding RFCs as well.

![related rfc](./assets/rfc6749-oauth2-deep-dive/related-rfc.png)

| RFC       | Name                 | One-Liner                                        |
| --------- | -------------------- | ------------------------------------------------ |
| RFC 6750  | Bearer Token Usage   | How to "use" tokens (Authorization header, etc.) |
| RFC 7636  | PKCE                 | Prevents authorization code interception         |
| RFC 7009  | Token Revocation     | API for invalidating tokens                      |
| RFC 7662  | Token Introspection  | API for querying token metadata                  |
| RFC 9126  | PAR                  | Pre-register authorization requests via POST     |
| RFC 8628  | Device Authorization | For input-constrained devices (TV, IoT)          |
| RFC 9068  | JWT Access Token     | Standardized JWT format for Access Tokens        |
| OIDC Core | OpenID Connect       | Adds "authentication" on top of OAuth 2.0        |

---

## Conclusion

RFC 6749 is a 76-page document, but its core is simple:

1. **Instead of handing over a password, hand over a token**
2. **Tokens have scope and expiration**
3. **How you obtain the token (Grant Type) depends on the use case**

With an understanding of OAuth 2.0's design philosophy, questions like "Why is PKCE necessary?", "Why is Implicit being deprecated?", and "Why is Refresh Token Rotation recommended?" all follow naturally.

Reading specs is arduous work, but it is far safer than continuing to treat the authorization layer as a black box.

## References

- [RFC 6749 - The OAuth 2.0 Authorization Framework](https://datatracker.ietf.org/doc/html/rfc6749)
- [RFC 6750 - The OAuth 2.0 Authorization Framework: Bearer Token Usage](https://datatracker.ietf.org/doc/html/rfc6750)
- [RFC 7636 - Proof Key for Code Exchange by OAuth Public Clients](https://datatracker.ietf.org/doc/html/rfc7636)
- [OAuth 2.1 Draft](https://datatracker.ietf.org/doc/draft-ietf-oauth-v2-1/)
- [OAuth 2.0 Security Best Current Practice](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-security-topics)
