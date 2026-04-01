---
title: 'Google Zanzibar Deep Dive: Handling 2 Trillion ACLs in Under 10ms'
published: false
description: 'A deep dive into the Google Zanzibar paper — covering Relation Tuples, the New Enemy problem, Zookies, the Leopard index, and system architecture. With notes on SpiceDB, OpenFGA, and other OSS implementations.'
tags:
  - authorization
  - security
  - architecture
  - google
series: Authorization
---

# Introduction

Spend any time in the authorization space and you'll notice that SpiceDB and OpenFGA both claim to be "inspired by Google Zanzibar." I got curious and pulled up the 2019 USENIX ATC paper — "Zanzibar: Google's Consistent, Global Authorization System" — to see what the fuss was about.

My first reaction after reading it: the data model is almost offensively simple. Over two trillion ACLs, ten million authorization checks per second, p95 latency under 10ms — and the whole thing runs on a single string: `object#relation@user`.

Why does something this minimal hold up at planetary scale without falling apart? This post is my attempt to answer that.

---

## Scope

First, let's place Zanzibar in the authorization stack.

| Layer              | What it does                              | Examples                             |
| :----------------- | :---------------------------------------- | :----------------------------------- |
| **Authentication** | Verifies who the user is                  | OpenID Connect, SAML                 |
| **Token issuance** | Hands out access tokens                   | OAuth 2.0 (RFC 6749)                 |
| **Authorization**  | **"Can this user access this resource?"** | **Zanzibar (this post)**, XACML, OPA |

Zanzibar is purely about authorization decisions. It's a different layer from OAuth. If OAuth is "handing someone a key," Zanzibar is "deciding which rooms that key opens."

Prerequisites:

- Basic access control concepts (who, what, can do what)
- A rough idea of how RBAC works

---

## 1. The Problem Zanzibar Solves

### 1.1 Why Google Needed a Unified Authorization System

When dozens of services each implement their own access control, things get messy fast:

| Problem                        | Why it hurts                                                                                                        |
| :----------------------------- | :------------------------------------------------------------------------------------------------------------------ |
| **Inconsistency**              | "Sharing" behaves differently in Drive vs. Photos — confusing for users                                             |
| **Cross-service coordination** | A Google Photos image embedded in a Docs file: whose ACL applies?                                                   |
| **Access-aware search**        | Building a search index that respects permissions across services is a nightmare if every team solves it separately |
| **Engineering waste**          | Every team reinventing consistency and scalability from scratch                                                     |

Zanzibar solves all of this by acting as a **single unified ACL store + evaluation engine** for all Google services.

### 1.2 Design Goals

The paper lists five goals:

| Goal                  | Description                                         | Concrete target                             |
| :-------------------- | :-------------------------------------------------- | :------------------------------------------ |
| **Correctness**       | Respect user intent                                 | Prevent the "New Enemy" problem (Section 5) |
| **Flexibility**       | Support diverse access control policies             | RBAC, ReBAC, hierarchical ACLs, etc.        |
| **Low latency**       | Authorization shouldn't slow down user interactions | p95 < 10ms                                  |
| **High availability** | If authorization is down, everything is down        | 99.999%+                                    |
| **Scale**             | One system for all of Google                        | 2T+ ACLs, 10M+ requests/sec                 |

"Correctness" is where the New Enemy problem comes in — it's not just about returning the right answer, it's about respecting the causal order of changes.

---

## 2. Relation Tuples — The Data Model

Zanzibar's core is a data model so simple it almost looks wrong: the **Relation Tuple**.

### 2.1 Syntax

```text
⟨object⟩#⟨relation⟩@⟨user⟩
```

"**This user** has **this relation** to **this object**." That's it.

Some examples:

| Tuple                                | Meaning                                                     |
| :----------------------------------- | :---------------------------------------------------------- |
| `doc:readme#owner@alice`             | alice is an **owner** of doc:readme                         |
| `group:eng#member@bob`               | bob is a **member** of group:eng                            |
| `doc:readme#viewer@group:eng#member` | Every **member** of group:eng is a **viewer** of doc:readme |
| `doc:readme#parent@folder:A#...`     | doc:readme lives inside folder:A                            |

