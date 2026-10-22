/**
 * UI Panels, Dashboard KPI Strip, Detail Slide-out, SMS Previews, and Reports.
 */
import * as Cesium from "cesium";
import { getViewer } from "./globe.js";
import {
  getSummary,
  getFeatureDetail,
  submitResponderFeedback,
  getWardSms,
  getLayerGeoJSON,
} from "./api.js";
import { renderLayer } from "./layers.js";
import { CONFIG } from "./config.js";

let selectedFeature = null;

export async function initPanels() {
  await updateKpiStrip();
  setupFeatureSelectionListener();
  setupReportButtons();
}

/** Updates top situational KPI strip */
export async function updateKpiStrip() {
  try {
    const summary = await getSummary();
    const strip = document.getElementById("kpiStrip");
    if (!strip) return;

    strip.innerHTML = `
      <div class="kpi-card">
        <div class="kpi-label">Affected Structures</div>
        <div class="kpi-value hazard">${summary.affected_buildings}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Flooded Roads</div>
        <div class="kpi-value caution">${summary.flooded_road_km} km</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Cut-off Habitats</div>
        <div class="kpi-value hazard">${summary.cutoff_habitats}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Top Priority Ward</div>
        <div class="kpi-value" style="font-size: var(--font-size-14);">${summary.top_wards?.[0]?.ward.split("(")[0] || "Ward 4"}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Time-to-Map</div>
        <div class="kpi-value safe">${summary.time_to_map_seconds}s</div>
      </div>
    `;
  } catch (err) {
    console.warn("Could not update KPI strip:", err);
  }
}

/** Listen for feature selection from globe */
function setupFeatureSelectionListener() {
  window.addEventListener("floodlens:feature-selected", async (e) => {
    const { entity, layer, featureId, properties } = e.detail;
    selectedFeature = { entity, layer, featureId, properties };
    openDetailPanel(layer, featureId, properties, entity);
  });
}

