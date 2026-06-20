"""
Config-driven data-sources registry (V4 §18).

Declares every data source / API the product knows about — the ACTIVE FHIR
sources we scan today and the ROADMAP stubs we don't yet — so the "several APIs"
have a single declared home and an endpoint to enumerate them.

Read-only: this loader does not influence run_scan behaviour. Wiring a source
into scanning is a deliberate later step.

JSON (not YAML) by design: pyyaml is not a project dependency (requirements.txt),
and a stdlib `json.load` keeps the registry dependency-light.
"""

import json
import os

_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "config",
    "sources.json",
)

_REQUIRED_FIELDS = ("id", "type", "status", "base_url", "notes")
_VALID_STATUS = ("active", "roadmap")


def load_sources(path: str = _CONFIG_PATH) -> list[dict]:
    """Return the declared data sources as a list of dicts.

    Each entry carries id, type, status (active|roadmap), base_url (or None) and
    notes. Raises ValueError if the config is malformed so a bad registry fails
    loudly rather than silently serving a partial list.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    raw = data.get("sources") if isinstance(data, dict) else data
    if not isinstance(raw, list):
        raise ValueError("sources config must be a list (or {'sources': [...]})")

    sources: list[dict] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError(f"source entry must be an object, got {type(entry).__name__}")
        missing = [k for k in _REQUIRED_FIELDS if k not in entry]
        if missing:
            raise ValueError(f"source {entry.get('id', '?')!r} missing fields: {missing}")
        if entry["status"] not in _VALID_STATUS:
            raise ValueError(
                f"source {entry['id']!r} has invalid status {entry['status']!r}; "
                f"expected one of {_VALID_STATUS}"
            )
        sources.append({k: entry[k] for k in _REQUIRED_FIELDS})
    return sources
