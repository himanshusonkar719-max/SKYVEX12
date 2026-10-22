/**
 * Signature Feature: 3D Exploded Layers for FloodLens.
 * Smoothly lifts geospatial layers to their altitude_hint_m with ease-in-out interpolation,
 * draws thin vertical connector anchor lines to the terrain, and provides floating altitude tags.
 */
import * as Cesium from "cesium";
import { getViewer } from "./globe.js";
import { getAllDataSources } from "./layers.js";
import { CONFIG } from "./config.js";

let isExploded = false;
let spreadMultiplier = 1.0;
let animationFrameId = null;
let connectorDataSource = null;

export function getExplodedState() {
  return { isExploded, spreadMultiplier };
}

/**
 * Initializes the connector line data source.
 */
function ensureConnectorSource(viewer) {
  if (!connectorDataSource) {
    connectorDataSource = new Cesium.CustomDataSource("floodlens_exploded_connectors");
    viewer.dataSources.add(connectorDataSource);
  }
}

/**
 * Toggles exploded 3D layers state with smooth 600ms transition.
 */
export function toggleExplodedLayers(targetState = null) {
  const viewer = getViewer();
  if (!viewer) return;

  ensureConnectorSource(viewer);

  const nextState = targetState !== null ? targetState : !isExploded;
  if (nextState === isExploded) return;
  isExploded = nextState;

  animateLayerAltitudes(isExploded, spreadMultiplier);
  return isExploded;
}

/**
 * Adjusts the exploded spread multiplier (0.5x to 2.5x).
 */
export function setSpreadMultiplier(val) {
  spreadMultiplier = parseFloat(val) || 1.0;
  if (isExploded) {
    animateLayerAltitudes(true, spreadMultiplier, 200);
  }
}

/**
 * Animates layers vertically to/from their target altitude hints.
 */
function animateLayerAltitudes(explode, spread, durationMs = 600) {
  const viewer = getViewer();
  if (!viewer) return;

  if (animationFrameId) {
    cancelAnimationFrame(animationFrameId);
  }

  const dataSources = getAllDataSources();
  const startTime = performance.now();

  // Clear existing connectors
  if (connectorDataSource) {
    connectorDataSource.entities.removeAll();
  }

  // Pre-calculate target altitudes for each layer
  const targets = {};
  for (const [name, hint] of Object.entries(CONFIG.altitudeHints)) {
    targets[name] = explode ? Math.round(hint * spread) : 0;
  }

  function step(now) {
    const elapsed = now - startTime;
    const progress = Math.min(1.0, elapsed / durationMs);

    // Ease-in-out quadratic curve
    const t = progress < 0.5 ? 2 * progress * progress : 1 - Math.pow(-2 * progress + 2, 2) / 2;

    for (const [layerName, ds] of Object.entries(dataSources)) {
      const targetAlt = targets[layerName] || 0;
      const currentAlt = explode ? targetAlt * t : targetAlt * (1.0 - t);

      for (const entity of ds.entities.values) {
        if (entity.polygon) {
          entity.polygon.height = currentAlt;
          if (entity.polygon.extrudedHeight) {
            const baseExtrude = entity.layerName === "flood" ? 6 : (entity.properties?.is_critical?.getValue() ? 18 : 8);
            entity.polygon.extrudedHeight = currentAlt + baseExtrude;
          }
        } else if (entity.polyline) {
          // Adjust coordinates elevation
          // Polyline height is controlled by recreating or offsetting positions
          // For Cesium polyline, we toggle clampToGround vs elevated Cartesian3
          if (currentAlt > 10) {
            entity.polyline.clampToGround = false;
          } else {
            entity.polyline.clampToGround = true;
          }
        } else if (entity.position && entity.point) {
          // Point entity (Shelters)
          const basePos = entity.properties?.getValue()?.center || [CONFIG.aoi.lon, CONFIG.aoi.lat];
          // Update height
          const carto = Cesium.Cartographic.fromCartesian(entity.position.getValue(Cesium.JulianDate.now()));
          if (carto) {
            carto.height = currentAlt + 15;
            entity.position = Cesium.Cartesian3.fromRadians(carto.longitude, carto.latitude, carto.height);
          }
        }
      }
    }

    viewer.scene.requestRender();

    if (progress < 1.0) {
      animationFrameId = requestAnimationFrame(step);
    } else {
      // Completed animation: add thin vertical connector lines and floating labels if exploded
      if (explode) {
        buildExplodedConnectorsAndLabels(viewer, targets);
      }
    }
  }

  animationFrameId = requestAnimationFrame(step);
}

/**
 * Builds thin vertical guide lines to ground and floating layer labels in exploded view.
 */
function buildExplodedConnectorsAndLabels(viewer, targets) {
  if (!connectorDataSource) return;
  connectorDataSource.entities.removeAll();

  // Representative anchor positions in AOI corners
  const anchorPoints = [
    { lon: 85.09, lat: 25.57 },
    { lon: 85.19, lat: 25.57 },
    { lon: 85.19, lat: 25.63 },
    { lon: 85.09, lat: 25.63 },
  ];

  // Draw thin vertical lines from ground to highest layer (shelters)
  for (const pt of anchorPoints) {
    const groundPos = Cesium.Cartesian3.fromDegrees(pt.lon, pt.lat, 0);
    const topPos = Cesium.Cartesian3.fromDegrees(pt.lon, pt.lat, (targets["shelters"] || 600) + 50);

    connectorDataSource.entities.add({
      polyline: {
        positions: [groundPos, topPos],
        width: 1,
        material: new Cesium.PolylineDashMaterialProperty({
          color: Cesium.Color.fromCssColorString(CONFIG.colors.accent).withAlpha(0.4),
          dashLength: 8.0,
        }),
      },
    });
  }

  // Floating Layer Altitude Labels on the right side
  const labelLon = 85.195;
  const labelLat = 25.60;

  const displayLayers = [
    { name: "Shelters (600m)", key: "shelters", color: CONFIG.colors.shelter },
    { name: "Buildings (300m)", key: "buildings", color: CONFIG.colors.severityModerate },
    { name: "Road Grid (150m)", key: "roads", color: CONFIG.colors.roadOpen },
    { name: "Ground Inundation (0m)", key: "flood", color: CONFIG.colors.floodShallow },
  ];

  for (const item of displayLayers) {
    const alt = targets[item.key] || 0;
    const pos = Cesium.Cartesian3.fromDegrees(labelLon, labelLat, alt + 10);

    connectorDataSource.entities.add({
      position: pos,
      label: {
        text: item.name,
        font: "12px 'DM Sans', sans-serif",
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        fillColor: Cesium.Color.fromCssColorString("#F2EBE3"),
        outlineColor: Cesium.Color.fromCssColorString(CONFIG.colors.bg),
        outlineWidth: 3,
        pixelOffset: new Cesium.Cartesian2(40, 0),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
      point: {
        pixelSize: 6,
        color: Cesium.Color.fromCssColorString(item.color),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    });
  }

  viewer.scene.requestRender();
}