/** Opens the right-side detail panel */
export async function openDetailPanel(layer, featureId, properties = {}, entity = null) {
  const panel = document.getElementById("detailPanel");
  if (!panel) return;

  panel.classList.add("open");

  // Show loading skeleton
  panel.innerHTML = `
    <div class="detail-header">
      <div class="detail-title">Inspecting Feature</div>
      <button class="btn-close" id="btnCloseDetail">✕</button>
    </div>
    <div style="color: var(--color-muted); font-size: 12px; margin: 20px 0;">Loading satellite SAR analytics...</div>
  `;

  document.getElementById("btnCloseDetail")?.addEventListener("click", closeDetailPanel);

  // Fetch human summary from backend / fallback
  const detail = await getFeatureDetail(layer, featureId);

  const confPct = Math.round((detail.properties?.confidence || 0.88) * 100);
  const isRoad = layer === "roads";
  const isWard = layer === "wards";
  const currentStatus = detail.properties?.status || "open";

  panel.innerHTML = `
    <div class="detail-header">
      <div>
        <div class="detail-title">${detail.name || `${layer.toUpperCase()} #${featureId}`}</div>
        <div style="font-size: 11px; color: var(--color-muted);">${layer.toUpperCase()} | ID: ${featureId}</div>
      </div>
      <button class="btn-close" id="btnCloseDetail" title="Close detail panel">✕</button>
    </div>

    <div class="detail-summary-card">
      ${detail.human_summary}
    </div>

    <div class="confidence-bar-wrap">
      <div style="display: flex; justify-content: space-between;">
        <span>Detection Confidence</span>
        <b style="color: var(--color-accent);">${confPct}%</b>
      </div>
      <div class="confidence-track">
        <div class="confidence-fill" style="width: ${confPct}%;"></div>
      </div>
      <div style="font-size: 10px; color: var(--color-muted);">${detail.confidence_statement}</div>
    </div>

    <div class="detail-prop-table">
      <div class="prop-row">
        <span class="prop-key">Layer</span>
        <span class="prop-val">${layer}</span>
      </div>
      ${
        detail.properties?.max_depth !== undefined
          ? `
        <div class="prop-row">
          <span class="prop-key">Water Depth</span>
          <span class="prop-val">${detail.properties.max_depth} m (${CONFIG.depthProxyLabel})</span>
        </div>
      `
          : ""
      }
      ${
        detail.properties?.severity !== undefined
          ? `
        <div class="prop-row">
          <span class="prop-key">Severity Level</span>
          <span class="prop-val" style="color: ${
            detail.properties.severity === "severe"
              ? "var(--data-severity-severe)"
              : detail.properties.severity === "moderate"
              ? "var(--data-severity-moderate)"
              : "var(--data-severity-low)"
          }; font-weight: 600;">${detail.properties.severity.toUpperCase()}</span>
        </div>
      `
          : ""
      }
      ${
        detail.properties?.urgency_score !== undefined
          ? `
        <div class="prop-row">
          <span class="prop-key">Ward Urgency</span>
          <span class="prop-val" style="color: var(--data-road-impassable); font-weight: 700;">${detail.properties.urgency_score} / 100</span>
        </div>
      `
          : ""
      }
      ${
        detail.properties?.capacity !== undefined
          ? `
        <div class="prop-row">
          <span class="prop-key">Capacity</span>
          <span class="prop-val">${detail.properties.occupancy} / ${detail.properties.capacity}</span>
        </div>
      `
          : ""
      }
    </div>

    <div class="detail-actions">
      <button class="btn-primary" id="btnFlyToFeature">Fly to Feature</button>
      
      ${
        isRoad
          ? `
        <button class="btn-secondary" id="btnToggleRoadStatus">
          ${currentStatus === "impassable" ? "Mark Road Open" : "Mark Road Impassable"}
        </button>
      `
          : ""
      }

      ${
        isWard
          ? `
        <button class="btn-secondary" id="btnPreviewWardSms">
          Preview Ward SMS Alert
        </button>
      `
          : ""
      }
    </div>
  `;

  // Attach handlers
  document.getElementById("btnCloseDetail")?.addEventListener("click", closeDetailPanel);

  document.getElementById("btnFlyToFeature")?.addEventListener("click", () => {
    flyToFeatureCentroid(detail.centroid);
  });

  if (isRoad) {
    document.getElementById("btnToggleRoadStatus")?.addEventListener("click", async () => {
      const nextStatus = currentStatus === "impassable" ? "open" : "impassable";
      await submitResponderFeedback(featureId, nextStatus);
      // Re-fetch roads GeoJSON and re-render
      const roadsData = await getLayerGeoJSON("roads");
      await renderLayer("roads", roadsData);
      openDetailPanel(layer, featureId, { ...properties, status: nextStatus }, entity);
    });
  }

  if (isWard) {
    document.getElementById("btnPreviewWardSms")?.addEventListener("click", async () => {
      openSmsPreviewModal(detail.name || `Ward ${featureId}`);
    });
  }
}

export function closeDetailPanel() {
  const panel = document.getElementById("detailPanel");
  if (panel) panel.classList.remove("open");
}

function flyToFeatureCentroid(centroid) {
  const viewer = getViewer();
  if (!viewer || !centroid) return;

  viewer.camera.flyTo({
    destination: Cesium.Cartesian3.fromDegrees(centroid[0], centroid[1], 1500),
    orientation: {
      heading: Cesium.Math.toRadians(0),
      pitch: Cesium.Math.toRadians(-45),
      roll: 0.0,
    },
    duration: 1.2,
  });
}

/** Shows SMS alert in phone-bubble UI */
export async function openSmsPreviewModal(wardName) {
  const sms = await getWardSms(wardName);

  let backdrop = document.getElementById("smsModalBackdrop");
  if (!backdrop) {
    backdrop = document.createElement("div");
    backdrop.id = "smsModalBackdrop";
    backdrop.className = "sms-modal-backdrop";
    document.body.appendChild(backdrop);
  }

  backdrop.innerHTML = `
    <div class="sms-phone-card">
      <div class="phone-speaker"></div>
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <span style="font-size: 11px; color: var(--color-muted);">Emergency Broadcast System</span>
        <button class="btn-close" id="btnCloseSmsModal">✕</button>
      </div>

      <div class="sms-bubble">
        ${sms.message}
      </div>

      <div class="sms-char-counter">
        ${sms.char_count} / 160 characters (GSM standard)
      </div>

      <div style="font-size: 10px; color: var(--color-muted); text-align: center;">
        Direct cellular cell-broadcast without internet dependency.
      </div>

      <button class="btn-primary" id="btnDispatchSmsSimulation">Simulate Cell Broadcast</button>
    </div>
  `;

  backdrop.style.display = "flex";

  document.getElementById("btnCloseSmsModal")?.addEventListener("click", () => {
    backdrop.style.display = "none";
  });

  document.getElementById("btnDispatchSmsSimulation")?.addEventListener("click", () => {
    alert(`SMS broadcast simulated to all mobile towers in ${wardName}!`);
    backdrop.style.display = "none";
  });
}

/** Setup PDF and GeoJSON report download buttons */
function setupReportButtons() {
  document.getElementById("btnDownloadPdf")?.addEventListener("click", () => {
    window.open(`${CONFIG.apiUrl}/report.pdf`, "_blank");
  });

  document.getElementById("btnDownloadGeoJson")?.addEventListener("click", () => {
    window.open(`${CONFIG.apiUrl}/report.geojson`, "_blank");
  });
}
