"""
manifest.py – Read and write the per-brand completion manifest.
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional

# Resolve path relative to this file
_HERE = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_MANIFEST = os.path.join(_HERE, "..", "output", "manifest.json")


def load_manifest(path: str = _DEFAULT_MANIFEST) -> dict:
    """Load the manifest JSON. Returns empty dict if not found."""
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_manifest(data: dict, path: str = _DEFAULT_MANIFEST) -> None:
    """Atomically save the manifest JSON."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def mark_complete(
    slug: str,
    assets: dict,
    drive_folder_id: str,
    path: str = _DEFAULT_MANIFEST,
) -> None:
    """Mark a brand as complete in the manifest."""
    data = load_manifest(path)
    data[slug] = {
        "status": "complete",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "assets": assets,
        "drive_folder_id": drive_folder_id,
    }
    save_manifest(data, path)


def mark_failed(
    slug: str,
    error: str,
    path: str = _DEFAULT_MANIFEST,
) -> None:
    """Mark a brand as failed in the manifest."""
    data = load_manifest(path)
    data[slug] = {
        "status": "failed",
        "failed_at": datetime.now(timezone.utc).isoformat(),
        "error": error,
    }
    save_manifest(data, path)


def is_complete(slug: str, path: str = _DEFAULT_MANIFEST) -> bool:
    """Return True if the brand is marked complete in the manifest."""
    data = load_manifest(path)
    return data.get(slug, {}).get("status") == "complete"


def get_status(slug: str, path: str = _DEFAULT_MANIFEST) -> Optional[str]:
    """Return current status for a brand slug, or None if not in manifest."""
    data = load_manifest(path)
    return data.get(slug, {}).get("status")


def summary(path: str = _DEFAULT_MANIFEST) -> dict:
    """Return counts of complete, failed, pending brands."""
    data = load_manifest(path)
    counts = {"complete": 0, "failed": 0, "total_tracked": len(data)}
    for entry in data.values():
        status = entry.get("status", "unknown")
        if status in counts:
            counts[status] += 1
    return counts
