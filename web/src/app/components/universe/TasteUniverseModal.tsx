"use client";

import React, { useState, useEffect, useMemo, useRef } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  X,
  Compass,
  Layers,
  Sparkles,
  RefreshCw,
  Monitor,
  Smartphone,
  Gauge,
  Info,
  Maximize2,
  Minimize2,
  ChevronDown,
  Cloud,
  Tag,
  Share2,
  Orbit,
} from "lucide-react";
import { useDiscoveryStore } from "../../store";
import { UniverseData, QualityTier, UniversePlacement, REGION_PALETTE_HEX } from "./types";
import { UniverseCanvas3D } from "./UniverseCanvas3D";
import { UniverseFallback2D } from "./UniverseFallback2D";
import { UniverseSidePanel } from "./UniverseSidePanel";
import { UniverseErrorBoundary } from "./UniverseErrorBoundary";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function checkWebGLSupport(): boolean {
  if (typeof window === "undefined") return false;
  try {
    const canvas = document.createElement("canvas");
    return Boolean(
      window.WebGLRenderingContext &&
        (canvas.getContext("webgl") || canvas.getContext("experimental-webgl"))
    );
  } catch {
    return false;
  }
}

export default function TasteUniverseModal() {
  const {
    isUniverseModalOpen,
    setUniverseModalOpen,
    universeFocusedRegionId,
    setUniverseFocusedRegionId,
    universeFocusedTrackId,
    setUniverseFocusedTrackId,
    exploringRegion,
    recommendations,
  } = useDiscoveryStore();

  const [hasWebGL, setHasWebGL] = useState(true);
  const [renderMode, setRenderMode] = useState<"3d" | "2d">("3d");
  const [tier, setTier] = useState<QualityTier>("high");
  const [fps, setFps] = useState<number>(60);
  const [isRegionDropdownOpen, setIsRegionDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement | null>(null);

  // 3D Visual Layer Toggles
  const [showNebulae, setShowNebulae] = useState(true);
  const [showLabels, setShowLabels] = useState(true);
  const [showConstellations, setShowConstellations] = useState(true);
  const [autoRotate, setAutoRotate] = useState(true);

  // Detect WebGL capability on mount
  useEffect(() => {
    const supported = checkWebGLSupport();
    setHasWebGL(supported);
    if (!supported) {
      setRenderMode("2d");
    }
  }, []);

  // Keyboard accessibility: Escape to close
  useEffect(() => {
    if (!isUniverseModalOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (universeFocusedTrackId) {
          setUniverseFocusedTrackId(null);
        } else {
          setUniverseModalOpen(false);
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isUniverseModalOpen, universeFocusedTrackId, setUniverseFocusedTrackId, setUniverseModalOpen]);

  // Fetch Universe catalog layout data
  const { data: universeData, isLoading, error } = useQuery<UniverseData>({
    queryKey: ["universeData"],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/universe`);
      if (!res.ok) {
        let msg = "Failed to load 3D universe data";
        try {
          const errData = await res.json();
          if (errData?.error?.message) {
            msg = errData.error.message;
          }
        } catch {
          // ignore parsing error
        }
        throw new Error(msg);
      }
      const raw = await res.json();
      return {
        ...raw,
        points_quantized: raw.points_quantized || raw.points || [],
        quality_metrics: raw.quality_metrics || raw.metrics || {
          trustworthiness_k15: 0.98,
          continuity_k15: 0.98,
          distortion_note: "3D distances are approximate projections.",
        },
        regions: (raw.regions || []).map((r: any) => ({
          ...r,
          region_id: r.region_id !== undefined ? r.region_id : r.id,
          name: r.name || r.label || `Region ${r.region_id ?? r.id}`,
        })),
      };
    },
    enabled: isUniverseModalOpen,
    staleTime: 1000 * 60 * 30, // 30 minutes cache
  });

  // Fetch 3D placements for current recommendations to render path
  const recTrackIds = useMemo(
    () => recommendations.slice(0, 15).map((r) => r.track.id),
    [recommendations]
  );

  const { data: recPlacements } = useQuery<{ placements: UniversePlacement[] }>({
    queryKey: ["recPlacements", recTrackIds.join(",")],
    queryFn: async () => {
      if (recTrackIds.length === 0) return { placements: [] };
      const res = await fetch(`${API_BASE}/universe/place`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ track_ids: recTrackIds }),
      });
      if (!res.ok) return { placements: [] };
      const data = await res.json();
      return {
        placements: data.placements || data.items || [],
      };
    },
    enabled: isUniverseModalOpen && recTrackIds.length > 0,
  });

  const recommendationCoords = useMemo(() => {
    const list = recPlacements?.placements;
    if (!list || list.length === 0) return undefined;
    return list.map((p) => p.position_3d);
  }, [recPlacements]);

  if (!isUniverseModalOpen) return null;

  const currentRegionName =
    universeFocusedRegionId !== null && universeData?.regions
      ? universeData.regions.find((r) => r.region_id === universeFocusedRegionId)?.name
      : null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="3D Taste Universe"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-md animate-in fade-in duration-200"
    >
      {/* Modal Container */}
      <div className="relative w-full h-full max-w-[100vw] max-h-[100vh] flex flex-col bg-[#07080b] text-white overflow-hidden font-sans">
        {/* Top Control Bar */}
        <header className="h-14 bg-[#0e1118]/85 border-b border-white/[0.08] px-4 flex items-center justify-between shrink-0 z-20 backdrop-blur-2xl">
          {/* Title & Brand */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-[#fa2d55] to-[#8b5cf6] flex items-center justify-center text-white shadow-ruby">
              <Compass className="w-4 h-4 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold tracking-tight text-white">
                  Taste Universe
                </h2>
                <span className="text-[10px] px-2 py-0.5 rounded-md bg-white/[0.06] text-white/80 border border-white/10 font-mono">
                  {renderMode.toUpperCase()} Map
                </span>
              </div>
              <p className="text-[10px] text-white/50">
                Deterministic 3D projection of catalog vectors (visualization only)
              </p>
            </div>
          </div>

          {/* Center: Region Jump Selector */}
          <div className="hidden md:flex items-center gap-2">
            <div className="relative" ref={dropdownRef}>
              <button
                type="button"
                onClick={() => setIsRegionDropdownOpen(!isRegionDropdownOpen)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/[0.05] hover:bg-white/[0.1] border border-white/10 text-xs text-white/90 transition-colors focus:outline-none focus:ring-2 focus:ring-[#fa2d55]"
              >
                <Layers className="w-3.5 h-3.5 text-[#fb7185]" />
                <span>{currentRegionName ? `Region: ${currentRegionName}` : "All 24 Regions"}</span>
                <ChevronDown className="w-3.5 h-3.5 text-white/50" />
              </button>

              {isRegionDropdownOpen && universeData?.regions && (
                <div className="absolute top-full left-0 mt-1.5 w-64 max-h-80 glass-dropdown rounded-xl border border-white/15 shadow-2xl overflow-y-auto p-1.5 z-50">
                  <button
                    type="button"
                    onClick={() => {
                      setUniverseFocusedRegionId(null);
                      setIsRegionDropdownOpen(false);
                    }}
                    className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs transition-colors ${
                      universeFocusedRegionId === null
                        ? "bg-[#fa2d55]/20 text-[#fb7185] font-semibold"
                        : "text-white/80 hover:bg-white/[0.08]"
                    }`}
                  >
                    View All Regions (Overview)
                  </button>
                  <div className="h-px bg-white/10 my-1" />
                  {universeData.regions.map((reg) => (
                    <button
                      key={reg.region_id}
                      type="button"
                      onClick={() => {
                        setUniverseFocusedRegionId(reg.region_id);
                        setIsRegionDropdownOpen(false);
                      }}
                      className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs flex items-center justify-between transition-colors ${
                        universeFocusedRegionId === reg.region_id
                          ? "bg-[#fa2d55]/20 text-[#fb7185] font-semibold"
                          : "text-white/80 hover:bg-white/[0.08]"
                      }`}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <span
                          className="w-2 h-2 rounded-full shrink-0"
                          style={{
                            backgroundColor:
                              REGION_PALETTE_HEX[reg.region_id % REGION_PALETTE_HEX.length],
                          }}
                        />
                        <span className="truncate">{reg.name}</span>
                      </div>
                      <span className="text-[10px] text-white/40 font-mono">
                        R{reg.region_id}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Quick Blindspot Fly-To Button */}
            {exploringRegion && (
              <button
                type="button"
                onClick={() => setUniverseFocusedRegionId(exploringRegion.id)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-500/15 hover:bg-sky-500/25 border border-sky-500/30 text-sky-200 text-xs font-semibold transition-colors"
              >
                <Sparkles className="w-3.5 h-3.5 text-sky-400" />
                <span>Fly to Blindspot ({exploringRegion.name})</span>
              </button>
            )}
          </div>

          {/* Right Header Controls: Mode toggle, Quality Tier, Close */}
          <div className="flex items-center gap-2.5">
            {/* 3D Visual Layer Toggles */}
            {renderMode === "3d" && (
              <div className="hidden lg:flex items-center gap-1 bg-white/[0.04] p-1 rounded-lg border border-white/10">
                <button
                  type="button"
                  title="Toggle Volumetric Nebulae"
                  onClick={() => setShowNebulae(!showNebulae)}
                  className={`flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium transition-all ${
                    showNebulae
                      ? "bg-[#fa2d55]/20 text-[#fb7185] border border-[#fa2d55]/30 shadow-sm"
                      : "text-white/50 hover:text-white hover:bg-white/[0.05]"
                  }`}
                >
                  <Cloud className="w-3.5 h-3.5" />
                  <span>Nebulae</span>
                </button>

                <button
                  type="button"
                  title="Toggle 3D Region Labels"
                  onClick={() => setShowLabels(!showLabels)}
                  className={`flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium transition-all ${
                    showLabels
                      ? "bg-[#fa2d55]/20 text-[#fb7185] border border-[#fa2d55]/30 shadow-sm"
                      : "text-white/50 hover:text-white hover:bg-white/[0.05]"
                  }`}
                >
                  <Tag className="w-3.5 h-3.5" />
                  <span>Labels</span>
                </button>

                <button
                  type="button"
                  title="Toggle Constellation Lines"
                  onClick={() => setShowConstellations(!showConstellations)}
                  className={`flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium transition-all ${
                    showConstellations
                      ? "bg-[#fa2d55]/20 text-[#fb7185] border border-[#fa2d55]/30 shadow-sm"
                      : "text-white/50 hover:text-white hover:bg-white/[0.05]"
                  }`}
                >
                  <Share2 className="w-3.5 h-3.5" />
                  <span>Constellations</span>
                </button>

                <button
                  type="button"
                  title="Toggle Celestial Orbit"
                  onClick={() => setAutoRotate(!autoRotate)}
                  className={`flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium transition-all ${
                    autoRotate
                      ? "bg-[#fa2d55]/20 text-[#fb7185] border border-[#fa2d55]/30 shadow-sm"
                      : "text-white/50 hover:text-white hover:bg-white/[0.05]"
                  }`}
                >
                  <Orbit className="w-3.5 h-3.5" />
                  <span>Orbit</span>
                </button>
              </div>
            )}

            {/* 3D / 2D Switcher */}
            {hasWebGL && (
              <div className="flex items-center bg-white/[0.05] p-0.5 rounded-lg border border-white/10">
                <button
                  type="button"
                  onClick={() => setRenderMode("3d")}
                  className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-all ${
                    renderMode === "3d"
                      ? "bg-white/[0.15] text-white shadow-sm"
                      : "text-white/60 hover:text-white"
                  }`}
                >
                  3D View
                </button>
                <button
                  type="button"
                  onClick={() => setRenderMode("2d")}
                  className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-all ${
                    renderMode === "2d"
                      ? "bg-white/[0.15] text-white shadow-sm"
                      : "text-white/60 hover:text-white"
                  }`}
                >
                  2D Canvas
                </button>
              </div>
            )}

            {/* Quality Tier Selector (3D only) */}
            {renderMode === "3d" && (
              <div className="hidden sm:flex items-center gap-1 bg-white/[0.05] px-2 py-1 rounded-lg border border-white/10 text-xs">
                <Gauge className="w-3.5 h-3.5 text-[#fa2d55]" />
                <span className="font-mono text-[11px] text-white/80 mr-1">{fps} FPS</span>
                <select
                  value={tier}
                  onChange={(e) => setTier(e.target.value as QualityTier)}
                  aria-label="Quality tier"
                  className="bg-transparent text-white/70 hover:text-white font-medium text-xs focus:outline-none cursor-pointer"
                >
                  <option value="high" className="bg-[#0e1118] text-white">
                    High (15k)
                  </option>
                  <option value="mid" className="bg-[#0e1118] text-white">
                    Mid (8k)
                  </option>
                  <option value="mobile" className="bg-[#0e1118] text-white">
                    Low (4k)
                  </option>
                </select>
              </div>
            )}

            {/* Close Button */}
            <button
              type="button"
              onClick={() => setUniverseModalOpen(false)}
              aria-label="Close 3D universe modal (Esc)"
              className="p-1.5 rounded-lg bg-white/[0.05] hover:bg-white/[0.1] border border-white/10 text-white/70 hover:text-white transition-colors focus:outline-none focus:ring-2 focus:ring-[#fa2d55]"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </header>

        {/* Main Viewport Content Area */}
        <div className="relative flex-1 w-full h-full overflow-hidden">
          {isLoading && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-[#0c0f17] z-30">
              <RefreshCw className="w-8 h-8 animate-spin text-[#d4af37]" />
              <p className="text-sm text-[#c8d0de] font-semibold">
                Loading 15,000 Catalog Stars & Quantized Embeddings...
              </p>
              <p className="text-xs text-[#8c96a8]">Wire payload: 510 KB Int16 array</p>
            </div>
          )}

          {error && (
            <div className="absolute inset-0 flex items-center justify-center p-6 bg-[#0c0f17] z-30">
              <div className="max-w-md p-5 bg-rose-950/40 border border-rose-800/50 rounded-2xl text-center text-rose-200">
                <p className="font-bold mb-1">Failed to initialize 3D Universe</p>
                <p className="text-xs text-rose-300">{(error as Error).message}</p>
              </div>
            </div>
          )}

          {universeData && (
            <>
              {renderMode === "3d" && hasWebGL ? (
                <UniverseErrorBoundary
                  onFallback={() => setRenderMode("2d")}
                  fallback={
                    <UniverseFallback2D
                      data={universeData}
                      focusedRegionId={universeFocusedRegionId}
                      onSelectRegion={(regId) => setUniverseFocusedRegionId(regId)}
                      onSelectTrack={(trkId) => setUniverseFocusedTrackId(trkId)}
                    />
                  }
                >
                  <UniverseCanvas3D
                    data={universeData}
                    tier={tier}
                    focusedRegionId={universeFocusedRegionId}
                    focusedTrackId={universeFocusedTrackId}
                    blindspotRegionId={exploringRegion?.id ?? null}
                    recommendationCoords={recommendationCoords}
                    onSelectTrack={(trkId) => setUniverseFocusedTrackId(trkId)}
                    onSelectRegion={(regId) => setUniverseFocusedRegionId(regId)}
                    onFpsReport={(measuredFps) => setFps(measuredFps)}
                    onTierChange={(newTier) => setTier(newTier)}
                    showNebulae={showNebulae}
                    showLabels={showLabels}
                    showConstellations={showConstellations}
                    autoRotate={autoRotate}
                  />
                </UniverseErrorBoundary>
              ) : (
                <UniverseFallback2D
                  data={universeData}
                  focusedRegionId={universeFocusedRegionId}
                  onSelectRegion={(regId) => setUniverseFocusedRegionId(regId)}
                  onSelectTrack={(trkId) => setUniverseFocusedTrackId(trkId)}
                />
              )}

              {/* Bottom Quick-Jump Region Ribbon */}
              {universeData?.regions && renderMode === "3d" && (
                <div className="absolute bottom-3 left-1/2 -translate-x-1/2 z-20 max-w-[95vw] sm:max-w-[85vw] flex items-center gap-1.5 p-1.5 rounded-full bg-[#080b12]/80 backdrop-blur-2xl border border-white/10 shadow-[0_8px_32px_rgba(0,0,0,0.6)] overflow-x-auto no-scrollbar pointer-events-auto">
                  <button
                    type="button"
                    onClick={() => setUniverseFocusedRegionId(null)}
                    className={`shrink-0 flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold transition-all ${
                      universeFocusedRegionId === null
                        ? "bg-[#fa2d55] text-white shadow-[0_0_12px_rgba(250,45,85,0.5)]"
                        : "bg-white/[0.05] hover:bg-white/[0.12] text-white/70 hover:text-white"
                    }`}
                  >
                    <span>Overview</span>
                  </button>

                  <div className="w-px h-3.5 bg-white/15 shrink-0" />

                  {universeData.regions.map((reg) => {
                    const isSelected = universeFocusedRegionId === reg.region_id;
                    const color = REGION_PALETTE_HEX[reg.region_id % REGION_PALETTE_HEX.length];
                    return (
                      <button
                        key={reg.region_id}
                        type="button"
                        onClick={() => setUniverseFocusedRegionId(reg.region_id)}
                        className={`shrink-0 flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-all ${
                          isSelected
                            ? "bg-white/20 text-white border border-white/30 shadow-md font-semibold"
                            : "bg-white/[0.04] hover:bg-white/[0.09] text-white/70 hover:text-white border border-white/5"
                        }`}
                      >
                        <span
                          className="w-2 h-2 rounded-full shrink-0 shadow-sm"
                          style={{ backgroundColor: color }}
                        />
                        <span className="truncate max-w-[130px]">{reg.name}</span>
                      </button>
                    );
                  })}
                </div>
              )}

              {/* Side Inspector Drawer */}
              <UniverseSidePanel
                trackId={universeFocusedTrackId}
                onClose={() => setUniverseFocusedTrackId(null)}
                onSelectTrack={(trkId) => setUniverseFocusedTrackId(trkId)}
              />
            </>
          )}
        </div>

        {/* Footer Status Bar */}
        <footer className="h-8 bg-[#090b10] border-t border-white/[0.08] px-4 flex items-center justify-between text-[11px] text-white/50 shrink-0 z-20">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1.5 text-white/70">
              <Info className="w-3 h-3 text-[#fa2d55]" />
              Trustworthiness (k=15):{" "}
              <strong className="text-white">
                {universeData
                  ? `${(universeData.quality_metrics.trustworthiness_k15 * 100).toFixed(1)}%`
                  : "98.3%"}
              </strong>
            </span>
            <span className="hidden sm:inline text-white/20">|</span>
            <span className="hidden sm:inline text-white/50">
              Decisions use 256d vectors; 3D coordinates are visualization only
            </span>
          </div>

          <div className="flex items-center gap-3">
            <span className="font-mono text-white/60">
              {tier === "high" ? "15,000" : tier === "mid" ? "8,000" : "4,000"} Points
            </span>
            <span className="text-white/50">Press <kbd className="px-1.5 py-0.5 rounded-md bg-white/[0.06] border border-white/10 text-[10px] text-white/80 font-mono">Esc</kbd> to close</span>
          </div>
        </footer>
      </div>
    </div>
  );
}
