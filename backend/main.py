"""FloodLens FastAPI Backend.
Hyperlocal flood detection, proxy depth estimation, impact scoring, and routing.
"""
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from backend.config import (
    AOI_BBOX,
    AOI_CENTER,
    DATA_DIR,
    DEPTH_PROXY_LABEL,
    DEPTH_PROXY_NOTE,
    LAYER_METADATA,
    PUBLIC_DATA_DIR,
)
from backend.schemas import (
    ErrorResponse,
    FloodFrameMeta,
    FloodFramesResponse,
    HealthResponse,
    LayerMeta,
    LayersResponse,
    SummaryResponse,
)
from backend.synthetic import generate_all_data

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [FloodLens] %(message)s",
)
logger = logging.getLogger("floodlens")

# Initialize FastAPI app
app = FastAPI(
    title="FloodLens API",
    description="Satellite-based hyperlocal flood detection, damage heatmaps, and impact routing.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for frontend Vite dev server and external clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enable GZip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# In-memory cache for ultra-fast GeoJSON responses
_DATA_CACHE: Dict[str, Any] = {}


def ensure_data_loaded():
    """Ensures that required GeoJSON datasets are generated and cached."""
    required_files = [
        "flood.geojson",
        "roads.geojson",
        "buildings.geojson",
        "shelters.geojson",
        "wards.geojson",
        "flood_frames.json",
        "summary.json",
    ]
    missing = [f for f in required_files if not (DATA_DIR / f).exists()]
    if missing:
        logger.info(f"Missing data files {missing}. Generating synthetic dataset...")
        generate_all_data()

    # Preload data into cache
    for filename in required_files:
        filepath = DATA_DIR / filename
        if filepath.exists() and filename not in _DATA_CACHE:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    _DATA_CACHE[filename] = json.load(f)
            except Exception as e:
                logger.error(f"Error reading {filename}: {e}")

    # Also preload frames t0-t5
    for t in range(6):
        fn = f"flood_t{t}.geojson"
        fp = DATA_DIR / fn
        if fp.exists() and fn not in _DATA_CACHE:
            with open(fp, "r", encoding="utf-8") as f:
                _DATA_CACHE[fn] = json.load(f)


@app.on_event("startup")
async def startup_event():
    """Startup hook to verify datasets and log ready status."""
    logger.info("Initializing FloodLens geospatial backend...")
    ensure_data_loaded()
    logger.info("FloodLens backend initialized successfully. All layers ready.")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Formats all HTTP exceptions into consistent {error, hint} structure."""
    detail = exc.detail
    hint = "Check request parameters or consult /docs for specification."
    if isinstance(detail, dict):
        error_msg = detail.get("error", str(detail))
        hint = detail.get("hint", hint)
    else:
        error_msg = str(detail)
    
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": error_msg, "hint": hint},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Catches unhandled exceptions and returns a graceful error response."""
    logger.error(f"Unhandled error processing {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal processing failure in FloodLens engine.",
            "hint": "The system encountered an unexpected state. Check input coordinates or fallback to synthetic data.",
        },
    )


@app.get("/health", summary="Health Check")
@app.get("/", summary="Root Liveness")
async def root_liveness():
    return {"status": "ok", "app": "FloodLens"}


@app.get("/api/health", response_model=HealthResponse, summary="System Health & Mode")
async def get_health():
    """Returns engine status, active mode, AOI bounding box, and depth proxy notice."""
    ensure_data_loaded()
    return HealthResponse(
        status="healthy",
        app="FloodLens",
        version="1.0.0",
        mode="synthetic",
        data_loaded=bool(_DATA_CACHE),
        aoi={
            "lat": AOI_CENTER["lat"],
            "lon": AOI_CENTER["lon"],
            "min_lon": AOI_BBOX["min_lon"],
            "min_lat": AOI_BBOX["min_lat"],
            "max_lon": AOI_BBOX["max_lon"],
            "max_lat": AOI_BBOX["max_lat"],
        },
        depth_proxy_label=DEPTH_PROXY_LABEL,
    )


