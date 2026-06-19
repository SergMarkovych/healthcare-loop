"""
Normalization + hashing for exact change detection.

VersionId / lastUpdated are not reliable across servers, so we detect change by
hashing the *content* of a resource with volatile metadata stripped. Two scans
that return the same clinical content produce the same hash, even if the server
bumped lastUpdated.
"""

import copy
import hashlib
import json

_VOLATILE_META = {"versionId", "lastUpdated", "source"}


def resource_key(res: dict) -> str:
    """Stable identity of a resource within a scan: 'ResourceType/id'."""
    return f"{res.get('resourceType', 'Unknown')}/{res.get('id', '?')}"


def patient_ref(res: dict) -> str | None:
    """Best-effort patient id this resource belongs to."""
    if res.get("resourceType") == "Patient":
        return res.get("id")
    for field in ("subject", "patient", "for", "beneficiary"):
        ref = res.get(field, {})
        if isinstance(ref, dict) and isinstance(ref.get("reference"), str):
            # e.g. "Patient/123"
            return ref["reference"].split("/")[-1]
    return None


def normalize(res: dict) -> dict:
    """Deep copy with volatile fields removed so hashes compare content only."""
    r = copy.deepcopy(res)
    meta = r.get("meta")
    if isinstance(meta, dict):
        for k in list(meta.keys()):
            if k in _VOLATILE_META:
                meta.pop(k, None)
        if not meta:
            r.pop("meta", None)
    # Narrative is server-rendered display text, not source-of-truth content.
    r.pop("text", None)
    return r


def stable_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(res: dict) -> str:
    return hashlib.sha256(stable_json(normalize(res)).encode("utf-8")).hexdigest()