Look at the third row. The `@` side isn't a user ID — it's `group:eng#member`. This is called a **userset**: "all users who have the member relation to group:eng." It lets ACLs point to groups, and it lets groups contain other groups.

The neat consequence: **ACLs and groups are the same data structure.** A group is just an object that uses "member" semantics.

### 2.2 What Relation Tuples Can Express

All four of these common patterns fit the same one-line format:

- **Direct access** — `doc:readme#viewer@alice` (alice is a viewer)
- **Group membership** — `group:eng#member@alice` (alice is in the eng group)
- **Indirect access** — `doc:readme#viewer@group:eng#member` (everyone in eng is a viewer)
- **Object hierarchy** — `doc:readme#parent@folder:A#...` (readme is inside folder:A)

No special syntax. One format for everything.

### 2.3 Why Tuples?

Traditional ACLs are usually stored per-object. Zanzibar switched to a tuple-based model for three reasons:

- **Efficient reads**: "What groups is user X a member of?" is just a reverse lookup on tuples
- **Incremental updates**: Adding or removing access means writing or deleting one tuple, not rewriting an entire ACL
- **Unified model**: ACLs and groups don't need separate data structures

---

## 3. Namespace Configuration — Defining Policies

Tuples alone can't express rules like "editors are automatically viewers too." That's what **Namespace Configuration** is for.

### 3.1 Userset Rewrites

Here's the namespace config from Figure 1 of the paper (written in a Protocol Buffers-style config language):

```proto
name: "doc"

relation { name: "owner" }

relation {
  name: "editor"
  userset_rewrite {
    union {
      child { _this {} }                              // directly added editors
      child { computed_userset { relation: "owner" } } // + all owners
    }
  }
}

relation {
  name: "viewer"
  userset_rewrite {
    union {
      child { _this {} }                               // directly added viewers
      child { computed_userset { relation: "editor" } } // + all editors
      child { tuple_to_userset {                        // + viewers of the parent folder
        tupleset { relation: "parent" }
        computed_userset {
          object: $TUPLE_USERSET_OBJECT
          relation: "viewer"
        }
      } }
    }
  }
}
```

The structure is concentric: `owner ⊂ editor ⊂ viewer`. And the "inherit viewer permissions from the parent folder" rule is defined in one place, globally, with no per-object tuples needed.

![Name Configuration](./assets/google-zanzibar-deep-dive/namespace-configuration.png)

### 3.2 The Three Leaf Node Types

Userset rewrite rules are trees built from three kinds of leaf nodes:

| Leaf node              | Meaning                                              | Example                                          |
| :--------------------- | :--------------------------------------------------- | :----------------------------------------------- |
| **`_this`**            | Users directly assigned this relation on this object | Someone explicitly added as `doc:readme#editor`  |
| **`computed_userset`** | Another relation on the same object                  | "owners are automatically editors"               |
| **`tuple_to_userset`** | Follow a relation to another object and inherit      | "look up the parent folder and take its viewers" |

Leaf nodes can be combined with **union**, **intersection**, and **exclusion**. This gives you RBAC, ReBAC, and ABAC-style policies — all from the same config language.

---

## 4. API

Zanzibar exposes five API methods:

| API        | Purpose             | Description                                                            |
| :--------- | :------------------ | :--------------------------------------------------------------------- |
| **Check**  | Authorization check | "Does user U have relation R to object O?"                             |
| **Read**   | Tuple lookup        | Returns raw tuples as stored (does not expand rewrites)                |
| **Write**  | Tuple modification  | Add or remove tuples                                                   |
| **Watch**  | Change streaming    | Stream tuple changes in real time                                      |
| **Expand** | Effective userset   | Returns the full tree of users who have a relation, following rewrites |

### 4.2 How Check Works

Check is the core API. Under the hood:

![Check](./assets/google-zanzibar-deep-dive/check.png)

> **Spanner** is the underlying storage — covered in Section 6. Check requests can also carry a **Zookie** to control consistency — explained in Section 5.

