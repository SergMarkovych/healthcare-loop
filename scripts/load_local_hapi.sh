#!/usr/bin/env bash
# Stand up a local HAPI FHIR server and load synthetic patients into it.
# No Synthea / JDK required — we POST a FHIR transaction bundle directly, which
# gives a real FHIR R4 server with patients we control (so the diff demo has a
# change we can make on purpose). Requires Docker.
#
#   ./scripts/load_local_hapi.sh
#   export FHIR_BASE_URL=http://localhost:8080/fhir   # then point the app at it
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"

docker rm -f hapi >/dev/null 2>&1 || true
docker run -d --name hapi -p 8080:8080 hapiproject/hapi:latest >/dev/null
echo "waiting for HAPI to boot..."
until curl -sf http://localhost:8080/fhir/metadata >/dev/null 2>&1; do sleep 5; done

curl -s -X POST http://localhost:8080/fhir \
  -H 'Content-Type: application/fhir+json' \
  --data-binary @"$HERE/synthetic_fhir_bundle.json" \
  -o /dev/null -w 'bundle load http=%{http_code}\n'

echo "HAPI ready at http://localhost:8080/fhir (patients hc-A, hc-B)"
