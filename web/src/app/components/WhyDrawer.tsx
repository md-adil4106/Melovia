"use client";

import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  CheckCircle2,
  Compass,
  Disc,
  Info,
  Music,
  Radio,
  Sparkles,
  Tag,
  Volume2,
  X,
} from "lucide-react";
import { Track, WhyExplanationData } from "../store";

interface WhyDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  track: Track | null;
  candidateSetId: string | null;
  apiBase: string;
}

export function WhyDrawer({
  isOpen,
  onClose,
  track,
  candidateSetId,
  apiBase,
}: WhyDrawerProps) {
  const drawerRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  // Focus trap and Escape listener
  useEffect(() => {
    if (!isOpen) return;

    // Focus close button on open
    setTimeout(() => {
      closeButtonRef.current?.focus();
    }, 50);

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }

      if (e.key === "Tab" && drawerRef.current) {
        const focusableElements = drawerRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        const first = focusableElements[0];
        const last = focusableElements[focusableElements.length - 1];

        if (e.shiftKey) {
          if (document.activeElement === first) {
            e.preventDefault();
            last?.focus();
          }
        } else {
          if (document.activeElement === last) {
            e.preventDefault();
            first?.focus();
          }
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  // Query explanation from API
  const { data, isLoading, isError } = useQuery<WhyExplanationData>({
    queryKey: ["whyExplanation", candidateSetId, track?.id],
    queryFn: async () => {
      if (!candidateSetId || !track) throw new Error("Missing parameters");
      const res = await fetch(
        `${apiBase}/recommendations/${candidateSetId}/items/${track.id}/why`
      );
      if (!res.ok) {
        throw new Error("Failed to load explanation");
      }
      return await res.json();
    },
    enabled: isOpen && !!candidateSetId && !!track,
  });

  if (!isOpen || !track) return null;

  const signals = data?.signals;
  const pctT = signals?.pct_t !== undefined ? Math.round(signals.pct_t * 100) : null;
  const pctA = signals?.pct_a !== undefined && signals.pct_a !== null ? Math.round(signals.pct_a * 100) : null;
  const novPct = signals?.novelty !== undefined ? Math.round(signals.novelty * 100) : null;
  const popPct = signals?.popularity_pct !== undefined ? Math.round(signals.popularity_pct) : Math.round(track.popularity_pct);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="why-drawer-title"
      data-testid="why-drawer"
      className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm transition-opacity duration-300"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={drawerRef}
        className="w-full max-w-lg bg-[#07080b]/95 backdrop-blur-2xl border-l border-white/10 h-full overflow-y-auto shadow-2xl flex flex-col justify-between animate-in slide-in-from-right duration-300"
      >
        {/* Drawer Header */}
        <div className="p-6 border-b border-white/10 bg-white/[0.03] sticky top-0 z-10 backdrop-blur-xl">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-3.5 min-w-0">
              <div className="relative w-12 h-12 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-[#fa2d55] flex-shrink-0 overflow-hidden shadow-md">
                <Music className="w-5 h-5 text-[#fa2d55]/70" />
                {track.artwork_url ? (
                  <img
                    src={track.artwork_url}
                    alt=""
                    className="absolute inset-0 w-full h-full object-cover rounded-xl"
                    onError={(e) => {
                      e.currentTarget.style.display = "none";
                    }}
                  />
                ) : null}
              </div>
              <div className="min-w-0">
                <span className="text-[11px] font-mono uppercase tracking-wider text-[#fa2d55] font-semibold flex items-center gap-1.5 mb-1">
                  <Sparkles className="w-3.5 h-3.5" />
                  Recommendation Signals
                </span>
                <h3
                  id="why-drawer-title"
                  className="text-lg font-bold text-white truncate font-sans"
                >
                  Why &quot;{track.title}&quot;?
                </h3>
                <p className="text-xs text-white/60 truncate">
                  by {track.artist_name} {track.year ? `• ${track.year}` : ""}
                </p>
              </div>
            </div>
            <button
              ref={closeButtonRef}
              onClick={onClose}
              data-testid="why-drawer-close"
              aria-label="Close why explanation"
              className="p-1.5 rounded-full text-white/60 hover:text-white hover:bg-white/10 transition-colors focus:outline-none focus:ring-2 focus:ring-[#fa2d55]"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Drawer Body */}
        <div className="p-6 space-y-6 flex-1">
          {/* Loading State */}
          {isLoading && (
            <div className="space-y-4 animate-pulse">
              <div className="h-4 bg-[#1b2230] rounded w-3/4" />
              <div className="h-20 bg-[#161c27] rounded-xl" />
              <div className="h-20 bg-[#161c27] rounded-xl" />
              <div className="h-32 bg-[#161c27] rounded-xl" />
            </div>
          )}

          {/* Error State */}
          {isError && (
            <div className="p-4 rounded-xl bg-red-950/30 border border-red-800/40 text-red-300 text-xs">
              Unable to load real-time explanation for this track. Please check that the candidate pool is active.
            </div>
          )}

          {/* Reasons List */}
          {!isLoading && data && (
            <>
              <div className="space-y-3">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-[#9aa4b8]">
                  Key Ranking Factors ({data.reasons?.length || 0})
                </h4>

                <div className="space-y-2.5">
                  {(data.reasons || []).map((reason, idx) => (
                    <div
                      key={reason.id || idx}
                      className="bg-white/[0.03] border border-white/[0.07] rounded-xl p-3.5 flex items-start gap-3 hover:border-white/15 transition-colors"
                    >
                      <div className="p-1.5 rounded-lg bg-[#fa2d55]/15 text-[#fa2d55] flex-shrink-0 mt-0.5">
                        {reason.id.includes("TAG") ? (
                          <Tag className="w-3.5 h-3.5" />
                        ) : reason.id.includes("ACOUSTIC") ? (
                          <Volume2 className="w-3.5 h-3.5" />
                        ) : reason.id.includes("ENERGY") || reason.id.includes("VALENCE") ? (
                          <Activity className="w-3.5 h-3.5" />
                        ) : reason.id.includes("ARTIST") ? (
                          <Disc className="w-3.5 h-3.5" />
                        ) : reason.id.includes("REGION") ? (
                          <Radio className="w-3.5 h-3.5" />
                        ) : (
                          <CheckCircle2 className="w-3.5 h-3.5" />
                        )}
                      </div>
                      <div className="space-y-1 min-w-0">
                        <p className="text-xs font-medium text-white/90 leading-relaxed">
                          {reason.text}
                        </p>
                        <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
                          {reason.signal_keys.map((key) => (
                            <span
                              key={key}
                              className="text-[9px] font-mono px-2 py-0.5 rounded-full bg-white/[0.04] border border-white/10 text-white/60"
                            >
                              {key}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Signal Bars */}
              <div className="space-y-4 pt-2">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-white/60">
                  Signal Strength Breakdown
                </h4>

                {/* Semantic Taste Channel */}
                <div className="bg-white/[0.03] border border-white/[0.07] rounded-xl p-3.5 space-y-2">
                  <div className="flex justify-between items-center text-xs">
                    <span className="font-medium text-white/90 flex items-center gap-1.5">
                      <Tag className="w-3.5 h-3.5 text-[#38bdf8]" />
                      Semantic Taste Alignment (t)
                    </span>
                    <span className="font-mono font-bold text-[#38bdf8]">
                      {pctT !== null ? `${pctT}%` : "—"}
                    </span>
                  </div>
                  <div className="w-full h-1.5 bg-white/10 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-[#38bdf8] rounded-full transition-all duration-500"
                      style={{ width: `${pctT || 0}%` }}
                    />
                  </div>
                  <p className="text-[11px] text-white/50">
                    Percentile match with your seed genres and community folksonomy tags.
                  </p>
                </div>

                {/* Acoustic Texture Channel */}
                <div className="bg-white/[0.03] border border-white/[0.07] rounded-xl p-3.5 space-y-2">
                  <div className="flex justify-between items-center text-xs">
                    <span className="font-medium text-white/90 flex items-center gap-1.5">
                      <Volume2 className="w-3.5 h-3.5 text-emerald-400" />
                      Acoustic Texture Match (a)
                    </span>
                    <span className="font-mono font-bold text-emerald-400">
                      {pctA !== null ? `${pctA}%` : "No Audio"}
                    </span>
                  </div>
                  <div className="w-full h-1.5 bg-white/10 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-emerald-400 rounded-full transition-all duration-500"
                      style={{ width: `${pctA || 0}%` }}
                    />
                  </div>
                  <p className="text-[11px] text-white/50">
                    {pctA !== null
                      ? "AcousticBrainz features matching tempo, energy, and harmonic timbre."
                      : "Acoustic analysis is unavailable for this track; weights were dynamically renormalized to semantic taste."}
                  </p>
                </div>

                {/* Novelty / Familiarity */}
                <div className="bg-white/[0.03] border border-white/[0.07] rounded-xl p-3.5 space-y-2">
                  <div className="flex justify-between items-center text-xs">
                    <span className="font-medium text-white/90 flex items-center gap-1.5">
                      <Compass className="w-3.5 h-3.5 text-[#fb7185]" />
                      Discovery Novelty
                    </span>
                    <span className="font-mono font-bold text-[#fb7185]">
                      {novPct !== null ? `${novPct}%` : "—"}
                    </span>
                  </div>
                  <div className="w-full h-1.5 bg-white/10 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-[#fa2d55] to-[#fb7185] rounded-full transition-all duration-500"
                      style={{ width: `${novPct || 0}%` }}
                    />
                  </div>
                  <p className="text-[11px] text-white/50">
                    Information-theoretic novelty measuring exploration of less familiar catalog territories.
                  </p>
                </div>

                {/* Popularity */}
                <div className="bg-white/[0.03] border border-white/[0.07] rounded-xl p-3.5 space-y-2">
                  <div className="flex justify-between items-center text-xs">
                    <span className="font-medium text-white/90 flex items-center gap-1.5">
                      <Disc className="w-3.5 h-3.5 text-purple-400" />
                      Catalog Exposure / Popularity
                    </span>
                    <span className="font-mono font-bold text-purple-400">
                      {popPct}%
                    </span>
                  </div>
                  <div className="w-full h-1.5 bg-white/10 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-purple-400 rounded-full transition-all duration-500"
                      style={{ width: `${popPct}%` }}
                    />
                  </div>
                  <p className="text-[11px] text-white/50">
                    Percentile standing in overall catalog exposure (lower indicates underground appeal).
                  </p>
                </div>
              </div>

              {/* Approximate Proxy Disclaimer */}
              <div className="flex items-start gap-2 text-[11px] text-white/50 p-3 rounded-xl bg-white/[0.02] border border-white/10">
                <Info className="w-3.5 h-3.5 text-white/60 flex-shrink-0 mt-0.5" />
                <span>
                  Reasons mentioning energy or emotional mood are based on composite heuristic proxies (energy_idx, valence_idx) and are indicated as approximate.
                </span>
              </div>
            </>
          )}
        </div>

        {/* Drawer Footer */}
        <div className="p-4 border-t border-white/10 bg-white/[0.02] flex justify-end backdrop-blur-xl">
          <button
            onClick={onClose}
            className="px-5 py-2 rounded-full bg-white/[0.08] hover:bg-white/[0.15] text-xs font-semibold text-white transition-all focus:outline-none focus:ring-2 focus:ring-[#fa2d55]"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