The key thing happening here is **recursive pointer chasing**. To check `viewer`, Zanzibar looks at `editor`. To check `editor`, it looks at `owner`. Deeply nested groups make this recursion expensive. The Leopard index (Section 7) exists specifically to solve that.

One gotcha with Read: it **does not expand userset rewrites**. Reading the `viewer` relation won't return owners or editors, even if the namespace config says they're viewers. For that, use Expand.

---

## 5. The "New Enemy" Problem

Zanzibar's most distinctive feature is **external consistency**. The guarantee: if transaction A commits before transaction B starts, B will always see A's result. The causal order of real-world events is reflected in the database.

This matters because of the "New Enemy" problem.

### 5.1 What Is the New Enemy Problem?

The paper walks through two examples.

**Example A: Ignoring ACL update order**

![New Enemy](./assets/google-zanzibar-deep-dive/new-enemy.png)

**Example B: Old ACL applied to new content**

1. Alice removes Bob from a document's ACL
2. Alice asks Charlie to add new content to the document
3. Bob shouldn't be able to see the new content. But if the ACL check evaluates against the **pre-removal ACL**, Bob gets through

This is the New Enemy problem: ignoring the causal ordering between ACL changes and content changes breaks access control in ways that are hard to reason about.

### 5.2 Zookie — Encoding Causality in a Token

Zanzibar fixes this with **Zookies**.

![Zookie](./assets/google-zanzibar-deep-dive/zookie.png)

How it works:

1. When content is modified, the client sends a **content-change check** to Zanzibar
2. Zanzibar encodes the **current global timestamp** into a Zookie and returns it
3. The client stores the Zookie alongside the new content
4. Subsequent ACL checks include the Zookie — telling Zanzibar: "evaluate using a snapshot **at least as fresh as this timestamp**"

Zookies are **opaque byte strings** by design. Clients can't set arbitrary timestamps; they can only pass back what Zanzibar gave them.

**Why not always evaluate at the latest snapshot?** That would require global synchronization across all replicas — wrecking latency and availability. The Zookie's "at-least-as-fresh" semantics let Zanzibar pick any snapshot newer than the encoded timestamp. In practice, most checks use already-replicated local data and never wait on cross-region round trips.

---

## 6. Architecture

To understand the architecture, you first need to know **Spanner**. It's Google's globally distributed database: data is replicated across data centers worldwide, and it provides **external consistency** (the same guarantee Zanzibar builds on). The mechanism is **TrueTime** — a time API backed by GPS and atomic clocks that produces timestamps with bounded error, allowing causally ordered commits across the globe.

Zanzibar is built on top of Spanner's consistency guarantees.

### 6.1 System Overview

![Architecture](./assets/google-zanzibar-deep-dive/architecture.png)

| Component                   | Role                                                                                              |
| :-------------------------- | :------------------------------------------------------------------------------------------------ |
| **aclserver**               | Core server. Handles Check, Read, Expand, Write. Fans out work to other aclservers in the cluster |
| **watchserver**             | Handles Watch requests. Tails the changelog and streams changes in near real time                 |
| **Spanner**                 | ACL storage. Provides external consistency and snapshot reads                                     |
| **Leopard**                 | Specialized index for deeply nested group membership evaluation                                   |
| **Periodic batch pipeline** | Offline jobs: snapshot dumps, tuple garbage collection, etc.                                      |

### 6.2 Storage

Each namespace's relation tuples live in a separate Spanner database. The primary key is `(shard ID, object ID, relation, user, commit timestamp)`.

The critical detail: **commit timestamp is part of the primary key.** Multiple versions of the same tuple are stored as separate rows. This lets Zanzibar do snapshot reads at any timestamp within the GC window — which is the foundation for Zookie semantics.

### 6.3 Replication

Zanzibar replicates all ACL data to **30+ locations worldwide**. Geographic partitioning doesn't work here — you can't predict which region will check which object's ACL.

Write consensus uses **Paxos** (a distributed consensus protocol where multiple nodes agree on a single value). The 5 voting replicas sit in 3 metropolitan areas in the eastern and central US, within 25ms of each other, keeping Paxos commit latency predictable.

