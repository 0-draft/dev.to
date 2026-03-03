---
title: 'RFC 8693 Deep Dive: Token Exchange'
published: false
description: 'A comprehensive, illustrated deep dive into RFC 8693 (Token Exchange), the OAuth 2.0 standard for exchanging one token for another, exploring the crucial differences between Impersonation and Delegation.'
tags:
  - oauth
  - oidc
  - security
  - microservices
series: OAuth
id: 3305365
cover_image: 'https://raw.githubusercontent.com/kanywst/dev.to.kanywst/refs/heads/main/articles/assets/rfc8693-token-exchange-deep-dive/cover.png'
---

# Introduction

In modern system architectures, particularly in microservices architectures, the following scenarios are incredibly common:

* **Conversion at the API Gateway**: You want to exchange a user's access token received from the frontend for a scoped-down token dedicated to each backend microservice. Why exchange it? Because the user's token often has too broad a scope. Following the principle of least privilege, the gateway swaps it for a token containing the "minimum required permissions" and the "appropriate destination (Audience)" before proxying the request to the backend.
* **Service-to-Service Communication**: When Service A calls Service B on behalf of a user, it needs to accurately convey "who is calling (Service A)" and "on whose behalf (the User)".
* **Support by Administrators**: An administrator needs to temporarily operate the system as a standard user account (Impersonation) to troubleshoot an issue.

The traditional OAuth 2.0 (RFC 6749) flows were primarily designed for "a client (app) obtaining authorization from a user to issue the initial access token." There was no standardized mechanism defined for "exchanging an already issued token for a new token intended for a different context."

**RFC 8693 (OAuth 2.0 Token Exchange)** emerged to solve exactly this problem.

---

## 1. What is Token Exchange (STS)?

RFC 8693 defines a mechanism (an HTTP and JSON-based protocol) that allows an OAuth 2.0 Authorization Server to act as an **STS (Security Token Service)**.

An STS is a "service that receives a security token, validates it, and issues a **new security token** as a result."

In Token Exchange, a new grant type `urn:ietf:params:oauth:grant-type:token-exchange` is introduced. By presenting a "token at hand" to the authorization server, the client can obtain a "new token" with different scopes or audiences (destinations).

---

## 2. Two Crucial Concepts: Impersonation and Delegation

The most important aspect of understanding RFC 8693 is the "semantics" (meaning) behind exchanging a token. The specification broadly categorizes this into two types:

### 1. Impersonation

This is when Principal A (e.g., a backend service or an administrator) **completely acts as** Principal B (e.g., a standard user).

When accessing a resource server using an Impersonation token, it appears to the resource server as if "B themselves made the access." The existence of A is hidden, or at least, A and B are indistinguishable in the context of access control.

* **Use Cases**: An API gateway receiving a user token and exchanging it for a system token to call internal legacy systems, or customer support obtaining a token with user privileges to reproduce a screen as the user sees it.

### 2. Delegation

This is when Principal A acts as an **Agent on behalf of** Principal B.

The defining characteristic of Delegation is that the new token **retains the information (the identity of A) indicating that "the subject is B, but the one actually taking the action is A."** This ensures that an Audit Trail can accurately record the history that "A performed the operation on behalf of B."

* **Use Cases**: Microservice A needs to call Microservice B while processing a user's request. Service B performs access control while recognizing that it was "called via Service A, originating from the user's request."

---

## 3. Token Exchange Requests and Responses

> ⚠️ Note: Client Authentication
> When making a token exchange request, the requester (Service A in this example) must pass authentication by the authorization server. While Basic Authentication using `client_id` and `client_secret` is commonly used, you can use any client authentication method supported by the authorization server, such as the highly secure **mTLS (Mutual TLS)** or **Private Key JWT**. Not just anyone can exchange tokens.

So, exactly what kind of HTTP request needs to be sent to exchange a token?

### Token Exchange Request

You send a `POST` request to the token endpoint including the following parameters:

| Parameter Name             | Required | Description                                                                                                                                      | Notes                                                                                                                                           |
| -------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| **`grant_type`**           | **Yes**  | Specifies the grant type.<br>                                                                                                                    | `urn:ietf:params:oauth:grant-type:token-exchange`                                                                                               |
| **`subject_token`**        | **Yes**  | The token to be exchanged.<br>(e.g., the access token received from the user)                                                                    |                                                                                                                                                 |
| **`subject_token_type`**   | **Yes**  | A URI indicating the type of the `subject_token`.<br>(e.g., `urn:ietf:params:oauth:token-type:access_token`)                                     |                                                                                                                                                 |
| **`requested_token_type`** | No       | A URI indicating the type of token you **want returned**.<br>(e.g., specify `urn:ietf:params:oauth:token-type:id_token` if you want an ID token) | Generally defaults to returning an access token if omitted.                                                                                     |
| **`resource`**             | No       | The location (such as a URI) of the resource where the new token will be used.                                                                   | **Used for downscoping**.<br>If multiple resources are specified simultaneously, the request might be rejected for having too broad of a scope. |
| **`audience`**             | No       | The logical destination of the new token (Client ID or service name).                                                                            | **Used for downscoping**.<br>How `resource` and `audience` are differentiated depends on the authorization server's implementation.             |
| **`scope`**                | No       | The permission scopes requested for the new token.                                                                                               | **Used for downscoping**.<br>You cannot request broader permissions than the original token possessed.                                          |
| **`actor_token`**          | No       | The token of the subject (Actor) acting on behalf.<br>Specify this when you want to perform **Delegation**.                                      | If specified, a token containing the `act` claim will be issued.                                                                                |
| **`actor_token_type`**     | Cond.    | A URI indicating the type of the `actor_token`.                                                                                                  | **Required** if `actor_token` is specified.                                                                                                     |

#### Token Type URIs Used

The following standardized values are used for URIs specified in `subject_token_type` and others:

* `urn:ietf:params:oauth:token-type:access_token` (OAuth 2.0 Access Token)
* `urn:ietf:params:oauth:token-type:refresh_token` (OAuth 2.0 Refresh Token)
* `urn:ietf:params:oauth:token-type:id_token` (OpenID Connect ID Token)
* `urn:ietf:params:oauth:token-type:saml2` (SAML 2.0 Assertion)

### Sample Request and Flow Diagram

As an example, let's look at a flow where a microservice (client) exchanges a user's access token for a token intended for another backend API.

![sample token exchange request](./assets/rfc8693-token-exchange-deep-dive/token-exchange-request.png)

#### HTTP Request Example

```http
POST /as/token.oauth2 HTTP/1.1
Host: as.example.com
Content-Type: application/x-www-form-urlencoded
Authorization: Basic cnMwODpsb25nLXNlY3VyZS1yYW5kb20tc2VjcmV0

grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Atoken-exchange
&resource=https%3A%2F%2Fbackend.example.com%2Fapi
&subject_token=accVkjcJyb4BWCxGsndESCJQbdFMogUC5PbRDqceLTC
&subject_token_type=urn%3Aietf%3Aparams%3Aoauth%3Atoken-type%3Aaccess_token

```

#### Token Exchange Response

Upon success, the authorization server returns JSON like the following:

```json
{
  "access_token": "eyJhbG...[new_token_string]...whw",
  "issued_token_type": "urn:ietf:params:oauth:token-type:access_token",
  "token_type": "Bearer",
  "expires_in": 3600
}

```

With this, Service A has successfully acquired a new token specifically for the backend API.

---

## 4. Expressing and Authorizing Delegation with JWT Claims (`act` / `may_act`)

In RFC 8693, to implement the semantics of Delegation using JWTs (JSON Web Tokens) and to control those permissions, two new claims are defined: **`act` (Actor)** and **`may_act` (Authorized Actor)**.

### 1. The `act` Claim Indicating the Acting Agent

The `act` claim is placed as an object within the JWT payload and indicates the identity of the current acting agent.

```json
{
  "iss": "https://issuer.example.com",
  "aud": "https://backend.example.com",
  "sub": "user@example.com",     // <-- Original access subject (User)
  "exp": 1443904177,
  "act": {
    "sub": "service-A@example.com" // <-- Actor acting on behalf (Service A)
  }
}

```

The backend receiving this token looks at `sub` to determine "this is a request from user@example.com," while simultaneously logging the `act` claim to maintain an audit trail showing that "however, the caller was service-A."

**Chain of Delegation**

If a more complex chain of microservice calls occurs (e.g., User → Service A → Service B → Service C), the `act` claim can be nested to record the entire history of the delegation.

