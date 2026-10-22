"""Data contract schemas for FloodLens API.
Enforces consistent shapes, type validation, and error reporting.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# Consistent Error Shape
class ErrorResponse(BaseModel):
    error: str = Field(..., description="High-level error summary")
    hint: str = Field(..., description="Actionable hint on how to fix or resolve")

# Health Schema
class HealthResponse(BaseModel):
    status: str = "healthy"
    app: str = "FloodLens"
    version: str = "1.0.0"
    mode: str = "synthetic"  # or 'sentinel-1'
    data_loaded: bool = True
    aoi: Dict[str, float]
    depth_proxy_label: str = "estimated depth (proxy)"

# Layer Schemas
class LayerMeta(BaseModel):
    name: str
    title: str
    size_kb: float
    altitude_hint_m: int
    feature_count: int
    color: str
    description: str

class LayersResponse(BaseModel):
    layers: List[LayerMeta]

# Summary Schema
class TopWard(BaseModel):
    ward: str
    urgency_score: float
    rank: int
    exposed_buildings: int
    blocked_roads_pct: float

class SummaryResponse(BaseModel):
    affected_buildings: int
    flooded_road_km: float
    cutoff_habitats: int
    top_wards: List[TopWard]
    generated_at: str
    time_to_map_seconds: float
    total_shelters: int
    shelter_available_capacity: int
    depth_proxy_note: str

# Flood Frames Schema
class FloodFrameMeta(BaseModel):
    t: int
    time_label: str  # e.g., "T+0h", "T+1h", ...
    filename: str
    max_depth_m: float
    mean_depth_m: float
    area_sq_km: float

class FloodFramesResponse(BaseModel):
    current_step: int
    total_steps: int
    frames: List[FloodFrameMeta]

# Feature Detail Schema
class FeatureDetailResponse(BaseModel):
    layer: str
    id: str
    name: Optional[str] = None
    properties: Dict[str, Any]
    human_summary: str  # e.g. "87% likely impassable due to 0.72m water depth"
    confidence_statement: str
    centroid: List[float]  # [lon, lat]
    depth_label: str = "estimated depth (proxy)"

# Routing Schemas
class RouteRequest(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)
    vehicle: str = Field("ambulance", pattern="^(ambulance|truck|foot)$")
    mode: str = Field("shortest", pattern="^(shortest|reliable)$")

class RouteStep(BaseModel):
    instruction: str
    distance_m: float
    depth_proxy_m: float

class RouteResponse(BaseModel):
    route: Optional[Dict[str, Any]] = None  # GeoJSON Feature or FeatureCollection
    distance_km: Optional[float] = None
    eta_minutes: Optional[float] = None
    reliability_pct: Optional[float] = None
    shelter_name: Optional[str] = None
    shelter_id: Optional[str] = None
    vehicle_used: str
    routing_mode: str
    max_water_encountered_m: Optional[float] = None
    reason: Optional[str] = None
    suggestion: Optional[str] = None

# Evacuation Plan Schemas
class WardEvacuationAssignment(BaseModel):
    ward: str
    evacuees: int
    assigned_shelter: str
    shelter_capacity: int
    distance_km: float
    priority_rank: int

class EvacuationPlanResponse(BaseModel):
    generated_at: str
    assignments: List[WardEvacuationAssignment]
    total_evacuees: int
    total_capacity: int
    unassigned_count: int
    status: str

# SMS Alert Schema
class SmsPreviewResponse(BaseModel):
    ward: str
    message: str = Field(..., max_length=160)
    char_count: int
    urgency_rank: int

# Responder Feedback Schema
class FeedbackRequest(BaseModel):
    road_id: str
    status: str = Field(..., pattern="^(open|impassable)$")
    depth_override_m: Optional[float] = None
    reporter: Optional[str] = "Field Responder"
    note: Optional[str] = None

class FeedbackResponse(BaseModel):
    success: bool
    road_id: str
    status: str
    updated_at: str
    active_overrides_count: int

# Pipeline Run Schemas
class PipelineRunRequest(BaseModel):
    force_synthetic: bool = False
    source: str = "synthetic"  # or "sentinel-1"

class PipelineStatusResponse(BaseModel):
    running: bool
    status: str
    message: str
    last_run_seconds: float
    data_source: str
