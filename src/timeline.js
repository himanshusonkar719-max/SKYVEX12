/**
 * Flood Simulation Timeline Scrubber for FloodLens.
 * Coordinates play/pause playback across 6 timesteps (T+0h to T+5h)
 * and animates terrain flood extrusion rising with depth readouts.
 */
import { getFloodFrames, getFloodFrameT } from "./api.js";
import { renderLayer } from "./layers.js";
import { CONFIG } from "./config.js";

let currentStep = 5; // Start at latest inundation
let isPlaying = false;
let playInterval = null;
let framesMeta = [];

export function getCurrentTimestep() {
  return currentStep;
}

export async function initTimeline(containerElement) {
  try {
    const data = await getFloodFrames();
    framesMeta = data.frames || [];
  } catch (err) {
    framesMeta = [
      { t: 0, time_label: "T+0h", max_depth_m: 1.2 },
      { t: 1, time_label: "T+1h", max_depth_m: 1.5 },
      { t: 2, time_label: "T+2h", max_depth_m: 1.8 },
      { t: 3, time_label: "T+3h", max_depth_m: 2.1 },
      { t: 4, time_label: "T+4h", max_depth_m: 2.4 },
      { t: 5, time_label: "T+5h", max_depth_m: 2.8 },
    ];
  }

  renderTimelineUI(containerElement);
}

function renderTimelineUI(container) {
  if (!container) return;

  container.innerHTML = `
    <button class="btn-play" id="btnPlayTimeline" title="Play flood simulation">▶</button>
    
    <div class="timeline-steps">
      <div class="timeline-track"></div>
      <div class="timeline-progress" id="timelineProgress" style="width: 100%;"></div>
      
      ${framesMeta
        .map(
          (frame) => `
        <div class="step-node ${frame.t === currentStep ? "active" : ""}" data-t="${frame.t}">
          <span class="step-label">${frame.time_label}</span>
        </div>
      `
        )
        .join("")}
    </div>

    <div class="depth-readout">
      <div class="depth-val" id="depthReadoutVal">Depth: 2.80 m</div>
      <div class="depth-proxy-tag">estimated depth (proxy)</div>
    </div>
  `;

  // Attach event listeners
  const playBtn = container.querySelector("#btnPlayTimeline");
  playBtn.addEventListener("click", () => togglePlay());

  const nodes = container.querySelectorAll(".step-node");
  nodes.forEach((node) => {
    node.addEventListener("click", (e) => {
      const t = parseInt(node.getAttribute("data-t"), 10);
      setTimelineStep(t);
      if (isPlaying) togglePlay(); // pause on manual selection
    });
  });

  updateTimelineDisplay();
}

export function togglePlay() {
  isPlaying = !isPlaying;
  const playBtn = document.getElementById("btnPlayTimeline");
  if (playBtn) {
    playBtn.textContent = isPlaying ? "⏸" : "▶";
    playBtn.title = isPlaying ? "Pause flood simulation" : "Play flood simulation";
  }

  if (isPlaying) {
    playInterval = setInterval(() => {
      let nextStep = currentStep + 1;
      if (nextStep >= framesMeta.length) nextStep = 0;
      setTimelineStep(nextStep);
    }, 1600);
  } else {
    clearInterval(playInterval);
    playInterval = null;
  }
}

export async function setTimelineStep(t) {
  currentStep = t;
  updateTimelineDisplay();

  try {
    const geojson = await getFloodFrameT(t);
    await renderLayer("flood", geojson);
  } catch (err) {
    console.error(`Failed to load flood frame T+${t}:`, err);
  }
}

function updateTimelineDisplay() {
  const container = document.querySelector(".timeline-bar");
  if (!container) return;

  const nodes = container.querySelectorAll(".step-node");
  nodes.forEach((node) => {
    const t = parseInt(node.getAttribute("data-t"), 10);
    if (t === currentStep) {
      node.classList.add("active");
    } else {
      node.classList.remove("active");
    }
  });

  // Update progress bar width
  const progress = container.querySelector("#timelineProgress");
  if (progress && framesMeta.length > 1) {
    const pct = (currentStep / (framesMeta.length - 1)) * 100;
    progress.style.width = `${pct}%`;
  }

  // Update depth readout
  const depthEl = container.querySelector("#depthReadoutVal");
  if (depthEl && framesMeta[currentStep]) {
    const maxDepth = framesMeta[currentStep].max_depth_m || 2.5;
    depthEl.textContent = `Peak: ${maxDepth.toFixed(2)} m`;
  }
}
