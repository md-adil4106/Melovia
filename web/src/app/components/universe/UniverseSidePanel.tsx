"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  X,
  Plus,
  Check,
  Compass,
  AlertTriangle,
  Music,
  ExternalLink,
  Volume2,
  RefreshCw,
  Sparkles,
  Disc,
} from "lucide-react";
import { NeighborDetails, REGION_PALETTE_HEX } from "./types";
import { useDiscoveryStore, Track } from "../../store";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface UniverseSidePanelProps {
  trackId: string | null;
  onClose: () => void;
  onSelectTrack: (trackId: string) => void;
}

export function UniverseSidePanel({
  trackId,
  onClose,
  onSelectTrack,
}: UniverseSidePanelProps) {
  const { addSeed, seeds } = useDiscoveryStore();

  const { data, isLoading, error } = useQuery<NeighborDetails>({
    queryKey: ["universeNeighbors", trackId],
    queryFn: async () => {
      if (!trackId) throw new Error("No track specified");
      const res = await fetch(`${API_BASE}/universe/neighbors/${encodeURIComponent(trackId)}`);
      if (!res.ok) {
        throw new Error("Failed to fetch track neighborhood details");
      }
      const json = await res.json();
      return {
        ...json,
        track_id: json.track_id || json.target_track_id || trackId,
        track_title: json.track_title || json.target_track_title || "",
        artist_name: json.artist_name || "",
        region_id: json.region_id ?? json.target_region_id ?? 0,
        region_name: json.region_name || "",
        position_3d: json.position_3d || [0, 0, 0],
        distortion_warning: json.distortion_warning || json.distortion_disclaimer || "",
        neighbors: (json.neighbors || []).map((nb: any) => ({
          ...nb,
          original_cosine_sim: nb.original_cosine_sim ?? nb.similarity_combined ?? 0,
          region_name: nb.region_name || "",
        })),
      };
    },
    enabled: !!trackId,
  });

  if (!trackId) return null;

  const isAlreadySeed = seeds.some((s) => s.id === trackId);
  const regionColor =
    data && typeof data.region_id === "number"
      ? REGION_PALETTE_HEX[data.region_id % REGION_PALETTE_HEX.length]
      : "#fa2d55";

  const handleAddAsSeed = () => {
    if (!data) return;
    const trackObj: Track = {
      id: data.track_id,
      track_idx: 0,
      title: data.track_title,
      artist_id: "unknown",
      artist_name: data.artist_name,
      popularity_pct: 50,
      has_a: true,
      has_t: true,
      region_id: data.region_id,
    };
    addSeed(trackObj);
  };

  return (
    <aside
      aria-label="Track Neighborhood Inspector"
      className="absolute top-0 right-0 bottom-0 w-full sm:w-[410px] bg-[#080b12]/92 backdrop-blur-3xl border-l border-white/[0.12] shadow-[-16px_0_48px_rgba(0,0,0,0.85)] z-50 flex flex-col animate-in slide-in-from-right duration-250 font-sans"
    >
      {/* Top Header */}
      <div className="p-4 border-b border-white/[0.08] flex items-center justify-between shrink-0 bg-white/[0.02]">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-[#fa2d55]/20 to-[#8b5cf6]/20 border border-white/10 flex items-center justify-center text-[#fa2d55] shadow-sm">
            <Compass className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-white/90">
              Track Inspector
            </h3>
            <span className="text-[10px] text-white/40">High-Dimensional Manifold</span>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close track inspector"
          className="p-1.5 rounded-lg text-white/60 hover:text-white hover:bg-white/[0.08] transition-colors focus:outline-none focus:ring-2 focus:ring-[#fa2d55]"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Main Scrollable Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 no-scrollbar">
        {isLoading && (
          <div className="py-24 text-center text-white/50 flex flex-col items-center justify-center gap-3">
            <RefreshCw className="w-7 h-7 animate-spin text-[#fa2d55]" />
            <p className="text-xs font-medium text-white/70">Querying 256-Dimensional Catalog...</p>
            <p className="text-[11px] text-white/40">Calculating exact manifold cosine geometry</p>
          </div>
        )}

        {error && (
          <div className="p-4 bg-rose-950/40 border border-rose-800/50 rounded-2xl text-xs text-rose-300 shadow-lg">
            <p className="font-semibold mb-1">Failed to inspect star</p>
            <p className="text-[11px] opacity-80">{(error as Error).message}</p>
          </div>
        )}

        {data && (
          <>
            {/* Primary Track Card with Spinning Vinyl Artwork */}
            <div className="relative overflow-hidden rounded-2xl bg-gradient-to-b from-white/[0.07] to-white/[0.02] border border-white/10 p-4 shadow-xl backdrop-blur-xl">
              {/* Subtle ambient colored glow */}
              <div
                className="absolute -top-12 -right-12 w-32 h-32 rounded-full opacity-20 blur-2xl pointer-events-none"
                style={{ backgroundColor: regionColor }}
              />

              <div className="flex items-center gap-4 mb-3.5">
                {/* Vinyl Record Player Graphic */}
                <div className="relative w-16 h-16 rounded-full bg-gradient-to-tr from-neutral-900 via-neutral-800 to-neutral-900 border border-white/20 shadow-2xl flex items-center justify-center shrink-0 animate-spin [animation-duration:14s]">
                  {/* Concentric Grooves */}
                  <div className="absolute inset-1.5 rounded-full border border-white/[0.06]" />
                  <div className="absolute inset-3 rounded-full border border-white/[0.08]" />
                  <div className="absolute inset-4.5 rounded-full border border-white/[0.06]" />
                  {/* Center Label */}
                  <div
                    className="w-6 h-6 rounded-full border border-white/30 flex items-center justify-center shadow-inner"
                    style={{ backgroundColor: regionColor }}
                  >
                    <div className="w-2 h-2 rounded-full bg-black/90 border border-white/40" />
                  </div>
                </div>

                {/* Track Metadata */}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span
                      className="text-[10px] font-mono px-2 py-0.5 rounded-full text-white/90 border border-white/15 font-semibold"
                      style={{ backgroundColor: `${regionColor}33` }}
                    >
                      Region {data.region_id}
                    </span>
                  </div>
                  <h4 className="text-base font-bold text-white leading-tight truncate" title={data.track_title}>
                    {data.track_title}
                  </h4>
                  <p className="text-xs text-white/70 font-medium truncate mt-0.5" title={data.artist_name}>
                    {data.artist_name}
                  </p>
                </div>
              </div>

              {/* Coordinates & Region Info */}
              <div className="flex items-center justify-between text-[11px] text-white/60 py-2.5 border-t border-white/[0.08]">
                <div className="flex items-center gap-1.5 truncate">
                  <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: regionColor }} />
                  <span className="truncate">Cluster: <strong className="text-white/90">{data.region_name}</strong></span>
                </div>
                <span className="font-mono text-[10px] text-white/50 shrink-0 ml-2">
                  3D: [{(data.position_3d || [0, 0, 0]).map((v) => Number(v).toFixed(2)).join(", ")}]
                </span>
              </div>

              {/* Action Button: Add to Seeds */}
              <div className="mt-2.5">
                <button
                  type="button"
                  onClick={handleAddAsSeed}
                  disabled={isAlreadySeed}
                  className={`w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs font-bold transition-all shadow-md ${
                    isAlreadySeed
                      ? "bg-white/[0.06] text-white/40 cursor-not-allowed border border-white/10"
                      : "bg-gradient-to-r from-[#fa2d55] to-[#f43f5e] hover:from-[#e11d48] hover:to-[#be123c] text-white shadow-[0_4px_16px_rgba(250,45,85,0.4)] hover:shadow-[0_6px_20px_rgba(250,45,85,0.6)] active:scale-[0.98]"
                  }`}
                >
                  {isAlreadySeed ? (
                    <>
                      <Check className="w-4 h-4 text-emerald-400" />
                      <span>Already in Seed Tracks</span>
                    </>
                  ) : (
                    <>
                      <Plus className="w-4 h-4" />
                      <span>Add as Recommendation Seed</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Non-linear Projection Distortion Disclosure */}
            <div className="p-3 bg-amber-500/[0.08] border border-amber-500/25 rounded-2xl flex items-start gap-2.5 shadow-sm">
              <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              <div className="text-[11px] text-amber-200/90 leading-relaxed">
                <span className="font-semibold text-amber-300">Geometric Distortion Note:</span>{" "}
                {data.distortion_warning}
              </div>
            </div>

            {/* Original Space Neighbors List */}
            <div className="space-y-2 pt-1">
              <div className="flex items-center justify-between px-0.5">
                <h5 className="text-xs font-bold uppercase tracking-wider text-white/70 flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-[#fb7185]" />
                  Original-Space Nearest Neighbors
                </h5>
                <span className="text-[10px] text-white/40 font-mono">Cosine Sim</span>
              </div>

              <div className="space-y-2">
                {data.neighbors.map((nb, i) => {
                  const simPct = Math.round(nb.original_cosine_sim * 100);
                  return (
                    <div
                      key={nb.track_id || i}
                      onClick={() => onSelectTrack(nb.track_id)}
                      className="group p-3 rounded-xl bg-white/[0.03] hover:bg-white/[0.08] border border-white/[0.08] hover:border-[#fa2d55]/40 cursor-pointer transition-all duration-150 shadow-sm hover:shadow-md"
                    >
                      <div className="flex items-start justify-between gap-2 mb-1.5">
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-bold text-white group-hover:text-[#fa2d55] truncate transition-colors">
                            {nb.title}
                          </p>
                          <p className="text-[11px] text-white/60 truncate mt-0.5">
                            {nb.artist_name} • {nb.region_name}
                          </p>
                        </div>
                        <div className="text-right shrink-0">
                          <span className="text-xs font-mono font-bold text-[#fb7185]">
                            {simPct}%
                          </span>
                        </div>
                      </div>

                      {/* Cosine Similarity Bar */}
                      <div className="w-full h-1 bg-white/[0.08] rounded-full overflow-hidden mb-2">
                        <div
                          className="h-full bg-gradient-to-r from-[#fa2d55] to-[#fb7185] rounded-full transition-all duration-300"
                          style={{ width: `${Math.max(5, simPct)}%` }}
                        />
                      </div>

                      {/* Shared tags */}
                      {nb.shared_tags && nb.shared_tags.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {nb.shared_tags.slice(0, 3).map((tag, idx) => (
                            <span
                              key={idx}
                              className="text-[9px] px-1.5 py-0.5 rounded-md bg-white/[0.05] text-white/70 border border-white/[0.08]"
                            >
                              #{tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </>
        )}
      </div>
    </aside>
  );
}
