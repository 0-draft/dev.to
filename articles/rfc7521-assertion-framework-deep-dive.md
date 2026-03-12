---
title: 'RFC 7521 Deep Dive: Assertion Framework — Using SAML and JWT in OAuth 2.0'
published: false
description: 'A deep dive into RFC 7521, the abstract framework for using SAML and JWT assertions as client authentication and authorization grants in OAuth 2.0, with diagrams.'
tags:
  - oauth
  - security
  - authentication
series: OAuth
---

# Introduction

In OAuth 2.0, client authentication typically uses a `client_id` and `client_secret` pair (or PKCE). For obtaining access tokens, common authorization grants include the "Authorization Code Grant" involving user authentication, and the "Client Credentials Grant" used for batch processing.

However, in actual enterprise environments or complex system integrations, the following requirements may arise:

* "We already have a robust authentication infrastructure using SAML or JWT within the company. Can we leverage this for OAuth 2.0 client authentication?"
* "The user is offline, and the server (client) wants to act on the user's behalf. Can we get an access token using a pre-approved 'assertion' without handing over a password?"
* "I don't want to send 'shared secrets' like client secrets over the network. I want to authenticate with a token signed using public-key cryptography."

**RFC 7521 (Assertion Framework for OAuth 2.0 Client Authentication and Authorization Grants)** was created to solve these challenges.

This post walks through what RFC 7521 solves and how it works, using diagrams along the way.

---

## 1. What is an Assertion?

To understand RFC 7521, we first need to clarify the definition of "assertion."

> An assertion is a package of information that allows identity and security information to be shared across security domains.（RFC 7521 Section 3）

Think of it as a digitally signed statement saying **"Here's who I am and what I'm allowed to do."**

The two common formats for assertions are:

* **SAML 2.0 Assertions** (XML format)
* **JSON Web Tokens (JWTs)** (JSON format)

---

### The Position of RFC 7521: "Abstract Framework"

Here is an important point. **RFC 7521 itself does not define a specific data format (whether XML or JSON).** It is merely a framework specification that defines the **abstract rules and HTTP parameters** for using assertions in OAuth 2.0.

When actually implementing, you combine it with the following "profiles (concrete specifications)" according to the assertion format.

| Format       | Abstract Framework Specification | Concrete Specification (Profile) |
| :----------- | :------------------------------- | :------------------------------- |
| **General**  | **RFC 7521** (this article)      | -                                |
| **SAML 2.0** | (Based on RFC 7521)              | **RFC 7522**                     |
| **JWT**      | (Based on RFC 7521)              | **RFC 7523**                     |

Think of it as RFC 7521 defining the container, and RFC 7522/7523 filling it in for each specific format.

---

## 2. Two Issuance Patterns for Assertions

Who creates the assertion? RFC 7521 assumes two main patterns.

### Pattern A: Issued by a Third Party (Token Service)

This is a pattern where a trusted central authentication server (Token Service / STS) exists, issues an assertion, and the client presents it to the OAuth 2.0 authorization server (Relying Party). This is often used when integrating enterprise single sign-on (SSO) infrastructure with an OAuth server.

![sts](./assets/rfc7521-assertion-framework-deep-dive/sts.png)

### Pattern B: Self-Issued

This is a pattern where the client itself has a private key (asymmetric key), creates and signs an assertion (e.g., JWT), and presents it to the authorization server. This is often used as a simple authentication method to avoid sending passwords (shared secrets) over the network.

![self issued](./assets/rfc7521-assertion-framework-deep-dive/self-issued.png)

### Reference: Bearer vs. Holder-of-Key

Section 3 of RFC 7521 contrasts two forms of assertion ownership:

* **Bearer Assertions**: Anyone possessing the assertion can use it. If leaked, it can be misused, making transport-level protection like TLS mandatory. RFC 7521 assumes this format by default.
* **Holder-of-Key Assertions**: Requires the presenter to prove possession of an additional cryptographic key (Proof-of-Possession). This is more secure but is not directly supported by this RFC and requires additional specifications.

---

## 3. The Two Major Use Cases of Assertions

