#!/usr/bin/env bash
# Load the same docs/folders model into SpiceDB and OpenFGA, write the same
# tuples, and compare what comes back: write tokens, snapshot reads,
# reverse lookups and conditions with missing context.
#
# Needs: docker, curl, jq. Uses host ports 28443 (SpiceDB HTTP) and 28080 (OpenFGA HTTP).
set -euo pipefail
cd "$(dirname "$0")"

SPICEDB_IMAGE=authzed/spicedb:v1.57.1
OPENFGA_IMAGE=openfga/openfga:v1.22.1
FGA_CLI_IMAGE=openfga/cli:v0.8.0
KEY=devkey
SP=http://localhost:28443
FGA=http://localhost:28080

cleanup() { docker rm -f zz-spicedb zz-openfga >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

docker run -d --name zz-spicedb -p 28443:8443 "$SPICEDB_IMAGE" \
  serve --grpc-preshared-key "$KEY" --http-enabled --datastore-engine memory >/dev/null
docker run -d --name zz-openfga -p 28080:8080 "$OPENFGA_IMAGE" run >/dev/null

wait_for() { for _ in $(seq 1 60); do curl -fs -o /dev/null "$1" && return 0; sleep 0.5; done; echo "timeout: $1"; exit 1; }
wait_for "$FGA/healthz"
until curl -fs -o /dev/null -H "Authorization: Bearer $KEY" -X POST "$SP/v1/schema/read" -d '{}' \
  || curl -s -H "Authorization: Bearer $KEY" -X POST "$SP/v1/schema/read" -d '{}' | grep -qi 'no schema'; do sleep 0.5; done

sp() { curl -s -H "Authorization: Bearer $KEY" -X POST "$SP$1" -d "$2"; }
fga() { curl -s -X POST "$FGA$1" -H 'content-type: application/json' -d "$2"; }

ref() { echo "{\"objectType\":\"$1\",\"objectId\":\"$2\"}"; }
rel() { # op type id relation subjtype subjid [caveat]
  local cav=""
  [ -n "${7:-}" ] && cav=",\"optionalCaveat\":{\"caveatName\":\"$7\"}"
  echo "{\"operation\":\"$1\",\"relationship\":{\"resource\":$(ref "$2" "$3"),\"relation\":\"$4\",\"subject\":{\"object\":$(ref "$5" "$6")}$cav}}"
}

echo "### SpiceDB $SPICEDB_IMAGE"
sp /v1/schema/write "$(jq -n --rawfile s schema.zed '{schema:$s}')" | jq -c .

W1=$(sp /v1/relationships/write "{\"updates\":[
  $(rel OPERATION_TOUCH folder eng viewer user beto),
  $(rel OPERATION_TOUCH document readme parent folder eng),
  $(rel OPERATION_TOUCH document readme owner user anne),
  $(rel OPERATION_TOUCH document plan viewer user chen in_office)]}")
echo "write response: $(echo "$W1" | jq -c .)"
T1=$(echo "$W1" | jq -r .writtenAt.token)

check_sp() { # consistency-json resource-id user-id [context-json]
  local ctx=""
  [ -n "${4:-}" ] && ctx=",\"context\":$4"
  sp /v1/permissions/check "{\"consistency\":$1,\"resource\":$(ref document "$2"),\"permission\":\"view\",\"subject\":{\"object\":$(ref user "$3")}$ctx}" \
    | jq -c '{permissionship, missing: .partialCaveatInfo.missingRequiredContext}'
}

echo "beto view readme (at_least_as_fresh T1): $(check_sp "{\"atLeastAsFresh\":{\"token\":\"$T1\"}}" readme beto)"
echo "LookupResources document#view for beto:"
sp /v1/permissions/resources "{\"consistency\":{\"atLeastAsFresh\":{\"token\":\"$T1\"}},\"resourceObjectType\":\"document\",\"permission\":\"view\",\"subject\":{\"object\":$(ref user beto)}}" \
  | jq -c '.result | {resourceObjectId, permissionship}'
