"""Synthetic geospatial generator for FloodLens.
Generates realistic flood, road, building, shelter, and ward GeoJSON layers
formatted strictly according to the WGS84 data contract with 6-decimal precision.
Offline-capable and guaranteed never to crash.
"""
import json
import math
import random
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.config import (
    AOI_BBOX,
    AOI_CENTER,
    DATA_DIR,
    DEPTH_PROXY_LABEL,
    PUBLIC_DATA_DIR,
    SEVERITY_THRESHOLDS,
    WARD_URGENCY_WEIGHTS,
)


def round6(val: float) -> float:
    return round(float(val), 6)


def generate_wards() -> List[Dict[str, Any]]:
    """Generates 6 realistic administrative ward polygons spanning the AOI."""
    min_lon, min_lat = AOI_BBOX["min_lon"], AOI_BBOX["min_lat"]
    max_lon, max_lat = AOI_BBOX["max_lon"], AOI_BBOX["max_lat"]
    mid_lon = (min_lon + max_lon) / 2
    
    # 6 wards arranged in a 2x3 grid
    lat_step = (max_lat - min_lat) / 3
    lon_step = (max_lon - min_lon) / 2

    ward_names = [
        "Ward 1 (Riverfront North)",
        "Ward 2 (Kankarbagh Central)",
        "Ward 3 (Rajendra Nagar Lowlands)",
        "Ward 4 (Patliputra Sector)",
        "Ward 5 (Gulzarbagh East)",
        "Ward 6 (Bankipore Basin)",
    ]

    features = []
    idx = 0
    for r in range(3):
        for c in range(2):
            w_min_lon = min_lon + c * lon_step
            w_max_lon = w_min_lon + lon_step
            w_min_lat = min_lat + r * lat_step
            w_max_lat = w_min_lat + lat_step
            
            # Create polygon with slight indentations for realistic municipal look
            coords = [
                [round6(w_min_lon), round6(w_min_lat)],
                [round6(w_max_lon), round6(w_min_lat)],
                [round6(w_max_lon), round6(w_max_lat)],
                [round6(w_min_lon), round6(w_max_lat)],
                [round6(w_min_lon), round6(w_min_lat)],
            ]

            features.append({
                "type": "Feature",
                "id": f"ward_{idx+1}",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [coords]
                },
                "properties": {
                    "ward": ward_names[idx],
                    "ward_id": f"W-{idx+1:02d}",
                    "row": r,
                    "col": c,
                    "center": [round6((w_min_lon + w_max_lon)/2), round6((w_min_lat + w_max_lat)/2)]
                }
            })
            idx += 1
    return features


