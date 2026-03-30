---
title: 'AuthZEN Authorization API 1.0 Deep Dive: The Standard API That Separates Authorization Decisions from Enforcement'
published: true
description: 'A deep dive into OpenID AuthZEN Authorization API 1.0 based on the original specification: PDP/PEP model, information model, Access Evaluation API, batch evaluation, Search APIs, PDP Metadata, HTTPS binding, and security design.'
tags:
  - oauth
  - security
  - authorization
  - api
series: Authorization
id: 3430620
cover_image: "https://raw.githubusercontent.com/kanywst/dev.to.kanywst/refs/heads/main/articles/assets/authzen-authorization-api-deep-dive/cover.png"
---

# Introduction

In the authentication space, OpenID Connect has become the de facto standard, centralizing identity around Identity Providers. In the authorization space — specifically delegated authorization — OAuth 2.0 stands as a robust standard.

But what about a standard API for **fine-grained authorization** within applications?

In the era of microservice architectures, everyone eventually hits the same wall: "Where and how should we evaluate authorization?"

- Service A uses OPA (Open Policy Agent)
- Service B adopted Cedar
- Service C is still dragging around a legacy in-house authorization library

When authorization logic is scattered across services like this, maintaining a consistent view of "who can do what on which resource" across the entire system becomes extremely difficult — auditing and policy changes become a nightmare.

The established best practice is to separate the **decision** (PDP) from the **enforcement** (PEP). But there was another problem: **no standard protocol existed to connect PDP and PEP.** While excellent policy engines like OPA, Cedar, and Topaz kept emerging, the communication interface between applications (PEP) and policy engines (PDP) remained proprietary — an era without a standard.

This situation has finally been resolved by the **AuthZEN Authorization API 1.0**, developed by the AuthZEN Working Group under the OpenID Foundation. Published as a Standards Track specification in March 2026, this simple JSON-based API is the long-awaited standard protocol for asking "Can **who** do **what** on **which resource**?" between PDP and PEP.

---

## Scope of This Article

First, let's clarify where the Authorization API fits in the landscape.

![scope](./assets/authzen-authorization-api-deep-dive/scope.png)

OAuth 2.0 is a mechanism for "a client to obtain tokens to access a resource server." AuthZEN Authorization API is a mechanism for "externalizing whether a given request should be allowed or denied within an application." They operate at different layers.

OAuth deals with Client-AS-RS communication. AuthZEN deals with PEP-PDP communication within applications. It's crucial not to confuse the two.

The Authorization API is version **1.0**, and endpoints SHOULD include `v1` in their paths (e.g., `/access/v1/evaluation`). Future revisions MUST NOT modify the existing API — only augment it. This means methods and parameters may be added, but the semantics of existing fields will never change. Additionally, receivers **MUST ignore unknown fields**, ensuring forward compatibility when old and new PDPs/PEPs coexist.

This article assumes the following prerequisite knowledge:

- Basics of HTTP / REST APIs (request-response structure)
- Reading and writing JSON
- Basic access control concepts (who, what, on which resource)

---

## 1. Why Separate Authorization Decisions?

### 1.1 The Limits of Embedded Authorization Logic (Silos and Technical Debt)

In a monolithic application, middleware could handle access control in one place. However, in modern microservice environments, authorization logic often gets embedded directly in each service's application code, creating silos.

![Limits](./assets/authzen-authorization-api-deep-dive/limits.png)

This pattern of "distributed and embedded authorization" causes increasingly severe problems as systems grow:

| Problem                           | Real-World Impact                                                                                                                                           |
| :-------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Policy Silos**                  | The conditions for "who can view a document" are scattered across multiple services, and no one can grasp the consistent policy across the entire system.   |
| **High Cost of Change**           | A business requirement change like "restrict external collaborator permissions" requires modifying multiple repositories and redeploying each one.          |
| **Inconsistency**                 | Different languages and implementation approaches (DB lookups, JWT evaluation, etc.) per service lead to permission bypass or contradictions in edge cases. |
| **Audit Difficulty (Compliance)** | Proving "who can access what" requires reading through each codebase, making security audits and SOC2 compliance requirements practically impossible.       |

### 1.2 PDP/PEP Model — Separating Decision from Enforcement

