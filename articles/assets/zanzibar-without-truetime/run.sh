#!/usr/bin/env bash
# Reproduces the hands-on section of zanzibar-without-truetime.md:
# SpiceDB v1.57.1 on PostgreSQL 17, a ZedToken decoded down to the
# PostgreSQL xid and snapshot, and the new enemy window that
# minimize_latency leaves open after a removal.
#
# Needs: docker, curl, jq, protoc (only for --decode_raw).
set -euo pipefail

NET=zwt-net
PG=zwt-pg
SDB=zwt-spicedb
KEY=demo-key
API=http://localhost:8443

cleanup() { docker rm -f "$SDB" "$PG" >/dev/null 2>&1 || true; docker network rm "$NET" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

docker network create "$NET" >/dev/null
docker run -d --name "$PG" --network "$NET" -e POSTGRES_PASSWORD=pw -e POSTGRES_DB=spicedb postgres:17-alpine >/dev/null
until docker exec "$PG" pg_isready -U postgres >/dev/null 2>&1; do sleep 0.5; done
sleep 1

URI="postgres://postgres:pw@$PG:5432/spicedb?sslmode=disable"
docker run --rm --network "$NET" authzed/spicedb:v1.57.1 migrate head \
  --datastore-engine postgres --datastore-conn-uri "$URI" >/dev/null 2>&1

docker run -d --name "$SDB" --network "$NET" -p 8443:8443 authzed/spicedb:v1.57.1 serve \
  --grpc-preshared-key "$KEY" --http-enabled \
  --datastore-engine postgres --datastore-conn-uri "$URI" >/dev/null
until curl -s -H "Authorization: Bearer $KEY" -X POST "$API/v1/schema/read" -d '{}' 2>/dev/null | grep -q 'no schema'; do sleep 0.5; done

call() { curl -s -H "Authorization: Bearer $KEY" -X POST "$API$1" -d "$2"; }

call /v1/schema/write '{"schema":"definition user {}\ndefinition folder {\n  relation viewer: user\n  permission view = viewer\n}\ndefinition document {\n  relation parent: folder\n  permission view = parent->view\n}"}' >/dev/null

rel() { # op resource relation subject
  printf '{"operation":"%s","relationship":{"resource":{"objectType":"%s","objectId":"%s"},"relation":"%s","subject":{"object":{"objectType":"%s","objectId":"%s"}}}}' "$@"
}

echo "== 1. Chen can view folder:A, readme is in folder:A"
W1=$(call /v1/relationships/write "{\"updates\":[$(rel OPERATION_TOUCH folder A viewer user chen),$(rel OPERATION_TOUCH document readme parent folder A)]}")
echo "$W1" | jq .
sleep 6   # let the 5s quantization window pass so the grant is visible to minimize_latency

check() { # consistency-json
  call /v1/permissions/check "{\"consistency\":$1,\"resource\":{\"objectType\":\"document\",\"objectId\":\"readme\"},\"permission\":\"view\",\"subject\":{\"object\":{\"objectType\":\"user\",\"objectId\":\"chen\"}}}" | jq -r .permissionship
}
echo "minimize_latency: $(check '{"minimizeLatency":true}')"

echo
echo "== 2. Anne removes Chen from folder:A"
W2=$(call /v1/relationships/write "{\"updates\":[$(rel OPERATION_DELETE folder A viewer user chen)]}")
echo "$W2" | jq .
TOK=$(echo "$W2" | jq -r .writtenAt.token)
now() { perl -MTime::HiRes=time -e 'printf "%.1f", time'; }
T0=$(now)

echo
echo "== 3. Checks right after the removal"
echo "minimize_latency:            $(check '{"minimizeLatency":true}')"
echo "at_least_as_fresh(removal):  $(check "{\"atLeastAsFresh\":{\"token\":\"$TOK\"}}")"
echo "fully_consistent:            $(check '{"fullyConsistent":true}')"
OLD=$(echo "$W1" | jq -r .writtenAt.token)
echo "at_exact_snapshot(grant):    $(check "{\"atExactSnapshot\":{\"token\":\"$OLD\"}}")"

echo
echo "== 4. What is inside the removal's ZedToken"
echo "$TOK" | base64 -d | protoc --decode_raw
REV=$(echo "$TOK" | base64 -d | protoc --decode_raw | awk -F'"' '/^  1:/{print $2}')
echo "-- revision field, base64-decoded again:"
echo "$REV" | base64 -d | protoc --decode_raw

echo
echo "== 5. The same numbers from PostgreSQL"
docker exec "$PG" psql -U postgres -d spicedb -At -c \
  "SELECT xid, snapshot, timestamp FROM relation_tuple_transaction ORDER BY xid DESC LIMIT 3;"

echo
echo "== 6. How long minimize_latency keeps saying yes after the removal"
while [ "$(check '{"minimizeLatency":true}')" = "PERMISSIONSHIP_HAS_PERMISSION" ]; do sleep 0.2; done
echo "removal acknowledged -> minimize_latency says NO_PERMISSION: $(echo "$(now) - $T0" | bc)s"
