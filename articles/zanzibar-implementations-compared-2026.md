---
title: 'Zanzibar Implementations Compared (Late 2026): SpiceDB, OpenFGA, Permify, Keto, Topaz, Warrant'
published: true
description: 'Six open-source projects say they are modelled on Google Zanzibar. I loaded the same model into two of them and read the protos of the rest. They differ on the consistency token, reverse lookup, conditions, storage and who still ships releases.'
tags:
  - authorization
  - security
  - architecture
  - opensource
series: Authorization
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/zanzibar-implementations-compared-2026/cover.png?v=54ffced2'
id: 5038208
date: '2026-11-14T22:24:58Z'
---

I wrote the same docs-and-folders model for SpiceDB and OpenFGA, loaded both, and wrote the same four tuples. SpiceDB answered the write with a token. OpenFGA answered with `{}`.

That empty object is the most important line in this comparison. The Zanzibar paper's answer to the "new enemy" problem is the zookie: a token you get back from a write and send with a later check, so the check is evaluated at a snapshot no older than your write. Six open-source projects describe themselves as Zanzibar-inspired. Two of them hand you a working zookie.

The paper itself, tuples, rewrites, Leopard and the 10 ms story are in my [Google Zanzibar Deep Dive](https://dev.to/kanywst/google-zanzibar-deep-dive-handling-2-trillion-acls-in-under-10ms-f06). If you are still deciding whether you need ReBAC at all, start with [RBAC vs ABAC vs ReBAC](https://dev.to/kanywst/rbac-vs-abac-vs-rebac-how-to-choose-and-implement-access-control-models-3i2d). This article assumes you already want a Zanzibar-style system and are picking one. Everything below was checked on 2026-11-15; the full notes with per-row sources live at [zanzibar-paper: Zanzibar-style systems compared](https://0-draft.github.io/zanzibar-paper/en/ecosystem/compare/).

## Who still ships

![Per-project lanes from first release to the latest release, with license changes, CNCF milestones, the Warrant and Permify acquisitions and Aserto's wind-down](./assets/zanzibar-implementations-compared-2026/diagrams/01-timeline.png?v=bb91896b)

`gh api repos/<org>/<repo>/releases/latest` on 2026-11-15:

| Project | Steward | License | Latest release | State |
| --- | --- | --- | --- | --- |
| SpiceDB | AuthZed | Apache-2.0 | v1.57.1 (2026-11-10) | Active |
| OpenFGA | CNCF Incubating, Okta as core maintainer; managed as Auth0 FGA | Apache-2.0 | v1.22.1 (2026-10-28) | Active |
| Permify | FusionAuth (acquired 2025-11-20) | AGPL-3.0 since 2025-05-12 | v1.7.6 (2026-11-05) | Active, docs moved to fusionauth.io |
| Ory Keto | Ory | Apache-2.0 | v26.2.0 (2026-03-20) | Last commit 2026-07-29 |
| Topaz | Former Aserto maintainers | Apache-2.0 | v0.33.28 (2026-11-14) | Active; Aserto shut its SaaS on 2025-05-31 |
| Warrant | WorkOS | Apache-2.0 | v1.15.1 (2024-06-10) | No release since; warrant.dev now points to WorkOS FGA |

Three governance facts change the risk profile more than any feature:

- OpenFGA is the only one owned by a foundation. The CNCF TOC moved it to Incubating on 2025-10-28 (announced 2025-11-11). A vendor exit does not take the project with it.
- Permify's LICENSE file has changed five times: Apache-2.0 (2022-07-14), GPL-3.0, AGPL-3.0, Apache-2.0 again (2023-02-14), and AGPL-3.0 (commit "docs: update license", 2025-05-12). Every release since then is AGPL, which matters the moment you modify it and serve it over a network. FusionAuth's acquisition post says "Permify stays open source", which is true and also not a license promise.
- Warrant's own README already told you where it stood: "this open source version of Warrant is only capable of handling low-to-moderate throughput and is best suited for POCs". The same paragraph names Warrant-Tokens as what high-throughput serving needs, and the OSS server never issues one. The repo has had no release in 17 months.

Topaz is the interesting survivor. Aserto's "final chapter" post (2025-04-27) wound the company down but said a group of maintainers would keep supporting Topaz, and they have: v0.33.28 shipped the day before I checked.

## Same model, two schema languages

The model: users, folders, documents. A document has an owner and viewers, sits in a folder, and anyone who can view the folder can view the document. Chen's viewer grant on one document only counts from the office network, so there is a condition too.

SpiceDB, following the arrow example in the [schema docs](https://authzed.com/docs/spicedb/concepts/schema) (`permission read = reader + parent_folder->read`) and the caveat example in the [caveats docs](https://authzed.com/docs/spicedb/concepts/caveats):

```text
definition user {}

caveat in_office(ip ipaddress) {
  ip.in_cidr("10.20.0.0/16")
}

definition folder {
  relation owner: user
  relation viewer: user
  permission view = viewer + owner
}

definition document {
  relation parent: folder
  relation owner: user
  relation viewer: user | user with in_office
  permission edit = owner
  permission view = viewer + edit + parent->view
}
```

OpenFGA, following the [gdrive sample store](https://github.com/openfga/sample-stores/blob/main/stores/gdrive/model.fga) (`define can_read: viewer or owner or viewer from parent`) and the [conditions guide](https://openfga.dev/docs/modeling/conditions):

```text
model
  schema 1.1

type user

type folder
  relations
    define owner: [user]
    define viewer: [user] or owner

type document
  relations
    define parent: [folder]
    define owner: [user]
    define editor: owner
    define viewer: [user, user with in_office] or editor or viewer from parent

condition in_office(ip: ipaddress) {
  ip.in_cidr("10.20.0.0/16")
}
```

Both of these were loaded into real servers by the script below, so they parse. The structural difference is visible already. SpiceDB splits `relation` (stored edges) from `permission` (computed, never written). OpenFGA has only `define`, and a relation is writable if and only if it has a type restriction in brackets. In OpenFGA you can write a tuple to `viewer` and also compute it; in SpiceDB you cannot write to `view`. OpenFGA's server only accepts the JSON form of the model, so the DSL goes through `fga model transform` first.

The other four, mapped onto the paper's three rewrite leaves (`_this`, `computed_userset`, `tuple_to_userset`):

| | Union / intersect / exclude | Folder inheritance (tuple_to_userset) | Schema format |
| --- | --- | --- | --- |
| SpiceDB | `+` `&` `-` | `parent->view` (also `.any()`, and `.all()` which intersects) | own language |
| OpenFGA | `or` `and` `but not` | `viewer from parent` | DSL compiled to JSON |
| Permify | `or` `and` `not` | `parent.viewer` | own language, plus `attribute` and `rule` |
| Ory Keto | `\|\|` `&&` `!` | `this.related.parents.traverse((p) => p.permits.view(ctx))` | TypeScript subset (OPL) |
| Topaz | `\|` `&` `-` | `parent->can_read` | YAML manifest, `version: 3` |
| Warrant | `anyOf` `allOf` `noneOf` | `inheritIf` + `ofType` + `withRelation` | JSON object types |

Keto's is the odd one. OPL looks like code, and the [rewrites example](https://github.com/ory/keto/blob/master/contrib/rewrites-example/namespaces.keto.ts) in Keto's repo is a class per namespace:

```ts
class File implements Namespace {
  related: {
    parents: (File | Folder)[]
    viewers: (User | SubjectSet<Group, "members">)[]
    owners: (User | SubjectSet<Group, "members">)[]
  }
  permits = {
    view: (ctx: Context): boolean =>
      this.related.parents.traverse((p) => p.permits.view(ctx)) ||
      this.related.viewers.includes(ctx.subject) ||
      this.related.owners.includes(ctx.subject),
    edit: (ctx: Context) => this.related.owners.includes(ctx.subject),
  }
}
```

It is not TypeScript you can run. It is a parse target that happens to type-check in your editor, which is either the best or the worst thing about it depending on whether your team will try to put an `if` in there.

## Running both

`run.sh` in [the assets directory](https://github.com/0-draft/dev.to/tree/main/articles/assets/zanzibar-implementations-compared-2026) starts `authzed/spicedb:v1.57.1` and `openfga/openfga:v1.22.1` with in-memory datastores, loads the two schemas above, writes the same tuples over HTTP, and asks both servers the same questions:

```text
folder:eng#viewer@user:beto
document:readme#parent@folder:eng
document:readme#owner@user:anne
document:plan#viewer@user:chen[in_office]
```

![Grid of the five steps of run.sh with SpiceDB's and OpenFGA's actual responses side by side, colored by whether each server could answer the question](./assets/zanzibar-implementations-compared-2026/diagrams/02-tokens.png?v=9b699341)

The interesting rows are 1, 4 and 5.

### Row 1 and 4: the token

SpiceDB's `WriteRelationships` response:

```json
{"writtenAt":{"token":"Gh8KEzE3OTQ2OTQxODIwNDI1MTQ0OTESCDUxMzE4Nzdh"}}
```

OpenFGA's `POST /stores/{id}/write` response:

```json
{}
```

After removing Beto from `folder:eng`, SpiceDB with `fullyConsistent` says `PERMISSIONSHIP_NO_PERMISSION`, and the same check with `atExactSnapshot` set to the token from the first write says `PERMISSIONSHIP_HAS_PERMISSION`. The ZedToken names a point in the datastore's history and you can evaluate at it. That is what makes the paper's "store the zookie next to the content version" pattern work: a document saved before an ACL tightened can be checked against the ACL that was in force when it was saved, and a document saved after can demand at least that fresh.

SpiceDB's four modes are `minimize_latency` (default for checks and lookups), `at_least_as_fresh`, `at_exact_snapshot` and `fully_consistent`. The catch with the default: reads are served at a revision quantized to `--datastore-revision-quantization-interval`, which defaults to `5s` (from `spicedb serve --help`), so `minimize_latency` can be a few seconds behind your own write. Send the token back with `at_least_as_fresh` on the request that follows a write.

OpenFGA's [consistency page](https://openfga.dev/docs/interacting/consistency) is upfront: zookies are not implemented and "OpenFGA is considering a similar feature in future releases". It offers `MINIMIZE_LATENCY` (default) and `HIGHER_CONSISTENCY`. The detail people miss: "OpenFGA caching is disabled by default", and with caching off both modes read the database directly. The staleness only appears when you turn on `--check-query-cache-enabled`, whose help text says it "turns Check and ListObjects into eventually consistent APIs" with a default TTL of `10s`. So out of the box OpenFGA is consistent and slower; tune it and you get a 10-second window with no token to close it except `HIGHER_CONSISTENCY` on every request that matters.

The rest:

| | Token | What it does |
| --- | --- | --- |
| Permify | Snap Token | Returned by Write; send it as `snap_token` on Check for "at least as fresh". Without one, the latest transaction id is used and doubles as a cache key ([docs](https://fusionauth.io/permify-docs/operations/snap-tokens)) |
| Ory Keto | `snaptoken` field | Every occurrence in `check_service.proto` says "This field is not implemented yet and has no effect." |
| Topaz | none | No token field in the v3 reader API |
| Warrant | `Warrant-Token` header | The OSS middleware only recognises the literal `latest`, which routes the read to the primary ([`wookie.go`](https://github.com/warrant-dev/warrant/blob/main/pkg/wookie/wookie.go)). The server never returns a token to carry |

If your application has the paper's new-enemy shape (remove a user, then add sensitive content, and the removed user must never see it), SpiceDB and Permify let you enforce it per request. With the others you either read at highest consistency or accept the cache window.

### Row 5: a condition without its context

Both servers store Chen's grant with the `in_office` condition and expect `ip` at check time. When it is missing:

```json
{"permissionship":"PERMISSIONSHIP_CONDITIONAL_PERMISSION",
 "partialCaveatInfo":{"missingRequiredContext":["ip"]}}
```

```json
{"code":"validation_error",
 "message":"failed to evaluate relationship condition: 'in_office' - tuple 'document:plan#viewer@user:chen' is missing context parameters '[ip]'"}
```

SpiceDB returns a third answer and tells you which fields would decide it. OpenFGA fails the request. Neither is wrong, but code that does `if resp.permissionship == HAS_PERMISSION` treats SpiceDB's conditional as a deny, and code that does `if err != nil { deny }` treats OpenFGA's error as a deny too, so both fail closed by accident. Write the branch on purpose.

Permify does conditions differently: an `attribute` stored on the entity and a `rule` called from a permission, both evaluated with CEL-like expressions. OpenFGA also has contextual tuples, which are per-request edges that are never stored; useful for "the caller is on network:office" facts that your gateway knows and your tuple store should not. Keto, Topaz (outside its Rego policies) and Warrant's OSS server have nothing in the paper's tuple that holds a condition.

## "Which documents can Anne see?"

Check walks out from one object. A list page asks the reverse, with filtering, sorting and pagination that only your database can do. The paper does not ship this API: Expand returns a tree, and Leopard is an internal index for flattening nested groups, not a listing endpoint. Every project had to decide what to offer here, and the answer decides your list endpoints more than the schema language does.

![Decision flow for a permission-aware list page: lookup-then-filter when the accessible set is small, query-then-bulk-check when the user sees a high share of candidates, and a Watch-fed index otherwise, with each project's API for each approach](./assets/zanzibar-implementations-compared-2026/diagrams/03-listing.png?v=33051241)

The limits in the first diamond are the vendors' own:

- SpiceDB `LookupResources` streams with a cursor, but "it's a heavy request that can cause performance problems when more than 10k results are involved" ([Querying Data](https://authzed.com/docs/spicedb/concepts/querying-data)).
- OpenFGA `ListObjects` and `ListUsers` stop at `listObjectsDeadline` / `listUsersDeadline` (default `3s`) or `listObjectsMaxResults` / `listUsersMaxResults` (default `1000`), whichever comes first ([Relationship Queries](https://openfga.dev/docs/interacting/relationship-queries)). A truncated list cannot be sorted correctly, so a 1000-item cap is a correctness limit for list pages, not just a performance one.

In the script, both returned the same answers: `LookupResources` and `list-objects` gave `readme` for Beto, `LookupSubjects` and `list-users` gave `anne` and `beto` for the readme.

Keto is the gap. Its v1alpha2 protos define `Check`, `BatchCheck`, `Expand`, `ListRelationTuples`, `TransactRelationTuples`, `DeleteRelationTuples` and `ListNamespaces`, and nothing that answers "objects this subject can reach". You can only list stored tuples or expand a tree from an object.

The third approach, an index next to your data kept current from a change stream, is the one the paper has in mind when it says Watch lets clients "maintain secondary indices". That requires a stream. SpiceDB and Permify have a `Watch` stream; OpenFGA has `ReadChanges`, which you poll with a continuation token; Keto, Topaz and Warrant have no change feed in their protos or routes, so the only way to build an index is to dual-write from your application and hope the two never disagree.

The only Leopard-like product is AuthZed Materialize, which "takes inspiration from the Leopard index component described in the Zanzibar paper". It is available only on AuthZed Dedicated, and its Event Streams feature (push precomputed permission changes into your own database) is in early access. Nothing else in the list documents a precomputed group index.

## Storage and topology

| | Datastores | Shape |
| --- | --- | --- |
| SpiceDB | CockroachDB, Cloud Spanner, PostgreSQL, MySQL ("only use if you cannot use PostgreSQL"), memdb (dev) | Peers dispatch sub-problems to each other over a consistent-hash ring so each sub-check is cached on one node |
| OpenFGA | memory (the default), PostgreSQL, MySQL, SQLite | Stateless API servers on one SQL database, optional read replica; per-node caches |
| Permify | PostgreSQL, memory | Servers on PostgreSQL MVCC snapshots; a per-pod cache keyed by snapshot |
| Ory Keto | PostgreSQL, MySQL, CockroachDB, SQLite (not for production) | Stateless containers with separate read and write ports on one SQL database |
| Topaz | Embedded BoltDB | Sidecar or microservice next to the app; Rego policies call into the local directory |
| Warrant | MySQL, PostgreSQL, SQLite | One Go HTTP service on one SQL database |

Two things worth knowing before you pick:

- OpenFGA's default `--datastore-engine` is `memory`. Data "is lost between server restarts". The quick-start works and then forgets everything; set `postgres` before anyone depends on it.
- SpiceDB's datastore page notes that on CockroachDB, `fully_consistent` does not guarantee read-after-write. If you need that guarantee there, use the ZedToken from the write with `at_least_as_fresh`, which is the paper's model anyway.

Topaz is the architectural outlier. With an embedded BoltDB per instance, it is closer to OPA with a relationship store than to a central Zanzibar service. That is a good fit for a sidecar that decides locally and a poor fit for a single global source of truth with snapshot reads.

## In-house: Himeji and Carta

Two companies published how they built their own in 2021. Airbnb's Himeji uses `entity # relation @ principal` tuples on sharded Amazon Aurora instead of Spanner, fans out on write rather than read, and targets a ~98% cache hit rate across consistent-hashed shards; InfoQ reports 99.999% availability, 12 ms at p99, and throughput going from 0 in March 2020 to 850k entities/sec a year later. Carta's AuthZ keeps a precomputed actor and object index that its author maps to Leopard's two set types, and issues a "Ticket", described as synonymous with a zookie, on each write so callers can wait for the async index to catch up.

The pattern in both: the team that builds its own ends up implementing the two pieces the OSS projects mostly skip, a Leopard-style index and a write token. If you need both at scale and do not want AuthZed Dedicated, that is the bill.

## What I would pick

- **You need the new-enemy guarantee per request:** SpiceDB. Permify if AGPL is acceptable to your legal team.
- **You need foundation governance and Apache-2.0 more than snapshot tokens:** OpenFGA. Leave caching off until you have measured, and know that `ListObjects` is for small collections.
- **You already run OPA and want relationships as data for Rego:** Topaz, knowing its steward is now a group of maintainers rather than a company.
- **You already run the Ory stack:** Keto works for check-only workloads. Plan list endpoints around the missing reverse lookup.
- **Warrant:** only if you are moving to WorkOS FGA anyway.

Run `run.sh` against whichever two you are torn between, swap in your own model, and look at what the write returns.

## References

- Pang et al., [Zanzibar: Google's Consistent, Global Authorization System](https://www.usenix.org/conference/atc19/presentation/pang), USENIX ATC '19, §2.2, §2.4, §3.2.4
- SpiceDB: [schema](https://authzed.com/docs/spicedb/concepts/schema), [consistency](https://authzed.com/docs/spicedb/concepts/consistency), [caveats](https://authzed.com/docs/spicedb/concepts/caveats), [datastores](https://authzed.com/docs/spicedb/concepts/datastores), [querying data](https://authzed.com/docs/spicedb/concepts/querying-data), [Materialize](https://authzed.com/docs/materialize/getting-started/overview), [`permission_service.proto`](https://github.com/authzed/api/blob/main/authzed/api/v1/permission_service.proto)
- OpenFGA: [consistency](https://openfga.dev/docs/interacting/consistency), [conditions](https://openfga.dev/docs/modeling/conditions), [relationship queries](https://openfga.dev/docs/interacting/relationship-queries), [configure OpenFGA](https://openfga.dev/docs/getting-started/setup-openfga/configure-openfga), [`openfga_service.proto`](https://github.com/openfga/api/blob/main/openfga/v1/openfga_service.proto), [CNCF incubation announcement](https://www.cncf.io/blog/2025/11/11/openfga-becomes-a-cncf-incubating-project/)
- Permify: [snap tokens](https://fusionauth.io/permify-docs/operations/snap-tokens), [`service.proto`](https://github.com/Permify/permify/blob/master/proto/base/v1/service.proto), [acquisition post](https://permify.co/post/fusionauth-acquires-permify/)
- Ory Keto: [Ory Permission Language](https://www.ory.com/docs/keto/reference/ory-permission-language), [`check_service.proto`](https://github.com/ory/keto/blob/master/proto/ory/keto/relation_tuples/v1alpha2/check_service.proto)
- Topaz: [architecture](https://www.topaz.sh/docs/architecture), [manifest reference](https://www.topaz.sh/docs/directory/manifest-reference), [`reader.proto`](https://github.com/aserto-dev/go-directory/blob/main/proto/aserto/directory/reader/v3/reader.proto), [Aserto, "The final chapter"](https://www.aserto.com/blog/the-final-chapter-for-aserto)
- Warrant: [repository and README](https://github.com/warrant-dev/warrant), [`wookie.go`](https://github.com/warrant-dev/warrant/blob/main/pkg/wookie/wookie.go)
- [InfoQ on Airbnb Himeji](https://www.infoq.com/news/2021/05/airbnb-himeji)