---

## 7. How They Hit 10ms

Two trillion ACLs. Ten million requests per second. p95 under 10ms. Here's how.

### 7.1 The Leopard Index

Recursive pointer chasing breaks down when groups are deeply nested or have huge numbers of sub-groups. Leopard preprocesses this.

Leopard maintains two index types:

- **GROUP_2_GROUP(G)**: All direct and indirect descendant groups of group G (pre-expanded)
- **MEMBER_2_GROUP(U)**: All groups user U is a direct member of

"Is user U a member of group G?" becomes a single set intersection:

```text
MEMBER_2_GROUP(U) ∩ GROUP_2_GROUP(G) ≠ ∅
```

Visualized:

![Leopard Index](./assets/google-zanzibar-deep-dive/leopard-index.png)

No deep recursion. The index is stored as skip lists, and set intersection runs in O(min(|A|,|B|)).

Leopard uses a two-tier design: an **offline batch layer** that periodically rebuilds the full index from a Spanner snapshot, and an **online incremental layer** that watches for changes via the Watch API and keeps the index current. The incremental layer is what makes Leopard queries consistent at any given snapshot timestamp.

### 7.2 Hot Spot Handling

When Google Drive shows search results, it fires dozens to hundreds of ACL checks simultaneously. If those documents all share a common group (say, `group:all-employees`), you get a hot spot on the data backing that group.

| Technique                  | What it does                                                                                                       |
| :------------------------- | :----------------------------------------------------------------------------------------------------------------- |
| **Distributed cache**      | aclservers form a consistent-hash cache cluster. Both the caller and callee of delegated RPCs cache results        |
| **Lock table**             | Deduplicates concurrent requests for the same cache key. One request runs; the rest wait for the result            |
| **Timestamp quantization** | Rounds evaluation timestamps up to 1-second or 10-second boundaries, dramatically increasing cache hit rate        |
| **Hot object prefetch**    | When a specific object sees a burst of checks, prefetch all its tuples into cache                                  |
| **Request hedging**        | If a Spanner or Leopard request is slow, send the same request to a second server and use whichever responds first |

Timestamp quantization deserves special mention. Spanner timestamps have microsecond resolution, but Zanzibar rounds them up to 1s or 10s at evaluation time. This means the vast majority of requests land on the same handful of timestamps and share cache results. Rounding up doesn't break consistency — a Spanner snapshot read at timestamp T includes all writes up to T, and if T is in the future, Spanner just waits.

### 7.3 Performance Isolation

In a shared service, one bad client can drag everyone down. Zanzibar's isolation mechanisms:

- Per-client CPU budget (throttled if exceeded and system is under load)
- Per-server limit on outstanding RPCs
- Per `(object, client)` limit on concurrent Spanner reads
- Per-client lock table keys (so one client's throttling doesn't block others)

---

## 8. Production Numbers (December 2018)

| Metric               | Value                            |
| :------------------- | :------------------------------- |
| **Namespaces**       | 1,500+                           |
| **Relation tuples**  | 2 trillion+ (~100 TB)            |
| **Replication**      | 30+ locations worldwide          |
| **Servers**          | 10,000+                          |
| **Check QPS (peak)** | ~4.2M                            |
| **Read QPS (peak)**  | ~8.2M                            |
| **Check Safe p50**   | 3ms                              |
| **Check Safe p95**   | ~10ms                            |
| **Check Safe p99**   | ~15ms                            |
| **Check Recent p95** | ~60ms                            |
| **Availability**     | 99.999% (sustained over 3 years) |

Two request categories:

- **Safe**: Zookie is older than 10 seconds → serves from local replica (fast)
- **Recent**: Zookie is within the last 10 seconds → may require cross-region round trips (~60ms)

Safe requests outnumber Recent by roughly 100:1. That gap is entirely by design — Zookies make the common case local.

---

## 9. Lessons from the Paper

Section 4.5 of the paper (Lessons Learned) is unusually candid for a systems paper. Five years of production, written honestly.

### 9.1 Flexibility Comes Later

