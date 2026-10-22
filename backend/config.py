"""Configuration for FloodLens backend.
Hyperlocal flood detection, proxy depth estimation, and impact routing.
"""
from pathlib import Path
from pydantic import BaseModel

# Directories
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"
PUBLIC_DATA_DIR = PROJECT_ROOT / "public" / "data"

# Ensure data directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
PUBLIC_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Area of Interest (AOI): Patna Flood Basin (Ganga-Son Confluence, Bihar)
# Realistic floodplain coordinates
AOI_CENTER = {"lat": 25.5941, "lon": 85.1376}
AOI_BBOX = {
    "min_lon": 85.0800,
    "min_lat": 25.5600,
    "max_lon": 85.2000,
    "max_lat": 25.6400,
}

# Proxy Depth Disclaimer
DEPTH_PROXY_LABEL = "estimated depth (proxy)"
DEPTH_PROXY_NOTE = "Depths are estimated proxies calculated from flood boundary distance and terrain contours, not direct in-situ gauge measurements."

# Building Severity Thresholds (meters)
SEVERITY_THRESHOLDS = {
    "low": 0.3,       # < 0.3m
    "moderate": 1.0,  # 0.3m - 1.0m
    "severe": 1.0     # > 1.0m
}

# Vehicle Depth Limits (meters)
# Vehicles cannot traverse roads with estimated depth (proxy) exceeding these limits
VEHICLE_DEPTH_LIMITS = {
    "ambulance": 0.3,
    "truck": 0.6,
    "foot": 1.0,
}

# Ward Urgency Formula Weights
# Urgency = 0.4*exposed_buildings_norm + 0.3*blocked_roads_pct + 0.2*critical_facilities_norm + 0.1*mean_depth_norm
WARD_URGENCY_WEIGHTS = {
    "exposed_buildings": 0.4,
    "blocked_roads": 0.3,
    "critical_facilities": 0.2,
    "mean_depth": 0.1,
}

# 3D Exploded Layers Altitude Hints (in meters above ground)
ALTITUDE_HINTS = {
    "flood": 0,
    "roads": 150,
    "buildings": 300,
    "confidence": 450,
    "shelters": 600,
    "wards": 50,
}

# Layer Metadata Definitions
LAYER_METADATA = {
    "flood": {
        "title": "Flood Extent & Depth",
        "altitude_hint_m": ALTITUDE_HINTS["flood"],
        "filename": "flood.geojson",
        "description": "Satellite-detected flood inundation with estimated depth (proxy) levels (0-3m).",
        "color": "#4FA3D1",
    },
    "roads": {
        "title": "Street Grid & Passability",
        "altitude_hint_m": ALTITUDE_HINTS["roads"],
        "filename": "roads.geojson",
        "description": "Hyperlocal road segments classified as open or impassable based on depth threshold and responder feedback.",
        "color": "#5FB878",
    },
    "buildings": {
        "title": "Building Footprints",
        "altitude_hint_m": ALTITUDE_HINTS["buildings"],
        "filename": "buildings.geojson",
        "description": "Structures categorized into low, moderate, and severe impact zones with critical hit detection.",
        "color": "#E8A03C",
    },
    "shelters": {
        "title": "Evacuation Shelters",
        "altitude_hint_m": ALTITUDE_HINTS["shelters"],
        "filename": "shelters.geojson",
        "description": "Designated relief camps, hospitals, and high-ground shelters with live capacity status.",
        "color": "#D4C0A6",
    },
    "wards": {
        "title": "Administrative Wards",
        "altitude_hint_m": ALTITUDE_HINTS["wards"],
        "filename": "wards.geojson",
        "description": "Zonal boundaries ranked by composite urgency score for prioritized aid dispatch.",
        "color": "#9C8D82",
    },
}
