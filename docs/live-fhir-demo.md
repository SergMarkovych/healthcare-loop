# Live FHIR demo — controlled-change diff (no Synthea/JDK)

The best "credible integration story": a real FHIR server, a change *you* control, and
the engine reporting the exact field-level diff. This path needs only Docker — patients
are loaded by POSTing a FHIR transaction bundle, so no Synthea or JDK is required.

## 1. Stand up local HAPI + load synthetic patients

```bash
./scripts/load_local_hapi.sh            # docker run hapi + load scripts/synthetic_fhir_bundle.json
```

Loads two synthetic patients — `hc-A` (Jordan Sample) and `hc-B` (Alex Demo) — with a
Condition, Observation(s), an Encounter, and `MedicationRequest/med-A` (metformin
500 mg twice daily).

## 2. Run the controlled-change diff through the app

```bash
APP=http://127.0.0.1:8000 ; HAPI=http://localhost:8080/fhir

curl -X POST $APP/api/fhir/reset
# scan 1
curl -X POST $APP/api/fhir/scan -H 'Content-Type: application/json' \
     -d "{\"source\":\"live\",\"patient_count\":5,\"base_url\":\"$HAPI\"}"

# the change you control: metformin 500 -> 1000 via the FHIR API
curl -X PUT $HAPI/MedicationRequest/med-A -H 'Content-Type: application/fhir+json' \
     -d '{"resourceType":"MedicationRequest","id":"med-A","status":"active","intent":"order","medicationCodeableConcept":{"text":"Metformin"},"subject":{"reference":"Patient/hc-A"},"dosageInstruction":[{"text":"1000 mg twice daily"}]}'

# scan 2, then the diff
curl -X POST $APP/api/fhir/scan -H 'Content-Type: application/json' \
     -d "{\"source\":\"live\",\"patient_count\":5,\"base_url\":\"$HAPI\"}"
curl $APP/api/fhir/diff
curl $APP/api/fhir/context/hc-A
```

## 3. Verified result

```
diff counts: { new: 0, updated: 1, unchanged: 6, not_returned: 0 }
UPDATED MedicationRequest/med-A
        dosageInstruction[0].text: "500 mg twice daily" -> "1000 mg twice daily"
```

`6 unchanged` despite HAPI bumping `versionId`/`lastUpdated` on every write — proving
change detection is **content-hash based, not metadata based**. The context board for
`hc-A` restates only the source-backed change (`MedicationRequest/med-A`) with no invented
clinical content.

Teardown: `docker rm -f hapi`.
