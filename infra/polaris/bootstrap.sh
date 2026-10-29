#!/bin/sh
set -eu

: "${POLARIS_CLIENT_ID:?set POLARIS_CLIENT_ID}"
: "${POLARIS_CLIENT_SECRET:?set POLARIS_CLIENT_SECRET}"
: "${POLARIS_CATALOG:?set POLARIS_CATALOG}"
: "${RUSTFS_BUCKET:?set RUSTFS_BUCKET}"

POLARIS_URI=${POLARIS_URI:-http://polaris:8181}
POLARIS_REALM=${POLARIS_REALM:-POLARIS}
S3_ENDPOINT=${S3_ENDPOINT:-http://rustfs:9000}
S3_REGION=${S3_REGION:-us-west-2}

TOKEN_RESPONSE=$(curl --fail-with-body --silent --show-error \
  "$POLARIS_URI/api/catalog/v1/oauth/tokens" \
  --user "$POLARIS_CLIENT_ID:$POLARIS_CLIENT_SECRET" \
  -H "Polaris-Realm: $POLARIS_REALM" \
  -d grant_type=client_credentials \
  -d scope=PRINCIPAL_ROLE:ALL)
TOKEN=$(printf '%s' "$TOKEN_RESPONSE" | sed -n 's/.*"access_token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
test -n "$TOKEN"

CATALOGS_URI="$POLARIS_URI/api/management/v1/catalogs"
CATALOG_URI="$CATALOGS_URI/$POLARIS_CATALOG"
AUTH_HEADER="Authorization: Bearer $TOKEN"

CATALOG_STATUS=$(curl --silent --show-error \
  -o /dev/null \
  -w '%{http_code}' \
  -H "$AUTH_HEADER" \
  -H "Polaris-Realm: $POLARIS_REALM" \
  "$CATALOG_URI")

case "$CATALOG_STATUS" in
  200)
    echo "Polaris catalog already exists: $POLARIS_CATALOG"
    ;;
  404)
    CATALOG_PAYLOAD=$(printf '%s' '{
      "catalog": {
        "name": "'"$POLARIS_CATALOG"'",
        "type": "INTERNAL",
        "readOnly": false,
        "properties": {
          "default-base-location": "s3://'"$RUSTFS_BUCKET"'/warehouse",
          "polaris.config.drop-with-purge.enabled": "true"
        },
        "storageConfigInfo": {
          "storageType": "S3",
          "endpoint": "'"$S3_ENDPOINT"'",
          "endpointInternal": "'"$S3_ENDPOINT"'",
          "pathStyleAccess": true,
          "region": "'"$S3_REGION"'"
        }
      }
    }')
    curl --fail-with-body --silent --show-error \
      -H "$AUTH_HEADER" \
      -H 'Accept: application/json' \
      -H 'Content-Type: application/json' \
      -H "Polaris-Realm: $POLARIS_REALM" \
      "$CATALOGS_URI" \
      -d "$CATALOG_PAYLOAD" >/dev/null
    echo "Created Polaris catalog: $POLARIS_CATALOG"
    ;;
  *)
    echo "Unexpected Polaris catalog lookup status: $CATALOG_STATUS" >&2
    exit 1
    ;;
esac

GRANTS_URI="$CATALOG_URI/catalog-roles/catalog_admin/grants"
GRANTS=$(curl --fail-with-body --silent --show-error \
  -H "$AUTH_HEADER" \
  -H "Polaris-Realm: $POLARIS_REALM" \
  "$GRANTS_URI")

if printf '%s' "$GRANTS" | grep -q 'CATALOG_MANAGE_CONTENT'; then
  echo "Polaris catalog_admin grant already exists"
else
  curl --fail-with-body --silent --show-error \
    -X PUT \
    -H "$AUTH_HEADER" \
    -H 'Content-Type: application/json' \
    -H "Polaris-Realm: $POLARIS_REALM" \
    "$GRANTS_URI" \
    -d '{"type":"catalog","privilege":"CATALOG_MANAGE_CONTENT"}' >/dev/null
  echo "Granted CATALOG_MANAGE_CONTENT to catalog_admin"
fi

curl --fail-with-body --silent --show-error \
  -H "$AUTH_HEADER" \
  -H "Polaris-Realm: $POLARIS_REALM" \
  "$CATALOG_URI" >/dev/null

echo "Polaris bootstrap is ready: $POLARIS_CATALOG"
