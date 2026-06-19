"""
Change detection between two scan runs.

Classification per resource key:
  - new            : present now, absent before
  - updated        : present in both, content hash differs (+ field-level diff)
  - unchanged      : present in both, same hash
  - not_returned   : present before, absent now (API did not return it this scan)

`not_returned` is deliberately neutral: it means the API didn't return the
resource, NOT that anything was deleted clinically.
"""

import json

from backend.fhir import normalize as norm


def field_diff(old, new, path: str = "") -> list[dict]:
    """Recursive, readable JSON diff. Lists compared by index (MVP-grade)."""
    diffs: list[dict] = []
    if type(old) is not type(new):
        diffs.append({"path": path or "/", "change": "changed", "old": old, "new": new})
        return diffs
    if isinstance(new, dict):
        for k in sorted(set(old) | set(new)):
            p = f"{path}.{k}" if path else k
            if k not in old:
                diffs.append({"path": p, "change": "added", "new": new[k]})
            elif k not in new:
                diffs.append({"path": p, "change": "removed", "old": old[k]})
            else:
                diffs += field_diff(old[k], new[k], p)
    elif isinstance(new, list):
        for i in range(max(len(old), len(new))):
            p = f"{path}[{i}]"
            if i >= len(old):
                diffs.append({"path": p, "change": "added", "new": new[i]})
            elif i >= len(new):
                diffs.append({"path": p, "change": "removed", "old": old[i]})
            else:
                diffs += field_diff(old[i], new[i], p)
    elif old != new:
        diffs.append({"path": path or "/", "change": "changed", "old": old, "new": new})
    return diffs


def _body(row) -> dict:
    return json.loads(row["body"])


def classify(prev_map: dict, curr_map: dict) -> dict:
    """prev_map / curr_map: {resource_key: snapshot row (sqlite Row or dict)}."""
    result = {"new": [], "updated": [], "unchanged": [], "not_returned": []}
    prev_keys, curr_keys = set(prev_map), set(curr_map)

    for key in sorted(curr_keys - prev_keys):
        row = curr_map[key]
        result["new"].append({
            "key": key, "resource_type": row["resource_type"], "patient_id": row["patient_id"],
        })

    for key in sorted(curr_keys & prev_keys):
        cur, prev = curr_map[key], prev_map[key]
        item = {"key": key, "resource_type": cur["resource_type"], "patient_id": cur["patient_id"]}
        if cur["content_hash"] == prev["content_hash"]:
            result["unchanged"].append(item)
        else:
            fd = field_diff(norm.normalize(_body(prev)), norm.normalize(_body(cur)))
            item["field_changes"] = fd
            item["change_count"] = len(fd)
            result["updated"].append(item)

    for key in sorted(prev_keys - curr_keys):
        row = prev_map[key]
        result["not_returned"].append({
            "key": key, "resource_type": row["resource_type"], "patient_id": row["patient_id"],
        })

    result["counts"] = {k: len(v) for k, v in result.items() if isinstance(v, list)}
    return result


def filter_for_patient(diff: dict, patient_id: str) -> dict:
    out = {}
    for k, v in diff.items():
        if isinstance(v, list):
            out[k] = [i for i in v if i.get("patient_id") == patient_id]
    out["counts"] = {k: len(v) for k, v in out.items()}
    return out