Here's the core of what RFC 7521 actually defines: **two independent use cases** for incorporating assertions into OAuth 2.0 flows. These can be used alone or in combination.

1. **Client Authentication**
2. **Authorization Grant**

Let's look at each in detail.

---

### Use Case 1: Client Authentication

This is the use case where **"an assertion is used instead of a `client_secret` to authenticate the client itself."**

In standard OAuth 2.0 (RFC 6749), when a confidential client accesses the token endpoint, it usually sends a `client_id` and `client_secret` using Basic authentication or similar. However, to avoid the risk of secret leakage and management costs, it sends an "assertion signed with a shared key or public key" to authenticate instead.

#### Request Parameters

When using an assertion for client authentication, the following parameters are included in the token request:

* `client_assertion_type`: URI indicating the assertion format (required)
* `client_assertion`: The signed assertion body (required)

#### Flow Diagram and HTTP Request Example

Here is an example of the actor and communication flow when using an assertion for authentication instead of a normal `client_secret` on the back end of the **Authorization Code Grant**.

![client authentication](./assets/rfc7521-assertion-framework-deep-dive/client-authentication.png)

The HTTP request looks like this:

```http
POST /token HTTP/1.1
Host: server.example.com
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&code=SplxlOBeZQQYbYS6WxSbIA
&client_assertion_type=urn%3Aietf%3Aparams%3Aoauth%3Aclient-assertion-type%3Asaml2-bearer
&client_assertion=PHNhbW...[omitted]...ZT
```

This allows **client authentication without ever sending a shared secret (password) over the network**.

#### Error Response

If the assertion used for client authentication is expired, the signature is invalid, or for any other reason fails validation, the authorization server must always return an **`invalid_client`** error (RFC 7521 Section 4.2.1).

---

### Use Case 2: Authorization Grant

The other use case is to **treat the assertion itself as an "authorization grant (proof of authority)"**.

In other words, instead of `authorization_code` or `client_credentials`, you directly submit the assertion to the token endpoint to obtain an access token.

This is particularly useful when the user isn't at a browser — if a trusted system has already issued an assertion for that user, the client can exchange it for an access token.

#### Request Parameters

When using an assertion as an authorization grant, the parameter usage changes.

* `grant_type`: URI indicating the assertion format (required. Replaces `authorization_code`, etc.)
* `assertion`: The assertion body (required)
* `scope`: Requested scopes (optional)

#### Flow Diagram and HTTP Request Example

![authorization grant](./assets/rfc7521-assertion-framework-deep-dive/authorization-grant.png)

In this flow, there is no browser redirection, and it completes solely through back-channel communication between the client and the authorization server.

The HTTP request looks like this. The characteristic feature is the specification of the assertion type in `grant_type`.

```http
POST /token HTTP/1.1
Host: server.example.com
Content-Type: application/x-www-form-urlencoded

grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Asaml2-bearer
&assertion=PHNhbWxwOl...[omitted]...ZT4
```

Note: In this use case, whether client authentication is also required depends on the authorization server's policy. If needed, it can be combined with the client authentication method described earlier.

#### Error Response

If the assertion presented as an authorization grant is invalid or expired, the authorization server must return an **`invalid_grant`** error (RFC 7521 Section 4.1.1). Note that the error code is clearly distinguished from the failure of client authentication ( `invalid_client`).

---

### Advanced: Special Use Cases (Edge Cases)

RFC 7521 Section 6 introduces several interesting special use cases.

1. **Client Acting on Behalf of Itself**
   * This is a pattern where a confidential client accesses its own resources.
   * This is expressed as a **combination of Use Case 1 (Client Authentication) and Client Credentials Grant**. `grant_type=client_credentials` is used, while `client_assertion` is used as the authentication method.
2. **Anonymous User**
   * This is a pattern where only specific attributes such as "18 years or older" are proven, and the ID (Subject) such as username is treated as "anonymous". By using the assertion's claims function, it becomes possible to issue access tokens while protecting privacy.

---

## 4. Assertion Validation Rules (Content & Processing)

