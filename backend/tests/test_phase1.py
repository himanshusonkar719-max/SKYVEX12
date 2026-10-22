"""Tests for Phase 1: synthetic data generation, thresholds, and core API endpoints."""
import json
import pytest
from fastapi.testclient import TestClient

from backend.config import DATA_DIR, SEVERITY_THRESHOLDS, WARD_URGENCY_WEIGHTS
from backend.main import app
from backend.synthetic import generate_all_data

client = TestClient(app)


def test_data_generation():
    """Verify synthetic data generator produces all expected files with valid content."""
    summary = generate_all_data()
    assert summary is not None
    assert summary["affected_buildings"] > 0
    assert summary["flooded_road_km"] > 0
    assert len(summary["top_wards"]) == 3
    assert "time_to_map_seconds" in summary

    # Check that all key files exist
    required_files = [
        "flood.geojson",
        "roads.geojson",
        "buildings.geojson",
        "shelters.geojson",
        "wards.geojson",
        "flood_frames.json",
        "summary.json",
        "flood_t0.geojson",
        "flood_t5.geojson",
    ]
    for rf in required_files:
        p = DATA_DIR / rf
        assert p.exists(), f"File {rf} missing from {DATA_DIR}"


def test_building_severity_thresholds():
    """Verify building severity categorization adheres to:
    depth < 0.3 low, 0.3-1.0 moderate, > 1.0 severe.
    """
    with open(DATA_DIR / "buildings.geojson", "r", encoding="utf-8") as f:
        data = json.load(f)

    features = data["features"]
    assert len(features) > 0

    for feat in features:
        props = feat["properties"]
        depth = props["depth"]
        severity = props["severity"]

        if depth >= 1.0:
            assert severity == "severe", f"Expected severe for depth {depth}, got {severity}"
        elif depth >= 0.3:
            assert severity == "moderate", f"Expected moderate for depth {depth}, got {severity}"
        else:
            assert severity == "low", f"Expected low for depth {depth}, got {severity}"


def test_ward_urgency_ordering():
    """Verify wards are ranked descending by urgency_score."""
    with open(DATA_DIR / "wards.geojson", "r", encoding="utf-8") as f:
        data = json.load(f)

    wards = data["features"]
    assert len(wards) == 6

    scores = [w["properties"]["urgency_score"] for w in wards]
    assert scores == sorted(scores, reverse=True), "Wards must be ordered descending by urgency_score"
    for idx, w in enumerate(wards):
        assert w["properties"]["rank"] == idx + 1


def test_api_health_endpoint():
    """Verify /api/health returns 200 with status, app, and depth proxy label."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app"] == "FloodLens"
    assert data["depth_proxy_label"] == "estimated depth (proxy)"
    assert "lat" in data["aoi"]


def test_api_layers_endpoint():
    """Verify /api/layers returns altitude hints and layer specs."""
    response = client.get("/api/layers")
    assert response.status_code == 200
    data = response.json()
    assert "layers" in data
    layer_names = [l["name"] for l in data["layers"]]
    for expected in ["flood", "roads", "buildings", "shelters", "wards"]:
        assert expected in layer_names

    # Check altitude hints
    flood_layer = next(l for l in data["layers"] if l["name"] == "flood")
    assert flood_layer["altitude_hint_m"] == 0
    roads_layer = next(l for l in data["layers"] if l["name"] == "roads")
    assert roads_layer["altitude_hint_m"] == 150
    buildings_layer = next(l for l in data["layers"] if l["name"] == "buildings")
    assert buildings_layer["altitude_hint_m"] == 300
    shelters_layer = next(l for l in data["layers"] if l["name"] == "shelters")
    assert shelters_layer["altitude_hint_m"] == 600


def test_api_layer_geojson():
    """Verify fetching individual GeoJSON layers."""
    for name in ["flood", "roads", "buildings", "shelters", "wards"]:
        response = client.get(f"/api/layers/{name}")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) > 0


def test_api_summary_endpoint():
    """Verify /api/summary returns key metrics."""
    response = client.get("/api/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["affected_buildings"] > 0
    assert data["flooded_road_km"] > 0
    assert len(data["top_wards"]) == 3
    assert "time_to_map_seconds" in data


def test_api_flood_frames_endpoint():
    """Verify /api/flood/frames returns 6 simulation steps."""
    response = client.get("/api/flood/frames")
    assert response.status_code == 200
    data = response.json()
    assert data["total_steps"] == 6
    assert len(data["frames"]) == 6

    # Test single frame retrieval
    t0_resp = client.get("/api/flood/frames/0")
    assert t0_resp.status_code == 200
    t0_data = t0_resp.json()
    assert t0_data["type"] == "FeatureCollection"


def test_invalid_layer_404():
    """Verify consistent {error, hint} on 404."""
    response = client.get("/api/layers/unknown_layer")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert "hint" in data
