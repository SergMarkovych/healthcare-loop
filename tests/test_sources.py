"""
Config-driven sources registry (V4 §18) via GET /api/sources.

Asserts the ACTIVE FHIR sources (fixtures + public/local HAPI) and the ROADMAP
stubs are listed with their status fields. Read-only config; no scan behaviour.
"""


def _fetch(client) -> list[dict]:
    resp = client.get("/api/sources")
    assert resp.status_code == 200
    return resp.json()


def test_sources_have_required_fields(client):
    sources = _fetch(client)
    assert sources, "expected a non-empty sources registry"
    for s in sources:
        assert set(s) == {"id", "type", "status", "base_url", "notes"}
        assert s["status"] in {"active", "roadmap"}


def test_active_fhir_sources_listed(client):
    sources = _fetch(client)
    by_id = {s["id"]: s for s in sources}

    assert by_id["fixtures"]["status"] == "active"
    assert by_id["fixtures"]["base_url"] is None

    assert by_id["hapi-public"]["status"] == "active"
    assert by_id["hapi-public"]["base_url"] == "https://hapi.fhir.org/baseR4"

    assert by_id["hapi-local"]["status"] == "active"
    assert by_id["hapi-local"]["base_url"] == "http://localhost:8080/fhir"


def test_roadmap_stubs_listed(client):
    sources = _fetch(client)
    by_id = {s["id"]: s for s in sources}

    expected_roadmap = {
        "smart-on-fhir", "cds-hooks", "health-canada-dpd",
        "ccdd", "mimic-iv", "mtsamples",
    }
    assert expected_roadmap.issubset(set(by_id))
    for sid in expected_roadmap:
        assert by_id[sid]["status"] == "roadmap", f"{sid} should be roadmap"


def test_loader_matches_endpoint(client):
    from backend.fhir.sources import load_sources

    assert load_sources() == _fetch(client)
