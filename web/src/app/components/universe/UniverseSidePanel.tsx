"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  X,
  Plus,
  Compass,
  AlertTriangle,
  Music,
  ExternalLink,
  Volume2,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { NeighborDetails } from "./types";
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
      return await res.json();
    },
    enabled: !!trackId,
  });

  if (!trackId) return null;

  const isAlreadySeed = seeds.some((s) => s.id === trackId);

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
      className="absolute top-0 right-0 bottom-0 w-full sm:w-96 bg-[#0d1017]/95 backdrop-blur-2xl border-l border-white/10 shadow-2xl z-50 flex flex-col animate-in slide-in-from-right duration-200 font-sans"
    >
      {/* Header */}
      <div className="p-4 border-b border-white/[0.08] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-[#fa2d55]/15 border border-[#fa2d55]/30 flex items-center justify-center text-[#fa2d55]">
            <Compass className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#fa2d55]">
              Track Inspector
            </h3>
            <span className="text-[10px] text-white/50">Original Space Neighborhood</span>
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

      {/* Content Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {isLoading && (
          <div className="py-20 text-center text-white/50 flex flex-col items-center justify-center gap-2">
            <RefreshCw className="w-6 h-6 animate-spin text-[#fa2d55]" />
            <p className="text-xs">Querying high-dimensional manifold...</p>
          </div>
        )}

        {error && (
          <div className="p-3.5 bg-rose-950/40 border border-rose-800/50 rounded-xl text-xs text-rose-300">
            Failed to inspect track: {(error as Error).message}
          </div>
        )}

        {data && (
          <>
            {/* Primary Track Card */}
            <div className="bg-white/[0.04] border border-white/10 rounded-xl p-4 shadow-sm backdrop-blur-md">
              <div className="flex items-start justify-between gap-2 mb-2">
                <div>
                  <h4 className="text-base font-bold text-white leading-snug">
                    {data.track_title}
                  </h4>
                  <p className="text-xs text-[#fb7185] font-medium">{data.artist_name}</p>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-white/[0.06] text-white/70 border border-white/10">
                  R{data.region_id}
                </span>
              </div>

              <div className="flex items-center justify-between text-[11px] text-white/60 pt-2 border-t border-white/[0.08]">
                <span>Region: <strong className="text-white">{data.region_name}</strong></span>
                <span className="font-mono text-[10px]">
                  3D: [{data.position_3d.map((v) => v.toFixed(2)).join(", ")}]
                </span>
              </div>

              {/* Seed Button */}
              <div className="mt-3">
                <button
                  type="button"
                  onClick={handleAddAsSeed}
                  disabled={isAlreadySeed}
                  className={`w-full flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg text-xs font-semibold transition-all ${
                    isAlreadySeed
                      ? "bg-white/[0.05] text-white/40 cursor-not-allowed border border-white/10"
                      : "btn-ruby"
                  }`}
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>{isAlreadySeed ? "Already in Seeds" : "Add to Seeds"}</span>
                </button>
              </div>
            </div>

            {/* Non-linear Projection Distortion Disclosure */}
            <div className="p-3 bg-amber-950/20 border border-amber-500/30 rounded-xl flex items-start gap-2.5">
              <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              <div className="text-[11px] text-amber-200/90 leading-relaxed">
                <span className="font-semibold text-amber-300">Geometric Distortion Note:</span>{" "}
                {data.distortion_warning}
              </div>
            </div>

            {/* Original Space Neighbors List */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <h5 className="text-xs font-bold uppercase tracking-wider text-white/60 flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-[#fb7185]" />
                  Original-Space Nearest Neighbors
                </h5>
                <span className="text-[10px] text-white/40 font-mono">Cosine Sim</span>
              </div>

              <div className="space-y-2">
                {data.neighbors.map((nb) => {
                  const simPct = Math.round(nb.original_cosine_sim * 100);
                  return (
                    <div
                      key={nb.track_id}
                      onClick={() => onSelectTrack(nb.track_id)}
                      className="group p-3 bg-white/[0.03] hover:bg-white/[0.07] border border-white/[0.08] hover:border-[#fa2d55]/40 rounded-xl cursor-pointer transition-all"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="text-xs font-semibold text-white group-hover:text-[#fa2d55] truncate transition-colors">
                            {nb.title}
                          </p>
                          <p className="text-[11px] text-white/60 truncate">
                            {nb.artist_name} • {nb.region_name}
                          </p>
                        </div>
                        <div className="text-right shrink-0">
                          <span className="text-xs font-mono font-bold text-[#fb7185]">
                            {simPct}%
                          </span>
                        </div>
                      </div>

                      {/* Shared tags */}
                      {nb.shared_tags && nb.shared_tags.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                          {nb.shared_tags.slice(0, 3).map((tag, idx) => (
                            <span
                              key={idx}
                              className="text-[9px] px-1.5 py-0.5 rounded-md bg-white/[0.06] text-white/70 border border-white/10"
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
