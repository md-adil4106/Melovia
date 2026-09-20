"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  Compass,
  Headphones,
  HelpCircle,
  MessageSquare,
  Music,
  Plus,
  RefreshCw,
  Search,
  Sliders,
  Sparkles,
  Volume2,
  X,
} from "lucide-react";
import { Track, RecommendedItem, useDiscoveryStore } from "./store";
import { WhyDrawer } from "./components/WhyDrawer";
import { ChatDrawer } from "./components/ChatDrawer";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function DiscoveryHome() {
  const {
    seeds,
    addSeed,
    removeSeed,
    clearSeeds,
    recommendations,
    setRecommendations,
    candidateSetId,
    setCandidateSetId,
    discovery,
    setDiscovery,
    appliedConstraints,
    removeAppliedConstraint,
    isChatDrawerOpen,
    setChatDrawerOpen,
  } = useDiscoveryStore();

  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const [sliderValue, setSliderValue] = useState(discovery);
  const [selectedTrackForWhy, setSelectedTrackForWhy] = useState<Track | null>(null);
  const [isWhyDrawerOpen, setIsWhyDrawerOpen] = useState(false);

  const handleOpenWhy = (track: Track) => {
    setSelectedTrackForWhy(track);
    setIsWhyDrawerOpen(true);
  };

  const handleDeleteConstraint = async (constraintId: string) => {
    if (!candidateSetId) return;
    try {
      const res = await fetch(
        `${API_BASE}/refine/${encodeURIComponent(constraintId)}?candidate_set_id=${encodeURIComponent(candidateSetId)}`,
        {
          method: "DELETE",
          credentials: "include",
        }
      );
      if (res.ok) {
        const data = await res.json();
        setRecommendations(data.items || []);
        removeAppliedConstraint(constraintId);
      }
    } catch {
      // fallback
    }
  };

  const searchInputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Sync local slider when store discovery changes externally
  useEffect(() => {
    setSliderValue(discovery);
  }, [discovery]);

  // Debounce search query by 250ms
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchQuery.trim());
    }, 250);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Query track search
  const {
    data: searchResults,
    isLoading: isSearchLoading,
  } = useQuery({
    queryKey: ["trackSearch", debouncedQuery],
    queryFn: async () => {
      if (!debouncedQuery) return [];
      const res = await fetch(`${API_BASE}/tracks/search?q=${encodeURIComponent(debouncedQuery)}&limit=8`);
      if (!res.ok) throw new Error("Failed to search tracks");
      const data = await res.json();
      return (data.items || []) as Track[];
    },
    enabled: debouncedQuery.length >= 2,
  });

  // Query system health
  const { data: healthData } = useQuery({
    queryKey: ["healthCheck"],
    queryFn: async () => {
      try {
        const res = await fetch(`${API_BASE}/health`);
        if (!res.ok) return null;
        return await res.json();
      } catch {
        return null;
      }
    },
    refetchInterval: 30000,
  });

  // Mutation for generating fresh recommendations
  const recommendMutation = useMutation({
    mutationFn: async ({ seedIds, d }: { seedIds: string[]; d: number }) => {
      const res = await fetch(`${API_BASE}/recommendations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          seed_track_ids: seedIds,
          n: 30,
          discovery: d,
          include_signals: true,
        }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData?.error?.message || "Failed to generate recommendations");
      }
      return await res.json();
    },
    onSuccess: (data) => {
      setRecommendations(data.items || []);
      setCandidateSetId(data.candidate_set_id);
    },
  });

  // Mutation for fast interactive reranking using cached candidate pool
  const rerankMutation = useMutation({
    mutationFn: async ({
      candidate_set_id,
      d,
      n = 30,
    }: {
      candidate_set_id: string;
      d: number;
      n?: number;
    }) => {
      const res = await fetch(`${API_BASE}/recommendations/rerank`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          candidate_set_id,
          discovery: d,
          n,
          include_signals: true,
        }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        if (res.status === 404 && errData?.error?.code === "CANDIDATE_SET_EXPIRED") {
          throw new Error("EXPIRED");
        }
        throw new Error(errData?.error?.message || "Failed to rerank recommendations");
      }
      return await res.json();
    },
    onSuccess: (data) => {
      setRecommendations(data.items || []);
    },
    onError: (err: Error) => {
      // If cached candidate set expired, automatically fallback to full recommendation generation
      if (err.message === "EXPIRED" && seeds.length > 0) {
        recommendMutation.mutate({
          seedIds: seeds.map((s) => s.id),
          d: sliderValue,
        });
      }
    },
  });

  // Debounce slider dragging by 120ms to fire rerank without UI stutter
  useEffect(() => {
    if (!candidateSetId || recommendations.length === 0) return;

    const timer = setTimeout(() => {
      if (Math.abs(sliderValue - discovery) > 0.001) {
        setDiscovery(sliderValue);
        rerankMutation.mutate({
          candidate_set_id: candidateSetId,
          d: sliderValue,
          n: 30,
        });
      }
    }, 120);

    return () => clearTimeout(timer);
  }, [sliderValue, candidateSetId, recommendations.length, discovery, setDiscovery, rerankMutation]);

  const handleSelectTrack = (track: Track) => {
    const added = addSeed(track);
    if (added) {
      setSearchQuery("");
      setDebouncedQuery("");
      setIsDropdownOpen(false);
      setHighlightedIndex(-1);
      searchInputRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!searchResults || searchResults.length === 0) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightedIndex((prev) => (prev < searchResults.length - 1 ? prev + 1 : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : searchResults.length - 1));
    } else if (e.key === "Enter" && highlightedIndex >= 0) {
      e.preventDefault();
      handleSelectTrack(searchResults[highlightedIndex]);
    } else if (e.key === "Escape") {
      setIsDropdownOpen(false);
    }
  };

  const handleDiscover = () => {
    if (seeds.length === 0) return;
    recommendMutation.mutate({
      seedIds: seeds.map((s) => s.id),
      d: sliderValue,
    });
  };

  // Close search dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node) &&
        !searchInputRef.current?.contains(event.target as Node)
      ) {
        setIsDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const isAnyLoading = recommendMutation.isPending || rerankMutation.isPending;

  return (
    <main className="min-h-screen bg-[#0d0f14] text-[#f1f3f7] font-sans pb-20">
      {/* Top Header */}
      <header className="border-b border-[#212631] bg-[#12161f]/80 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#d4af37] to-[#8c6d1f] flex items-center justify-center text-black font-bold shadow-md">
              <Compass className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-wider font-serif-display text-[#f5ecd5]">
                MELOVIA
              </h1>
              <p className="text-xs text-[#8c96a8]">Explainable Music Discovery</p>
            </div>
          </div>

          {/* Backend Status Indicator */}
          <div className="flex items-center gap-2 text-xs">
            {healthData ? (
              <span className="flex items-center gap-1.5 text-emerald-400 bg-emerald-950/40 border border-emerald-800/50 px-2.5 py-1 rounded-full">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Catalog {healthData.catalog?.version || "ready"} ({healthData.catalog?.track_count?.toLocaleString() || 0} tracks)
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-amber-400 bg-amber-950/40 border border-amber-800/50 px-2.5 py-1 rounded-full">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                Connecting...
              </span>
            )}
          </div>
        </div>
      </header>

      {/* Main Container */}
      <div className="max-w-4xl mx-auto px-4 pt-8">
        {/* Hero Section */}
        <section className="text-center mb-8">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#1b212d] border border-[#2b3345] text-xs text-[#d4af37] mb-3">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Interactive Discovery Control (WOW #1)</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-[#f1f3f7] tracking-tight mb-2 font-serif-display">
            Steerable Discovery from Seed Tracks
          </h2>
          <p className="text-sm sm:text-base text-[#8c96a8] max-w-xl mx-auto">
            Choose 1 to 10 seed tracks, then dynamically tune the Familiarity ↔ Discovery slider to traverse from familiar sounds to exploratory musical horizons.
          </p>
        </section>

        {/* Seed Search & Input Box */}
        <section className="bg-[#141923] border border-[#232a3b] rounded-2xl p-6 mb-6 shadow-xl relative">
          <div className="flex items-center justify-between mb-3">
            <label htmlFor="seed-search" className="text-sm font-semibold text-[#c8d0de] flex items-center gap-2">
              <Search className="w-4 h-4 text-[#d4af37]" />
              Search Seed Tracks
            </label>
            <span className="text-xs text-[#8c96a8]">
              <strong className="text-[#d4af37]">{seeds.length}</strong> / 10 seeds selected
            </span>
          </div>

          {/* Search Input Field */}
          <div className="relative">
            <input
              id="seed-search"
              ref={searchInputRef}
              type="text"
              placeholder={
                seeds.length >= 10
                  ? "Maximum of 10 seeds reached"
                  : "Type track title or artist name (e.g. Bohemian Rhapsody, Daft Punk)..."
              }
              disabled={seeds.length >= 10}
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setIsDropdownOpen(true);
              }}
              onFocus={() => setIsDropdownOpen(true)}
              onKeyDown={handleKeyDown}
              className="w-full bg-[#0d1017] border border-[#262e40] rounded-xl px-4 py-3 text-sm text-[#f1f3f7] placeholder-[#5a657a] focus:outline-none focus:ring-2 focus:ring-[#d4af37]/60 focus:border-transparent transition-all disabled:opacity-50"
            />

            {isSearchLoading && (
              <div className="absolute right-3 top-3 text-xs text-[#8c96a8] animate-spin">
                <RefreshCw className="w-5 h-5" />
              </div>
            )}

            {/* Dropdown Suggestions */}
            {isDropdownOpen && searchResults && searchResults.length > 0 && (
              <div
                ref={dropdownRef}
                className="absolute left-0 right-0 top-full mt-2 bg-[#12161f] border border-[#2a3347] rounded-xl shadow-2xl z-50 overflow-hidden max-h-72 overflow-y-auto"
              >
                <div className="p-1.5 divide-y divide-[#1e2535]">
                  {searchResults.map((t, idx) => {
                    const isAlreadySeed = seeds.some((s) => s.id === t.id);
                    const isHighlighted = idx === highlightedIndex;
                    return (
                      <button
                        key={t.id}
                        type="button"
                        onClick={() => handleSelectTrack(t)}
                        disabled={isAlreadySeed}
                        className={`w-full text-left px-3 py-2.5 rounded-lg flex items-center justify-between transition-colors ${
                          isHighlighted ? "bg-[#1f2738]" : "hover:bg-[#181f2d]"
                        } ${isAlreadySeed ? "opacity-40 cursor-not-allowed" : ""}`}
                      >
                        <div className="min-w-0 pr-3">
                          <p className="text-sm font-medium text-[#f1f3f7] truncate">{t.title}</p>
                          <p className="text-xs text-[#8c96a8] truncate">
                            {t.artist_name} {t.year ? `• ${t.year}` : ""}
                          </p>
                        </div>
                        <div className="flex items-center gap-1.5 text-xs text-[#d4af37]">
                          {isAlreadySeed ? (
                            <span className="text-[#647187]">Selected</span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-xs bg-[#242b3a] px-2 py-0.5 rounded text-[#c8d0de]">
                              <Plus className="w-3 h-3 text-[#d4af37]" /> Add
                            </span>
                          )}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Seed Chips */}
          <div className="mt-4 pt-4 border-t border-[#1d2331]">
            {seeds.length === 0 ? (
              <p className="text-xs text-[#626e85] italic">
                No seed tracks selected yet. Search above to add seeds.
              </p>
            ) : (
              <div className="flex flex-wrap items-center gap-2">
                {seeds.map((s) => (
                  <div
                    key={s.id}
                    className="inline-flex items-center gap-2 bg-[#1b2230] border border-[#2b354a] rounded-lg px-3 py-1.5 text-xs text-[#f1f3f7] shadow-sm animate-in fade-in duration-200"
                  >
                    <Music className="w-3.5 h-3.5 text-[#d4af37]" />
                    <span className="font-medium max-w-[160px] truncate">{s.title}</span>
                    <span className="text-[#8c96a8] max-w-[100px] truncate">({s.artist_name})</span>
                    <button
                      type="button"
                      onClick={() => removeSeed(s.id)}
                      aria-label={`Remove ${s.title} by ${s.artist_name}`}
                      className="text-[#8c96a8] hover:text-rose-400 p-0.5 rounded transition-colors focus:outline-none focus:ring-1 focus:ring-rose-400"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}

                <button
                  type="button"
                  onClick={clearSeeds}
                  className="text-xs text-[#717d94] hover:text-rose-400 ml-auto transition-colors underline"
                >
                  Clear all
                </button>
              </div>
            )}
          </div>

          {/* Action Row */}
          <div className="mt-6 flex items-center justify-between">
            <div className="text-xs text-[#8c96a8] flex items-center gap-1.5">
              <Sliders className="w-3.5 h-3.5 text-[#d4af37]" />
              Dual-Channel + MMR Diversity
            </div>

            <button
              type="button"
              onClick={handleDiscover}
              disabled={seeds.length === 0 || recommendMutation.isPending}
              className="inline-flex items-center gap-2 bg-gradient-to-r from-[#d4af37] to-[#b38e24] hover:from-[#e2bf48] hover:to-[#c49e2f] text-black font-bold px-6 py-2.5 rounded-xl shadow-lg transition-all transform active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed disabled:transform-none"
            >
              {recommendMutation.isPending ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Generating...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>Discover Tracks</span>
                </>
              )}
            </button>
          </div>
        </section>

        {/* Error Notification */}
        {(recommendMutation.isError || rerankMutation.isError) && (
          <div className="bg-rose-950/40 border border-rose-800/60 rounded-xl p-4 mb-6 text-rose-200 text-sm flex items-start gap-3">
            <div className="p-1 rounded bg-rose-900/60 text-rose-300">
              <X className="w-4 h-4" />
            </div>
            <div>
              <h4 className="font-semibold">Discovery Error</h4>
              <p className="text-xs text-rose-300 mt-0.5">
                {(recommendMutation.error as Error)?.message ||
                  (rerankMutation.error as Error)?.message ||
                  "An unexpected error occurred."}
              </p>
            </div>
          </div>
        )}

        {/* Sticky Discovery Control Slider Bar (Above Results) */}
        {recommendations.length > 0 && (
          <div className="sticky top-[57px] z-30 bg-[#12161f]/95 backdrop-blur-md border border-[#2b354a] rounded-xl p-4 mb-6 shadow-2xl transition-all">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Sliders className="w-4 h-4 text-[#d4af37]" />
                <span className="text-xs font-semibold text-[#f1f3f7] uppercase tracking-wider">
                  Discovery Control (Familiarity ↔ Discovery)
                </span>
                {rerankMutation.isPending && (
                  <span className="flex items-center gap-1 text-[11px] text-[#d4af37] animate-pulse">
                    <RefreshCw className="w-3 h-3 animate-spin" />
                    Reranking...
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setChatDrawerOpen(true)}
                  className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold bg-purple-600/20 border border-purple-500/40 text-purple-300 hover:bg-purple-600/30 hover:border-purple-500/60 transition-colors focus:outline-none focus:ring-2 focus:ring-purple-400"
                  aria-label="Open steer discovery chat drawer"
                >
                  <MessageSquare className="w-3.5 h-3.5 text-purple-400" />
                  <span>Steer Vibe</span>
                  {appliedConstraints.length > 0 && (
                    <span className="ml-0.5 px-1.5 py-0.2 rounded-full bg-purple-500 text-white text-[10px] font-bold">
                      {appliedConstraints.length}
                    </span>
                  )}
                </button>

                <span className="text-xs text-[#8c96a8]">Discovery:</span>
                <span
                  data-testid="discovery-pct-badge"
                  className="font-mono text-xs font-bold text-[#d4af37] bg-[#1a202c] border border-[#2d3748] px-2 py-0.5 rounded"
                >
                  {Math.round(sliderValue * 100)}%
                </span>
              </div>
            </div>

            {/* Slider Input */}
            <div className="space-y-1.5">
              <input
                type="range"
                id="discovery-slider"
                data-testid="discovery-slider"
                min="0"
                max="1"
                step="0.05"
                value={sliderValue}
                onChange={(e) => setSliderValue(parseFloat(e.target.value))}
                onKeyDown={(e) => {
                  if (e.key === "Home") setSliderValue(0.0);
                  else if (e.key === "End") setSliderValue(1.0);
                }}
                aria-label="Discovery level"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={Math.round(sliderValue * 100)}
                aria-valuetext={`Discovery level ${Math.round(sliderValue * 100)}%`}
                className="w-full h-2 bg-[#1b2230] rounded-lg appearance-none cursor-pointer accent-[#d4af37] focus:outline-none focus:ring-2 focus:ring-[#d4af37]/60"
              />

              <div className="flex justify-between items-center text-[11px] text-[#8c96a8]">
                <span className="flex items-center gap-1 text-emerald-400/90 font-medium">
                  ← Familiarity (0%)
                </span>
                <span className="text-[#64748b]">Balanced (50%)</span>
                <span className="flex items-center gap-1 text-amber-400/90 font-medium">
                  Discovery (100%) →
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Active Applied Session Constraints Banner */}
        {appliedConstraints.length > 0 && (
          <div className="flex items-center gap-2 mb-4 flex-wrap p-3 rounded-xl bg-purple-950/30 border border-purple-800/40 shadow-sm animate-in fade-in">
            <span className="text-xs font-semibold text-purple-300 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-purple-400" />
              Session Steering:
            </span>
            {appliedConstraints.map((c) => (
              <span
                key={c.id}
                className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-lg text-xs font-medium bg-zinc-900 text-zinc-200 border border-purple-500/30 shadow-sm"
              >
                <span className="text-purple-400 font-mono text-[10px] uppercase">
                  {c.type}:
                </span>
                <span>{c.description}</span>
                <button
                  type="button"
                  onClick={() => handleDeleteConstraint(c.id)}
                  className="text-zinc-400 hover:text-red-400 p-0.5 rounded transition-colors"
                  aria-label={`Remove constraint ${c.description}`}
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
            <button
              type="button"
              onClick={() => setChatDrawerOpen(true)}
              className="text-xs text-purple-400 hover:text-purple-300 underline ml-auto font-medium transition-colors"
            >
              Modify in Chat →
            </button>
          </div>
        )}

        {/* Results Section */}
        <section className="mb-16">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-bold text-[#f1f3f7] flex items-center gap-2 font-serif-display">
              <Headphones className="w-5 h-5 text-[#d4af37]" />
              Recommended Tracks
            </h3>
            {recommendations.length > 0 && (
              <span className="text-xs text-[#8c96a8] bg-[#141923] px-2.5 py-1 rounded-full border border-[#232a3b]">
                {recommendations.length} recommendations ranked
              </span>
            )}
          </div>

          {/* Skeleton Loading State */}
          {recommendMutation.isPending && (
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <div
                  key={i}
                  className="bg-[#141923] border border-[#202738] rounded-xl p-4 flex items-center justify-between animate-pulse"
                >
                  <div className="flex items-center gap-4">
                    <div className="w-8 h-8 rounded-lg bg-[#20283b]" />
                    <div className="space-y-2">
                      <div className="w-48 h-4 bg-[#20283b] rounded" />
                      <div className="w-32 h-3 bg-[#192030] rounded" />
                    </div>
                  </div>
                  <div className="w-16 h-6 bg-[#20283b] rounded-full" />
                </div>
              ))}
            </div>
          )}

          {/* Empty State */}
          {!recommendMutation.isPending && recommendations.length === 0 && (
            <div className="border border-dashed border-[#232b3d] rounded-2xl p-12 text-center bg-[#10141d]/50">
              <Compass className="w-12 h-12 mx-auto text-[#424d63] mb-3" />
              <h4 className="text-base font-semibold text-[#c8d0de] mb-1">Your discovery feed is empty</h4>
              <p className="text-xs text-[#8c96a8] max-w-sm mx-auto">
                Search and select at least one seed track above, then click &quot;Discover Tracks&quot; to compute relevance-ranked music.
              </p>
            </div>
          )}

          {/* Recommendation Items List with animated reordering & novelty ticks */}
          {!recommendMutation.isPending && recommendations.length > 0 && (
            <div className="space-y-3">
              {recommendations.map((item: RecommendedItem, idx: number) => {
                const matchPct = Math.round(item.score * 100);
                const novPct = item.signals?.novelty !== undefined ? Math.round(item.signals.novelty * 100) : null;
                const isHighNovelty = (item.signals?.novelty ?? 0) >= 0.5;
                const isModerateNovelty = (item.signals?.novelty ?? 0) >= 0.25;

                return (
                  <article
                    key={item.track.id}
                    className="bg-[#141923] border border-[#232a3b] hover:border-[#38435d] rounded-xl p-4 transition-all duration-300 ease-out motion-reduce:transition-none hover:bg-[#161c28] flex flex-col sm:flex-row sm:items-center justify-between gap-4 group"
                  >
                    <div className="flex items-center gap-3.5 min-w-0">
                      <span className="w-7 text-center font-mono text-xs font-semibold text-[#5a667d]">
                        #{idx + 1}
                      </span>
                      <div className="w-9 h-9 rounded-lg bg-[#1c2230] border border-[#2a3449] flex items-center justify-center text-[#d4af37] flex-shrink-0">
                        <Volume2 className="w-4 h-4" />
                      </div>
                      <div className="min-w-0">
                        <h4 className="text-sm font-semibold text-[#f1f3f7] truncate group-hover:text-[#d4af37] transition-colors">
                          {item.track.title}
                        </h4>
                        <p className="text-xs text-[#8c96a8] truncate">
                          {item.track.artist_name} {item.track.year ? `• ${item.track.year}` : ""}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center justify-between sm:justify-end gap-2.5 pl-10 sm:pl-0 flex-wrap">
                      {/* Subtle Familiarity <-> Discovery Tick Indicator */}
                      {novPct !== null && (
                        <div
                          className="flex items-center gap-1.5 text-[10px] font-mono px-2 py-0.5 rounded bg-[#10141d] border border-[#222a3b]"
                          title={`Novelty: ${novPct}% | Familiarity: ${100 - novPct}%`}
                        >
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${
                              isHighNovelty
                                ? "bg-[#e2bf48]"
                                : isModerateNovelty
                                ? "bg-[#38bdf8]"
                                : "bg-[#34d399]"
                            }`}
                          />
                          <span className="text-[#8c96a8]">
                            {isHighNovelty ? "Discovery" : isModerateNovelty ? "Balanced" : "Familiar"}
                          </span>
                          <span className="text-[#606d84]">{novPct}%</span>
                        </div>
                      )}

                      {/* Audio channel badge */}
                      {item.track.has_a ? (
                        <span className="text-[10px] text-emerald-400 bg-emerald-950/40 border border-emerald-800/40 px-2 py-0.5 rounded font-mono">
                          Audio
                        </span>
                      ) : (
                        <span className="text-[10px] text-zinc-500 bg-zinc-900 border border-zinc-800 px-2 py-0.5 rounded font-mono">
                          No Audio
                        </span>
                      )}

                      {/* Match Score Badge */}
                      <div className="flex items-center gap-2 bg-[#1b2230] border border-[#2b354a] px-2.5 py-1 rounded-lg">
                        <span className="text-xs font-mono font-bold text-[#d4af37]">
                          {matchPct}%
                        </span>
                        <span className="text-[10px] text-[#8c96a8]">match</span>
                      </div>

                      {/* Why Explanation Button */}
                      <button
                        type="button"
                        onClick={() => handleOpenWhy(item.track)}
                        data-testid={`why-button-${item.track.id}`}
                        aria-label={`Why was ${item.track.title} recommended?`}
                        className="inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg bg-[#1b2230] border border-[#2b354a] hover:border-[#d4af37]/60 text-[#c8d0de] hover:text-[#d4af37] transition-colors focus:outline-none focus:ring-2 focus:ring-[#d4af37]"
                      >
                        <HelpCircle className="w-3.5 h-3.5 text-[#d4af37]" />
                        <span>Why?</span>
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </div>

      {/* Accessible Explainability Drawer */}
      <WhyDrawer
        isOpen={isWhyDrawerOpen}
        onClose={() => setIsWhyDrawerOpen(false)}
        track={selectedTrackForWhy}
        candidateSetId={candidateSetId}
        apiBase={API_BASE}
      />

      {/* Accessible Natural Language Steering Drawer (WOW #4) */}
      <ChatDrawer
        isOpen={isChatDrawerOpen}
        onClose={() => setChatDrawerOpen(false)}
        apiBase={API_BASE}
      />
    </main>
  );
}
