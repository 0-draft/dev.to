---
title: 'OpenID Connect Dynamic Client Registration 1.0 Deep Dive: Dynamic Client Registration for Automation and Scale'
published: false
description: A comprehensive guide to OpenID Connect Dynamic Client Registration 1.0 (based on RFC 7591/7592). Why do we need dynamic registration? We explain its use cases and sequences with easy-to-understand diagrams.
tags:
  - oauth
  - oidc
  - security
  - authentication
series: OIDC
id: 3330432
---

# Introduction

When developing an application using OAuth 2.0 or OpenID Connect (OIDC), what is the very first step you take?
Usually, you log into the management console of an Identity Provider (IdP/OP) like Google, Auth0, or Okta, click the "Create New Application" button, manually register the callback URL (`redirect_uri`), and obtain a Client ID and Client Secret.

However, in modern architectures where systems scale massively or involve numerous microservices and native apps, this **"manual pre-registration"** can become a significant bottleneck and source of friction in development and operations.

* **Secure authentication per mobile app instance** (Assigning unique credentials for each installation)
* **Automated onboarding per tenant in SaaS environments** (Automatically generating an OAuth client in the background the moment a customer signs a contract)
* **Dynamic provisioning of microservices and AI agents** (Allowing systems to autonomously retrieve credentials without human intervention)

The standard specification designed to meet these demands for high automation and scalability is **OpenID Connect Dynamic Client Registration 1.0** (and its foundational specs, OAuth 2.0 Dynamic Client Registration: RFC 7591 / RFC 7592).

In this article, we will dive deep into how this specification frees us from the world of "clicking through management screens," exploring its use cases and operational principles.

---

## 1. Why Do We Need "Dynamic Client Registration"? (Use Cases)

Before looking at the specific mechanisms, let's organize the challenges (use cases) this specification solves.

### 1-A. Enhancing Mobile App Security

Embedding an OAuth Client Secret directly into a native mobile app is known as a strict anti-pattern, as it can be easily extracted via reverse engineering (mobile apps should fundamentally be treated as Public Clients).

By using Dynamic Client Registration (DCR), you can **issue a new Client ID and credentials dedicated exclusively to that specific device instance the first time the user installs and launches the app**. Even if that specific device's credentials are compromised, the blast radius is limited to that single instance, significantly improving overall security.

### 1-B. Automation in SaaS / Multi-Tenant Environments

In B2B SaaS platforms or Open Banking API ecosystems, you often face situations where "thousands or tens of thousands of third parties (RPs) are connecting to your company's Authorization Server."

Manually reviewing and registering all of these would quickly overwhelm any system administration department. By exposing DCR as an API, RPs can programmatically send registration requests, instantly obtain a Client ID, and start integrating. This achieves a highly scalable "self-service" model.

### 1-C. CI/CD and Microservices Automation (M2M Integration)

In modern development, infrastructure environments (Dev, Staging, Prod) and microservices are frequently spun up and torn down. By incorporating DCR, this entire flow can be fully codified and automated.

For example, when a Pod is dynamically spun up on a Kubernetes cluster, it can prove its workload identity (SVID) using tools like SPIFFE/SPIRE. Based on that, it can send a DCR request to the IdP to dynamically obtain a dedicated OAuth Client ID. This functions as a robust authentication foundation for Zero Trust architectures.

![k8s](./assets/oidc-registration-1_0-deep-dive/k8s.png)

---

## 2. The Overall Flow of Dynamic Client Registration

So, what kind of communication actually takes place?
As the name suggests, DCR is a very simple HTTP-based protocol where "the Client (Relying Party) sends its own information to the Authorization Server's (OpenID Provider's) endpoint to be registered."

Let's take a look at the sequence diagram below.

![DCR Flow](./assets/oidc-registration-1_0-deep-dive/dcr-flow.png)

It is broadly divided into two phases.

### Phase 1: Registration Endpoint Discovery

