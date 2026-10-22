/**
 * Cesium 3D Globe Controller for FloodLens.
 * Manages viewer initialization, terrain/imagery fallback without token,
 * violet atmospheric tinting, camera presets (1/2/3/0), and space flight intro.
 */
import * as Cesium from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";
import { CONFIG } from "./config.js";

let viewer = null;
let currentHighlightedEntity = null;
let originalColor = null;

export function getViewer() {
  return viewer;
}

/**
 * Initializes the Cesium 3D viewer.
 * Guaranteed to run offline or without a Cesium Ion token via OpenStreetMap & Ellipsoid.
 */
export async function initGlobe(containerId, onIntroComplete = null) {
  // Configure Cesium Ion token if provided
  if (CONFIG.cesiumToken) {
    Cesium.Ion.defaultAccessToken = CONFIG.cesiumToken;
  }

  // Base imagery provider: OpenStreetMap standard tiles (guaranteed free, zero token)
  const baseImageryProvider = new Cesium.UrlTemplateImageryProvider({
    url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    subdomains: ["a", "b", "c"],
    maximumLevel: 19,
    credit: "OpenStreetMap contributors",
  });

  // WGS84 Ellipsoid terrain (guaranteed never to error out on offline/no token)
  const terrainProvider = new Cesium.EllipsoidTerrainProvider();

  viewer = new Cesium.Viewer(containerId, {
    baseLayer: new Cesium.ImageryLayer(baseImageryProvider),
    terrainProvider: terrainProvider,
    animation: false,
    timeline: false,
    baseLayerPicker: false,
    fullscreenButton: false,
    geocoder: false,
    homeButton: false,
    infoBox: false,
    sceneModePicker: false,
    selectionIndicator: false,
    navigationHelpButton: false,
    scene3DOnly: true,
    requestRenderMode: true,
    maximumRenderTimeChange: Infinity,
  });

  const scene = viewer.scene;

  // Scene background color: #1A1222
  scene.backgroundColor = Cesium.Color.fromCssColorString(CONFIG.colors.bg);

  // Atmosphere tinted violet
  if (scene.skyAtmosphere) {
    scene.skyAtmosphere.hueShift = -0.15; // Shift towards violet/indigo
    scene.skyAtmosphere.saturationShift = 0.2;
    scene.skyAtmosphere.brightnessShift = -0.1;
  }

  // Lighting & globe settings
  scene.globe.enableLighting = false;
  scene.globe.baseColor = Cesium.Color.fromCssColorString("#1A1222");
  scene.globe.depthTestAgainstTerrain = true;

  // Setup click & hover handlers
  setupInteractions(viewer);

  // Orchestrated Intro Flight
  const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  if (prefersReduced) {
    // Snap straight to AOI
    flyToAOI(false);
    if (onIntroComplete) onIntroComplete();
  } else {
    // Cinematic intro: camera starts high in space, spins slightly, then dives to AOI
    viewer.camera.setView({
      destination: Cesium.Cartesian3.fromDegrees(85.1376, 25.5941, 12000000),
      orientation: {
        heading: Cesium.Math.toRadians(0),
        pitch: Cesium.Math.toRadians(-90),
        roll: 0.0,
      },
    });
    scene.requestRender();

    // Begin flight after a brief beat
    setTimeout(() => {
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(
          CONFIG.aoi.lon,
          CONFIG.aoi.lat - 0.05,
          CONFIG.aoi.height
        ),
        orientation: {
          heading: Cesium.Math.toRadians(12),
          pitch: Cesium.Math.toRadians(-48),
          roll: 0.0,
        },
        duration: 2.4,
        easingFunction: Cesium.EasingFunction.QUADRATIC_IN_OUT,
        complete: () => {
          scene.requestRender();
          if (onIntroComplete) onIntroComplete();
        },
      });
    }, 200);
  }

  // Setup camera keyboard shortcuts (1/2/3/0)
  setupKeyboardShortcuts();

  return viewer;
}

