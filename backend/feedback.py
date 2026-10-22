"""Field responder feedback manager for FloodLens.
Allows ground responders to override road status (mark open or blocked),
adjusting routing graph edge weights in real-time.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from backend.config import DATA_DIR, PUBLIC_DATA_DIR

logger = logging.getLogger("floodlens.feedback")

FEEDBACK_FILE = DATA_DIR / "feedback_overrides.json"

# In-memory dictionary: road_id -> override record
_OVERRIDES: Dict[str, Dict[str, Any]] = {}


def load_overrides():
    """Loads existing overrides from disk if present."""
    global _OVERRIDES
    if FEEDBACK_FILE.exists():
        try:
            with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
                _OVERRIDES = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load feedback overrides: {e}")
            _OVERRIDES = {}


def save_overrides():
    """Persists overrides to storage."""
    try:
        with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
            json.dump(_OVERRIDES, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save feedback overrides: {e}")


def apply_feedback(
    road_id: str,
    status: str,
    depth_override_m: Optional[float] = None,
    reporter: Optional[str] = "Field Responder",
    note: Optional[str] = None,
) -> Dict[str, Any]:
    """Records a responder override for a road segment."""
    load_overrides()
    record = {
        "road_id": road_id,
        "status": status,  # "open" or "impassable"
        "depth_override_m": depth_override_m,
        "reporter": reporter or "Field Responder",
        "note": note or "",
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
    _OVERRIDES[road_id] = record
    save_overrides()
    
    # Also update roads.geojson in data directories
    update_roads_geojson(road_id, status, depth_override_m)
    return record


def get_all_overrides() -> List[Dict[str, Any]]:
    """Returns list of all active field overrides."""
    load_overrides()
    return list(_OVERRIDES.values())


def get_road_override(road_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves override for a specific road if present."""
    load_overrides()
    return _OVERRIDES.get(road_id)


def update_roads_geojson(road_id: str, status: str, depth_override: Optional[float] = None):
    """Reflects the override in roads.geojson in both backend and public data."""
    for folder in [DATA_DIR, PUBLIC_DATA_DIR]:
        roads_file = folder / "roads.geojson"
        if not roads_file.exists():
            continue
        try:
            with open(roads_file, "r", encoding="utf-8") as f:
                fc = json.load(f)
            
            modified = False
            for feat in fc.get("features", []):
                if feat.get("id") == road_id or feat.get("properties", {}).get("id") == road_id:
                    feat["properties"]["status"] = status
                    feat["properties"]["p_open"] = 0.99 if status == "open" else 0.01
                    if depth_override is not None:
                        feat["properties"]["max_depth"] = depth_override
                    feat["properties"]["responder_override"] = True
                    feat["properties"]["override_status"] = status
                    modified = True
                    break

            if modified:
                with open(roads_file, "w", encoding="utf-8") as f:
                    json.dump(fc, f, indent=2)
        except Exception as e:
            logger.error(f"Error updating {roads_file}: {e}")