```json
{
  "sub": "user@example.com",
  "act": {
    "sub": "https://service-B.example.com",   // <-- Current Actor (Service B)
    "act": {
      "sub": "https://service-A.example.com"  // <-- Previous Actor (Service A)
    }
  }
}

```

For access control decisions, it is recommended to consider only the top-level claim and the direct Actor (the `sub` of the outermost `act`), while treating the nested historical records purely as "information" for auditing purposes (RFC 8693 Section 4.1).

### 2. The `may_act` Claim Authorizing Delegation

For "Service A to become an agent for the User," there must be prior configuration or proof allowing it. The `may_act` claim expresses this.

When a `may_act` claim exists within the `subject_token` (the user's original token), it specifies **"which actors are authorized to act as my agent (Actor)."**

```json
{
  "sub": "user@example.com",
  "may_act": {
    "sub": "service-A@example.com" // <-- Authorizes Service A to be the agent
  }
}

```

When the authorization server receives a token exchange request, it inspects this `may_act` claim to verify (authorize) whether the requesting client (or the subject presented in the `actor_token`) truly possesses delegation authority.

### Other JWT Claims and Introspection Support

In addition to the two above, RFC 8693 formally registers the following claims as extensions to the JWT specification (and for application in Token Introspection):

* **`client_id` Claim**: The identifier of the OAuth client that requested the token.
* **`scope` Claim**: A list of scopes associated with the token.
* Even in OAuth 2.0 Token Introspection (RFC 7662) responses, `act` and `may_act` are defined to be included as top-level members.

---

## 5. Practical Use Cases: Workload Identity and Federation

The concepts in RFC 8693 (and the related RFC 7523 JWT Grant) are currently most actively utilized in "keyless authentication" across **CI/CD pipelines** and **container orchestration**.
In these scenarios, the distinguishing feature is the exchange of tokens "across borders" to different Issuers.

### 1. GitHub Actions (OIDC) and Cloud Provider Integration

Previously, deploying to AWS or Google Cloud from CI/CD required storing permanent secret keys (like `AWS_ACCESS_KEY_ID`) in GitHub Secrets. However, this carries a high risk of leakage.

Today, a mechanism known as **OIDC Federation** is the mainstream approach. This is exactly the **Token Exchange pattern**.

1. **Issue Subject Token**: When running a job, GitHub Actions issues its own signed **OIDC token (JWT)** (Issuer: `token.actions.githubusercontent.com`).
2. **Token Exchange**: Processes like the AWS CLI within the job present this OIDC token to the cloud provider's STS (Security Token Service).
3. **Issue Token**: AWS verifies GitHub's signature, checks the trust configuration (matching Subject or Repository), and then issues a **temporary AWS access token**.

This enables secure deployments purely through token exchange, completely eliminating the need to manage persistent keys.

![github actions](./assets/rfc8693-token-exchange-deep-dive/github-actions.png)

### 2. Kubernetes Service Account (KSA) Utilization

Pods running on Kubernetes are mounted with a **Service Account Token (JWT)** by default. There is a growing pattern of using this as the "Subject Token" for exchange.
The token utilized here is a **Projected Service Account Token**, where the Audience has been customized for external integration.

* **Pod Identity (EKS IRSA / GKE Workload Identity)**:
Exchanges the K8s token held by the Pod (e.g., `aud: sts.amazonaws.com`) for a cloud provider's IAM token (AWS/GCP). This allows the Pod to access services like AWS S3 or Google Cloud Spanner.
* **Integration with Vault**:
Presents the K8s token to a secret management tool like HashiCorp Vault, exchanging it to retrieve database passwords or API keys.
* **Service Mesh (Istio/SPIRE)**:
In service-to-service communication, the process of exchanging a K8s token for an mTLS certificate (SVID) can also be considered a form of Token Exchange in a broader sense.

![sa](./assets/rfc8693-token-exchange-deep-dive/sa.png)

> **💡 Column: Why does it have to be "OIDC" and not just a "plain JWT"?**
> The reason tokens issued by GitHub Actions are trusted isn't merely because they are in JWT format. It's because they support a mechanism called **OIDC Discovery (OpenID Connect Discovery)**.
> The receiving cloud (AWS/GCP) looks at the `iss` (Issuer) claim in the token, automatically fetches (Discovers) the issuer's "public key" over the internet, and "verifies" the signature. It then checks if "claims" like `sub` and `aud` match the configured policies.
> This automated process of **"Discovery, Verification, and Claim Checking"** is the true essence of Workload Identity, rendering static key management obsolete.

### * Note: The Relationship Between RFC 8693 and RFC 7523 (JWT Grant)

At a strict implementation level, AWS and GCP Workload Identity are often based not on RFC 8693 itself, but on its predecessor/sibling standard, **RFC 7523 (JWT Authorization Grant)**.

* **RFC 8693**: Uses `grant_type=...:token-exchange`. An explicit "exchange" protocol.
* **RFC 7523**: Uses `grant_type=...:jwt-bearer`. Presents a JWT as a "signature" to obtain a token.

However, the **architectural purpose and structure are entirely identical**: "Exchanging a token issued by a trusted third party (IdP/GitHub/K8s) for a token of the service you want to use." OSS authorization servers like Keycloak implement these explicitly as RFC 8693, natively providing functionality to exchange K8s tokens for API gateway tokens.

---

## 6. Guide for Implementers: What is the STS Validating Internally?

While RFC 8693 states that "the authorization server must validate the token," it doesn't define the exact steps.
In actual operations, an STS (Security Token Service) generally determines whether to permit an exchange through a 3-step filtering process.

### Step 1: Signature and Validity Verification (Authentication)

Confirms that the received `subject_token` is not forged.

* **Signature Verification**: If it's a JWT, it validates the signature using the JWKS (public key); if it's an Opaque token, it performs introspection.
* **Claim Verification**: Checks that `iss` (Issuer), `exp` (Expiration), and `aud` (Audience) are as expected.

### Step 2: Policy Check (Exchange Rules)

Evaluates the business logic: "Is it acceptable to exchange this token for that target (Audience/Scope)?"

* **Workload Identity Example**: Checks mapping rules (Trust Relationships) like "If the token is from GitHub's `my-repo` repository (`sub`), allow exchange to AWS's `S3AccessRole` (`role`)."
* **Delegation Example**: If the original token contains a `may_act` claim, it verifies that the subject listed there matches the current requesting client.

### Step 3: Client Authorization

Verifies whether the client making the token exchange request (the API gateway or microservice itself) has the authority to utilize the STS.

---

## 7. Security Considerations

While Token Exchange is a powerful feature, incorrect implementation or misconfiguration can lead to severe security risks, such as Privilege Escalation.

### 1. Strict Client Authentication and Authorization Verification

You must not allow arbitrary clients to perform Impersonation or Delegation. The authorization server must strictly verify "whether the requesting client holds the legitimate authority to perform Impersonation or Delegation for the `sub` of the specified `subject_token`."

### 2. Narrowing Down Target Resources (Audience)

As a fundamental rule, the newly issued token should not have broader privileges than the original token (it should be downscoped). By using the `resource` or `audience` parameters during the request to limit the usage destination of the new token, you should minimize the potential damage in the unlikely event the new token is leaked.

### 3. Token Verification

When the authorization server receives a `subject_token` or `actor_token` that it did not issue itself (such as a SAML assertion issued by an external IdP), it must reliably verify the signature, expiration date, and issuer before processing the exchange (e.g., in combination with RFC 7521).

---

## Conclusion

RFC 8693 (OAuth 2.0 Token Exchange) is a standard protocol designed to **"safely pass permissions while preserving context"** within increasingly complex microservices architectures and system integrations.

* By presenting an existing token, you can obtain a **token tailored for a new purpose** (such as a downscoped token or a token aimed at a different audience).
* It provides two powerful semantics: **Impersonation**, which completely assumes the identity of the access subject, and **Delegation**, which retains the identity of the acting agent.
* By leveraging the JWT **`act` claim**, you can maintain a clear Audit Trail even in multi-hop communication.
* Its concepts play a central role in modern cloud-native, keyless authentication infrastructures, such as **Workload Identity (Federation)**.

As the foundational technology for token conversion at API gateways and service-to-service communication in Zero Trust networks, this specification is poised to become even more critical in the future.

### References

* [RFC 8693 - OAuth 2.0 Token Exchange](https://datatracker.ietf.org/doc/html/rfc8693)
* [RFC 6749 - The OAuth 2.0 Authorization Framework](https://datatracker.ietf.org/doc/html/rfc6749)
* [RFC 7521 - Assertion Framework for OAuth 2.0 Client Authentication and Authorization Grants](https://datatracker.ietf.org/doc/html/rfc7521)
