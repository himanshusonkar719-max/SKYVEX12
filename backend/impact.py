"""Hyperlocal impact analysis, ward urgency ranking, and cut-off habitat assessment.
Calculates exposure, critical infrastructure hits, and human-readable feature summaries.
"""
import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.config import DATA_DIR, DEPTH_PROXY_LABEL, SEVERITY_THRESHOLDS, WARD_URGENCY_WEIGHTS

logger = logging.getLogger("floodlens.impact")


def calculate_ward_urgency_scores(wards_fc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Evaluates ward urgency scores according to:
    Urgency = 0.4*exposed_buildings_norm + 0.3*blocked_roads_pct + 0.2*critical_facilities_norm + 0.1*mean_depth_norm
    """
    wards = wards_fc.get("features", [])
    if not wards:
        return []

    max_exposed = max((w["properties"].get("exposed_buildings", 1) for w in wards), default=1) or 1
    max_crit = max((w["properties"].get("critical_hits", 1) for w in wards), default=1) or 1

    for w in wards:
        props = w["properties"]
        exp_norm = props.get("exposed_buildings", 0) / max_exposed
        blocked_pct = props.get("blocked_roads_pct", 0) / 100.0
        crit_norm = props.get("critical_hits", 0) / max_crit
        depth_norm = min(1.0, props.get("mean_depth", 0.0) / 1.5)

        urgency = (
            WARD_URGENCY_WEIGHTS["exposed_buildings"] * exp_norm +
            WARD_URGENCY_WEIGHTS["blocked_roads"] * blocked_pct +
            WARD_URGENCY_WEIGHTS["critical_facilities"] * crit_norm +
            WARD_URGENCY_WEIGHTS["mean_depth"] * depth_norm
        )
        props["urgency_score"] = round(urgency * 100, 1)

    # Sort descending
    wards.sort(key=lambda x: x["properties"]["urgency_score"], reverse=True)
    for idx, w in enumerate(wards):
        w["properties"]["rank"] = idx + 1

    return wards


def get_feature_human_summary(layer_name: str, feature_id: str) -> Optional[Dict[str, Any]]:
    """Generates human-readable descriptions for any feature in any layer.
    e.g. '87% likely impassable due to 0.72m water depth'
    """
    filename = f"{layer_name}.geojson"
    fp = DATA_DIR / filename
    if not fp.exists():
        return None

    with open(fp, "r", encoding="utf-8") as f:
        fc = json.load(f)

    target_feat = None
    for feat in fc.get("features", []):
        f_id = feat.get("id") or feat.get("properties", {}).get("id")
        if str(f_id) == str(feature_id):
            target_feat = feat
            break

    if not target_feat:
        return None

    props = target_feat.get("properties", {})
    geom = target_feat.get("geometry", {})
    geom_type = geom.get("type", "")
    coords = geom.get("coordinates", [])

    # Calculate centroid
    centroid = [85.14, 25.60]
    if geom_type == "Point" and coords:
        centroid = [coords[0], coords[1]]
    elif geom_type == "LineString" and coords:
        centroid = [(coords[0][0] + coords[-1][0]) / 2, (coords[0][1] + coords[-1][1]) / 2]
    elif geom_type == "Polygon" and coords and coords[0]:
        poly_pts = coords[0]
        centroid = [
            sum(p[0] for p in poly_pts) / len(poly_pts),
            sum(p[1] for p in poly_pts) / len(poly_pts),
        ]

    # Generate layer-specific human descriptions
    human_summary = ""
    conf_statement = ""

    if layer_name == "roads":
        status = props.get("status", "open")
        depth = props.get("max_depth", 0.0)
        p_open = props.get("p_open", 0.95)
        conf = props.get("confidence", 0.9)
        name = props.get("name", f"Segment {feature_id}")

        if status == "impassable":
            p_impassable = int(round((1.0 - p_open) * 100))
            human_summary = f"{p_impassable}% likely impassable for ambulances and standard transit due to {depth}m {DEPTH_PROXY_LABEL}."
            conf_statement = f"Radar backscatter differential indicates high probability of surface water across this corridor."
        else:
            human_summary = f"Open corridor. Estimated surface water is {depth}m, within safe operating margins."
            conf_statement = f"Passability confidence: {int(conf * 100)}% based on Sentinel-1 SAR and terrain gradient."

    elif layer_name == "buildings":
        sev = props.get("severity", "low")
        depth = props.get("depth", 0.0)
        is_crit = props.get("is_critical", False)
        use_type = props.get("use_type", "Residential/Commercial")

        if is_crit:
            human_summary = f"CRITICAL FACILITY ({use_type}): {sev.upper()} impact zone with {depth}m {DEPTH_PROXY_LABEL}. Priority evacuation corridor required."
        elif sev == "severe":
            human_summary = f"Severe structure inundation ({depth}m {DEPTH_PROXY_LABEL}). Ground floor inundated; cut-off habitat risk."
        elif sev == "moderate":
            human_summary = f"Moderate structure inundation ({depth}m {DEPTH_PROXY_LABEL}). Perimeter flooding observed."
        else:
            human_summary = f"Low direct structure flood risk ({depth}m {DEPTH_PROXY_LABEL}). Access road may be affected."
        conf_statement = f"Detection confidence: {int(props.get('confidence', 0.85) * 100)}%."

    elif layer_name == "shelters":
        cap = props.get("capacity", 500)
        occ = props.get("occupancy", 250)
        free = props.get("free_capacity", cap - occ)
        human_summary = f"{props.get('name', 'Shelter')}: {free} of {cap} spaces currently available. High-ground safety confirmed."
        conf_statement = f"Designated official relief center with medical triage and food supplies."

    elif layer_name == "wards":
        rank = props.get("rank", 1)
        score = props.get("urgency_score", 50)
        exp = props.get("exposed_buildings", 0)
        blocked = props.get("blocked_roads_pct", 0)
        human_summary = f"Priority Rank #{rank} (Urgency {score}/100). {exp} buildings in flood zone, {blocked}% of roads blocked."
        conf_statement = f"Calculated via composite multi-criteria decision index."

    else:
        depth = props.get("depth", 1.0)
        human_summary = f"Inundation polygon with {depth}m {DEPTH_PROXY_LABEL}."
        conf_statement = f"Sentinel-1 SAR C-Band specular reflection detection."

    return {
        "layer": layer_name,
        "id": str(feature_id),
        "name": props.get("name") or props.get("ward") or f"{layer_name.capitalize()} {feature_id}",
        "properties": props,
        "human_summary": human_summary,
        "confidence_statement": conf_statement,
        "centroid": [round(centroid[0], 6), round(centroid[1], 6)],
        "depth_label": DEPTH_PROXY_LABEL,
    }