@app.get("/api/layers", response_model=LayersResponse, summary="Available Geospatial Layers")
async def get_layers():
    """Lists all available geospatial layers with their altitude hints (for 3D explode view),
    file sizes in KB, feature counts, and descriptions.
    """
    ensure_data_loaded()
    layers_list = []

    for name, meta in LAYER_METADATA.items():
        filename = meta["filename"]
        filepath = DATA_DIR / filename
        size_kb = 0.0
        feature_count = 0
        
        if filepath.exists():
            size_kb = round(os.path.getsize(filepath) / 1024.0, 1)
            cached = _DATA_CACHE.get(filename)
            if cached and "features" in cached:
                feature_count = len(cached["features"])

        layers_list.append(
            LayerMeta(
                name=name,
                title=meta["title"],
                size_kb=size_kb,
                altitude_hint_m=meta["altitude_hint_m"],
                feature_count=feature_count,
                color=meta["color"],
                description=meta["description"],
            )
        )

    return LayersResponse(layers=layers_list)


@app.get("/api/layers/{name}", summary="Fetch Layer GeoJSON")
async def get_layer_geojson(name: str):
    """Retrieves full GeoJSON FeatureCollection for a specific layer.
    Supported layers: flood, roads, buildings, shelters, wards.
    """
    ensure_data_loaded()
    if name not in LAYER_METADATA:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": f"Layer '{name}' not found.",
                "hint": f"Available layers are: {', '.join(LAYER_METADATA.keys())}",
            },
        )

    filename = LAYER_METADATA[name]["filename"]
    if filename in _DATA_CACHE:
        return _DATA_CACHE[filename]

    filepath = DATA_DIR / filename
    if not filepath.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": f"Layer dataset file '{filename}' is missing from storage.",
                "hint": "Trigger /api/pipeline/run to regenerate synthetic data.",
            },
        )

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
        _DATA_CACHE[filename] = data
        return data


@app.get("/api/summary", response_model=SummaryResponse, summary="Flood Impact Summary")
async def get_summary():
    """Returns high-level situational metrics: affected buildings, flooded road km,
    cut-off habitats, top 3 urgent wards, and generation benchmark time.
    """
    ensure_data_loaded()
    summary_data = _DATA_CACHE.get("summary.json")
    if not summary_data:
        summary_path = DATA_DIR / "summary.json"
        if summary_path.exists():
            with open(summary_path, "r", encoding="utf-8") as f:
                summary_data = json.load(f)
                _DATA_CACHE["summary.json"] = summary_data
        else:
            summary_data = generate_all_data()

    return SummaryResponse(**summary_data)


@app.get("/api/flood/frames", response_model=FloodFramesResponse, summary="Flood Propagation Timesteps")
async def get_flood_frames():
    """Lists metadata for all 6 flood simulation time steps (T+0h to T+5h)."""
    ensure_data_loaded()
    frames_data = _DATA_CACHE.get("flood_frames.json")
    if not frames_data:
        fp = DATA_DIR / "flood_frames.json"
        if fp.exists():
            with open(fp, "r", encoding="utf-8") as f:
                frames_data = json.load(f)
                _DATA_CACHE["flood_frames.json"] = frames_data
        else:
            generate_all_data()
            frames_data = _DATA_CACHE["flood_frames.json"]

    return FloodFramesResponse(**frames_data)


@app.get("/api/flood/frames/{t}", summary="Fetch Specific Flood Timestep GeoJSON")
async def get_flood_frame_t(t: int):
    """Retrieves GeoJSON for flood timestep t (0 to 5)."""
    if t < 0 or t > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": f"Invalid timestep t={t}.",
                "hint": "Timestep t must be an integer between 0 and 5 (T+0h to T+5h).",
            },
        )

    ensure_data_loaded()
    filename = f"flood_t{t}.geojson"
    if filename in _DATA_CACHE:
        return _DATA_CACHE[filename]

    filepath = DATA_DIR / filename
    if not filepath.exists():
        generate_all_data()

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
        _DATA_CACHE[filename] = data
        return data


@app.post("/api/pipeline/run", summary="Trigger Detection Pipeline")
async def run_pipeline():
    """Triggers data regeneration / satellite SAR flood detection pipeline."""
    start = time.time()
    summary = generate_all_data()
    _DATA_CACHE.clear()
    ensure_data_loaded()
    elapsed = round(time.time() - start, 2)
    return {
        "status": "success",
        "message": "Detection pipeline executed. GeoJSON layers regenerated.",
        "time_seconds": elapsed,
        "summary": summary,
    }


@app.get("/api/pipeline/status", summary="Pipeline Engine Status")
async def get_pipeline_status():
    """Reports status of the processing pipeline."""
    return {
        "running": False,
        "status": "idle",
        "message": "Pipeline ready for on-demand inference.",
        "last_run_seconds": 3.84,
        "data_source": "synthetic (Sentinel-1 SAR C-Band ready)",
    }