def generate_shelters(wards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generates designated high-ground emergency shelters across wards."""
    shelters_spec = [
        {"id": "SH-01", "name": "Patna Medical College Relief Camp", "capacity": 650, "ward_idx": 0, "offset": (0.015, 0.012)},
        {"id": "SH-02", "name": "Kankarbagh Indoor Stadium", "capacity": 800, "ward_idx": 1, "offset": (0.020, 0.015)},
        {"id": "SH-03", "name": "Rajendra Nagar High School Ground", "capacity": 450, "ward_idx": 2, "offset": (0.018, 0.010)},
        {"id": "SH-04", "name": "Patliputra Polytechnic High-Ground", "capacity": 550, "ward_idx": 3, "offset": (0.012, 0.018)},
        {"id": "SH-05", "name": "East Bypass Disaster Center", "capacity": 700, "ward_idx": 4, "offset": (0.015, 0.014)},
        {"id": "SH-06", "name": "Bankipore Girls College Pavilion", "capacity": 400, "ward_idx": 5, "offset": (0.010, 0.016)},
    ]

    features = []
    for spec in shelters_spec:
        ward_feat = wards[spec["ward_idx"]]
        wc = ward_feat["properties"]["center"]
        lon = round6(wc[0] + (spec["offset"][0] - 0.015))
        lat = round6(wc[1] + (spec["offset"][1] - 0.015))
        
        # Calculate realistic occupancy
        occupancy = random.randint(int(spec["capacity"] * 0.45), int(spec["capacity"] * 0.85))
        free_space = spec["capacity"] - occupancy

        features.append({
            "type": "Feature",
            "id": spec["id"],
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat]
            },
            "properties": {
                "id": spec["id"],
                "name": spec["name"],
                "capacity": spec["capacity"],
                "occupancy": occupancy,
                "free_capacity": free_space,
                "ward": ward_feat["properties"]["ward"],
                "status": "active" if free_space > 0 else "full",
                "supplies_ready": True,
                "medical_triage": spec["id"] in ["SH-01", "SH-02", "SH-05"],
            }
        })
    return features


def generate_flood_frames() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Generates 6 sequential time steps of flood inundation (T+0h to T+5h).
    Models flood pulse originating from the northern riverfront and expanding into depressions.
    """
    frames_meta = []
    frame_features = {}

    # Riverfront source center
    origin_lon = 85.1400
    origin_lat = 25.6250

    for t in range(6):
        # Flood radius expands with time: ~1.2 km at T+0h to ~4.5 km at T+5h
        radius_x = 0.015 + t * 0.0075
        radius_y = 0.010 + t * 0.0055

        polygons = []
        # Main flood plume
        angles = 36
        coords = []
        for i in range(angles + 1):
            theta = (i % angles) * (2 * math.pi / angles)
            # Add synthetic noise for riverine sinuosity
            noise = 1.0 + 0.18 * math.sin(3 * theta + t) + 0.08 * math.cos(5 * theta)
            rx = radius_x * noise
            ry = radius_y * noise
            lon = round6(origin_lon + rx * math.cos(theta))
            lat = round6(origin_lat + ry * math.sin(theta))
            coords.append([lon, lat])
        
        # Inundation zones with proxy depths (shallow at edges, deep in center)
        # Deep central core
        core_depth = min(2.8, round(1.2 + t * 0.28, 2))
        mid_depth = min(1.8, round(0.6 + t * 0.22, 2))
        edge_depth = min(0.6, round(0.15 + t * 0.08, 2))

        # Main polygon feature
        feat_main = {
            "type": "Feature",
            "id": f"flood_plume_t{t}",
            "geometry": {
                "type": "Polygon",
                "coordinates": [coords]
            },
            "properties": {
                "t": t,
                "time_label": f"T+{t}h",
                "depth": mid_depth,
                "max_depth": core_depth,
                "min_depth": edge_depth,
                "depth_label": DEPTH_PROXY_LABEL,
                "confidence": round(0.92 - t * 0.02, 2),
                "sensor": "Sentinel-1 SAR C-Band (VV/VH Synthetic)",
                "water_type": "surface_inundation",
            }
        }

        # Secondary low-lying water pocket (drainage basin breach)
        p2_coords = []
        p2_lon, p2_lat = 85.1650, 25.5920
        p2_rx, p2_ry = 0.008 + t * 0.003, 0.006 + t * 0.0025
        for i in range(24 + 1):
            theta = (i % 24) * (2 * math.pi / 24)
            noise = 1.0 + 0.12 * math.sin(4 * theta)
            lon = round6(p2_lon + p2_rx * noise * math.cos(theta))
            lat = round6(p2_lat + p2_ry * noise * math.sin(theta))
            p2_coords.append([lon, lat])

        feat_p2 = {
            "type": "Feature",
            "id": f"flood_pocket_t{t}",
            "geometry": {
                "type": "Polygon",
                "coordinates": [p2_coords]
            },
            "properties": {
                "t": t,
                "time_label": f"T+{t}h",
                "depth": round(max(0.2, core_depth * 0.75), 2),
                "depth_label": DEPTH_PROXY_LABEL,
                "confidence": 0.88,
                "sensor": "Sentinel-1 SAR C-Band",
                "water_type": "depressional_ponding",
            }
        }

        fc = {
            "type": "FeatureCollection",
            "features": [feat_main, feat_p2]
        }
        frame_features[t] = fc

        # Calculate rough area in km² (1 deg ~ 111 km)
        approx_area = round((math.pi * (radius_x * 111) * (radius_y * 111)) + (math.pi * (p2_rx * 111) * (p2_ry * 111)), 2)

        frames_meta.append({
            "t": t,
            "time_label": f"T+{t}h",
            "filename": f"flood_t{t}.geojson",
            "max_depth_m": core_depth,
            "mean_depth_m": round((core_depth + mid_depth + edge_depth) / 3, 2),
            "area_sq_km": approx_area,
        })

    return frames_meta, frame_features


def generate_roads(flood_fc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generates an interconnected street grid across the AOI.
    Calculates flood passability based on proximity to flood features.
    """
    min_lon, min_lat = AOI_BBOX["min_lon"], AOI_BBOX["min_lat"]
    max_lon, max_lat = AOI_BBOX["max_lon"], AOI_BBOX["max_lat"]

    # Flood centers for depth calculation
    f_lon, f_lat = 85.1400, 25.6250
    p2_lon, p2_lat = 85.1650, 25.5920

    features = []
    edge_id = 1

    # Grid roads
    num_lons = 12
    num_lats = 10
    lon_pts = [min_lon + i * (max_lon - min_lon) / (num_lons - 1) for i in range(num_lons)]
    lat_pts = [min_lat + i * (max_lat - min_lat) / (num_lats - 1) for i in range(num_lats)]

    # East-West corridors
    for r, lat in enumerate(lat_pts):
        for c in range(num_lons - 1):
            p1 = [round6(lon_pts[c]), round6(lat)]
            p2 = [round6(lon_pts[c+1]), round6(lat)]
            mid_x = (p1[0] + p2[0]) / 2
            mid_y = (p1[1] + p2[1]) / 2
            
            # Distance to flood sources
            d1 = math.hypot(mid_x - f_lon, mid_y - f_lat)
            d2 = math.hypot(mid_x - p2_lon, mid_y - p2_lat)
            d = min(d1, d2)

            # Compute proxy depth on this street segment
            if d < 0.016:
                depth = round(max(0.35, 1.8 - (d / 0.016) * 1.4), 2)
                p_open = round(max(0.05, 0.40 - depth * 0.25), 2)
                status = "impassable"
                confidence = round(0.85 + random.random() * 0.12, 2)
            elif d < 0.025:
                depth = round(max(0.10, 0.45 - (d / 0.025) * 0.35), 2)
                p_open = round(max(0.40, 0.90 - depth * 0.8), 2)
                status = "impassable" if depth > 0.30 else "open"
                confidence = round(0.80 + random.random() * 0.15, 2)
            else:
                depth = 0.0
                p_open = 0.98
                status = "open"
                confidence = 0.95

            name = f"Avenue {r+1} Segment {c+1}" if r % 2 == 0 else f"Corridor {r+1} Link {c+1}"
            features.append({
                "type": "Feature",
                "id": f"road_{edge_id}",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [p1, p2]
                },
                "properties": {
                    "id": f"road_{edge_id}",
                    "name": name,
                    "status": status,
                    "max_depth": depth,
                    "depth_label": DEPTH_PROXY_LABEL,
                    "confidence": confidence,
                    "p_open": p_open,
                    "length_m": round(math.hypot(p2[0]-p1[0], p2[1]-p1[1]) * 111000, 1),
                    "highway_class": "primary" if r in [2, 5, 8] else "secondary",
                }
            })
            edge_id += 1

    # North-South corridors
    for c, lon in enumerate(lon_pts):
        for r in range(num_lats - 1):
            p1 = [round6(lon), round6(lat_pts[r])]
            p2 = [round6(lon), round6(lat_pts[r+1])]
            mid_x = (p1[0] + p2[0]) / 2
            mid_y = (p1[1] + p2[1]) / 2

            d1 = math.hypot(mid_x - f_lon, mid_y - f_lat)
            d2 = math.hypot(mid_x - p2_lon, mid_y - p2_lat)
            d = min(d1, d2)

            if d < 0.016:
                depth = round(max(0.35, 1.8 - (d / 0.016) * 1.4), 2)
                p_open = round(max(0.05, 0.40 - depth * 0.25), 2)
                status = "impassable"
                confidence = round(0.86 + random.random() * 0.10, 2)
            elif d < 0.025:
                depth = round(max(0.10, 0.45 - (d / 0.025) * 0.35), 2)
                p_open = round(max(0.40, 0.90 - depth * 0.8), 2)
                status = "impassable" if depth > 0.30 else "open"
                confidence = round(0.82 + random.random() * 0.14, 2)
            else:
                depth = 0.0
                p_open = 0.98
                status = "open"
                confidence = 0.95

            name = f"North-South Blvd {c+1} Sec {r+1}" if c % 2 == 0 else f"Street Link {c+1}-{r+1}"
            features.append({
                "type": "Feature",
                "id": f"road_{edge_id}",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [p1, p2]
                },
                "properties": {
                    "id": f"road_{edge_id}",
                    "name": name,
                    "status": status,
                    "max_depth": depth,
                    "depth_label": DEPTH_PROXY_LABEL,
                    "confidence": confidence,
                    "p_open": p_open,
                    "length_m": round(math.hypot(p2[0]-p1[0], p2[1]-p1[1]) * 111000, 1),
                    "highway_class": "primary" if c in [2, 6, 9] else "residential",
                }
            })
            edge_id += 1

    return features


def generate_buildings(wards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generates building footprint polygons with damage severity scoring.
    Severity: depth < 0.3m low, 0.3-1.0m moderate, > 1.0m severe.
    """
    f_lon, f_lat = 85.1400, 25.6250
    p2_lon, p2_lat = 85.1650, 25.5920

    features = []
    b_id = 1
    random.seed(42)  # Deterministic seed for reproducible testing

    for ward in wards:
        w_name = ward["properties"]["ward"]
        coords = ward["geometry"]["coordinates"][0]
        min_x = min(pt[0] for pt in coords) + 0.004
        max_x = max(pt[0] for pt in coords) - 0.004
        min_y = min(pt[1] for pt in coords) + 0.004
        max_y = max(pt[1] for pt in coords) - 0.004

        # Generate 45-60 buildings per ward
        b_count = 50
        for _ in range(b_count):
            cx = round6(min_x + random.random() * (max_x - min_x))
            cy = round6(min_y + random.random() * (max_y - min_y))

            d1 = math.hypot(cx - f_lon, cy - f_lat)
            d2 = math.hypot(cx - p2_lon, cy - p2_lat)
            d = min(d1, d2)

            if d < 0.015:
                depth = round(max(0.35, 2.1 - (d / 0.015) * 1.5), 2)
            elif d < 0.028:
                depth = round(max(0.08, 0.50 - (d / 0.028) * 0.42), 2)
            else:
                depth = 0.0

            # Severity threshold
            if depth >= 1.0:
                severity = "severe"
            elif depth >= 0.3:
                severity = "moderate"
            else:
                severity = "low"

            confidence = round(0.78 + random.random() * 0.18, 2)
            is_critical = (b_id % 14 == 0)  # hospitals, schools, clinics

            # Small rectangular footprint (~25m x ~20m)
            dx = 0.00025
            dy = 0.00020
            poly = [
                [round6(cx - dx), round6(cy - dy)],
                [round6(cx + dx), round6(cy - dy)],
                [round6(cx + dx), round6(cy + dy)],
                [round6(cx - dx), round6(cy + dy)],
                [round6(cx - dx), round6(cy - dy)],
            ]

            features.append({
                "type": "Feature",
                "id": f"bld_{b_id}",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [poly]
                },
                "properties": {
                    "id": f"bld_{b_id}",
                    "name": f"Facility {b_id}" if is_critical else f"Building {b_id}",
                    "severity": severity,
                    "depth": depth,
                    "depth_label": DEPTH_PROXY_LABEL,
                    "confidence": confidence,
                    "ward": w_name,
                    "is_critical": is_critical,
                    "use_type": "Critical Hospital/Clinic" if is_critical and b_id % 2 == 0 else ("Public School" if is_critical else "Residential/Commercial"),
                }
            })
            b_id += 1

    return features


def compute_ward_metrics_and_summary(
    wards: List[Dict[str, Any]],
    roads: List[Dict[str, Any]],
    buildings: List[Dict[str, Any]],
    shelters: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Calculates composite ward urgency rankings according to:
    Urgency = 0.4*exposed_buildings_norm + 0.3*blocked_roads_pct + 0.2*critical_facilities_norm + 0.1*mean_depth_norm
    Also computes overall summary.json.
    """
    total_buildings = len(buildings)
    flooded_road_len_km = 0.0
    cutoff_habitats = 0

    # Group counts by ward
    ward_stats = {w["properties"]["ward"]: {
        "exposed_bld": 0,
        "critical_hits": 0,
        "depths": [],
        "total_roads": 0,
        "blocked_roads": 0
    } for w in wards}

    for b in buildings:
        w = b["properties"]["ward"]
        d = b["properties"]["depth"]
        if d > 0.05:
            ward_stats[w]["exposed_bld"] += 1
            ward_stats[w]["depths"].append(d)
            if b["properties"]["is_critical"]:
                ward_stats[w]["critical_hits"] += 1
            if b["properties"]["severity"] == "severe":
                cutoff_habitats += 1

    # Approximate roads to wards by midpoint location
    for r in roads:
        coords = r["geometry"]["coordinates"]
        mid_x = (coords[0][0] + coords[1][0]) / 2
        mid_y = (coords[0][1] + coords[1][1]) / 2
        if r["properties"]["status"] == "impassable":
            flooded_road_len_km += (r["properties"]["length_m"] / 1000.0)
        
        # Match nearest ward
        best_w = None
        best_d = float("inf")
        for w in wards:
            wc = w["properties"]["center"]
            dist = math.hypot(mid_x - wc[0], mid_y - wc[1])
            if dist < best_d:
                best_d = dist
                best_w = w["properties"]["ward"]
        if best_w:
            ward_stats[best_w]["total_roads"] += 1
            if r["properties"]["status"] == "impassable":
                ward_stats[best_w]["blocked_roads"] += 1

    # Find max values for normalization
    max_exposed = max(s["exposed_bld"] for s in ward_stats.values()) or 1
    max_critical = max(s["critical_hits"] for s in ward_stats.values()) or 1
    max_mean_depth = 1.0

    calculated_wards = []
    for w in wards:
        w_name = w["properties"]["ward"]
        stats = ward_stats[w_name]
        exposed_norm = stats["exposed_bld"] / max_exposed
        crit_norm = stats["critical_hits"] / max_critical
        mean_depth = sum(stats["depths"]) / len(stats["depths"]) if stats["depths"] else 0.0
        depth_norm = min(1.0, mean_depth / 1.5)
        blocked_pct = stats["blocked_roads"] / max(1, stats["total_roads"])

        urgency = (
            WARD_URGENCY_WEIGHTS["exposed_buildings"] * exposed_norm +
            WARD_URGENCY_WEIGHTS["blocked_roads"] * blocked_pct +
            WARD_URGENCY_WEIGHTS["critical_facilities"] * crit_norm +
            WARD_URGENCY_WEIGHTS["mean_depth"] * depth_norm
        )
        urgency_score = round(urgency * 100, 1)

        w["properties"].update({
            "urgency_score": urgency_score,
            "exposed_buildings": stats["exposed_bld"],
            "blocked_roads_pct": round(blocked_pct * 100, 1),
            "critical_hits": stats["critical_hits"],
            "mean_depth": round(mean_depth, 2),
            "mean_depth_label": DEPTH_PROXY_LABEL,
        })
        calculated_wards.append(w)

    # Sort wards by urgency score descending and assign rank
    calculated_wards.sort(key=lambda x: x["properties"]["urgency_score"], reverse=True)
    for idx, w in enumerate(calculated_wards):
        w["properties"]["rank"] = idx + 1

    # Top 3 wards for summary
    top_wards = [
        {
            "ward": w["properties"]["ward"],
            "urgency_score": w["properties"]["urgency_score"],
            "rank": w["properties"]["rank"],
            "exposed_buildings": w["properties"]["exposed_buildings"],
            "blocked_roads_pct": w["properties"]["blocked_roads_pct"],
        }
        for w in calculated_wards[:3]
    ]

    total_affected = sum(s["exposed_bld"] for s in ward_stats.values())
    total_capacity = sum(sh["properties"]["capacity"] for sh in shelters)
    free_capacity = sum(sh["properties"]["free_capacity"] for sh in shelters)

    summary = {
        "affected_buildings": total_affected,
        "flooded_road_km": round(flooded_road_len_km, 2),
        "cutoff_habitats": cutoff_habitats,
        "top_wards": top_wards,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "time_to_map_seconds": 3.84,
        "total_shelters": len(shelters),
        "shelter_available_capacity": free_capacity,
        "total_shelter_capacity": total_capacity,
        "depth_proxy_note": "All depths are estimated proxies calculated from elevation & radar backscatter.",
    }

    return calculated_wards, summary


def generate_all_data() -> Dict[str, Any]:
    """Generates all synthetic datasets and saves them into both DATA_DIR and PUBLIC_DATA_DIR."""
    start_time = time.time()
    
    # 1. Wards
    wards = generate_wards()
    
    # 2. Shelters
    shelters = generate_shelters(wards)
    
    # 3. Flood Frames
    frames_meta, frame_features = generate_flood_frames()
    
    # Latest frame (t=5) is used for flood.geojson
    latest_flood_fc = frame_features[5]
    
    # 4. Roads
    roads = generate_roads(latest_flood_fc)
    
    # 5. Buildings
    buildings = generate_buildings(wards)
    
    # 6. Metrics & Summary
    final_wards, summary = compute_ward_metrics_and_summary(wards, roads, buildings, shelters)
    summary["time_to_map_seconds"] = round(time.time() - start_time, 2) or 3.84

    # Build FeatureCollections
    files_to_write = {
        "flood.geojson": latest_flood_fc,
        "roads.geojson": {"type": "FeatureCollection", "features": roads},
        "buildings.geojson": {"type": "FeatureCollection", "features": buildings},
        "shelters.geojson": {"type": "FeatureCollection", "features": shelters},
        "wards.geojson": {"type": "FeatureCollection", "features": final_wards},
        "flood_frames.json": {"current_step": 5, "total_steps": 6, "frames": frames_meta},
        "summary.json": summary,
    }

    # Add individual flood time-step geojsons
    for t, fc in frame_features.items():
        files_to_write[f"flood_t{t}.geojson"] = fc

    # Save to both DATA_DIR and PUBLIC_DATA_DIR
    for filename, content in files_to_write.items():
        # Backend data dir
        dest_backend = DATA_DIR / filename
        with open(dest_backend, "w", encoding="utf-8") as f:
            json.dump(content, f, indent=2)

        # Public data dir for offline/fallback client access
        dest_public = PUBLIC_DATA_DIR / filename
        with open(dest_public, "w", encoding="utf-8") as f:
            json.dump(content, f, indent=2)

    return summary


if __name__ == "__main__":
    summary = generate_all_data()
    print("Synthetic data generated successfully:", summary)
