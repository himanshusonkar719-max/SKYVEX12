/**
 * Layer Management for FloodLens.
 * Loads and renders GeoJSON layers with semantic styling and manages visibility/opacity.
 */
import * as Cesium from "cesium";
import { getViewer } from "./globe.js";
import { getLayerGeoJSON } from "./api.js";
import { CONFIG } from "./config.js";

// Active Cesium CustomDataSource per layer
const layerDataSources = {};
const layerVisibility = {
  flood: true,
  roads: true,
  buildings: true,
  shelters: true,
  wards: true,
};
const layerOpacity = {
  flood: 0.8,
  roads: 0.9,
  buildings: 0.85,
  shelters: 1.0,
  wards: 0.4,
};

export function getLayerDataSource(layerName) {
  return layerDataSources[layerName];
}

export function getAllDataSources() {
  return layerDataSources;
}

/**
 * Initializes and loads all geospatial layers into the viewer.
 */
export async function loadAllLayers() {
  const viewer = getViewer();
  if (!viewer) return;

  const layerNames = ["wards", "flood", "roads", "buildings", "shelters"];

  for (const name of layerNames) {
    try {
      const geojson = await getLayerGeoJSON(name);
      await renderLayer(name, geojson);
    } catch (err) {
      console.error(`Failed to load layer '${name}':`, err);
    }
  }

  viewer.scene.requestRender();
}

/**
 * Renders a specific GeoJSON dataset into a dedicated Cesium CustomDataSource.
 */
export async function renderLayer(name, geojson) {
  const viewer = getViewer();
  if (!viewer) return;

  // Remove existing if present
  if (layerDataSources[name]) {
    viewer.dataSources.remove(layerDataSources[name]);
  }

  const ds = new Cesium.CustomDataSource(`floodlens_${name}`);
  layerDataSources[name] = ds;
  await viewer.dataSources.add(ds);

  const opacity = layerOpacity[name] || 0.8;
  const features = geojson.features || [];

  for (const feat of features) {
    const props = feat.properties || {};
    const geom = feat.geometry || {};
    const fId = feat.id || props.id || Math.random().toString();

    if (name === "flood") {
      renderFloodPolygon(ds, feat, opacity, fId);
    } else if (name === "roads") {
      renderRoadLine(ds, feat, opacity, fId);
    } else if (name === "buildings") {
      renderBuildingPolygon(ds, feat, opacity, fId);
    } else if (name === "shelters") {
      renderShelterPoint(ds, feat, opacity, fId);
    } else if (name === "wards") {
      renderWardPolygon(ds, feat, opacity, fId);
    }
  }

  ds.show = layerVisibility[name] !== false;
  viewer.scene.requestRender();
}

/** Flood polygon styling */
function renderFloodPolygon(ds, feat, opacity, fId) {
  const coords = feat.geometry.coordinates[0];
  const depth = feat.properties.depth || 1.0;
  
  // Interpolate between shallow #4FA3D1 and deep #1E5F8C
  const colorHex = depth > 1.2 ? CONFIG.colors.floodDeep : CONFIG.colors.floodShallow;
  const color = Cesium.Color.fromCssColorString(colorHex).withAlpha(opacity);

  const positions = coords.map((c) => Cesium.Cartesian3.fromDegrees(c[0], c[1], 0));

  ds.entities.add({
    id: `flood_${fId}`,
    layerName: "flood",
    featureId: fId,
    properties: feat.properties,
    polygon: {
      hierarchy: new Cesium.PolygonHierarchy(positions),
      material: color,
      outline: true,
      outlineColor: Cesium.Color.fromCssColorString("#4FA3D1").withAlpha(0.9),
      outlineWidth: 2,
      height: 0,
      extrudedHeight: Math.max(1, depth * 4), // visual extrusion
    },
  });
}

/** Roads LineString styling */
function renderRoadLine(ds, feat, opacity, fId) {
  const coords = feat.geometry.coordinates;
  const status = feat.properties.status || "open";
  const colorHex = status === "impassable" ? CONFIG.colors.roadImpassable : CONFIG.colors.roadOpen;
  const color = Cesium.Color.fromCssColorString(colorHex).withAlpha(opacity);

  const positions = coords.map((c) => Cesium.Cartesian3.fromDegrees(c[0], c[1], 2));

  ds.entities.add({
    id: `road_${fId}`,
    layerName: "roads",
    featureId: fId,
    properties: feat.properties,
    polyline: {
      positions: positions,
      width: status === "impassable" ? 4 : 3,
      material: color,
      clampToGround: true,
    },
  });
}

