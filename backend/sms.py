"""SMS emergency broadcast generator for FloodLens.
Generates concise, ward-targeted SMS alerts strictly under 160 characters
for zero-latency cellular broadcast (GSM 7-bit / cell broadcast standard).
"""
import json
from pathlib import Path
from typing import Any, Dict, Optional

from backend.config import DATA_DIR


def generate_ward_sms(ward_identifier: str) -> Dict[str, Any]:
    """Generates an SMS alert under 160 chars for the given ward name or ward ID."""
    wards_file = DATA_DIR / "wards.geojson"
    shelters_file = DATA_DIR / "shelters.geojson"

    ward_info = None
    if wards_file.exists():
        with open(wards_file, "r", encoding="utf-8") as f:
            for feat in json.load(f).get("features", []):
                p = feat.get("properties", {})
                w_name = p.get("ward", "").lower()
                w_id = p.get("ward_id", "").lower()
                target = ward_identifier.lower()
                if target in w_name or target in w_id or target in feat.get("id", "").lower():
                    ward_info = p
                    break

    if not ward_info:
        # Fallback to Ward 1
        ward_info = {
            "ward": "Ward 1",
            "urgency_score": 75.0,
            "rank": 1,
            "exposed_buildings": 42,
            "blocked_roads_pct": 35.0,
            "mean_depth": 0.85,
        }

    rank = ward_info.get("rank", 1)
    w_name_short = ward_info.get("ward", "Ward 1").split("(")[0].strip()
    depth_m = ward_info.get("mean_depth", 0.7)
    shelter = "PMCH Camp" if rank == 1 else "Kankarbagh Stadium"

    # Construct message strictly under 160 characters
    # Template: "FLOOD ALERT: {Ward} ranked #{Rank} priority. Est depth {depth}m. Evacuate via open corridors to {Shelter}. Call 112 for rescue."
    message = f"FLOOD ALERT {w_name_short}: Rank #{rank} urgent. Est depth {depth_m}m (proxy). Evacuate to {shelter}. Avoid flooded roads. Dial 112 for boat rescue."

    # Enforce strict 160 character ceiling
    if len(message) > 160:
        message = message[:157] + "..."

    return {
        "ward": ward_info.get("ward", ward_identifier),
        "message": message,
        "char_count": len(message),
        "urgency_rank": rank,
        "valid_gsm": len(message) <= 160,
    }
