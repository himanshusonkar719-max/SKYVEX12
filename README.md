# FloodLens: Satellite-Based Hyperlocal Flood Detection & 3D Impact Mapping

FloodLens is an emergency response geospatial system built for Hackathon problem **ST-02 (Space Tech)**. It ingests pre/post-event satellite radar imagery (Sentinel-1 SAR C-Band) to detect inundation extents, models street-level impassable-road masks, computes ward-level composite urgency rankings, calculates vehicle-specific emergency evacuation routes to high-ground shelters, and visualizes the disaster scene on an interactive 3D Cesium globe with exploded layer separation.

---

## Key Highlights

- **Interactive 3D Cesium Globe with Exploded Layers**: Visually lifts layers to their altitude hints (`flood: 0m`, `roads: 150m`, `buildings: 300m`, `shelters: 600m`) with vertical ground connectors.
- **Hyperlocal Street Passability**: Evaluates road water thresholds per vehicle type (`Ambulance: 0.3m`, `Truck: 0.6m`, `Foot: 1.0m`).
- **Reliability Routing**: Graph routing with edge weights proportional to $-\log(p_{\text{open}})$, navigating around flooded segments to the nearest shelter with available capacity.
- **Scientific Depth Labeling**: All calculated depths are strictly labeled as **`estimated depth (proxy)`** derived from radar backscatter change and distance-to-water contours.
- **100% Offline-Capable**: Auto-generates synthetic WGS84 GeoJSON datasets if satellite feeds or network connections are unavailable. Never crashes.

---

## Project Structure

```
floodlens/
├── backend/
│   ├── config.py         # AOI coordinates, weights, altitude hints, proxy depth note
│   ├── schemas.py        # Pydantic request & response contracts ({error, hint})
│   ├── synthetic.py      # Deterministic 6-decimal WGS84 GeoJSON generator
│   ├── main.py           # FastAPI application (CORS, GZip, cached layers)
│   ├── tests/            # Pytest test suite for thresholds, urgency & API
│   └── data/             # Static GeoJSON and frame datasets
├── public/data/          # Frontend fallback copies for offline reliability
├── run.sh                # Zero-manual-step bootstrap and runner
├── .env.example          # Environment configuration
└── README.md             # Documentation and curl examples
```

---

## Quickstart

Run with zero manual steps:
```bash
./run.sh
```

Or manually:
```bash
# 1. Generate geospatial data
python3 -m backend.synthetic

# 2. Run backend
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# 3. In another terminal, run frontend
npm run dev
```

---

## Running the Pytest Suite

```bash
python3 -m pytest backend/tests/test_phase1.py -v
```

---

## API Documentation & Curl Examples

### 1. System Health & AOI
```bash
curl -s http://127.0.0.1:8000/api/health | jq .
```
Response:
```json
{
  "status": "healthy",
  "app": "FloodLens",
  "version": "1.0.0",
  "mode": "synthetic",
  "data_loaded": true,
  "aoi": {
    "lat": 25.5941,
    "lon": 85.1376,
    "min_lon": 85.08,
    "min_lat": 25.56,
    "max_lon": 85.2,
    "max_lat": 25.64
  },
  "depth_proxy_label": "estimated depth (proxy)"
}
```

### 2. Available Geospatial Layers (with 3D Altitude Hints)
```bash
curl -s http://127.0.0.1:8000/api/layers | jq .
```
Response:
```json
{
  "layers": [
    {
      "name": "flood",
      "title": "Flood Extent & Depth",
      "size_kb": 12.4,
      "altitude_hint_m": 0,
      "feature_count": 2,
      "color": "#4FA3D1"
    },
    {
      "name": "roads",
      "title": "Street Grid & Passability",
      "size_kb": 48.6,
      "altitude_hint_m": 150,
      "feature_count": 226,
      "color": "#5FB878"
    },
    {
      "name": "buildings",
      "title": "Building Footprints",
      "size_kb": 85.2,
      "altitude_hint_m": 300,
      "feature_count": 300,
      "color": "#E8A03C"
    },
    {
      "name": "shelters",
      "title": "Evacuation Shelters",
      "size_kb": 3.8,
      "altitude_hint_m": 600,
      "feature_count": 6,
      "color": "#D4C0A6"
    },
    {
      "name": "wards",
      "title": "Administrative Wards",
      "size_kb": 8.1,
      "altitude_hint_m": 50,
      "feature_count": 6,
      "color": "#9C8D82"
    }
  ]
}
```

### 3. Fetch Layer GeoJSON (e.g. Roads)
```bash
curl -s http://127.0.0.1:8000/api/layers/roads | head -c 250
```

### 4. Situational Impact Summary
```bash
curl -s http://127.0.0.1:8000/api/summary | jq .
```
Response:
```json
{
  "affected_buildings": 139,
  "flooded_road_km": 36.82,
  "cutoff_habitats": 24,
  "top_wards": [
    {
      "ward": "Ward 4 (Patliputra Sector)",
      "urgency_score": 76.5,
      "rank": 1,
      "exposed_buildings": 46,
      "blocked_roads_pct": 39.5
    }
  ],
  "time_to_map_seconds": 0.02,
  "total_shelters": 6,
  "shelter_available_capacity": 1031
}
```

### 5. Inundation Time Steps (T+0h to T+5h)
```bash
curl -s http://127.0.0.1:8000/api/flood/frames | jq .
```

### 6. Specific Timestep GeoJSON
```bash
curl -s http://127.0.0.1:8000/api/flood/frames/3 | head -c 250
```

### 7. Interactive API Documentation
Open `http://127.0.0.1:8000/docs` in your browser for Swagger UI or `http://127.0.0.1:8000/redoc` for ReDoc.