/** Buildings Polygon styling */
function renderBuildingPolygon(ds, feat, opacity, fId) {
  const coords = feat.geometry.coordinates[0];
  const sev = feat.properties.severity || "low";
  let colorHex = CONFIG.colors.severityLow;
  if (sev === "severe") colorHex = CONFIG.colors.severitySevere;
  else if (sev === "moderate") colorHex = CONFIG.colors.severityModerate;

  const color = Cesium.Color.fromCssColorString(colorHex).withAlpha(opacity);
  const positions = coords.map((c) => Cesium.Cartesian3.fromDegrees(c[0], c[1], 0));

  // Critical facilities stand taller
  const heightM = feat.properties.is_critical ? 18 : 8;

  ds.entities.add({
    id: `bld_${fId}`,
    layerName: "buildings",
    featureId: fId,
    properties: feat.properties,
    polygon: {
      hierarchy: new Cesium.PolygonHierarchy(positions),
      material: color,
      extrudedHeight: heightM,
      outline: true,
      outlineColor: Cesium.Color.BLACK.withAlpha(0.4),
      outlineWidth: 1,
    },
  });
}

/** Shelters Point Marker styling */
function renderShelterPoint(ds, feat, opacity, fId) {
  const [lon, lat] = feat.geometry.coordinates;
  const name = feat.properties.name || "Shelter";
  const freeCap = feat.properties.free_capacity || 0;

  ds.entities.add({
    id: `shelter_${fId}`,
    layerName: "shelters",
    featureId: fId,
    properties: feat.properties,
    position: Cesium.Cartesian3.fromDegrees(lon, lat, 15),
    point: {
      pixelSize: 14,
      color: Cesium.Color.fromCssColorString(CONFIG.colors.shelter).withAlpha(opacity),
      outlineColor: Cesium.Color.fromCssColorString("#1A1222"),
      outlineWidth: 3,
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
    },
    label: {
      text: `${name} (${freeCap} open)`,
      font: "11px 'DM Sans', sans-serif",
      style: Cesium.LabelStyle.FILL_AND_OUTLINE,
      fillColor: Cesium.Color.fromCssColorString("#F2EBE3"),
      outlineColor: Cesium.Color.fromCssColorString("#1A1222"),
      outlineWidth: 3,
      pixelOffset: new Cesium.Cartesian2(0, -20),
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
    },
  });
}

/** Wards Polygon styling */
function renderWardPolygon(ds, feat, opacity, fId) {
  const coords = feat.geometry.coordinates[0];
  const rank = feat.properties.rank || 1;
  const positions = coords.map((c) => Cesium.Cartesian3.fromDegrees(c[0], c[1], 0));

  // Subtle boundary
  ds.entities.add({
    id: `ward_${fId}`,
    layerName: "wards",
    featureId: fId,
    properties: feat.properties,
    polygon: {
      hierarchy: new Cesium.PolygonHierarchy(positions),
      material: Cesium.Color.fromCssColorString("#9C8D82").withAlpha(0.12),
      outline: true,
      outlineColor: Cesium.Color.fromCssColorString("#B9A38B").withAlpha(0.6),
      outlineWidth: 2,
    },
  });
}

/** Toggle layer on/off */
export function setLayerVisibility(layerName, visible) {
  layerVisibility[layerName] = visible;
  const ds = layerDataSources[layerName];
  if (ds) {
    ds.show = visible;
    getViewer()?.scene.requestRender();
  }
}

/** Update layer opacity */
export function setLayerOpacity(layerName, opacity) {
  layerOpacity[layerName] = opacity;
  const ds = layerDataSources[layerName];
  if (!ds) return;

  for (const entity of ds.entities.values) {
    if (entity.polygon && entity.polygon.material) {
      const curr = entity.polygon.material.getValue();
      if (curr && curr.color) {
        entity.polygon.material = curr.color.withAlpha(opacity);
      }
    } else if (entity.polyline && entity.polyline.material) {
      const curr = entity.polyline.material.getValue();
      if (curr && curr.color) {
        entity.polyline.material = curr.color.withAlpha(opacity);
      }
    }
  }
  getViewer()?.scene.requestRender();
}