The initial userset rewrite only had `_this`. `computed_userset` and `tuple_to_userset` were added later, in response to actual client requirements from Drive and Photos. Google didn't design the perfect abstraction upfront — they extended it as real use cases showed up.

### 9.2 Most Freshness Requirements Are Loose

The majority of clients are fine with slightly stale ACL evaluations. Zanzibar's Zookie protocol was designed around this: default to loose freshness, tighten only when necessary. That's the key to hitting p95 10ms — most requests never need cross-region coordination.

### 9.3 You Can't Skip Hot Spot Mitigation

The Drive search case — hundreds of simultaneous ACL checks that all fan into the same popular group — created hot spots that general caching couldn't fully absorb. They added targeted optimizations: hotness detection, full-tuple prefetch, delayed cancellation of secondary checks when waiters are queued. Hot spot handling wasn't nice-to-have; it was essential.

### 9.4 ReBAC as a Paradigm

Zanzibar has effectively become the reference implementation for **Relationship-Based Access Control (ReBAC)**. The comparison:

| Model     | Decision basis                             | Example                                             |
| :-------- | :----------------------------------------- | :-------------------------------------------------- |
| **RBAC**  | User's role                                | "admin role → can delete"                           |
| **ABAC**  | User and resource attributes               | "same department + business hours → access granted" |
| **ReBAC** | **Relationship between user and resource** | "owner of the doc, or viewer of its parent folder"  |

ReBAC's advantage is that real-world organizational structure — folder hierarchies, team memberships, org charts — maps directly to the authorization model. Google Drive's "share this folder with your team" is a textbook ReBAC problem.

---

## 10. The OSS Ecosystem

The paper landed in 2019 and immediately spawned a cluster of projects:

| Project              | By           | Notes                                                                                                             |
| :------------------- | :----------- | :---------------------------------------------------------------------------------------------------------------- |
| **SpiceDB**          | AuthZed      | The most faithful OSS implementation. Founded by former Zanzibar team members. Uses its own schema language (Zed) |
| **OpenFGA**          | Okta / Auth0 | Zanzibar-inspired ReBAC engine. CNCF incubating (2024). Integrated into the Auth0 ecosystem                       |
| **Ory Keto**         | Ory          | Zanzibar-based authorization service, part of Ory's auth stack                                                    |
| **Google Cloud IAM** | Google       | Explicitly built on top of Zanzibar (stated in the paper itself)                                                  |

It's not just OSS. **Airbnb built an internal system called "Himeji"** directly inspired by Zanzibar. Carta and Notion have both adopted Zanzibar-style approaches.

---

## Wrap-up

The key ideas from Zanzibar:

1. **`object#relation@user` — a single tuple format that unifies ACLs and groups**. The same structure handles direct permissions, group membership, and object hierarchies
2. **Userset Rewrites for flexible policy definition.** `owner ⊂ editor ⊂ viewer` and folder-to-document inheritance, all declared in one namespace config
3. **Zookies solve the New Enemy problem.** An opaque token encodes a causal timestamp; subsequent checks respect that ordering
4. **Built on Spanner's external consistency.** TrueTime (GPS + atomic clocks) makes causally ordered commits possible at global scale
5. **Leopard makes deep nesting fast.** Pre-expand group-to-group relationships; membership checks become a set intersection in O(min(|A|,|B|))
6. **Timestamp quantization + distributed caching absorb hot spots.** Hundreds of simultaneous checks from a single search query don't blow up the system
7. **Zanzibar defined the ReBAC landscape.** SpiceDB, OpenFGA, and Ory Keto are all downstream of this paper

Think of Zanzibar as the GFS of authorization systems. GFS established the design patterns for distributed storage. Zanzibar did the same for relationship-based access control.

---

## References

- [Zanzibar: Google's Consistent, Global Authorization System (USENIX ATC '19)](https://www.usenix.org/conference/atc19/presentation/pang)
- [SpiceDB (AuthZed)](https://github.com/authzed/spicedb)
- [OpenFGA (Okta/Auth0)](https://openfga.dev/)
- [Ory Keto](https://www.ory.sh/keto/)
- [Google Cloud IAM](https://cloud.google.com/iam/)
