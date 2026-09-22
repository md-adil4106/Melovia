"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  ArrowDown,
  ArrowUp,
  Download,
  ListMusic,
  Minus,
  Music,
  Plus,
  RefreshCw,
  Sparkles,
  TrendingUp,
  Volume2,
  Waves,
  Wind,
  X,
  Zap,
} from "lucide-react";
import { useDiscoveryStore, RecommendedItem, Track } from "../store";
import { ExportModal } from "./export/ExportModal";

/* ── Types ─────────────────────────────────────────────── */

interface TransitionDetail {
  from_track_id: string;
  to_track_id: string;
  tempo_delta: number | null;
  energy_delta: number | null;
  semantic_distance: number;
  same_artist: boolean;
  cost: number;
}

interface ArcDataPoint {
  position: number;
  normalized_pos: number;
  target_energy: number;
  realized_energy: number | null;
  track_id: string;
}

interface SequenceResponse {
  tracks: RecommendedItem[];
  transitions: TransitionDetail[];
  arc_points: ArcDataPoint[];
  total_cost: number;
  mean_transition_cost: number;
  arc_correlation: number;
  active_weights: Record<string, number>;
  dropped_features: string[];
}

type ArcPreset = "steady" | "build" | "wave" | "wind_down";

const ARC_INFO: Record<ArcPreset, { label: string; desc: string; icon: typeof TrendingUp }> = {
  steady:    { label: "Steady",    desc: "Consistent energy",       icon: Minus },
  build:     { label: "Build",     desc: "Low → high energy ramp",  icon: TrendingUp },
  wave:      { label: "Wave",      desc: "Rise, peak, and descend", icon: Waves },
  wind_down: { label: "Wind Down", desc: "High → low energy cool",  icon: Wind },
};

/* ── Component ─────────────────────────────────────────── */