@app.get("/api/wards", summary="Ranked Administrative Wards")
async def get_wards():
    """Returns municipal wards with urgency scores, rankings, and impact metrics."""
    ensure_data_loaded()
    filename = "wards.geojson"
    if filename in _DATA_CACHE:
        return _DATA_CACHE[filename]
    
    filepath = DATA_DIR / filename
    if not filepath.exists():
        generate_all_data()

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
        _DATA_CACHE[filename] = data
        return data


@app.get("/api/feature/{layer}/{feature_id}", summary="Detailed Feature Impact Summary")
async def get_feature_detail(layer: str, feature_id: str):
    """Provides human-readable summaries and confidence scores for selected features.
    e.g. '87% likely impassable due to 0.72m estimated depth (proxy)'
    """
    ensure_data_loaded()
    from backend.impact import get_feature_human_summary

    summary = get_feature_human_summary(layer, feature_id)
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": f"Feature '{feature_id}' not found in layer '{layer}'.",
                "hint": "Verify the layer name and feature identifier.",
            },
        )
    return summary


@app.get("/api/route", summary="Compute Emergency Evacuation Route (GET)")
@app.post("/api/route", summary="Compute Emergency Evacuation Route (POST)")
async def calculate_route(
    lat: float,
    lon: float,
    vehicle: str = "ambulance",
    mode: str = "shortest",
):
    """Calculates optimal evacuation path to nearest available emergency shelter.
    Limits: ambulance 0.3m, truck 0.6m, foot 1.0m.
    Modes: 'shortest' (distance) or 'reliable' (-log(p_open)).
    """
    ensure_data_loaded()
    from backend.routing import plan_emergency_route

    if vehicle not in ["ambulance", "truck", "foot"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": f"Invalid vehicle '{vehicle}'.",
                "hint": "Vehicle must be one of: 'ambulance', 'truck', 'foot'.",
            },
        )

    if mode not in ["shortest", "reliable"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": f"Invalid routing mode '{mode}'.",
                "hint": "Routing mode must be 'shortest' or 'reliable'.",
            },
        )

    result = plan_emergency_route(lat, lon, vehicle=vehicle, mode=mode)
    return result


@app.get("/api/evacuation/plan", summary="Municipal Evacuation Plan")
async def get_evacuation_plan():
    """Generates capacity-constrained assignment of wards to shelters via min-cost flow."""
    ensure_data_loaded()
    from backend.routing import compute_evacuation_plan

    return compute_evacuation_plan()


@app.get("/api/sms/{ward}", summary="Generate Ward SMS Broadcast")
async def get_sms_alert(ward: str):
    """Generates concise, ward-targeted SMS alert strictly under 160 characters."""
    ensure_data_loaded()
    from backend.sms import generate_ward_sms

    return generate_ward_sms(ward)


@app.get("/api/feedback", summary="List Responder Overrides")
async def list_feedback():
    """Returns active field responder passability overrides."""
    from backend.feedback import get_all_overrides

    return {"overrides": get_all_overrides()}


@app.post("/api/feedback", summary="Submit Responder Override")
async def submit_feedback(request: Request):
    """Allows ground teams to mark roads as blocked or open."""
    from backend.feedback import apply_feedback

    body = await request.json()
    road_id = body.get("road_id")
    status_val = body.get("status")
    depth_override = body.get("depth_override_m")
    reporter = body.get("reporter", "Field Responder")
    note = body.get("note", "")

    if not road_id or status_val not in ["open", "impassable"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Missing road_id or invalid status.",
                "hint": "Provide road_id and status ('open' or 'impassable').",
            },
        )

    override = apply_feedback(
        road_id=road_id,
        status=status_val,
        depth_override_m=depth_override,
        reporter=reporter,
        note=note,
    )
    _DATA_CACHE.pop("roads.geojson", None)
    return {"success": True, "override": override}


@app.get("/api/report.geojson", summary="Download GIS Briefing GeoJSON")
async def download_geojson_report():
    """Returns unified GIS-ready GeoJSON FeatureCollection."""
    ensure_data_loaded()
    from backend.report import generate_geojson_report

    return generate_geojson_report()


@app.get("/api/report.pdf", summary="Download PDF Briefing")
async def download_pdf_report():
    """Returns downloadable executive single-page PDF briefing."""
    ensure_data_loaded()
    from fastapi.responses import Response
    from backend.report import generate_pdf_report_bytes

    pdf_bytes = generate_pdf_report_bytes()
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="FloodLens_Situational_Report.pdf"'},
    )

