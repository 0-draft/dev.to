---
title: 'Zookies Without TrueTime: How SpiceDB, OpenFGA and the Rest Order Their Writes'
published: true
description: 'The Zanzibar paper''s answer to the new enemy problem leans on Spanner''s TrueTime. Open-source implementations run on CockroachDB, PostgreSQL and MySQL. I decoded real ZedTokens, read the overlap-key SQL, and measured the window that minimize_latency leaves open.'
tags:
  - authorization
  - security
  - database
  - distributedsystems
series: Authorization
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/zanzibar-without-truetime/cover.png?v=da1a23be'
id: 5038216
date: '2026-11-14T22:27:00Z'
---

I removed a user from a folder in SpiceDB, got the write acknowledged, and asked SpiceDB whether that user could still read a document in the folder. It said yes. For up to 4.9 seconds.

That is not a bug. It is the default consistency mode doing what it says, and it is exactly the window the Zanzibar paper's zookies exist to close. The paper closes it with Spanner and TrueTime. Almost nobody outside Google has TrueTime, so I wanted to know what SpiceDB, Permify, OpenFGA, Ory Keto and Warrant put in its place, down to the SQL.

I covered the paper itself (tuples, the new enemy problem, zookies, Leopard) in [Google Zanzibar Deep Dive](https://dev.to/kanywst/google-zanzibar-deep-dive-handling-2-trillion-acls-in-under-10ms-f06), so this one starts where that left off. The longer notes, with every source, live at [Ordering without TrueTime](https://0-draft.github.io/zanzibar-paper/en/guides/without-truetime/).

Everything below was checked on 2026-11-15 against SpiceDB v1.57.1, OpenFGA v1.22.1, Permify v1.7.6, Ory Keto and Warrant at `main`, and the paper text (USENIX ATC '19).

## What a zookie actually needs from the database

Strip away Spanner and the zookie protocol asks the storage layer for two things. §2.2 calls them "external consistency and snapshot reads with bounded staleness":

1. Commit order follows causality. If `x` happened before `y`, then "`x ≺ y` ... will be assigned timestamps that reflect the causal order: `T_x < T_y`". That includes updates "coordinated via channels invisible to Zanzibar": Alice tells Charlie in a hallway, Charlie moves the document. The database never sees the hallway.
2. Reads at or after a point. "A check is always evaluated at a consistent snapshot no earlier than the given zookie" (§2.4.4).

Neither property says "wall clock". The zookie is "an opaque byte sequence encoding a globally meaningful timestamp" and the paper made it opaque "to discourage our clients from choosing arbitrary timestamps and to allow future extensions" (§2.4). Any position in a history works, as long as the two properties hold for it.

The paper also explains why a logical clock would not do: Lamport clocks "require explicit participation of all 'processes', where in Zanzibar's use cases some of the 'processes' can be external clients or even human users" (§5). So the order has to come from the database. There are three places it can come from:

- Synchronized clocks with a bounded error, plus a wait: Spanner, with TrueTime and commit wait.
- Loosely synchronized clocks: CockroachDB's hybrid logical clocks, which order transactions correctly only when they conflict.
- One primary: PostgreSQL and MySQL. One server sees every commit in order, so causality is free. Global replication is what you give up.

The middle one is where things get interesting.

## CockroachDB: make every write collide

CockroachDB has no TrueTime. Its nodes keep loosely synchronized clocks under `--max-offset`, default `500ms`, and "If observed clock offsets exceed this limit, servers will crash to minimize the likelihood of reading inconsistent data" ([`cockroach start`](https://docs.cockroachlabs.com/docs/stable/cockroach-start)). Inside that 500 ms, two transactions that touch different keys can commit with timestamps in the wrong order. Cockroach Labs calls this "causal reverse" ([Living without atomic clocks](https://www.cockroachlabs.com/blog/living-without-atomic-clocks/)).

AuthZed reproduced the new enemy problem on exactly that gap in 2021 ([The One Crucial Difference Between Spanner and CockroachDB](https://authzed.com/blog/prevent-newenemy-cockroachdb)). The schema was `permission allowed = direct - excluded`. Write `excluded`, then write `direct`, then check at the second write's snapshot, all "in sequence (not parallel)". With one node's clock skewed by chaos-mesh's watchmaker and its network delayed by chaosd, "the check in 3 will succeed". Their summary: "Cockroach does not provide external consistency for transactions involving non-overlapping keys."

The fix is to make the keys overlap. AuthZed found "we needed both transactions to write to the same key in order for Cockroach to assign the timestamps properly". A shared read was not enough.

![Two sequence diagrams. Left, with the insecure overlap strategy: node 1, whose clock is 250 ms fast, commits the removal at 10.250; node 2 later commits the move at 10.100, and a check at 10.100 sees the move without the removal and allows Chen. Right, with the static strategy: both writes also upsert the same row in the transactions table, the write-write conflict pushes the second commit to 10.251, and the check at 10.251 denies Chen.](./assets/zanzibar-without-truetime/diagrams/01-crdb-skew.png?v=c87c8ddd)

The timestamps in the diagram are illustrative. The mechanism is not. Here is the statement SpiceDB v1.57.1 runs at the end of every write transaction on CockroachDB ([`crdb/readwrite.go`](https://github.com/authzed/spicedb/blob/v1.57.1/internal/datastore/crdb/readwrite.go), [`crdb/crdb.go`](https://github.com/authzed/spicedb/blob/v1.57.1/internal/datastore/crdb/crdb.go)):

```go
queryTouchTransaction = fmt.Sprintf(
    "INSERT INTO %s (%s) VALUES ($1::text) ON CONFLICT (%s) DO UPDATE SET %s = now()",
    schema.TableTransactions,   // "transactions"
    schema.ColTransactionKey,   // "key"
    ...

// Touching the transaction key happens last so that the "write intent" for
// the transaction as a whole lands in a range for the affected tuples.
for k := range rwt.overlapKeySet {
    if _, err := tx.Exec(ctx, queryTouchTransaction, k); err != nil {
```

Which keys land in `overlapKeySet` depends on `--datastore-tx-overlap-strategy` ([datastores docs](https://authzed.com/docs/spicedb/concepts/datastores), [`crdb/keys.go`](https://github.com/authzed/spicedb/blob/v1.57.1/internal/datastore/crdb/keys.go)):

| Strategy | Key written | Docs |
| --- | --- | --- |
| `static` (default) | the value of `--datastore-tx-overlap-key` | "All writes overlap to guarantee safety at the cost of write throughput" |
| `prefix` | the part of each resource and subject type before `/`, else `defaultsynckey` | "Only writes that contain objects with same prefix overlap" |
| `request` | the comma-separated values of the `io.spicedb.requestoverlapkey` header | "Only writes with the same io.spicedb.requestoverlapkey header overlap" |
| `insecure` | nothing | "possibly leaving you vulnerable to the New Enemy Problem" |

I ran it against a single-node CockroachDB v25.2.2 to see the rows ([`run-crdb.sh`](https://github.com/0-draft/dev.to/blob/main/articles/assets/zanzibar-without-truetime/run-crdb.sh)). Write `x` deletes a `folder` tuple, write `y` touches a `document` tuple (output trimmed to the `transactions` rows):

```text
== strategy: static
-- write x: remove Chen from folder:A (a tuple on folder)
  key | 2026-11-14 22:19:29.214657
-- write y: move readme into folder:A (a tuple on document)
  key | 2026-11-14 22:19:29.445054
  key | crdb_internal_mvcc_timestamp 1794694769445101854.0000000000

== strategy: prefix
  defaultsynckey | 2026-11-14 22:19:37.382299

== strategy: insecure
(0 rows)
```

Three things I did not expect:

- Under `static`, the row is literally named `key`. The driver's own default constant is `defaultsynckey`, but `spicedb serve` passes its flag default, `--datastore-tx-overlap-key` = `"key"`, which wins.
- `prefix` only splits anything if your type names have a `/`. `folder` and `document` have none, so both fall back to `defaultsynckey` and the strategy behaves like `static`. With `tenant1/folder` and `tenant2/document` they would stop overlapping, and so would the guarantee across tenants.
- The overlap row's MVCC timestamp, `1794694769445101854`, is exactly the revision inside `y`'s ZedToken (decoded below). The last writer of that row is the last committed write.

The cost is one hot row. Every `static` write in the cluster contends on it. AuthZed's line is "This does add a small amount of latency to the write path, but it leaves the read paths performant." Spanner pays with commit wait on every write; SpiceDB on CockroachDB pays with a serialized row.

One read-side caveat that the overlap key does not fix. SpiceDB gets "now" from `SELECT cluster_logical_timestamp()` on whatever node it is connected to, and the docs warn that this "can differ across nodes", so "`fully_consistent` does not guarantee read-after-write consistency on CockroachDB." The token from the write does not have that problem, because it names the write's own commit timestamp. On CockroachDB, `at_least_as_fresh` with a stored ZedToken is stronger than `fully_consistent`.

## PostgreSQL: the snapshot is the token

On PostgreSQL there is one primary, so property 1 needs no clock at all. SpiceDB's driver says so in a comment: "timestamps cannot be used for ordering transactions in PG", and two snapshots can be "mutually uncomparable" ([`postgres/revisions.go`](https://github.com/authzed/spicedb/blob/v1.57.1/internal/datastore/postgres/revisions.go)). A revision is a transaction id plus a `pg_snapshot`.

I wanted to see that inside a real token, so [`run.sh`](https://github.com/0-draft/dev.to/blob/main/articles/assets/zanzibar-without-truetime/run.sh) starts SpiceDB v1.57.1 on PostgreSQL 17, writes the schema below, and decodes what comes back:

```text
definition user {}
definition folder {
  relation viewer: user
  permission view = viewer
}
definition document {
  relation parent: folder
  permission view = parent->view
}
```

Removing Chen from `folder:A` returns:

```json
{
  "writtenAt": {
    "token": "GiQKGENNc0dJTW9HS09pRC84eWxxb0wwR0E9PRIINzMzNjBjODY="
  }
}
```

`protoc --decode_raw` twice gets to the bottom of it:

```text
$ echo "$TOK" | base64 -d | protoc --decode_raw
3 {
  1: "CMsGIMoGKOiD/8ylqoL0GA=="
  2: "73360c86"
}
$ echo CMsGIMoGKOiD/8ylqoL0GA== | base64 -d | protoc --decode_raw
1: 843
4: 842
5: 1794694700802753000

$ psql -c 'SELECT xid, snapshot, timestamp FROM relation_tuple_transaction ORDER BY xid DESC LIMIT 1'
842|842:842:|2026-11-14 22:18:20.802753
```

![Anatomy of two real ZedTokens. PostgreSQL: base64 decodes to DecodedZedToken field 3 with a revision string and an 8-character datastore id prefix; the revision decodes again to PostgresRevision with xmin 843, xmax 843, no in-progress xids, txid 842 and a nanosecond timestamp, meaning snapshot 843:843: in which the removal xid 842 is visible. CockroachDB: the revision is an HLC decimal, 1794694769445101854.0000000000, equal to the overlap row's MVCC timestamp. A token whose prefix does not match the datastore is treated as fully consistent by default.](./assets/zanzibar-without-truetime/diagrams/02-zedtoken-anatomy.png?v=509f220a)

The field numbers come from SpiceDB's [`impl.proto`](https://github.com/authzed/spicedb/blob/v1.57.1/proto/internal/impl/v1/impl.proto) (`DecodedZedToken.v1 = 3`: `revision`, `datastore_unique_id_prefix`, `schema_hash`) and [`pgrevision.proto`](https://github.com/authzed/spicedb/blob/v1.57.1/proto/internal/impl/v1/pgrevision.proto) (`xmin`, `relative_xmax`, `relative_xips`, `optional_txid`, `optional_timestamp`). PostgreSQL recorded the removal's own snapshot as `842:842:`, taken while 842 was still running. SpiceDB calls `snapshot.markComplete(842)` on it, which gives `843:843:`: every xid below 843 is visible. That is property 1 in PostgreSQL's vocabulary. Any snapshot that contains the removal also contains everything that committed before it, because that is what a `pg_snapshot` is.

The timestamp is there, but only as a hint. `optional_timestamp` is used for things like GC windows, never for ordering.

Permify builds its Snap Token from the same raw material: a PostgreSQL `XID8` plus a snapshot string, encoded as base64 of `"xid:snapshot"` ([`snapshot/token.go`](https://github.com/Permify/permify/blob/v1.7.6/internal/storage/postgres/snapshot/token.go)). Its docs describe it only as "a token that consists of an encoded timestamp" ([Snap Tokens](https://fusionauth.io/permify-docs/operations/snap-tokens)). I did not trace how Permify's read path uses it.

## How "at least as fresh" is implemented

The paper's semantics are a lower bound: Zanzibar may "choose any timestamp fresher than the one encoded in a zookie" (§2.2). SpiceDB implements that as a max, in [`pkg/middleware/consistency/consistency.go`](https://github.com/authzed/spicedb/blob/v1.57.1/pkg/middleware/consistency/consistency.go):

```go
// pickBestRevision compares the provided ZedToken with the optimized revision of the datastore, and returns the most
// recent one.
databaseRev, hash, err := dl.OptimizedRevision(ctx)
...
if databaseRev.GreaterThan(decoded.Revision) {
    return databaseRev, hash, false, nil
}
return decoded.Revision, decoded.SchemaHash, true, nil
```

`OptimizedRevision` is the quantized revision every `minimize_latency` request uses: rounded to `--datastore-revision-quantization-interval` (default `5s`) so that concurrent checks share cache entries. That is the paper's §3.2.5 trick ("rounded up to a coarse granularity, such as one or ten seconds") with one difference. Spanner can round *up* into the future because "the read will wait until TrueTime has moved past T". A SQL database cannot read the future, so SpiceDB rounds *down* into the past. Rounding down is where the window comes from.

Note what `GreaterThan` means for PostgreSQL. Two snapshots can be incomparable. If neither is greater, the code falls through to the token's revision, which is the safe choice.

The `datastore_unique_id_prefix` field guards against a different mistake: a token minted by another SpiceDB datastore (a restore, a migration, a different cluster). The default `--mismatch-zed-token-behavior=full-consistency` ignores such a token and reads at head; `min-latency` and `error` are the alternatives.

## Measuring the window

Steps 3 and 6 of `run.sh` grant Chen access, wait for it to settle, remove him, then check four ways and poll:

```text
== 3. Checks right after the removal
minimize_latency:            PERMISSIONSHIP_HAS_PERMISSION
at_least_as_fresh(removal):  PERMISSIONSHIP_NO_PERMISSION
fully_consistent:            PERMISSIONSHIP_NO_PERMISSION
at_exact_snapshot(grant):    PERMISSIONSHIP_HAS_PERMISSION

== 6. How long minimize_latency keeps saying yes after the removal
removal acknowledged -> minimize_latency says NO_PERMISSION: 4.6s
```

Over five more runs, the stale `HAS_PERMISSION` lasted 0.7, 4.6, 4.8, 4.9 and 4.1 seconds. That spread is the position of the removal inside the 5-second quantum. `minimize_latency` is the default for `CheckPermission` ([consistency docs](https://authzed.com/docs/spicedb/concepts/consistency)), so an application that ignores ZedTokens gets this window on every revocation.

The `at_exact_snapshot` line is the other side of opacity. Handing back the grant's token gives a historical answer on purpose, which is useful for paginating and dangerous for authorization. The paper deliberately did not let clients "read or evaluate ACLs at an arbitrary snapshot" (§5).

The paper's flow is still the right one: run the content-change check, store the returned token "with the content change in an atomic write to the client storage" (§2.2), and send it as `at_least_as_fresh` on later checks of that content. SpiceDB's docs say the same: the token "should be stored alongside the newly updated content in the application database", in a `text` column on PostgreSQL. The tokens come back in `written_at`, `deleted_at`, `checked_at` and `read_at` ([`permission_service.proto`](https://github.com/authzed/api/blob/main/authzed/api/v1/permission_service.proto)).

## Read replicas bring the lag back

A single primary gives you ordering. Read replicas take some of it away again, and that is where the token earns its keep. With `--datastore-read-replica-conn-uri`, SpiceDB wraps the datastore in [`proxy/checkingreplicated.go`](https://github.com/authzed/spicedb/blob/v1.57.1/internal/datastore/proxy/checkingreplicated.go):

```go
// If the revision is not known to the replica, use the primary instead.
if err := rr.replica.CheckRevision(ctx, rr.rev); err != nil {
    var irr datastore.InvalidRevisionError
    if errors.As(err, &irr) {
        if irr.Reason() == datastore.CouldNotDetermineRevision {
            rr.chosenReader = rr.primary.SnapshotReader(rr.rev)
```

So a check carrying the removal's token asks the replica "do you have xid 842?" and goes to the primary if not. That is the paper's Safe and Recent split (§4.1) on one machine: old tokens are served locally, fresh ones pay a round trip. The docs add two warnings for MySQL: it "requires two roundtrips instead of one", and "Do not use a load balancer between SpiceDB and MySQL replicas", because SpiceDB has to know which replica answered the revision check. MySQL revisions are an `AUTO_INCREMENT` id in a transactions table ([`mysql` initial schema](https://github.com/authzed/spicedb/blob/v1.57.1/internal/datastore/mysql/migrations/zz_migration.0001_initial_schema.go)). That a later-committed transaction always gets a larger id is my reading of how InnoDB assigns them; SpiceDB's docs do not state it.

On Cloud Spanner, SpiceDB "assumes the database is linearizable and skips the transaction overlap strategy" and reads its revision with `SELECT CURRENT_TIMESTAMP()` ([`spanner/revisions.go`](https://github.com/authzed/spicedb/blob/v1.57.1/internal/datastore/spanner/revisions.go)). That is the configuration closest to the paper.

## Without a token at all

The other implementations mostly skip the token.

OpenFGA says the paper "has a feature called Zookies" and offers two modes instead: `MINIMIZE_LATENCY` (default), where it "will serve queries from the cache when possible", and `HIGHER_CONSISTENCY`, where it "will skip the cache and query the database directly" ([consistency](https://openfga.dev/docs/interacting/consistency)). With a PostgreSQL read replica configured, the second mode also picks the primary ([`postgres.go`](https://github.com/openfga/openfga/blob/v1.22.1/pkg/storage/postgres/postgres.go)):

```go
func (s *Datastore) getPgxPool(consistency openfgav1.ConsistencyPreference) *pgxpool.Pool {
    if consistency == openfgav1.ConsistencyPreference_HIGHER_CONSISTENCY {
        // If we are using higher consistency, we need to use the write database.
        return s.primaryDB
    }
```

That is "as fresh as the primary", not "at least as fresh as my write". The cost difference is the point of zookies: with a token, only checks of recently changed content go to the primary; with a mode, every check that might care does. OpenFGA's docs suggest keeping a last-modified timestamp per resource and requesting higher consistency only while it is newer than the cache TTL, which means the application stores half a zookie itself.

Ory Keto has `snaptoken` and `latest` fields in its v1alpha2 Check API, each marked "This field is not implemented yet and has no effect" ([`check_service.proto`](https://github.com/ory/keto/blob/master/proto/ory/keto/relation_tuples/v1alpha2/check_service.proto)).

Warrant reads a `Warrant-Token` header, and the only value it acts on is `latest` ([`wookie.go`](https://github.com/warrant-dev/warrant/blob/main/pkg/wookie/wookie.go)), which routes the read to the primary. The open-source server never hands one out.

![Matrix of nine product and datastore combinations against where commit order comes from, what token is returned, how a read at least as fresh as the token is served, and what gap remains. Spanner-backed rows and SpiceDB on PostgreSQL leave no gap with a token; CockroachDB depends on the overlap strategy; OpenFGA, Ory Keto and Warrant expose no per-write token.](./assets/zanzibar-without-truetime/diagrams/03-product-matrix.png?v=70e2ea46)

## What I would check before trusting one of these

- A token has to exist and your write path has to store it. Without one, your revocation latency is the cache TTL or the quantization interval, whichever is longer. I measured up to 4.9 s on SpiceDB defaults.
- On CockroachDB, look at the overlap strategy and key. `insecure` reopens the 2021 bug. `prefix` with un-prefixed type names is `static`. `request` is only as safe as your clients' discipline with the header.
- On CockroachDB, `fully_consistent` is not read-after-write, per the docs. Pass the token.
- No load balancer between SpiceDB and MySQL replicas.
- Nothing in the authorization path should pick an old snapshot. `at_exact_snapshot` is fine for pagination. Pointing it at an authorization decision undoes the reason zookies are opaque.

The paper's guarantee survives without TrueTime when someone pays for ordering: one primary, one hot row, or a commit wait. What does not survive is skipping the token and hoping the cache is fresh enough.

## References

- Ruoming Pang et al., [Zanzibar: Google's Consistent, Global Authorization System](https://www.usenix.org/conference/atc19/presentation/pang), USENIX ATC '19, §2.2, §2.4, §2.4.4, §3.2.5, §4.1, §5.
- James C. Corbett et al., [Spanner: Google's Globally-Distributed Database](https://www.usenix.org/system/files/conference/osdi12/osdi12-final-16.pdf), OSDI '12.
- AuthZed, [The One Crucial Difference Between Spanner and CockroachDB](https://authzed.com/blog/prevent-newenemy-cockroachdb), 2021-10-14.
- SpiceDB docs: [Datastores](https://authzed.com/docs/spicedb/concepts/datastores), [Consistency](https://authzed.com/docs/spicedb/concepts/consistency). Source at [v1.57.1](https://github.com/authzed/spicedb/tree/v1.57.1).
- Cockroach Labs, [`cockroach start`](https://docs.cockroachlabs.com/docs/stable/cockroach-start).
- OpenFGA, [Query Consistency Modes](https://openfga.dev/docs/interacting/consistency); source at [v1.22.1](https://github.com/openfga/openfga/tree/v1.22.1).
- Permify, [Snap Tokens](https://fusionauth.io/permify-docs/operations/snap-tokens); source at [v1.7.6](https://github.com/Permify/permify/tree/v1.7.6).
- [Ory Keto `check_service.proto`](https://github.com/ory/keto/blob/master/proto/ory/keto/relation_tuples/v1alpha2/check_service.proto), [Warrant `wookie.go`](https://github.com/warrant-dev/warrant/blob/main/pkg/wookie/wookie.go).
- Reproduction scripts: [`run.sh`](https://github.com/0-draft/dev.to/blob/main/articles/assets/zanzibar-without-truetime/run.sh) (PostgreSQL) and [`run-crdb.sh`](https://github.com/0-draft/dev.to/blob/main/articles/assets/zanzibar-without-truetime/run-crdb.sh) (CockroachDB).
