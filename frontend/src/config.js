/**
 * Frontend Configuration for FloodLens.
 * Coordinates, altitude hints, color mappings, and API endpoints.
 */

export const CONFIG = {
  // Area of Interest (Patna Ganga Flood Basin, Bihar)
  aoi: {
    lat: 25.5941,
    lon: 85.1376,
    height: 18000,
  },

  // Camera Presets (keys 1/2/3/0)
  cameraPresets: {
    top: {
      destination: { lon: 85.1376, lat: 25.5941, height: 16000 },
      orientation: { heading: 0, pitch: -90, roll: 0 },
      label: "Top View",
      key: "1",
    },
    tilt: {
      destination: { lon: 85.1200, lat: 25.5500, height: 7500 },
      orientation: { heading: 25, pitch: -38, roll: 0 },
      label: "3D Oblique",
      key: "2",
    },
    street: {
      destination: { lon: 85.1380, lat: 25.6050, height: 1400 },
      orientation: { heading: 15, pitch: -18, roll: 0 },
      label: "Street View",
      key: "3",
    },
    reset: {
      destination: { lon: 85.1376, lat: 25.5941, height: 24000 },
      orientation: { heading: 0, pitch: -65, roll: 0 },
      label: "Reset",
      key: "0",
    },
  },

  // 3D Exploded Layer Altitudes in meters
  altitudeHints: {
    flood: 0,
    roads: 150,
    buildings: 300,
    confidence: 450,
    shelters: 600,
    wards: 50,
  },

  // Palette & Data Colors
  colors: {
    floodShallow: "#4FA3D1",
    floodDeep: "#1E5F8C",
    roadOpen: "#5FB878",
    roadImpassable: "#E5534B",
    severityLow: "#7FB77E",
    severityModerate: "#E8A03C",
    severitySevere: "#D9453B",
    route: "#D4C0A6",
    shelter: "#D4C0A6",
    accent: "#B9A38B",
    bg: "#1A1222",
  },

  depthProxyLabel: "estimated depth (proxy)",
  depthProxyNote: "Depths are estimated proxies calculated from flood boundary distance and terrain contours.",

  apiUrl: import.meta.env.VITE_API_URL || "/api",
  cesiumToken: import.meta.env.VITE_CESIUM_TOKEN || "",
};