The client first needs to know, "Where should I send the registration request?"
This is resolved using the mechanism of [OpenID Connect Discovery 1.0](https://dev.to/kanywst/openid-connect-discovery-10-deep-dive-ops-self-introduction-and-dynamic-configuration-retrieval-3321766).

The client accesses the OP's `/.well-known/openid-configuration` and looks for the `"registration_endpoint"` key in the metadata. That URL is the entry point for dynamic registration.

### Phase 2: Issuing and Completing the Registration Request

The client sends an HTTP `POST` request to the identified Client Registration Endpoint.
The payload (JSON) at this time includes the client's attributes (metadata).

---

## 3. Deep Dive into Requests and Responses

Let's look closely at exactly what data is sent and received.

### 3-A. Client Registration Request

The client submits the information it wants to register in `application/json` format.

```http
POST /connect/register HTTP/1.1
Content-Type: application/json
Accept: application/json
Host: server.example.com
Authorization: Bearer <Initial Access Token> (*Optional)

{
 "application_type": "web",
 "redirect_uris": [
   "[https://client.example.org/callback](https://client.example.org/callback)"
 ],
 "client_name": "My Dashboard App",
 "logo_uri": "[https://client.example.org/logo.png](https://client.example.org/logo.png)",
 "token_endpoint_auth_method": "client_secret_basic",
 "jwks_uri": "[https://client.example.org/my_public_keys.jwks](https://client.example.org/my_public_keys.jwks)"
}
```

According to the specification, **the only required parameter is `redirect_uris` (an array of callback URLs)**.
However, in real-world operations, information like the following is often sent alongside it:

* `application_type`: `web` or `native`. Based on this, the AS can change the type and restrictions of the issued credentials.
* `client_name` / `logo_uri`: The app name and logo image displayed on the Consent Screen when the user logs in (authorizes).
* `token_endpoint_auth_method`: The client authentication method at the token endpoint (e.g., `client_secret_basic`, or the more secure `private_key_jwt`).
* `jwks_uri`: The location of the client's public keys. This is necessary when using advanced OIDC encryption/signature features (like JAR, JARM).

#### 🛡 The Role of the Initial Access Token (IAT)

"If anyone can hit the API and generate infinite clients, wouldn't it become a hotbed for DDoS attacks and spam?"
To address this exact concern, the specification recommends using an **Initial Access Token (IAT)** as a mechanism to protect the endpoint.

This is a special Bearer Token strictly for calling the registration API. By issuing a limited IAT in advance via a developer portal, or by passing the IAT to provisioning software through a secure out-of-band channel, you can restrict dynamic registration so that only authorized entities can perform it.

#### ⚠️ Security Considerations: SSRF Risks

When implementing and operating a DCR endpoint, you must be careful with URL parameters like `logo_uri` and `jwks_uri`. If the IdP is designed to fetch these URLs, a malicious developer could register URLs pointing to the internal network (such as cloud metadata endpoints), creating a risk of the IdP being used as a stepping stone for **Server-Side Request Forgery (SSRF)**. Proper URL validation and network restrictions are essential.

### 3-B. Client Registration Response

If the AS successfully validates the metadata in the request (e.g., checking that the URI formats are valid), it returns an HTTP `201 Created` along with the newly issued information.

```http
HTTP/1.1 201 Created
Content-Type: application/json
Cache-Control: no-store

{
 "client_id": "s6BhdRkqt3",
 "client_secret": "ZJYCqe3GGRvdrudKyZS0XhGv_Z45DuKhCUk0gBR1vZk",
 "client_secret_expires_at": 1577858400,
 "registration_access_token": "this.is.an.access.token.value.ffx83",
 "registration_client_uri": "[https://server.example.com/connect/register?client_id=s6BhdRkqt3](https://server.example.com/connect/register?client_id=s6BhdRkqt3)",
 "redirect_uris": ["[https://client.example.org/callback](https://client.example.org/callback)"],
 "client_name": "My Dashboard App",
 ... (other registered metadata)
}
```

We have finally obtained the highly anticipated **`client_id` and `client_secret**`!
The application holds these values in memory from the response and proceeds to the standard OIDC authentication flows. This is the moment we completely break free from the world of manual registration.

---

## 4. Post-Registration Management Mechanisms (Read / Update / Delete)

Registering client information once is not the end of the story. Lifecycle management is also necessary for situations like "the logo URL has changed" or "we want to discard this client now."

Notice the two unfamiliar parameters in the successful registration response:

* **`registration_client_uri`**:
This is the dedicated endpoint URL for modifying the configuration of this specific client (Client Configuration Endpoint).
* **`registration_access_token`**:
This is a dedicated access token used to access the URI above to retrieve (Read) or update (Update) information.

You perform CRUD operations by sending requests to the URL provided in the previous response (`registration_client_uri`), setting the `registration_access_token` in the Authorization header, and changing the HTTP method. (*Note: Update/Delete operations are defined in the extension specification, RFC 7592.*)

### Reading Metadata (Read)

Check how your client is currently recognized and registered by the AS (server).

```http
GET /connect/register?client_id=s6BhdRkqt3 HTTP/1.1
Accept: application/json
Authorization: Bearer this.is.an.access.token.value.ffx83
```

The response will be the complete metadata JSON (the current state), similar to what was returned during registration.

### Updating Registration Information (Update / RFC 7592)

If you want to add a callback URL, prepare a new complete JSON of the metadata and send it via HTTP `PUT`.
**It is important to note that this is a `PUT` request, not a `PATCH`. Therefore, you must send the entire metadata, overwriting everything, not just the parts you want to change.**

```http
PUT /connect/register?client_id=s6BhdRkqt3 HTTP/1.1
Content-Type: application/json
Authorization: Bearer this.is.an.access.token.value.ffx83

{
 "client_id": "s6BhdRkqt3",
 "client_secret": "ZJYCqe3GGRvdrudKyZS0XhGv_Z45DuKhCUk0gBR1vZk",
 "application_type": "web",
 "client_name": "My Dashboard App",
 "redirect_uris": [
   "[https://client.example.org/callback](https://client.example.org/callback)",
   "[https://client.example.org/callback2](https://client.example.org/callback2)"  // Newly added
 ]
}
```

![Post Registration Management](./assets/oidc-registration-1_0-deep-dive/post-registration.png)

As shown here, Dynamic Client Registration provides a mechanism to fully automate not just "registration" but the entire "subsequent lifecycle" via APIs.

---

## 5. Support Status in OSS and Major IdPs

When actually implementing and utilizing this specification, the support status among major products is as follows:

* **OSS Identity Providers**: **Keycloak** and **Ory Hydra** robustly support DCR as a standard specification. Furthermore, federation IdPs commonly used in cloud-native environments, such as **Dex**, can be combined with peripheral tools to build dynamic client management mechanisms.
* **SaaS IDaaS**: **Auth0** and **Okta** also provide dedicated APIs for dynamic client registration, which are widely utilized for automated provisioning via Terraform or custom scripts.

---

## 6. Supplement: The Relationship Between OpenID Connect and OAuth 2.0 (RFC 7591)

When you search for "OIDC Dynamic Client Registration," you might also come across "OAuth 2.0 Dynamic Client Registration (RFC 7591)," which can cause some confusion.

Historically, the OpenID Connect working group pioneered this dynamic registration specification (OIDC Registration 1.0). Later, recognizing that "this is a highly useful mechanism not limited to OIDC but for OAuth 2.0 in general," it was compiled by the IETF as a more general-purpose standard specification in RFC 7591 (Registration) and RFC 7592 (Management).

Today, **OIDC Registration 1.0 is treated as a protocol that is de facto compatible with RFC 7591 (while extending it with OIDC-specific metadata definitions).** Implementers can safely understand it as following RFC 7591 as the basic framework, with the ability to exchange additional OIDC-specific attributes (e.g., `id_token_signed_response_alg`, `subject_type`).

---

## 7. Conclusion

OpenID Connect Dynamic Client Registration 1.0 is a pivotal specification for eliminating manual operations on management screens and enabling the **"As Code" registration of clients**.

* **The Essential Path to Automation**: It enables the isolation of mobile app instances, SaaS tenant provisioning, and dynamic provisioning via CI/CD pipelines.
* **Standardized, Simple API**: Simply discover the endpoint via `/.well-known/openid-configuration` and POST some JSON to obtain a `client_id` and `client_secret`.
* **Management via Registration Access Token**: Even after registration, you are given a dedicated token (and URI) that allows you to continuously update (PUT) or destroy (DELETE) metadata programmatically.

While not every application needs it, it is a powerful "weapon for scaling" that architects of growing systems and B2B platforms absolutely need to know about.

### Reference Links

* [OpenID Connect Dynamic Client Registration 1.0](https://openid.net/specs/openid-connect-registration-1_0.html)
* [RFC 7591 - OAuth 2.0 Dynamic Client Registration Protocol](https://datatracker.ietf.org/doc/html/rfc7591)
* [RFC 7592 - OAuth 2.0 Dynamic Client Registration Management Protocol](https://datatracker.ietf.org/doc/html/rfc7592)
