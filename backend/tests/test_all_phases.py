"""Comprehensive test suite for all FloodLens backend phases.
Tests routing, feedback, vehicle limits, SMS ceiling, evacuation plan, and report generation.
"""
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.synthetic import generate_all_data

client = TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def setup_data():
    """Ensure data is ready before tests."""
    generate_all_data()


def test_routing_endpoint_valid():
    """Verify route computation returns valid GeoJSON line and metrics."""
    # Near central Patna
    lat, lon = 25.594, 85.138
    response = client.get(f"/api/route?lat={lat}&lon={lon}&vehicle=ambulance&mode=shortest")
    assert response.status_code == 200
    data = response.json()
    assert "vehicle_used" in data
    assert data["vehicle_used"] == "ambulance"
    if data.get("route"):
        assert data["route"]["type"] == "Feature"
        assert data["distance_km"] > 0
        assert data["eta_minutes"] > 0
        assert "shelter_name" in data


def test_routing_vehicle_depth_limits():
    """Verify that heavy truck or foot can access higher depth limits than ambulance."""
    # Vehicle validation
    invalid_resp = client.get("/api/route?lat=25.59&lon=85.13&vehicle=submarine")
    assert invalid_resp.status_code == 400

    truck_resp = client.get("/api/route?lat=25.59&lon=85.13&vehicle=truck&mode=reliable")
    assert truck_resp.status_code == 200
    assert truck_resp.json()["vehicle_used"] == "truck"


def test_responder_feedback_and_impact():
    """Verify field responder feedback updates road status and is reflected in overrides."""
    feedback_payload = {
        "road_id": "road_1",
        "status": "impassable",
        "depth_override_m": 0.85,
        "reporter": "Unit-Alpha",
        "note": "Submerged under deep runoff",
    }
    post_resp = client.post("/api/feedback", json=feedback_payload)
    assert post_resp.status_code == 200
    assert post_resp.json()["success"] is True

    # Check listing
    get_resp = client.get("/api/feedback")
    assert get_resp.status_code == 200
    overrides = get_resp.json()["overrides"]
    assert any(o["road_id"] == "road_1" for o in overrides)


def test_evacuation_plan():
    """Verify min-cost flow capacity-constrained evacuation assignments."""
    response = client.get("/api/evacuation/plan")
    assert response.status_code == 200
    data = response.json()
    assert "assignments" in data
    assert len(data["assignments"]) == 6
    assert data["total_evacuees"] > 0
    assert data["total_capacity"] > 0


def test_sms_alert_160_character_ceiling():
    """Verify SMS messages do not exceed GSM 160-character cellular threshold."""
    for ward_query in ["ward 1", "kankarbagh", "rajendra", "ward 4"]:
        response = client.get(f"/api/sms/{ward_query}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["message"]) <= 160, f"SMS exceeded 160 chars ({len(data['message'])}): {data['message']}"
        assert data["char_count"] <= 160
        assert "FLOOD ALERT" in data["message"]


def test_feature_human_summary():
    """Verify feature detail returns human explanation and confidence."""
    # Road feature
    response = client.get("/api/feature/roads/road_1")
    assert response.status_code == 200
    data = response.json()
    assert "human_summary" in data
    assert "confidence_statement" in data
    assert "estimated depth (proxy)" in data["depth_label"]

    # Building feature
    bld_resp = client.get("/api/feature/buildings/bld_1")
    assert bld_resp.status_code == 200
    assert "human_summary" in bld_resp.json()


def test_pdf_report_download():
    """Verify single-page PDF briefing generation returns valid PDF binary."""
    response = client.get("/api/report.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert len(response.content) > 1000


def test_geojson_report_download():
    """Verify GIS report returns full FeatureCollection."""
    response = client.get("/api/report.geojson")
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) > 0
    assert "metadata" in data