echo "LookupSubjects user for document:readme#view:"
sp /v1/permissions/subjects "{\"consistency\":{\"atLeastAsFresh\":{\"token\":\"$T1\"}},\"resource\":$(ref document readme),\"permission\":\"view\",\"subjectObjectType\":\"user\"}" \
  | jq -c '.result.subject.subjectObjectId'

W2=$(sp /v1/relationships/write "{\"updates\":[$(rel OPERATION_DELETE folder eng viewer user beto)]}")
echo "removed beto from folder:eng, new token $(echo "$W2" | jq -r .writtenAt.token)"
echo "beto view readme (fully_consistent):     $(check_sp '{"fullyConsistent":true}' readme beto)"
echo "beto view readme (at_exact_snapshot T1): $(check_sp "{\"atExactSnapshot\":{\"token\":\"$T1\"}}" readme beto)"

echo "chen view plan, no context:      $(check_sp '{"fullyConsistent":true}' plan chen)"
echo "chen view plan, ip=10.20.1.5:    $(check_sp '{"fullyConsistent":true}' plan chen '{"ip":"10.20.1.5"}')"
echo "chen view plan, ip=192.0.2.9:    $(check_sp '{"fullyConsistent":true}' plan chen '{"ip":"192.0.2.9"}')"

echo
echo "### OpenFGA $OPENFGA_IMAGE"
STORE=$(fga /stores '{"name":"demo"}' | jq -r .id)
MODEL_JSON=$(docker run --rm -v "$PWD":/w -w /w "$FGA_CLI_IMAGE" model transform --file model.fga)
MODEL=$(fga "/stores/$STORE/authorization-models" "$MODEL_JSON" | jq -r .authorization_model_id)
echo "store $STORE model $MODEL"

tk() { echo "{\"user\":\"$1\",\"relation\":\"$2\",\"object\":\"$3\"$([ -n "${4:-}" ] && echo ",\"condition\":{\"name\":\"$4\"}")}"; }
W=$(fga "/stores/$STORE/write" "{\"authorization_model_id\":\"$MODEL\",\"writes\":{\"tuple_keys\":[
  $(tk user:beto viewer folder:eng),
  $(tk folder:eng parent document:readme),
  $(tk user:anne owner document:readme),
  $(tk user:chen viewer document:plan in_office)]}}")
echo "write response: $W"

check_fga() { # user object [context-json]
  local ctx=""
  [ -n "${3:-}" ] && ctx=",\"context\":$3"
  fga "/stores/$STORE/check" "{\"authorization_model_id\":\"$MODEL\",\"tuple_key\":$(tk "$1" viewer "$2")$ctx}" | jq -c .
}

echo "beto viewer readme: $(check_fga user:beto document:readme)"
echo "ListObjects document#viewer for beto:"
fga "/stores/$STORE/list-objects" "{\"authorization_model_id\":\"$MODEL\",\"type\":\"document\",\"relation\":\"viewer\",\"user\":\"user:beto\"}" | jq -c .
echo "ListUsers user for document:readme#viewer:"
fga "/stores/$STORE/list-users" "{\"authorization_model_id\":\"$MODEL\",\"object\":{\"type\":\"document\",\"id\":\"readme\"},\"relation\":\"viewer\",\"user_filters\":[{\"type\":\"user\"}]}" \
  | jq -c '[.users[].object.id]'

fga "/stores/$STORE/write" "{\"authorization_model_id\":\"$MODEL\",\"deletes\":{\"tuple_keys\":[$(tk user:beto viewer folder:eng)]}}" >/dev/null
echo "removed beto from folder:eng"
echo "beto viewer readme: $(check_fga user:beto document:readme)"

echo "chen viewer plan, no context:   $(check_fga user:chen document:plan)"
echo "chen viewer plan, ip=10.20.1.5: $(check_fga user:chen document:plan '{"ip":"10.20.1.5"}')"
echo "chen viewer plan, ip=192.0.2.9: $(check_fga user:chen document:plan '{"ip":"192.0.2.9"}')"