The solution is to **externalize authorization decisions to a dedicated service**.

![PDP/PEP](./assets/authzen-authorization-api-deep-dive/pep-pdp.png)

The terminology for this model is defined in XACML and NIST SP 800-162 (ABAC):

| Term    | Full Name                   | Role                                                                             |
| :------ | :-------------------------- | :------------------------------------------------------------------------------- |
| **PDP** | Policy Decision Point       | **Decides** whether to allow access based on policy                              |
| **PEP** | Policy Enforcement Point    | **Enforces** the PDP's decision                                                  |
| **PAP** | Policy Administration Point | **Manages** policies (out of AuthZEN's scope)                                    |
| **PIP** | Policy Information Point    | **Provides** attribute information needed for decisions (out of AuthZEN's scope) |

The AuthZEN Authorization API standardizes the **PEP -> PDP communication**.

### 1.3 Why a Standard API Is Needed

The PDP/PEP model itself is not a new concept. So why is a standard API needed now?

Because the PDP implementation landscape is highly fragmented.

| PDP Implementation | Developer    | Policy Language       | API                     |
| :----------------- | :----------- | :-------------------- | :---------------------- |
| **OPA**            | Styra / CNCF | Rego                  | Proprietary REST API    |
| **Cedar**          | AWS          | Cedar                 | Proprietary API         |
| **Topaz**          | Aserto       | Rego / OPA-compatible | Proprietary REST / gRPC |
| **Axiomatics**     | Axiomatics   | ALFA / XACML          | Proprietary REST API    |
| **SpiceDB**        | AuthZed      | Zanzibar-style        | Proprietary gRPC        |

Since each PDP has its own API, applications become tightly coupled to a specific PDP. If you want to switch PDPs, you need to rewrite all authorization call code on the application side.

The AuthZEN Authorization API aims to **standardize the PDP-PEP interface**, making PDP implementations interchangeable.

![Authzen](./assets/authzen-authorization-api-deep-dive/authzen.png)

---

## 2. The Information Model of the Authorization API

The core of the Authorization API is the information model called the "4-tuple." An Access Evaluation request consists of four elements.

![Decision](./assets/authzen-authorization-api-deep-dive/decision.png)

Let's examine each one in detail.

### 2.1 Subject (Who)

A Subject represents the user or machine principal (such as a service account) requesting access.

| Field        | Required | Type   | Description                                                     |
| :----------- | :------- | :----- | :-------------------------------------------------------------- |
| `type`       | REQUIRED | string | The type of Subject (`user`, `service`, `device`, etc.)         |
| `id`         | REQUIRED | string | Unique identifier for the Subject (unique within its `type`)    |
| `properties` | OPTIONAL | object | Additional attributes (department, IP address, device ID, etc.) |

```json
{
  "type": "user",
  "id": "alice@acmecorp.com",
  "properties": {
    "department": "Sales",
    "ip_address": "172.217.22.14",
    "device_id": "8:65:ee:17:7e:0b"
  }
}
```

The `properties` field is important. Many authorization systems operate statelessly, so the PEP needs to pass all attributes required for policy evaluation at request time. For example, if there's a policy stating "only Sales department users can access," the PEP must include `department` in properties — otherwise the PDP cannot make a decision.

### 2.2 Resource (On What)

A Resource represents the target of the access request.

| Field        | Required | Type   | Description                                                |
| :----------- | :------- | :----- | :--------------------------------------------------------- |
| `type`       | REQUIRED | string | The type of Resource (`document`, `account`, `book`, etc.) |
| `id`         | REQUIRED | string | Unique identifier for the Resource                         |
| `properties` | OPTIONAL | object | Additional attributes                                      |

```json
{
  "type": "book",
  "id": "123",
  "properties": {
    "library_record": {
      "title": "AuthZEN in Action",
      "isbn": "978-0593383322"
    }
  }
}
```

Since `properties` can contain nested JSON objects, resource metadata can be expressed flexibly.

### 2.3 Action (What)

An Action represents the operation the Subject intends to perform on the Resource.

| Field        | Required | Type   | Description           |
| :----------- | :------- | :----- | :-------------------- |
| `name`       | REQUIRED | string | Name of the action    |
| `properties` | OPTIONAL | object | Additional attributes |

```json
{
  "name": "can_read",
  "properties": {
    "method": "GET"
  }
}
```

The specification defines common action names corresponding to CRUD operations:

| Action       | Description                                      |
| :----------- | :----------------------------------------------- |
| `can_access` | Generic access (when not distinguishing by type) |
| `can_create` | Create                                           |
| `can_read`   | Read (including list retrieval)                  |
| `can_update` | Update (partial or full replacement)             |
| `can_delete` | Delete                                           |

These are recommended common names, but application-specific action names (e.g., `can_approve`, `can_publish`) can be freely used.

### 2.4 Context (Under What Circumstances)

Context is an arbitrary JSON object representing environmental information or circumstances of the request.

```json
{
  "time": "1985-10-26T01:22-07:00"
}
```

Time, network information, risk scores, and other information needed for decisions but not belonging to Subject, Action, or Resource go here.

---

## 3. Access Evaluation API — Request and Response

Now that we understand the information model, let's look at the actual API.

### 3.1 Request

Assemble the 4-tuple into JSON and send it to the PDP.

```json
{
  "subject": {
    "type": "user",
    "id": "alice@acmecorp.com"
  },
  "resource": {
    "type": "account",
    "id": "123"
  },
  "action": {
    "name": "can_read",
    "properties": {
      "method": "GET"
    }
  },
  "context": {
    "time": "1985-10-26T01:22-07:00"
  }
}
```

In plain language, this query asks:

> Can the user **alice@acmecorp.com** **read (can_read)** **account #123**? (At time 1985-10-26T01:22-07:00)

### 3.2 Response — Decision

The simplest response is just a JSON with a `decision` field:

```json
{
  "decision": true
}
```

`decision` is a boolean — `true` = allow, `false` = deny. **That's it.** The specification is intentionally designed to be simple.

### 3.3 Response — Additional Context

The PDP can return additional information via a `context` field alongside the `decision`. Use cases cited by the specification:

- **"Advice" or "obligations"** — Additional instructions like "record this access in the audit log" (a concept from XACML; Section 9 compares XACML in detail)
- **UI rendering hints** — "This operation is not permitted, so gray out the button"
- **Step-up authentication instructions** — "This operation requires additional authentication"

```json
{
  "decision": false,
  "context": {
    "id": "0",
    "reason_admin": {
      "en": "Request failed policy C076E82F"
    },
    "reason_user": {
      "en-403": "Insufficient privileges. Contact your administrator",
      "es-403": "Privilegios insuficientes. Póngase en contacto con su administrador"
    }
  }
}
```

`reason_admin` provides administrator-facing reasons (not to be shown to end users), while `reason_user` provides user-facing reasons. Multi-language support is also possible.

An example returning step-up authentication hints:

```json
{
  "decision": false,
  "context": {
    "acr_values": "urn:com:example:loa:3",
    "amr_values": "mfa hwk"
  }
}
```

In this case, the PEP can instruct the user to "re-authenticate at LOA 3 or higher (MFA + hardware key) and retry."

Notably, even when `decision: true`, if the PEP does not understand the `context`, it MAY choose to reject the access. Conversely, `decision: false` is strict — the PEP MUST NOT permit access.

---

## 4. Access Evaluations API — Batch Evaluation

The Access Evaluation API in Section 3 was "one request = one decision." But in real applications, there are scenarios where you need to check permissions for multiple resources simultaneously when rendering a screen.

For example, on a document list screen, checking "can this user read?" for each of 30 documents individually would mean 30 API calls — highly inefficient.

The **Access Evaluations API** (note the trailing `s`) is a batch evaluation API that solves this problem.

### 4.1 Batch Request

Bundle multiple evaluation requests in an `evaluations` array:

```json
{
  "subject": {
    "type": "user",
    "id": "alice@example.com"
  },
  "action": {
    "name": "can_read"
  },
  "evaluations": [
    {
      "resource": {
        "type": "document",
        "id": "boxcarring.md"
      }
    },
    {
      "resource": {
        "type": "document",
        "id": "subject-search.md"
      }
    },
    {
      "resource": {
        "type": "document",
        "id": "resource-search.md"
      }
    }
  ]
}
```

The key mechanism here is **default values**. Top-level `subject`, `action`, `resource`, and `context` serve as defaults for each element in the `evaluations` array. In the example above, all three evaluations use the same `subject` and `action`, so they're specified at the top level to avoid duplication.

Individual evaluations can override defaults:

```json
{
  "subject": {
    "type": "user",
    "id": "alice@example.com"
  },
  "action": {
    "name": "can_read"
  },
  "evaluations": [
    {
      "resource": { "type": "document", "id": "1" }
    },
    {
      "resource": { "type": "document", "id": "2" }
    },
    {
      "action": { "name": "can_edit" },
      "resource": { "type": "document", "id": "3" }
    }
  ]
}
```

Only the third evaluation overrides the `action` to `can_edit`.

### 4.2 Batch Response

The response also uses an `evaluations` array, corresponding to the request in the same order:

```json
{
  "evaluations": [
    { "decision": true },
    { "decision": false, "context": { "reason": "resource not found" } },
    { "decision": false, "context": { "reason": "Subject is a viewer of the resource" } }
  ]
}
```

### 4.3 Evaluation Semantics — Three Execution Modes

Batch evaluation supports three execution modes via `options.evaluations_semantic`:

| Semantic                     | Behavior                                              | Programming Analogy |
| :--------------------------- | :---------------------------------------------------- | :------------------ |
| **`execute_all`**            | Execute all requests and return all results (default) | Array `map`         |
| **`deny_on_first_deny`**     | Short-circuit on first denial                         | `&&` operator       |
| **`permit_on_first_permit`** | Short-circuit on first permit                         | `\|\|` operator     |

Let's see how they work with a concrete example. Suppose we check `read` permissions for three documents (doc#1, doc#2, doc#3), with results of `true`, `false`, `true` respectively:

- **`execute_all`**: Evaluates all three -> returns `[true, false, true]`
- **`deny_on_first_deny`**: doc#1 -> true, doc#2 -> false, stops here. doc#3 is not evaluated -> returns `[true, false]`
- **`permit_on_first_permit`**: doc#1 -> true, stops here. doc#2 and doc#3 are not evaluated -> returns `[true]`

`deny_on_first_deny` is useful for scenarios where "all checks must pass." For example, sequentially verifying that a user has a specific role AND is the resource owner AND it's within business hours. `permit_on_first_permit` is for scenarios where "matching any one rule is sufficient."

### 4.4 Error Handling

Batch evaluation has two types of errors:

1. **Transport-level errors** — Errors affecting the entire request (HTTP 4XX / 5XX)
2. **Individual evaluation errors** — A specific evaluation within the `evaluations` array fails. Returns `decision: false` + error information in `context`

```json
{
  "evaluations": [
    { "decision": true },
    {
      "decision": false,
      "context": {
        "error": { "status": 404, "message": "Resource not found" }
      }
    },
    { "decision": false, "context": { "reason": "Subject is a viewer" } }
  ]
}
```

Individual errors default to deny (`false`), and the overall request does not fail.

---

## 5. Search APIs — Reverse Lookups for "Who?" and "What?"

The Access Evaluation API was a **forward lookup**: "Can Alice read document#123?" But real applications also need reverse lookups:

- **"Who can read document#123?"** — Display in sharing settings
- **"Which documents can Alice read?"** — Filter the document list
- **"What operations can Alice perform on document#123?"** — Control UI button visibility

These are the **Search APIs**. By omitting the `id` of one element from the 4-tuple in the request, the PDP returns a list of permitted entities.

### 5.1 Three Types of Search APIs

| API                 | Omitted Element   | Question                                                | Endpoint                     |
| :------------------ | :---------------- | :------------------------------------------------------ | :--------------------------- |
| **Subject Search**  | Subject's `id`    | "Who can perform this action on this resource?"         | `/access/v1/search/subject`  |
| **Resource Search** | Resource's `id`   | "Which resources can this user perform this action on?" | `/access/v1/search/resource` |
| **Action Search**   | The entire Action | "What actions can this user perform on this resource?"  | `/access/v1/search/action`   |

### 5.2 Subject Search Example

```json
// Request: Which users can can_read account#123?
{
  "subject": {
    "type": "user"
  },
  "action": {
    "name": "can_read"
  },
  "resource": {
    "type": "account",
    "id": "123"
  }
}
```

The `subject` has a `type` but no `id`. This signals "search for Subjects."

```json
// Response
{
  "results": [
    { "type": "user", "id": "alice@example.com" },
    { "type": "user", "id": "bob@example.com" }
  ]
}
```

### 5.3 Resource Search Example

```json
// Request: Which accounts can alice can_read?
{
  "subject": {
    "type": "user",
    "id": "alice@example.com"
  },
  "action": {
    "name": "can_read"
  },
  "resource": {
    "type": "account"
  }
}
```

### 5.4 Pagination

Search APIs can return large result sets. Pagination is designed around **opaque tokens**.

![Pagination](./assets/authzen-authorization-api-deep-dive/pagination.png)

| Field             | Direction | Description                                                                |
| :---------------- | :-------- | :------------------------------------------------------------------------- |
| `page.limit`      | Request   | Maximum items per page                                                     |
| `page.token`      | Request   | `next_token` from the previous response (for page 2+)                      |
| `page.next_token` | Response  | Token for the next page. Empty string means final page                     |
| `page.count`      | Response  | Number of items in this page                                               |
| `page.total`      | Response  | Total item count (estimate, may fluctuate)                                 |
| `page.properties` | Both      | Implementation-specific attributes such as sorting or filtering (optional) |

Important constraint: During pagination, `subject`, `action`, `resource`, and `context` MUST NOT be changed. If changed, the PDP SHOULD return an error.

### 5.5 Search API Semantics

Important rules defined by the specification:

- Results from a Search API, when passed to the Access Evaluation API, SHOULD yield `decision: true`. However, this is not guaranteed since the decision may depend on time-varying factors
- Searches SHOULD be performed **transitively**. For example, if user U is a member of group G, and group G is a viewer of document D, then user U should appear in Subject Search results for document D

---

## 6. PDP Metadata — The PDP's Self-Description

**PDP Metadata** is the mechanism by which a PDP tells its clients (PEPs) which endpoints it supports.

The mechanism follows the **`.well-known` URI** pattern (RFC 8615) — a web convention for publishing server configuration at a known URL. For example, OAuth authorization servers publish their configuration at `/.well-known/oauth-authorization-server`. AuthZEN PDPs follow the same pattern.

### 6.1 Discovery Endpoint

```
GET /.well-known/authzen-configuration HTTP/1.1
Host: pdp.example.com
```

In multi-tenant environments, tenant-specific metadata can be provided:

```
GET /.well-known/authzen-configuration/tenant1 HTTP/1.1
Host: pdp.example.com
```

### 6.2 Metadata Response

```json
{
  "policy_decision_point": "https://pdp.example.com",
  "access_evaluation_endpoint": "https://pdp.example.com/access/v1/evaluation",
  "access_evaluations_endpoint": "https://pdp.example.com/access/v1/evaluations",
  "search_subject_endpoint": "https://pdp.example.com/access/v1/search/subject",
  "search_resource_endpoint": "https://pdp.example.com/access/v1/search/resource",
  "search_action_endpoint": "https://pdp.example.com/access/v1/search/action",
  "capabilities": ["urn:ietf:params:authzen:some-capability"]
}
```

| Parameter                     | Required | Description                                        |
| :---------------------------- | :------- | :------------------------------------------------- |
| `policy_decision_point`       | REQUIRED | PDP identifier (URL)                               |
| `access_evaluation_endpoint`  | REQUIRED | Single evaluation API endpoint                     |
| `access_evaluations_endpoint` | OPTIONAL | Batch evaluation API endpoint                      |
| `search_subject_endpoint`     | OPTIONAL | Subject search endpoint                            |
| `search_resource_endpoint`    | OPTIONAL | Resource search endpoint                           |
| `search_action_endpoint`      | OPTIONAL | Action search endpoint                             |
| `capabilities`                | OPTIONAL | List of URNs for capabilities supported by the PDP |

If an optional parameter is absent, the PEP can determine that the corresponding API is not supported. For example, if `search_subject_endpoint` is missing, Subject Search is not available.

### 6.3 Signed Metadata

Metadata can also be provided as a **JWT (JSON Web Token, RFC 7519)** via the `signed_metadata` parameter, enabling tamper detection through its header-payload-signature structure.

Requirements for signed metadata in the specification:

- The JWT MUST be signed with **JWS (RFC 7515)**
- The JWT MUST contain an `iss` (issuer) claim
- Values in signed metadata **take precedence** over plain JSON metadata
- `signed_metadata` itself SHOULD NOT appear as a claim within the JWT
- If the PEP does not support signature verification, it MAY ignore `signed_metadata`

This enables metadata integrity verification independent of TLS/PKI. This is particularly valuable in environments with intermediate proxies, where TLS alone cannot guarantee end-to-end integrity.

### 6.4 Validation

The PEP MUST verify that the `policy_decision_point` value in the metadata matches the PDP identifier used to construct the `.well-known` URL. If they don't match, the metadata MUST NOT be used. This is the same mix-up attack countermeasure used in OAuth AS Metadata.

---

## 7. HTTPS Binding — The Actual HTTP Requests

While the Authorization API itself is designed to be transport-agnostic, the specification defines the **HTTPS binding** as mandatory (with potential future additions for gRPC, CoAP, etc.).

### 7.1 Endpoint List

All requests are sent via HTTPS POST.

| API                    | Default Path                 | Metadata Parameter            |
| :--------------------- | :--------------------------- | :---------------------------- |
| **Access Evaluation**  | `/access/v1/evaluation`      | `access_evaluation_endpoint`  |
| **Access Evaluations** | `/access/v1/evaluations`     | `access_evaluations_endpoint` |
| **Subject Search**     | `/access/v1/search/subject`  | `search_subject_endpoint`     |
| **Resource Search**    | `/access/v1/search/resource` | `search_resource_endpoint`    |
| **Action Search**      | `/access/v1/search/action`   | `search_action_endpoint`      |

If endpoint URLs are provided via PDP Metadata (Section 6), use those. Otherwise, use the default paths.

### 7.2 Request Example

```http
POST /access/v1/evaluation HTTP/1.1
Host: pdp.mycompany.com
Content-Type: application/json
Authorization: Bearer <myoauthtoken>
X-Request-ID: bfe9eb29-ab87-4ca3-be83-a1d5d8305716

{
  "subject": {
    "type": "user",
    "id": "alice@acmecorp.com"
  },
  "resource": {
    "type": "todo",
    "id": "1"
  },
  "action": {
    "name": "can_read"
  },
  "context": {
    "time": "1985-10-26T01:22-07:00"
  }
}
```

### 7.3 Response Example

```http
HTTP/1.1 200 OK
Content-Type: application/json
X-Request-ID: bfe9eb29-ab87-4ca3-be83-a1d5d8305716

{
  "decision": true
}
```

### 7.4 Error Responses

The critical point here is that **authorization "denial" and HTTP errors are entirely different things**.

| Status Code                 | Meaning                                                                    |
| :-------------------------- | :------------------------------------------------------------------------- |
| **200 + `decision: false`** | The authorization request was processed successfully; the result is "deny" |
| **400**                     | Malformed request                                                          |
| **401**                     | PEP is not authenticated to the PDP (e.g., invalid Bearer token)           |
| **403**                     | PEP is not authorized to use the PDP                                       |
| **500**                     | PDP internal error                                                         |

In other words, `401` means "the PEP failed to authenticate to the PDP," while `200 + decision: false` means "the PDP denied access based on policy." These two must not be confused.

![Response](./assets/authzen-authorization-api-deep-dive/response.png)

### 7.5 Request ID

The PEP can assign a unique ID to requests via the `X-Request-ID` header. The PDP MUST include the same ID in the response. This is used for tracing and debugging in distributed systems.

---

## 8. Mapping to Authorization Models

The Authorization API does not assume a specific authorization model. It works with RBAC, ABAC, ReBAC, or any other model.

### 8.1 Usage with Each Authorization Model

| Authorization Model | Subject Usage                                 | Resource Usage                                         | Context Usage                            |
| :------------------ | :-------------------------------------------- | :----------------------------------------------------- | :--------------------------------------- |
| **RBAC**            | Include role information in `properties`      | Type and ID                                            | Often unused                             |
| **ABAC**            | Include attribute information in `properties` | Include attribute information in `properties`          | Environmental info: time, location, etc. |
| **ReBAC**           | Resolve relationships via ID                  | Include owner/relationship information in `properties` | Often unused                             |

The flexibility of `properties` and `context` in the Authorization API enables this model-agnostic design.

---

## 9. Comparison with XACML

The Authorization API is not a successor to XACML, but addresses the same problem domain. Let's compare.

| Comparison           | XACML                                         | AuthZEN Authorization API                          |
| :------------------- | :-------------------------------------------- | :------------------------------------------------- |
| **Era**              | 2003 (1.0), 2013 (3.0)                        | Published March 2026 (Standards Track)             |
| **Data Format**      | XML                                           | JSON                                               |
| **Decision Values**  | Permit / Deny / NotApplicable / Indeterminate | true / false                                       |
| **Policy Language**  | XACML (XML-based) defined                     | **Not defined** (uses OPA, Cedar, etc.)            |
| **Batch Evaluation** | Multiple Decision Profile                     | Access Evaluations API + evaluation semantics      |
| **Search**           | None (PDP-dependent)                          | Search APIs (Subject / Resource / Action)          |
| **Discovery**        | None                                          | PDP Metadata (`.well-known/authzen-configuration`) |
| **Transport**        | SOAP / HTTP                                   | HTTPS (+ future gRPC)                              |
| **Complexity**       | Very high                                     | Intentionally simple                               |
| **Adoption**         | Large enterprises / government                | Designed for modern cloud-native environments      |

The biggest difference is that **XACML standardized both the decision method (policy language) and the communication protocol, while AuthZEN deliberately avoids the decision method and standardizes only the communication protocol**.

This is an intentional design decision. Given that OPA (Rego), Cedar, Topaz, and others already have mature policy languages, standardizing only the interface that connects PDPs to PEPs is more practical than also standardizing a policy language.

---

## 10. Security Considerations

The PEP-PDP communication is the very foundation of access control. If this communication is attacked, the authorization decisions themselves can be tampered with.

### 10.1 Communication Integrity and Confidentiality

TLS (HTTPS) is REQUIRED for PEP-PDP communication. The reasons are clear:

- **Integrity**: An attacker modifying requests or responses could rewrite `decision: false` to `true`
- **Confidentiality**: Requests contain "who is trying to access what," and leakage would expose internal structure and behavioral patterns

### 10.2 PEP Authentication

The PDP SHOULD authenticate the PEP. Without authentication, attackers could flood the PDP with requests for:

- **DoS attacks** — Taking down the PDP and disabling all authorization decisions
- **Policy probing** — Testing various request patterns to infer internal policies

Authentication methods are out of scope for the specification, but the following are cited:

- mTLS
- OAuth-based authentication (Bearer Token)
- API keys

### 10.3 JSON Payload Considerations

The specification RECOMMENDS that JSON payloads follow the **I-JSON profile (RFC 7493)**:

- UTF-8 encoding (no invalid Unicode sequences)
- Numeric values within IEEE 754 double-precision range
- Unique member names after escape processing
- Null-valued properties SHOULD be omitted

### 10.4 Trust Model

The specification states clearly: **The PDP must trust the PEP.**

This may seem surprising at first, but it makes sense when you think about it. The PEP is ultimately the one that allows or denies access, and no PDP can be effective if the PEP ignores its decisions. The PDP trusting the attribute values sent by the PEP is part of this trust relationship.

### 10.5 Response Integrity

The PDP MAY add **digital signatures** to responses. While TLS provides transport-layer protection, signatures provide application-layer non-repudiation and integrity verification. This is particularly valuable in environments with intermediate proxies.

### 10.6 Availability and DoS Countermeasures

If the PDP goes down, access control for the entire application ceases to function. The specification recommends the following defenses for PDPs:

- Payload size limits
- Rate limiting
- Protection against invalid JSON and deeply nested JSON
- Memory consumption limits

![Availability and DoS](./assets/authzen-authorization-api-deep-dive/availability-and-dos.png)

---

## 11. The Ecosystem in Practice

### 11.1 AuthZEN Working Group

AuthZEN (Authorization Zone) was established as a Working Group under the OpenID Foundation in 2023. Key contributors and companies:

| Company          | Contribution                                                |
| :--------------- | :---------------------------------------------------------- |
| **Aserto**       | Specification editor (Omri Gazitt), Topaz PDP               |
| **Axiomatics**   | Specification editor (David Brossard), XACML/ALFA expertise |
| **SGNL**         | Specification editor (Atul Tulshibagwale), contributor      |
| **Styra**        | Developer of OPA                                            |
| **AWS**          | Developer of Cedar                                          |
| **AuthZed**      | Developer of SpiceDB (Zanzibar)                             |
| **Okta / Auth0** | Developer of OpenFGA (ReBAC engine)                         |

### 11.2 Interop Demo — Can You Really Swap PDPs?

"Standardize the API and PDPs become interchangeable" might sound idealistic. However, the AuthZEN WG has demonstrated this at Interop events.

At **Identiverse 2024** (June 2024), a demo "Todo App" operated with a single PEP implementation that connected to 5+ different PDPs (Topaz, Axiomatics, OpenFGA, etc.) by simply switching endpoint URLs. It was proven that PDPs can be swapped without any code changes.

### 11.3 Relationship to Zero Trust Architecture

AuthZEN directly aligns with NIST SP 800-207 (Zero Trust Architecture). Zero Trust is not just about "not trusting the network boundary" — it also demands that "every request is individually authorized." AuthZEN provides exactly this "per-request authorization decision" through a standard API.

### 11.4 Current Status

Authorization API 1.0 was **officially published as Standards Track on March 11, 2026.** After progressing through the Implementer's Draft stage, all the APIs discussed in this article are defined:

- Access Evaluation API (single evaluation)
- Access Evaluations API (batch evaluation)
- Search APIs (Subject / Resource / Action search)
- PDP Metadata (discovery)

The specification also includes the establishment of IANA registries (PDP Metadata, PDP Capabilities, Well-Known URI `authzen-configuration`, URN sub-namespace `authzen`).

---

## Conclusion

![Conclusion](./assets/authzen-authorization-api-deep-dive/conclusion.png)

Key takeaways of AuthZEN Authorization API 1.0:

1. **A standard API that separates authorization decisions (PDP) from enforcement (PEP).** Externalize authorization logic from application code
2. **The 4-tuple information model (Subject / Action / Resource / Context).** Express "who," "what," "on which resource," and "under what circumstances" in simple JSON
3. **Decision is boolean (true / false).** Intentionally simpler than XACML's 4 possible values
4. **Access Evaluations API for batch evaluation.** Supports default values and 3 evaluation semantics (execute_all / deny_on_first_deny / permit_on_first_permit)
5. **Search APIs for reverse lookups.** Search "who can access," "what can be accessed," and "what actions are allowed" with pagination
6. **PDP Metadata for discovery.** Advertise PDP capabilities via `.well-known/authzen-configuration`
7. **Does not define a policy language.** Existing PDPs like OPA, Cedar, XACML, and Topaz work as-is. Only the API is standardized
8. **HTTPS binding is mandatory.** gRPC and others may be added in the future. PEP-PDP communication is protected with TLS + authentication
9. **Authorization "denial" and HTTP errors are distinct.** `200 + decision: false` is a policy-based denial; `401` is a PEP authentication failure
10. **Developed by the AuthZEN WG under the OpenID Foundation, officially published March 2026.** Major authorization engine developers participated, and interoperability was demonstrated at Interop events

If XACML was "the XML of the authorization world," AuthZEN is "the JSON REST API of the authorization world." They do the same thing — connect PDPs and PEPs via a standard protocol — but AuthZEN has been redesigned for simplicity to match the modern development experience.

---

## References

- [Authorization API 1.0 (OpenID Foundation)](https://openid.net/specs/authorization-api-1_0.html)
- [OpenID AuthZEN Working Group](https://openid.net/wg/authzen/)
- [XACML 3.0 (OASIS)](http://docs.oasis-open.org/xacml/3.0/xacml-3.0-core-spec-os-en.html)
- [NIST SP 800-162: Guide to Attribute Based Access Control (ABAC)](https://csrc.nist.gov/publications/detail/sp/800-162/final)
