export interface Region3D {
  region_id: number;
  name: string;
  genre_focus: string;
  centroid_3d: [number, number, number];
  exposure: number;
}

export interface QualityMetrics {
  trustworthiness_k15: number;
  continuity_k15: number;
  distortion_note: string;
}

export interface UniverseData {
  points_quantized: number[]; // Flat array: [x0, y0, z0, reg0, trk0, ...]
  scale: number;
  point_count: number;
  regions: Region3D[];
  quality_metrics: QualityMetrics;
}

export interface TrackNeighbor {
  track_id: string;
  title: string;
  artist_name: string;
  original_cosine_sim: number;
  shared_tags: string[];
  region_name: string;
}

export interface NeighborDetails {
  track_id: string;
  track_title: string;
  artist_name: string;
  position_3d: [number, number, number];
  region_id: number;
  region_name: string;
  distortion_warning: string;
  neighbors: TrackNeighbor[];
}

export interface UniversePlacement {
  id: string;
  position_3d: [number, number, number];
  nearest_catalog_id: string;
  confidence: number;
}

export type QualityTier = "high" | "mid" | "mobile";

// 24 distinct, high-contrast, visually pleasing colors for catalog regions
export const REGION_PALETTE_HEX: string[] = [
  "#f43f5e", // 0: Rose
  "#ec4899", // 1: Pink
  "#d946ef", // 2: Fuchsia
  "#a855f7", // 3: Purple
  "#8b5cf6", // 4: Violet
  "#6366f1", // 5: Indigo
  "#3b82f6", // 6: Blue
  "#0ea5e9", // 7: Sky
  "#06b6d4", // 8: Cyan
  "#14b8a6", // 9: Teal
  "#10b981", // 10: Emerald
  "#22c55e", // 11: Green
  "#84cc16", // 12: Lime
  "#eab308", // 13: Yellow
  "#d4af37", // 14: Melovia Gold
  "#f59e0b", // 15: Amber
  "#f97316", // 16: Orange
  "#ef4444", // 17: Red
  "#38bdf8", // 18: Light Blue
  "#a78bfa", // 19: Light Violet
  "#f472b6", // 20: Light Pink
  "#fbbf24", // 21: Warm Amber
  "#4ade80", // 22: Mint
  "#2dd4bf", // 23: Aqua
];

// Helper to convert hex to [r, g, b] in [0, 1]
export function hexToRgb01(hex: string): [number, number, number] {
  const clean = hex.replace("#", "");
  const num = parseInt(clean, 16);
  const r = ((num >> 16) & 255) / 255;
  const g = ((num >> 8) & 255) / 255;
  const b = (num & 255) / 255;
  return [r, g, b];
}