/** Flies camera to AOI center */
export function flyToAOI(animated = true) {
  if (!viewer) return;
  const dest = Cesium.Cartesian3.fromDegrees(
    CONFIG.aoi.lon,
    CONFIG.aoi.lat - 0.04,
    CONFIG.aoi.height
  );
  if (animated) {
    viewer.camera.flyTo({
      destination: dest,
      orientation: {
        heading: Cesium.Math.toRadians(10),
        pitch: Cesium.Math.toRadians(-48),
        roll: 0.0,
      },
      duration: 1.5,
    });
  } else {
    viewer.camera.setView({
      destination: dest,
      orientation: {
        heading: Cesium.Math.toRadians(10),
        pitch: Cesium.Math.toRadians(-48),
        roll: 0.0,
      },
    });
    viewer.scene.requestRender();
  }
}

/** Apply a named camera preset */
export function applyCameraPreset(presetKey) {
  if (!viewer) return;
  const preset = CONFIG.cameraPresets[presetKey];
  if (!preset) return;

  const dest = Cesium.Cartesian3.fromDegrees(
    preset.destination.lon,
    preset.destination.lat,
    preset.destination.height
  );

  viewer.camera.flyTo({
    destination: dest,
    orientation: {
      heading: Cesium.Math.toRadians(preset.orientation.heading),
      pitch: Cesium.Math.toRadians(preset.orientation.pitch),
      roll: Cesium.Math.toRadians(preset.orientation.roll),
    },
    duration: 1.2,
    easingFunction: Cesium.EasingFunction.QUADRATIC_OUT,
    complete: () => viewer.scene.requestRender(),
  });
}

/** Setup hotkeys 1, 2, 3, 0 */
function setupKeyboardShortcuts() {
  window.addEventListener("keydown", (e) => {
    // Ignore if input/textarea is focused
    if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) return;

    if (e.key === "1") {
      applyCameraPreset("top");
    } else if (e.key === "2") {
      applyCameraPreset("tilt");
    } else if (e.key === "3") {
      applyCameraPreset("street");
    } else if (e.key === "0") {
      applyCameraPreset("reset");
    }
  });
}

/** Click and Hover interactions */
function setupInteractions(viewer) {
  const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);

  // Left Click: Feature selection or routing destination
  handler.setInputAction((click) => {
    const pickedObject = viewer.scene.pick(click.position);
    if (Cesium.defined(pickedObject) && pickedObject.id) {
      const entity = pickedObject.id;
      // Dispatch custom event for detail panel
      window.dispatchEvent(
        new CustomEvent("floodlens:feature-selected", {
          detail: {
            entity,
            layer: entity.layerName || "unknown",
            featureId: entity.featureId || entity.id,
            properties: entity.properties ? entity.properties.getValue() : {},
          },
        })
      );
    } else {
      // Clicked on ground or empty space: route origin candidate
      const ray = viewer.camera.getPickRay(click.position);
      const cartesian = viewer.scene.globe.pick(ray, viewer.scene);
      if (cartesian) {
        const cartographic = Cesium.Cartographic.fromCartesian(cartesian);
        const lon = Cesium.Math.toDegrees(cartographic.longitude);
        const lat = Cesium.Math.toDegrees(cartographic.latitude);
        window.dispatchEvent(
          new CustomEvent("floodlens:map-clicked", {
            detail: { lon, lat },
          })
        );
      }
    }
  }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

  // Mouse Move: Hover highlight
  handler.setInputAction((movement) => {
    const pickedObject = viewer.scene.pick(movement.endPosition);
    if (Cesium.defined(pickedObject) && pickedObject.id && pickedObject.id.polygon) {
      if (currentHighlightedEntity !== pickedObject.id) {
        // Reset previous
        if (currentHighlightedEntity && originalColor && currentHighlightedEntity.polygon) {
          currentHighlightedEntity.polygon.material = originalColor;
        }
        currentHighlightedEntity = pickedObject.id;
        originalColor = currentHighlightedEntity.polygon.material;
        currentHighlightedEntity.polygon.material = Cesium.Color.fromCssColorString("#FFFFFF").withAlpha(0.85);
        viewer.scene.requestRender();
      }
    } else {
      if (currentHighlightedEntity && originalColor && currentHighlightedEntity.polygon) {
        currentHighlightedEntity.polygon.material = originalColor;
        currentHighlightedEntity = null;
        originalColor = null;
        viewer.scene.requestRender();
      }
    }
  }, Cesium.ScreenSpaceEventType.MOUSE_MOVE);
}