export function PlaylistBuilder({
  isOpen,
  onClose,
  apiBase,
}: {
  isOpen: boolean;
  onClose: () => void;
  apiBase: string;
}) {
  const {
    candidateSetId,
    selectedArc,
    setSelectedArc,
    playlistLength,
    setPlaylistLength,
  } = useDiscoveryStore();

  const [result, setResult] = useState<SequenceResponse | null>(null);
  const [localTracks, setLocalTracks] = useState<RecommendedItem[]>([]);
  const [isExportOpen, setIsExportOpen] = useState(false);
  const drawerRef = useRef<HTMLDivElement>(null);

  // Sequence mutation
  const sequenceMutation = useMutation({
    mutationFn: async () => {
      if (!candidateSetId) throw new Error("No candidate set available.");
      const res = await fetch(`${apiBase}/playlist/sequence`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          candidate_set_id: candidateSetId,
          arc: selectedArc,
          length: playlistLength,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail?.message || err?.detail || `Sequencing failed (${res.status})`);
      }
      return (await res.json()) as SequenceResponse;
    },
    onSuccess: (data) => {
      setResult(data);
      setLocalTracks(data.tracks);
    },
  });

  // Auto-sequence on open
  useEffect(() => {
    if (isOpen && candidateSetId && !result) {
      sequenceMutation.mutate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, candidateSetId]);

  // Reset on close
  const handleClose = useCallback(() => {
    setResult(null);
    setLocalTracks([]);
    onClose();
  }, [onClose]);

  // Escape key
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [isOpen, handleClose]);

  // Reorder helpers
  const moveTrack = useCallback(
    (fromIdx: number, direction: "up" | "down") => {
      setLocalTracks((prev) => {
        const toIdx = direction === "up" ? fromIdx - 1 : fromIdx + 1;
        if (toIdx < 0 || toIdx >= prev.length) return prev;
        const next = [...prev];
        [next[fromIdx], next[toIdx]] = [next[toIdx], next[fromIdx]];
        return next;
      });
    },
    []
  );

  const removeTrack = useCallback(
    (trackId: string) => {
      setLocalTracks((prev) => prev.filter((t) => t.track.id !== trackId));
    },
    []
  );

  if (!isOpen) return null;

  /* ── SVG Arc Chart ─────────────────────────────────────── */
  const arcPoints = result?.arc_points ?? [];
  const svgW = 480;
  const svgH = 120;
  const pad = { l: 32, r: 12, t: 12, b: 24 };
  const plotW = svgW - pad.l - pad.r;
  const plotH = svgH - pad.t - pad.b;

  const toX = (u: number) => pad.l + u * plotW;
  const toY = (e: number) => pad.t + (1 - e) * plotH;

  const targetPath =
    arcPoints.length > 1
      ? arcPoints
          .map((p, i) => `${i === 0 ? "M" : "L"} ${toX(p.normalized_pos).toFixed(1)} ${toY(p.target_energy).toFixed(1)}`)
          .join(" ")
      : "";

  const realizedPath =
    arcPoints.length > 1
      ? arcPoints
          .filter((p) => p.realized_energy != null)
          .map((p, i) => `${i === 0 ? "M" : "L"} ${toX(p.normalized_pos).toFixed(1)} ${toY(p.realized_energy!).toFixed(1)}`)
          .join(" ")
      : "";

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
        onClick={handleClose}
        aria-hidden="true"
      />

      {/* Drawer */}
      <div
        ref={drawerRef}
        role="dialog"
        aria-modal="true"
        aria-label="Playlist Builder"
        className="fixed inset-y-0 right-0 z-50 w-full max-w-xl bg-[#07080b]/95 backdrop-blur-2xl border-l border-white/10 shadow-2xl flex flex-col overflow-hidden animate-in slide-in-from-right duration-300"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/10 bg-white/[0.02]">
          <div className="flex items-center gap-2.5">
            <ListMusic className="w-5 h-5 text-[#fa2d55]" />
            <h2 className="text-base font-bold text-white font-sans tracking-tight">
              Playlist Builder
            </h2>
          </div>
          <button
            type="button"
            onClick={handleClose}
            aria-label="Close playlist builder"
            className="p-1.5 rounded-full text-white/60 hover:text-white hover:bg-white/10 transition-colors focus:outline-none focus:ring-2 focus:ring-[#fa2d55]"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Controls */}
        <div className="px-5 py-4 border-b border-white/10 space-y-4 bg-white/[0.01]">
          {/* Arc Preset Buttons */}
          <div>
            <label className="text-xs font-semibold text-white/60 uppercase tracking-wider mb-2 block">
              Energy Arc
            </label>
            <div className="flex gap-2">
              {(Object.keys(ARC_INFO) as ArcPreset[]).map((arc) => {
                const info = ARC_INFO[arc];
                const Icon = info.icon;
                const active = selectedArc === arc;
                return (
                  <button
                    key={arc}
                    type="button"
                    onClick={() => {
                      setSelectedArc(arc);
                      if (candidateSetId) sequenceMutation.mutate();
                    }}
                    aria-pressed={active}
                    className={`flex-1 flex flex-col items-center gap-1 px-2 py-2 rounded-xl text-xs font-medium transition-all focus:outline-none focus:ring-2 focus:ring-[#fa2d55] ${
                      active
                        ? "bg-[#fa2d55]/15 border border-[#fa2d55]/60 text-white shadow-sm"
                        : "bg-white/[0.04] border border-white/10 text-white/70 hover:border-white/20 hover:text-white"
                    }`}
                  >
                    <Icon className="w-4 h-4 text-[#fa2d55]" />
                    <span>{info.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Length Stepper */}
          <div className="flex items-center justify-between">
            <label className="text-xs font-semibold text-white/60 uppercase tracking-wider">
              Playlist Length
            </label>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setPlaylistLength(playlistLength - 1)}
                disabled={playlistLength <= 2}
                aria-label="Decrease playlist length"
                className="p-1.5 rounded-full bg-white/[0.06] border border-white/10 text-white/70 hover:text-white disabled:opacity-40 transition-colors focus:outline-none focus:ring-1 focus:ring-[#fa2d55]"
              >
                <Minus className="w-3.5 h-3.5" />
              </button>
              <span className="font-mono text-sm font-bold text-white w-8 text-center">
                {playlistLength}
              </span>
              <button
                type="button"
                onClick={() => setPlaylistLength(playlistLength + 1)}
                disabled={playlistLength >= 30}
                aria-label="Increase playlist length"
                className="p-1.5 rounded-full bg-white/[0.06] border border-white/10 text-white/70 hover:text-white disabled:opacity-40 transition-colors focus:outline-none focus:ring-1 focus:ring-[#fa2d55]"
              >
                <Plus className="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                onClick={() => sequenceMutation.mutate()}
                disabled={!candidateSetId || sequenceMutation.isPending}
                aria-label="Re-sequence playlist"
                className="ml-2 inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full text-xs font-semibold bg-gradient-to-r from-[#fa2d55] to-[#e11d48] text-white shadow-ruby transition-all active:scale-95 disabled:opacity-40 focus:outline-none focus:ring-2 focus:ring-[#fa2d55]"
              >
                {sequenceMutation.isPending ? (
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Sparkles className="w-3.5 h-3.5" />
                )}
                <span>Sequence</span>
              </button>
            </div>
          </div>
        </div>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          {/* Loading */}
          {sequenceMutation.isPending && (
            <div className="flex items-center justify-center py-12 text-white/60">
              <RefreshCw className="w-6 h-6 animate-spin mr-3 text-[#fa2d55]" />
              <span className="text-sm">Sequencing playlist&hellip;</span>
            </div>
          )}

          {/* Error */}
          {sequenceMutation.isError && (
            <div className="bg-rose-950/40 border border-rose-500/40 rounded-2xl p-4 text-rose-200 text-sm">
              <p className="font-semibold">Sequencing Error</p>
              <p className="text-xs mt-1 text-rose-300">{(sequenceMutation.error as Error)?.message}</p>
            </div>
          )}

          {/* Results */}
          {result && !sequenceMutation.isPending && (
            <>
              {/* Energy Arc SVG Chart */}
              {arcPoints.length > 1 && (
                <div>
                  <h3 className="text-xs font-semibold text-white/60 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                    <Zap className="w-3.5 h-3.5 text-[#fa2d55]" />
                    Energy Arc — Target vs Realized
                  </h3>
                  <div className="bg-white/[0.03] border border-white/[0.08] rounded-2xl p-4 shadow-md">
                    <svg
                      viewBox={`0 0 ${svgW} ${svgH}`}
                      className="w-full h-auto"
                      role="img"
                      aria-label={`Energy arc chart: ${selectedArc} preset with ${arcPoints.length} tracks. Arc correlation: ${result.arc_correlation.toFixed(2)}.`}
                    >
                      {/* Grid lines */}
                      {[0, 0.25, 0.5, 0.75, 1].map((e) => (
                        <line
                          key={e}
                          x1={pad.l}
                          y1={toY(e)}
                          x2={svgW - pad.r}
                          y2={toY(e)}
                          stroke="rgba(255, 255, 255, 0.08)"
                          strokeWidth="1"
                        />
                      ))}
                      {/* Y-axis labels */}
                      {[0, 0.5, 1].map((e) => (
                        <text
                          key={e}
                          x={pad.l - 4}
                          y={toY(e) + 3}
                          textAnchor="end"
                          className="fill-white/40 text-[9px]"
                        >
                          {e.toFixed(1)}
                        </text>
                      ))}
                      {/* Target arc (dashed ruby) */}
                      {targetPath && (
                        <path
                          d={targetPath}
                          fill="none"
                          stroke="#fa2d55"
                          strokeWidth="2"
                          strokeDasharray="6 3"
                          opacity="0.8"
                        />
                      )}
                      {/* Realized arc (solid emerald) */}
                      {realizedPath && (
                        <path
                          d={realizedPath}
                          fill="none"
                          stroke="#34d399"
                          strokeWidth="2"
                        />
                      )}
                      {/* Realized points */}
                      {arcPoints
                        .filter((p) => p.realized_energy != null)
                        .map((p) => (
                          <circle
                            key={p.position}
                            cx={toX(p.normalized_pos)}
                            cy={toY(p.realized_energy!)}
                            r="4"
                            fill="#34d399"
                            stroke="#0e1218"
                            strokeWidth="1.5"
                          >
                            <title>
                              #{p.position + 1}: Energy {(p.realized_energy! * 100).toFixed(0)}% (target {(p.target_energy * 100).toFixed(0)}%)
                            </title>
                          </circle>
                        ))}
                    </svg>
                    {/* Accessible table alternative */}
                    <table className="sr-only">
                      <caption>Energy arc data: target vs realized energy by position</caption>
                      <thead>
                        <tr>
                          <th>Position</th>
                          <th>Target Energy</th>
                          <th>Realized Energy</th>
                          <th>Track</th>
                        </tr>
                      </thead>
                      <tbody>
                        {arcPoints.map((p) => (
                          <tr key={p.position}>
                            <td>{p.position + 1}</td>
                            <td>{(p.target_energy * 100).toFixed(0)}%</td>
                            <td>{p.realized_energy != null ? `${(p.realized_energy * 100).toFixed(0)}%` : "N/A"}</td>
                            <td>{p.track_id}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {/* Legend */}
                    <div className="flex items-center gap-4 mt-2 text-[10px] text-[#8c96a8]">
                      <div className="flex items-center gap-1.5">
                        <span className="w-4 h-0.5 bg-[#d4af37] opacity-70 inline-block" style={{ borderTop: "2px dashed #d4af37" }} />
                        <span>Target</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="w-4 h-0.5 bg-[#34d399] inline-block" />
                        <span>Realized</span>
                      </div>
                      <span className="ml-auto font-mono">
                        r = {result.arc_correlation.toFixed(2)}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* Flow Stats */}
              <div className="flex gap-3 flex-wrap">
                <div className="bg-[#141923] border border-[#232a3b] rounded-lg px-3 py-2 text-center">
                  <div className="text-[10px] text-[#8c96a8] uppercase">Transition Cost</div>
                  <div className="font-mono text-sm font-bold text-[#f1f3f7]">{result.mean_transition_cost.toFixed(3)}</div>
                </div>
                <div className="bg-[#141923] border border-[#232a3b] rounded-lg px-3 py-2 text-center">
                  <div className="text-[10px] text-[#8c96a8] uppercase">Arc Correlation</div>
                  <div className="font-mono text-sm font-bold text-[#34d399]">{result.arc_correlation.toFixed(2)}</div>
                </div>
                {result.dropped_features.length > 0 && (
                  <div className="bg-[#141923] border border-amber-800/40 rounded-lg px-3 py-2 text-center">
                    <div className="text-[10px] text-amber-400 uppercase">Dropped</div>
                    <div className="font-mono text-xs text-amber-300">{result.dropped_features.join(", ")}</div>
                  </div>
                )}
              </div>

              {/* Sequenced Track List */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-xs font-semibold text-[#8c96a8] uppercase tracking-wider flex items-center gap-1.5">
                    <Music className="w-3.5 h-3.5 text-[#d4af37]" />
                    Sequenced Tracks ({localTracks.length})
                  </h3>
                  <button
                    type="button"
                    onClick={() => setIsExportOpen(true)}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-[#1b2230] hover:bg-[#252f42] text-[#d4af37] border border-[#d4af37]/40 transition-colors focus:outline-none focus:ring-1 focus:ring-[#d4af37]"
                  >
                    <Download className="w-3.5 h-3.5" />
                    Export
                  </button>
                </div>
                <div className="space-y-1">
                  {localTracks.map((item, idx) => {
                    const energy = item.track.scalars?.energy;
                    const transition = result.transitions[idx - 1];
                    return (
                      <div key={item.track.id}>
                        {/* Transition indicator between tracks */}
                        {idx > 0 && transition && (
                          <div className="flex items-center gap-2 px-3 py-0.5 text-[9px] text-[#5a667d]">
                            <span className="flex-1 border-t border-dashed border-[#1d2331]" />
                            <span className="font-mono">
                              Δ {transition.cost.toFixed(3)}
                              {transition.energy_delta != null && ` | ΔE ${transition.energy_delta.toFixed(2)}`}
                            </span>
                            <span className="flex-1 border-t border-dashed border-[#1d2331]" />
                          </div>
                        )}
                        {/* Track row */}
                        <div className="flex items-center gap-2 bg-[#141923] border border-[#232a3b] rounded-lg px-3 py-2 group hover:border-[#38435d] transition-colors">
                          <span className="w-6 text-center font-mono text-[10px] font-bold text-[#5a667d]">
                            {idx + 1}
                          </span>
                          <div className="relative w-7 h-7 rounded bg-[#1c2230] border border-[#2a3449] flex items-center justify-center text-[#d4af37] flex-shrink-0 overflow-hidden shadow-sm">
                            <Music className="w-3.5 h-3.5 text-[#d4af37]/70" />
                            {item.track.artwork_url ? (
                              <img
                                src={item.track.artwork_url}
                                alt=""
                                className="absolute inset-0 w-full h-full object-cover rounded"
                                onError={(e) => {
                                  e.currentTarget.style.display = "none";
                                }}
                              />
                            ) : null}
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="text-xs font-semibold text-[#f1f3f7] truncate">
                              {item.track.title}
                            </div>
                            <div className="text-[10px] text-[#8c96a8] truncate">
                              {item.track.artist_name}
                            </div>
                          </div>
                          {energy != null && (
                            <span className="text-[10px] font-mono text-[#8c96a8] bg-[#10141d] px-1.5 py-0.5 rounded border border-[#1f2637]">
                              E {(energy * 100).toFixed(0)}%
                            </span>
                          )}
                          {/* Reorder + Remove controls */}
                          <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
                            <button
                              type="button"
                              onClick={() => moveTrack(idx, "up")}
                              disabled={idx === 0}
                              aria-label={`Move ${item.track.title} up in sequence`}
                              className="p-1 rounded text-[#8c96a8] hover:text-[#f1f3f7] hover:bg-[#1b2230] disabled:opacity-30 transition-colors focus:outline-none focus:ring-1 focus:ring-[#d4af37]"
                            >
                              <ArrowUp className="w-3 h-3" />
                            </button>
                            <button
                              type="button"
                              onClick={() => moveTrack(idx, "down")}
                              disabled={idx === localTracks.length - 1}
                              aria-label={`Move ${item.track.title} down in sequence`}
                              className="p-1 rounded text-[#8c96a8] hover:text-[#f1f3f7] hover:bg-[#1b2230] disabled:opacity-30 transition-colors focus:outline-none focus:ring-1 focus:ring-[#d4af37]"
                            >
                              <ArrowDown className="w-3 h-3" />
                            </button>
                            <button
                              type="button"
                              onClick={() => removeTrack(item.track.id)}
                              aria-label={`Remove ${item.track.title} from playlist`}
                              className="p-1 rounded text-[#8c96a8] hover:text-rose-400 hover:bg-[#1b2230] transition-colors focus:outline-none focus:ring-1 focus:ring-rose-400"
                            >
                              <X className="w-3 h-3" />
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      <ExportModal
        isOpen={isExportOpen}
        onClose={() => setIsExportOpen(false)}
        tracks={localTracks}
        playlistName={`Melovia - ${ARC_INFO[selectedArc].label} Arc`}
        apiBase={apiBase}
      />
    </>
  );
}