Section 5 of RFC 7521 defines **rules that any authorization server accepting assertions must verify**. Regardless of the format (SAML/JWT), the following must be met.

| Metadata (Claim)    | Description                                                                                                                                                               | Verification Point                                                                               |
| :------------------ | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :----------------------------------------------------------------------------------------------- |
| **Issuer**          | The entity that issued the assertion. In the case of self-issuance, it becomes the client identifier (`client_id`).                                                       | Check if the issuer is trusted by the authorization server.                                      |
| **Subject**         | Indicates "who" the assertion is for. In client authentication, it becomes the `client_id`, and in authorization grants, it becomes the authorized user (resource owner). | Used to determine whose authority to issue the token.                                            |
| **Audience**        | The intended recipient of the assertion. This should include the **authorization server's token endpoint URL**.                                                           | **Mandatory Verification**. Assertions not addressed to the server must be immediately rejected. |
| **Expires At**      | The time until which the assertion is valid.                                                                                                                              | **Mandatory Verification**. Expired assertions must be rejected.                                 |
| **Issued At**       | The time at which the assertion was issued.                                                                                                                               | (Optional) Assertions with excessively future issuance times should be rejected.                 |
| **Assertion ID**    | A unique ID for each assertion.                                                                                                                                           | (Optional) Used for one-time use restrictions and replay prevention.                             |
| **Signature / MAC** | Proof that the data has not been tampered with.                                                                                                                           | **Mandatory Verification**. Invalid signatures must be rejected.                                 |

**Audience verification** is especially critical. Without this check, an attacker could reuse an assertion issued for a different service to fool your authorization server.

---

## 5. Security Considerations

Here's a summary of the main security risks RFC 7521 highlights, and how to address them.

### Forged Assertion

An attack where an attacker tries to break through by forging an assertion on their own.

* **Countermeasure**: Mandatory verification using a strong digital signature (or MAC). The management of public key certificates and key rotation are very important.

### Stolen Assertion

An attack where an attacker steals a legitimate assertion from the network and retransmits (Replays) it from their own client. Since assertions have the property of **Bearer (usable by those who have them)**, they are dangerous if stolen.

* **Countermeasure 1 (Mandatory)**: Communication with the token endpoint must be **TLS (HTTPS) mandatory** to prevent eavesdropping on the communication path.
* **Countermeasure 2**: Set the expiration date (Expires At) as short as possible (generally within a few minutes).
* **Countermeasure 3**: Include a unique ID (Assertion ID: `jti` claim in JWT) in the assertion and record the used ID on the authorization server side to prevent reuse of once-used assertions (Replay Attack).

### Unauthorized Disclosure of Personal Information and Privacy

Including unnecessary personal information (PII) in an assertion increases the risk of privacy infringement. The issuer of the token and the authorization server should thoroughly implement the "principle of minimum authority and information minimization," including only the information truly necessary for granting authority (RFC 7521 Sections 8.3, 8.4).

---

## Conclusion

RFC 7521 is the bridge between assertion-based identity systems (SAML, JWT) and the OAuth 2.0 world.

* It breaks away from client authentication dependent on passwords via `client_secret` and realizes **more secure authentication based on public key cryptography**.
* It enables **advanced authorization grants on the back channel** by smoothly integrating with existing enterprise authentication infrastructure (Token Service).

If you're looking to build more secure OAuth 2.0 integrations or make use of existing SSO tokens, RFC 7521 and its concrete profiles — RFC 7523 (JWT) and RFC 7522 (SAML) — are well worth understanding.

### References

* [RFC 7521 - Assertion Framework for OAuth 2.0 Client Authentication and Authorization Grants](https://datatracker.ietf.org/doc/html/rfc7521)
* [RFC 7522 - Security Assertion Markup Language (SAML) 2.0 Profile for OAuth 2.0 Client Authentication and Authorization Grants](https://datatracker.ietf.org/doc/html/rfc7522)
* [RFC 7523 - JSON Web Token (JWT) Profile for OAuth 2.0 Client Authentication and Authorization Grants](https://datatracker.ietf.org/doc/html/rfc7523)
