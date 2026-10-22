/**
 * Emergency Evacuation Route Tool for FloodLens.
 * Allows user to click on the map and calculate a vehicle-specific evacuation route
 * to the nearest available high-ground shelter.
 */
import * as Cesium from "cesium";
import { getViewer } from "./globe.js";
import { getEmergencyRoute } from "./api.js";
import { CONFIG } from "./config.js";

let routeDataSource = null;
let currentOrigin = null;
let selectedVehicle = "ambulance";
let selectedMode = "shortest";
let isRouteToolActive = true;

export function initRouteTool(viewer) {
  if (!routeDataSource) {
    routeDataSource = new Cesium.CustomDataSource("floodlens_active_route");
    viewer.dataSources.add(routeDataSource);
  }

  // Listen for map clicks
  window.addEventListener("floodlens:map-clicked", (e) => {
    if (!isRouteToolActive) return;
    const { lon, lat } = e.detail;
    calculateAndDisplayRoute(lat, lon);
  });
}

export function setVehicle(vehicle) {
  selectedVehicle = vehicle;
  if (currentOrigin) {
    calculateAndDisplayRoute(currentOrigin.lat, currentOrigin.lon);
  }
}

export function setRoutingMode(mode) {
  selectedMode = mode;
  if (currentOrigin) {
    calculateAndDisplayRoute(currentOrigin.lat, currentOrigin.lon);
  }
}

export async function calculateAndDisplayRoute(lat, lon) {
  currentOrigin = { lat, lon };
  const viewer = getViewer();
  if (!viewer || !routeDataSource) return;

  routeDataSource.entities.removeAll();

  // Add Origin Pin
  routeDataSource.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat, 10),
    point: {
      pixelSize: 12,
      color: Cesium.Color.fromCssColorString(CONFIG.colors.accent),
      outlineColor: Cesium.Color.WHITE,
      outlineWidth: 2,
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
    },
    label: {
      text: "Evacuation Origin",
      font: "11px 'DM Sans', sans-serif",
      style: Cesium.LabelStyle.FILL_AND_OUTLINE,
      fillColor: Cesium.Color.WHITE,
      outlineColor: Cesium.Color.BLACK,
      outlineWidth: 3,
      pixelOffset: new Cesium.Cartesian2(0, -18),
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
    },
  });

  // Call API / client fallback
  const result = await getEmergencyRoute(lat, lon, selectedVehicle, selectedMode);

  const dockInfoEl = document.getElementById("routeDockInfo");

  if (!result || !result.route) {
    if (dockInfoEl) {
      dockInfoEl.innerHTML = `
        <div style="color: var(--data-road-impassable); font-size: 11px;">
          <b>No Route Found</b>: ${result?.reason || "Path impassable"}<br/>
          <i>${result?.suggestion || "Try switching vehicle to Truck or Foot."}</i>
        </div>
      `;
    }
    viewer.scene.requestRender();
    return;
  }

  const coords = result.route.geometry.coordinates;
  const positions = coords.map((c) => Cesium.Cartesian3.fromDegrees(c[0], c[1], 8));

  // Glowing animated evacuation corridor
  routeDataSource.entities.add({
    polyline: {
      positions: positions,
      width: 5,
      material: new Cesium.PolylineGlowMaterialProperty({
        glowPower: 0.3,
        color: Cesium.Color.fromCssColorString(CONFIG.colors.route),
      }),
      clampToGround: false,
    },
  });

  // Flowing dashed overlay for motion
  routeDataSource.entities.add({
    polyline: {
      positions: positions,
      width: 3,
      material: new Cesium.PolylineDashMaterialProperty({
        color: Cesium.Color.WHITE,
        dashLength: 16.0,
      }),
      clampToGround: false,
    },
  });

  // Update Route UI Dock
  if (dockInfoEl) {
    dockInfoEl.innerHTML = `
      <div style="display: flex; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 4px;">
        <span style="color: var(--color-muted);">Target Shelter:</span>
        <b style="color: var(--color-text);">${result.shelter_name || "Relief Camp"}</b>
      </div>
      <div style="display: flex; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 4px;">
        <span style="color: var(--color-muted);">Distance:</span>
        <b>${result.distance_km} km</b>
      </div>
      <div style="display: flex; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 4px;">
        <span style="color: var(--color-muted);">ETA (${selectedVehicle}):</span>
        <b style="color: var(--data-road-open);">${result.eta_minutes} mins</b>
      </div>
      <div style="display: flex; justify-content: space-between;">
        <span style="color: var(--color-muted);">Corridor Reliability:</span>
        <b style="color: var(--color-accent);">${result.reliability_pct}%</b>
      </div>
    `;
  }

  viewer.scene.requestRender();
}

export function clearRoute() {
  currentOrigin = null;
  if (routeDataSource) {
    routeDataSource.entities.removeAll();
  }
  const dockInfoEl = document.getElementById("routeDockInfo");
  if (dockInfoEl) {
    dockInfoEl.innerHTML = `<span style="color: var(--color-muted);">Click anywhere on the map to route to the nearest safe shelter.</span>`;
  }
  getViewer()?.scene.requestRender();
}
