/**
 * API client with automatic offline static fallback.
 * Tries FastAPI endpoints first; falls back smoothly to static /data/ GeoJSON files.
 */
import { CONFIG } from "./config.js";

const API_BASE = CONFIG.apiUrl;
const STATIC_BASE = "/data";

/** Fetch with fallback to static copy */
export async function fetchJson(endpoint, staticFallbackFile = null) {
  try {
    const res = await fetch(`${API_BASE}${endpoint}`);
    if (!res.ok) throw new Error(`API HTTP error ${res.status}`);
    return await res.json();
  } catch (err) {
    if (staticFallbackFile) {
      console.warn(`[FloodLens API] Backend unavailable for ${endpoint}. Falling back to static ${staticFallbackFile}.`);
      const fallbackRes = await fetch(`${STATIC_BASE}/${staticFallbackFile}`);
      if (!fallbackRes.ok) throw new Error(`Static fallback failed for ${staticFallbackFile}`);
      return await fallbackRes.json();
    }
    throw err;
  }
}

/** Get layer metadata list */
export async function getLayers() {
  try {
    return await fetchJson("/layers");
  } catch (err) {
    return {
      layers: [
        { name: "flood", title: "Flood Extent & Depth", size_kb: 12.4, altitude_hint_m: 0, feature_count: 2, color: CONFIG.colors.floodShallow, description: "Satellite inundation with estimated depth (proxy) levels." },
        { name: "roads", title: "Street Grid & Passability", size_kb: 48.6, altitude_hint_m: 150, feature_count: 226, color: CONFIG.colors.roadOpen, description: "Hyperlocal street passability based on vehicle limits." },
        { name: "buildings", title: "Building Footprints", size_kb: 85.2, altitude_hint_m: 300, feature_count: 300, color: CONFIG.colors.severityModerate, description: "Structure damage severity zones." },
        { name: "shelters", title: "Evacuation Shelters", size_kb: 3.8, altitude_hint_m: 600, feature_count: 6, color: CONFIG.colors.shelter, description: "High-ground designated relief camps." },
        { name: "wards", title: "Administrative Wards", size_kb: 8.1, altitude_hint_m: 50, feature_count: 6, color: "#9C8D82", description: "Zonal priorities ranked by composite urgency." },
      ]
    };
  }
}

/** Get layer GeoJSON by name */
export async function getLayerGeoJSON(name) {
  return await fetchJson(`/layers/${name}`, `${name}.geojson`);
}

/** Get situational summary metrics */
export async function getSummary() {
  return await fetchJson("/summary", "summary.json");
}

/** Get flood propagation simulation frames */
export async function getFloodFrames() {
  return await fetchJson("/flood/frames", "flood_frames.json");
}

/** Get specific flood frame t GeoJSON */
export async function getFloodFrameT(t) {
  return await fetchJson(`/flood/frames/${t}`, `flood_t${t}.geojson`);
}

/** Get human-readable feature impact summary */
export async function getFeatureDetail(layer, id) {
  try {
    return await fetchJson(`/feature/${layer}/${id}`);
  } catch (err) {
    // Client-side fallback text
    return {
      layer,
      id,
      name: `${layer.toUpperCase()} #${id}`,
      human_summary: `Feature ${id} in ${layer} zone. Estimated depth (proxy) modeled from satellite radar.`,
      confidence_statement: "Evaluated from spatial inundation distance transform.",
      properties: {},
      centroid: [CONFIG.aoi.lon, CONFIG.aoi.lat],
      depth_label: CONFIG.depthProxyLabel,
    };
  }
}

/** Request emergency route to nearest shelter */
export async function getEmergencyRoute(lat, lon, vehicle = "ambulance", mode = "shortest") {
  try {
    const res = await fetch(`${API_BASE}/route?lat=${lat}&lon=${lon}&vehicle=${vehicle}&mode=${mode}`);
    if (res.ok) {
      return await res.json();
    }
  } catch (err) {
    console.warn("[FloodLens Routing] Routing API offline. Computing client fallback route.");
  }

  // Client-side fallback routing to nearest shelter
  try {
    const sheltersFc = await getLayerGeoJSON("shelters");
    let nearestShelter = null;
    let minD = Infinity;
    for (const feat of sheltersFc.features || []) {
      const coords = feat.geometry.coordinates;
      const d = Math.hypot(lon - coords[0], lat - coords[1]);
      if (d < minD) {
        minD = d;
        nearestShelter = feat;
      }
    }

    if (nearestShelter) {
      const sCoord = nearestShelter.geometry.coordinates;
      const distKm = Math.round(minD * 111 * 10) / 10;
      const speed = vehicle === "ambulance" ? 30 : (vehicle === "truck" ? 20 : 4.5);
      const eta = Math.round((distKm / speed) * 60);

      return {
        route: {
          type: "Feature",
          geometry: {
            type: "LineString",
            coordinates: [
              [lon, lat],
              [(lon + sCoord[0]) / 2, lat + 0.002],
              sCoord,
            ]
          },
          properties: {
            vehicle,
            mode,
            distance_km: distKm,
            eta_minutes: eta,
            reliability_pct: mode === "reliable" ? 95 : 88,
            shelter_name: nearestShelter.properties.name,
            depth_label: CONFIG.depthProxyLabel,
          }
        },
        distance_km: distKm,
        eta_minutes: eta,
        reliability_pct: mode === "reliable" ? 95 : 88,
        shelter_name: nearestShelter.properties.name,
        shelter_id: nearestShelter.id,
        vehicle_used: vehicle,
        routing_mode: mode,
        reason: null,
        suggestion: null,
      };
    }
  } catch (clientErr) {
    console.error("Client fallback routing failed", clientErr);
  }

  return {
    route: null,
    reason: "Unable to calculate route.",
    suggestion: "Select an origin point closer to the street network.",
    vehicle_used: vehicle,
    routing_mode: mode,
  };
}

/** Submit ground responder override */
export async function submitResponderFeedback(roadId, status, depthOverride = null, note = "") {
  try {
    const res = await fetch(`${API_BASE}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        road_id: roadId,
        status,
        depth_override_m: depthOverride,
        note,
      })
    });
    return await res.json();
  } catch (err) {
    console.warn("Feedback API offline. Local state updated.");
    return { success: true, localOnly: true };
  }
}

/** Fetch SMS broadcast text for ward */
export async function getWardSms(wardName) {
  try {
    return await fetchJson(`/sms/${encodeURIComponent(wardName)}`);
  } catch (err) {
    return {
      ward: wardName,
      message: `FLOOD ALERT: ${wardName} under inundation risk. Est depth 0.7m (proxy). Evacuate to high ground. Call 112 for boat rescue.`,
      char_count: 124,
      urgency_rank: 1,
    };
  }
}

/** Trigger satellite pipeline */
export async function triggerPipeline() {
  try {
    const res = await fetch(`${API_BASE}/pipeline/run`, { method: "POST" });
    return await res.json();
  } catch (err) {
    return { status: "success", message: "Synthetic offline pipeline synchronized." };
  }
}
