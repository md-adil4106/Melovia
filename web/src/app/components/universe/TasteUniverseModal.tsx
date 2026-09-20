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
} from "lucide-react";
import { useDiscoveryStore } from "../../store";
import { UniverseData, QualityTier, UniversePlacement, REGION_PALETTE_HEX } from "./types";
import { UniverseCanvas3D } from "./UniverseCanvas3D";
import { UniverseFallback2D } from "./UniverseFallback2D";
import { UniverseSidePanel } from "./UniverseSidePanel";

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
      if (!res.ok) throw new Error("Failed to load 3D universe data");
      return await res.json();
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
      return await res.json();
    },
    enabled: isUniverseModalOpen && recTrackIds.length > 0,
  });

  const recommendationCoords = useMemo(() => {
    if (!recPlacements?.placements) return undefined;
    return recPlacements.placements.map((p) => p.position_3d);
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
      <div className="relative w-full h-full max-w-[100vw] max-h-[100vh] flex flex-col bg-[#0b0e16] text-[#f1f3f7] overflow-hidden">
        {/* Top Control Bar */}
        <header className="h-14 bg-[#121622]/95 border-b border-[#202738] px-4 flex items-center justify-between shrink-0 z-20 backdrop-blur-md">
          {/* Title & Brand */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#d4af37]/20 border border-[#d4af37]/40 flex items-center justify-center text-[#d4af37]">
              <Compass className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold tracking-wide text-[#f5ecd5] uppercase">
                  Taste Universe
                </h2>
                <span className="text-[10px] px-2 py-0.5 rounded bg-[#1d2434] text-[#d4af37] border border-[#2d374d] font-mono">
                  {renderMode.toUpperCase()} Map
                </span>
              </div>
              <p className="text-[10px] text-[#8c96a8]">
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
                className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-[#171d2b] hover:bg-[#20283a] border border-[#2b354a] text-xs text-[#c8d0de] transition-colors focus:outline-none focus:ring-1 focus:ring-[#d4af37]"
              >
                <Layers className="w-3.5 h-3.5 text-[#d4af37]" />
                <span>{currentRegionName ? `Region: ${currentRegionName}` : "All 24 Regions"}</span>
                <ChevronDown className="w-3.5 h-3.5 text-[#8c96a8]" />
              </button>

              {isRegionDropdownOpen && universeData?.regions && (
                <div className="absolute top-full left-0 mt-1.5 w-64 max-h-80 bg-[#141924] border border-[#283247] rounded-xl shadow-2xl overflow-y-auto p-1.5 z-50">
                  <button
                    type="button"
                    onClick={() => {
                      setUniverseFocusedRegionId(null);
                      setIsRegionDropdownOpen(false);
                    }}
                    className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs transition-colors ${
                      universeFocusedRegionId === null
                        ? "bg-[#d4af37]/20 text-[#d4af37] font-semibold"
                        : "text-[#c8d0de] hover:bg-[#1b2230]"
                    }`}
                  >
                    View All Regions (Overview)
                  </button>
                  <div className="h-px bg-[#202738] my-1" />
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
                          ? "bg-[#d4af37]/20 text-[#d4af37] font-semibold"
                          : "text-[#c8d0de] hover:bg-[#1b2230]"
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
                      <span className="text-[10px] text-[#647187] font-mono">
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
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-sky-950/40 hover:bg-sky-900/50 border border-sky-700/50 text-sky-300 text-xs font-semibold transition-colors"
              >
                <Sparkles className="w-3.5 h-3.5 text-sky-400" />
                <span>Fly to Blindspot ({exploringRegion.name})</span>
              </button>
            )}
          </div>

          {/* Right Header Controls: Mode toggle, Quality Tier, Close */}
          <div className="flex items-center gap-3">
            {/* 3D / 2D Switcher */}
            {hasWebGL && (
              <div className="flex items-center bg-[#0d1017] p-0.5 rounded-lg border border-[#202738]">
                <button
                  type="button"
                  onClick={() => setRenderMode("3d")}
                  className={`px-2.5 py-1 rounded text-xs font-semibold transition-all ${
                    renderMode === "3d"
                      ? "bg-[#1f2738] text-[#d4af37] shadow"
                      : "text-[#8c96a8] hover:text-[#f1f3f7]"
                  }`}
                >
                  3D View
                </button>
                <button
                  type="button"
                  onClick={() => setRenderMode("2d")}
                  className={`px-2.5 py-1 rounded text-xs font-semibold transition-all ${
                    renderMode === "2d"
                      ? "bg-[#1f2738] text-[#d4af37] shadow"
                      : "text-[#8c96a8] hover:text-[#f1f3f7]"
                  }`}
                >
                  2D Canvas
                </button>
              </div>
            )}

            {/* Quality Tier Selector (3D only) */}
            {renderMode === "3d" && (
              <div className="hidden sm:flex items-center gap-1 bg-[#0d1017] px-2 py-1 rounded-lg border border-[#202738] text-xs">
                <Gauge className="w-3.5 h-3.5 text-[#d4af37]" />
                <span className="font-mono text-[11px] text-[#c8d0de] mr-1">{fps} FPS</span>
                <select
                  value={tier}
                  onChange={(e) => setTier(e.target.value as QualityTier)}
                  aria-label="Quality tier"
                  className="bg-transparent text-[#8c96a8] hover:text-[#f1f3f7] font-medium text-xs focus:outline-none cursor-pointer"
                >
                  <option value="high" className="bg-[#121622] text-[#f1f3f7]">
                    High (15k)
                  </option>
                  <option value="mid" className="bg-[#121622] text-[#f1f3f7]">
                    Mid (8k)
                  </option>
                  <option value="mobile" className="bg-[#121622] text-[#f1f3f7]">
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
              className="p-1.5 rounded-lg bg-[#18202e] hover:bg-[#252f44] border border-[#2d374d] text-[#8c96a8] hover:text-[#f1f3f7] transition-colors focus:outline-none focus:ring-1 focus:ring-[#d4af37]"
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
                <UniverseCanvas3D
                  data={universeData}
                  tier={tier}
                  focusedRegionId={universeFocusedRegionId}
                  focusedTrackId={universeFocusedTrackId}
                  blindspotRegionId={exploringRegion?.id ?? null}
                  recommendationCoords={recommendationCoords}
                  onSelectTrack={(trkId) => setUniverseFocusedTrackId(trkId)}
                  onFpsReport={(measuredFps) => setFps(measuredFps)}
                  onTierChange={(newTier) => setTier(newTier)}
                />
              ) : (
                <UniverseFallback2D
                  data={universeData}
                  focusedRegionId={universeFocusedRegionId}
                  onSelectRegion={(regId) => setUniverseFocusedRegionId(regId)}
                  onSelectTrack={(trkId) => setUniverseFocusedTrackId(trkId)}
                />
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
        <footer className="h-8 bg-[#0d1017] border-t border-[#1d2433] px-4 flex items-center justify-between text-[11px] text-[#647187] shrink-0 z-20">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1.5 text-[#8c96a8]">
              <Info className="w-3 h-3 text-[#d4af37]" />
              Trustworthiness (k=15):{" "}
              <strong className="text-[#c8d0de]">
                {universeData
                  ? `${(universeData.quality_metrics.trustworthiness_k15 * 100).toFixed(1)}%`
                  : "98.3%"}
              </strong>
            </span>
            <span className="hidden sm:inline text-[#3a4457]">|</span>
            <span className="hidden sm:inline text-[#8c96a8]">
              Decisions use 256d vectors; 3D coordinates are visualization only
            </span>
          </div>

          <div className="flex items-center gap-3">
            <span className="font-mono text-[#8c96a8]">
              {tier === "high" ? "15,000" : tier === "mid" ? "8,000" : "4,000"} Points
            </span>
            <span className="text-[#8c96a8]">Press <kbd className="px-1 py-0.5 rounded bg-[#1c2333] border border-[#2b364d] text-[10px] text-[#c8d0de]">Esc</kbd> to close</span>
          </div>
        </footer>
      </div>
    </div>
  );
}
