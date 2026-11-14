#!/usr/bin/env bash
# Shows the overlap key SpiceDB v1.57.1 writes on CockroachDB: every
# relationship write also upserts one row of the `transactions` table,
# so two writes that touch unrelated tuples still conflict on that row.
#
# Needs: docker, curl, jq.
set -euo pipefail

NET=zwt-crdb-net
DB=zwt-crdb
SDB=zwt-crdb-spicedb
KEY=demo-key
API=http://localhost:8444
STRATEGY=${1:-static}

cleanup() { docker rm -f "$SDB" "$DB" >/dev/null 2>&1 || true; docker network rm "$NET" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

docker network create "$NET" >/dev/null
docker run -d --name "$DB" --network "$NET" cockroachdb/cockroach:v25.2.2 start-single-node --insecure >/dev/null
until docker exec "$DB" cockroach sql --insecure -e 'CREATE DATABASE IF NOT EXISTS spicedb' >/dev/null 2>&1; do sleep 1; done

URI="postgres://root@$DB:26257/spicedb?sslmode=disable"
docker run --rm --network "$NET" authzed/spicedb:v1.57.1 migrate head \
  --datastore-engine cockroachdb --datastore-conn-uri "$URI" >/dev/null 2>&1

docker run -d --name "$SDB" --network "$NET" -p 8444:8443 authzed/spicedb:v1.57.1 serve \
  --grpc-preshared-key "$KEY" --http-enabled \
  --datastore-engine cockroachdb --datastore-conn-uri "$URI" \
  --datastore-tx-overlap-strategy "$STRATEGY" >/dev/null
until curl -s -H "Authorization: Bearer $KEY" -X POST "$API/v1/schema/read" -d '{}' 2>/dev/null | grep -q 'no schema'; do sleep 0.5; done

call() { curl -s -H "Authorization: Bearer $KEY" -X POST "$API$1" -d "$2"; }
call /v1/schema/write '{"schema":"definition user {}\ndefinition folder {\n  relation viewer: user\n}\ndefinition document {\n  relation parent: folder\n}"}' >/dev/null

rel() {
  printf '{"operation":"%s","relationship":{"resource":{"objectType":"%s","objectId":"%s"},"relation":"%s","subject":{"object":{"objectType":"%s","objectId":"%s"}}}}' "$@"
}

sql() { docker exec "$DB" cockroach sql --insecure -d spicedb --format=table -e "$1"; }

echo "== strategy: $STRATEGY"
call /v1/relationships/write "{\"updates\":[$(rel OPERATION_TOUCH folder A viewer user chen)]}" >/dev/null
echo "-- write x: remove Chen from folder:A (a tuple on folder)"
call /v1/relationships/write "{\"updates\":[$(rel OPERATION_DELETE folder A viewer user chen)]}" | jq -c .
sql 'SELECT key, "timestamp" FROM transactions ORDER BY key'
echo "-- write y: move readme into folder:A (a tuple on document)"
call /v1/relationships/write "{\"updates\":[$(rel OPERATION_TOUCH document readme parent folder A)]}" | jq -c .
sql 'SELECT key, "timestamp" FROM transactions ORDER BY key'
echo "-- crdb_internal_mvcc_timestamp of the key row(s): the HLC of the last writer"
sql 'SELECT key, crdb_internal_mvcc_timestamp FROM transactions ORDER BY key'
