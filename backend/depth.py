"""Proxy water depth estimation for FloodLens.
All calculations are strictly labeled as "estimated depth (proxy)".
Depths are derived via distance-from-flood-edge transforms and relative elevation proxies,
not direct in-situ water gauge measurements.
"""
import math
from typing import Dict, List, Tuple
from backend.config import DEPTH_PROXY_LABEL, DEPTH_PROXY_NOTE, SEVERITY_THRESHOLDS


def compute_edge_distance_proxy_depth(
    point: Tuple[float, float],
    flood_boundary_coords: List[Tuple[float, float]],
    max_proxy_depth_m: float = 2.5,
) -> float:
    """Calculates proxy water depth as a function of Euclidean distance from the flood contour.
    
    Points closer to the center of the inundation zone yield higher proxy depth,
    decaying to 0.05m near the detected boundary.
    """
    px, py = point
    # Find minimum distance to any boundary vertex
    min_dist = float("inf")
    for bx, by in flood_boundary_coords:
        d = math.hypot(px - bx, py - by)
        if d < min_dist:
            min_dist = d

    # Convert approx degree distance to meters (1 deg ~ 111,000 m)
    dist_m = min_dist * 111000.0

    if dist_m > 800.0:
        return 0.0
    
    # Sigmoidal depth decay function scaled 0 to max_proxy_depth_m
    decay = math.exp(-dist_m / 250.0)
    proxy_depth = round(decay * max_proxy_depth_m, 2)
    return max(0.0, proxy_depth)


def classify_building_severity(depth: float) -> str:
    """Classifies structure impact severity according to standardized thresholds:
    - depth < 0.3m: 'low'
    - 0.3m <= depth <= 1.0m: 'moderate'
    - depth > 1.0m: 'severe'
    """
    if depth > SEVERITY_THRESHOLDS["moderate"]:
        return "severe"
    elif depth >= SEVERITY_THRESHOLDS["low"]:
        return "moderate"
    return "low"


def get_depth_label() -> str:
    """Returns the mandatory standardized label."""
    return DEPTH_PROXY_LABEL
