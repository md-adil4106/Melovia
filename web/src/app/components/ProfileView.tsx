"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Sparkles,
  Compass,
  Info,
  Layers,
  ArrowRight,
  TrendingUp,
  RefreshCw,
  ExternalLink,
  HelpCircle,
  BarChart2,
  Table as TableIcon,
} from "lucide-react";
import {
  useDiscoveryStore,
  TasteProfileData,
  BlindspotItem,
} from "../store";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ProfileViewProps {
  onExploreRegion: (regionId: number, regionName: string) => void;
}

export function ProfileView({ onExploreRegion }: ProfileViewProps) {
  const queryClient = useQueryClient();
  const { seeds } = useDiscoveryStore();
  const [showTableAlternative, setShowTableAlternative] = useState(false);
  const [activeTooltip, setActiveTooltip] = useState<string | null>(null);

  // ListenBrainz import form state
  const [lbUsername, setLbUsername] = useState("");
  const [lbMessage, setLbMessage] = useState<string | null>(null);
  const [lbError, setLbError] = useState<string | null>(null);

  // Fetch Taste Profile
  const seedIdsQuery = seeds.map((s) => `seed_ids=${encodeURIComponent(s.id)}`).join("&");
  const profileUrl = seedIdsQuery
    ? `${API_BASE}/taste/profile?${seedIdsQuery}`
    : `${API_BASE}/taste/profile`;

  const {
    data: profileData,
    isLoading: isProfileLoading,
    refetch: refetchProfile,
  } = useQuery<TasteProfileData>({
    queryKey: ["tasteProfile", seeds.map((s) => s.id).join(",")],
    queryFn: async () => {
      const res = await fetch(profileUrl, { credentials: "include" });
      if (!res.ok) throw new Error("Failed to load taste profile");
      return await res.json();
    },
  });

  // Fetch Blindspots
  const blindspotsUrl = seedIdsQuery
    ? `${API_BASE}/taste/blindspots?${seedIdsQuery}`
    : `${API_BASE}/taste/blindspots`;

  const {
    data: blindspotsData,
    isLoading: isBlindspotsLoading,
  } = useQuery<{ blindspots: BlindspotItem[] }>({
    queryKey: ["tasteBlindspots", seeds.map((s) => s.id).join(",")],
    queryFn: async () => {
      const res = await fetch(blindspotsUrl, { credentials: "include" });
      if (!res.ok) throw new Error("Failed to load blindspots");
      return await res.json();
    },
  });

  // ListenBrainz Import Mutation
  const lbMutation = useMutation({
    mutationFn: async (username: string) => {
      const res = await fetch(`${API_BASE}/profile/import-listenbrainz`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ username, limit: 50 }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.error?.message || "Import failed");
      }
      return await res.json();
    },
    onSuccess: (data) => {
      setLbMessage(data.message || `Successfully imported ${data.imported_count} tracks!`);
      setLbError(null);
      setLbUsername("");
      queryClient.invalidateQueries({ queryKey: ["tasteProfile"] });
      queryClient.invalidateQueries({ queryKey: ["tasteBlindspots"] });
    },
    onError: (err: any) => {
      setLbError(err.message || "Could not reach ListenBrainz");
      setLbMessage(null);
    },
  });

  if (isProfileLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-[#8c96a8]">
        <RefreshCw className="w-8 h-8 animate-spin text-[#d4af37] mb-3" />
        <p className="text-sm font-medium">Computing your deterministic Music DNA & Profile...</p>
      </div>
    );
  }

  const isLowConfidence = profileData?.confidence === "low";
  const dimensions = profileData?.dimensions;
  const dna = profileData?.music_dna;
  const archetype = profileData?.archetype;
  const blindspots = blindspotsData?.blindspots || [];

  return (
    <div className="space-y-8 animate-fadeIn pb-16">
      {/* Top Header & Confidence Banner */}
      <div className="bg-[#141923] border border-[#232a3b] rounded-2xl p-6 shadow-xl relative overflow-hidden">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Sparkles className="w-5 h-5 text-[#d4af37]" />
              <h2 className="text-2xl font-bold text-[#f1f3f7] font-serif-display">
                Music DNA & Taste Profile
              </h2>
            </div>
            <p className="text-xs sm:text-sm text-[#8c96a8]">
              Grounded strictly in computed acoustic vectors, entropy, and release era data.
              Descriptive, non-evaluative analytics.
            </p>
          </div>

          <div className="flex items-center gap-3">
            {/* Confidence Badge */}
            <div
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border ${
                isLowConfidence
                  ? "bg-amber-950/40 border-amber-800/50 text-amber-300"
                  : "bg-emerald-950/40 border-emerald-800/50 text-emerald-300"
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  isLowConfidence ? "bg-amber-400 animate-pulse" : "bg-emerald-400"
                }`}
              />
              <span>{isLowConfidence ? "Low Confidence" : "High Confidence"}</span>
              <span className="text-[10px] opacity-75">
                ({profileData?.known_track_count || 0} tracks)
              </span>
            </div>

            {/* Refresh Button */}
            <button
              type="button"
              onClick={() => refetchProfile()}
              className="p-2 bg-[#1b2230] hover:bg-[#252e42] border border-[#2a3449] rounded-xl text-[#8c96a8] hover:text-[#f1f3f7] transition-colors"
              title="Refresh Profile"
              aria-label="Refresh Profile"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Low Confidence Warning Callout */}
        {isLowConfidence && (
          <div className="mt-4 p-3.5 bg-amber-950/20 border border-amber-800/40 rounded-xl flex items-start gap-3">
            <Info className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <div className="text-xs text-amber-200/90 leading-relaxed">
              <span className="font-semibold text-amber-300">Sample size notice:</span>{" "}
              {profileData?.confidence_reason ||
                "Fewer than 8 tracks are currently in your profile. Select more seeds or like tracks to unlock high-confidence dimensions."}
            </div>
          </div>
        )}
      </div>

      {/* Archetype & Music DNA Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Archetype Card */}
        <div className="bg-[#141923] border border-[#232a3b] rounded-2xl p-6 shadow-xl flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <span className="text-[11px] uppercase tracking-wider font-semibold text-[#8c96a8]">
                Musical Archetype
              </span>
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-[#1b2230] border border-[#2a3449] text-[#d4af37]">
                Rule-Derived
              </span>
            </div>

            <h3 className="text-2xl font-extrabold text-[#f1f3f7] tracking-tight mb-1">
              {archetype?.name || "The Balanced Explorer"}
            </h3>
            <p className="text-xs text-[#d4af37] italic mb-4 font-serif-display">
              &ldquo;{archetype?.tagline}&rdquo;
            </p>

            <p className="text-xs sm:text-sm text-[#8c96a8] leading-relaxed mb-4">
              {archetype?.description}
            </p>
          </div>

          <div className="pt-4 border-t border-[#1e2535]">
            <p className="text-[11px] font-semibold text-[#647187] uppercase tracking-wider mb-2">
              Triggered By Signals
            </p>
            <div className="flex flex-wrap gap-1.5">
              {archetype?.matched_rules?.map((rule, idx) => (
                <span
                  key={idx}
                  className="text-xs bg-[#192130] text-[#c8d0de] border border-[#252f44] px-2.5 py-1 rounded-lg"
                >
                  {rule}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Music DNA Card */}
        <div className="bg-[#141923] border border-[#232a3b] rounded-2xl p-6 shadow-xl">
          <div className="flex items-center justify-between mb-4">
            <span className="text-[11px] uppercase tracking-wider font-semibold text-[#8c96a8] flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-[#d4af37]" />
              Music DNA
            </span>
            <span className="text-xs text-[#647187]">Acoustic & Semantic Footprint</span>
          </div>

          {/* Dominant Tags */}
          <div className="mb-5">
            <p className="text-xs font-semibold text-[#c8d0de] mb-2">Dominant Folksonomy Tags</p>
            {dna?.dominant_tags && dna.dominant_tags.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {dna.dominant_tags.map((t, idx) => (
                  <span
                    key={idx}
                    className="inline-flex items-center gap-1.5 bg-[#1a2333] border border-[#27354d] text-xs px-2.5 py-1 rounded-lg text-[#f1f3f7]"
                  >
                    <span className="text-[#d4af37]">#{t.tag}</span>
                    <span className="text-[10px] text-[#647187]">({t.count}x)</span>
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-xs text-[#647187] italic">No tag footprint recorded yet.</p>
            )}
          </div>

          {/* Mean Scalars with Ranges */}
          <div>
            <p className="text-xs font-semibold text-[#c8d0de] mb-3">Acoustic Descriptors (Mean & Range)</p>
            <div className="space-y-3">
              {dna?.mean_scalars &&
                Object.entries(dna.mean_scalars).map(([sname, svals]) => {
                  const pct = Math.round(svals.mean * 100);
                  const minPct = Math.round(svals.min * 100);
                  const maxPct = Math.round(svals.max * 100);
                  const label = sname.replace("_bpm", " (BPM)").replace("_", " ");

                  return (
                    <div key={sname} className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="text-[#8c96a8] capitalize">{label}</span>
                        <span className="text-[#f1f3f7] font-mono text-[11px]">
                          {sname === "tempo_bpm"
                            ? `${Math.round(svals.mean)} bpm [${Math.round(svals.min)}–${Math.round(svals.max)}]`
                            : `${(svals.mean).toFixed(2)} [${svals.min.toFixed(2)}–${svals.max.toFixed(2)}]`}
                        </span>
                      </div>
                      {sname !== "tempo_bpm" && (
                        <div className="h-1.5 bg-[#1e2535] rounded-full overflow-hidden relative">
                          {/* Range background */}
                          <div
                            className="absolute top-0 bottom-0 bg-[#d4af37]/20 rounded-full"
                            style={{ left: `${minPct}%`, width: `${Math.max(4, maxPct - minPct)}%` }}
                          />
                          {/* Mean indicator */}
                          <div
                            className="absolute top-0 bottom-0 w-2 bg-[#d4af37] rounded-full -ml-1"
                            style={{ left: `${pct}%` }}
                          />
                        </div>
                      )}
                    </div>
                  );
                })}
            </div>
          </div>
        </div>
      </div>

      {/* Taste-o-Meter Dimensions */}
      <div className="bg-[#141923] border border-[#232a3b] rounded-2xl p-6 shadow-xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6 pb-4 border-b border-[#1e2535]">
          <div>
            <h3 className="text-lg font-bold text-[#f1f3f7] flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-[#d4af37]" />
              Taste-o-Meter Dimensions
            </h3>
            <p className="text-xs text-[#8c96a8]">
              Estimated on your tracks, with 90% bootstrap confidence interval whiskers [5%–95%]
              and percentiles relative to the catalog reference distribution.
            </p>
          </div>

          <button
            type="button"
            onClick={() => setShowTableAlternative(!showTableAlternative)}
            className="inline-flex items-center gap-1.5 text-xs text-[#8c96a8] hover:text-[#f1f3f7] bg-[#1a212e] px-3 py-1.5 rounded-lg border border-[#283247] transition-colors self-start sm:self-auto"
            aria-label="Toggle accessible data table view"
          >
            {showTableAlternative ? (
              <>
                <BarChart2 className="w-3.5 h-3.5" />
                <span>Show Bar Chart</span>
              </>
            ) : (
              <>
                <TableIcon className="w-3.5 h-3.5" />
                <span>Accessible Table</span>
              </>
            )}
          </button>
        </div>

        {/* Accessible Data Table Alternative */}
        {showTableAlternative ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-[#252f44] text-[#8c96a8]">
                  <th className="py-2.5 px-3">Dimension</th>
                  <th className="py-2.5 px-3">Point Value</th>
                  <th className="py-2.5 px-3">90% Bootstrap CI</th>
                  <th className="py-2.5 px-3">Catalog Percentile</th>
                  <th className="py-2.5 px-3">Definition</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1b2230]">
                {dimensions &&
                  Object.entries(dimensions).map(([key, dim]) => {
                    if (!dim) {
                      return (
                        <tr key={key} className="text-[#647187]">
                          <td className="py-3 px-3 capitalize font-medium">{key}</td>
                          <td colSpan={4} className="py-3 px-3 italic">
                            Requires at least 10 feedback events to compute.
                          </td>
                        </tr>
                      );
                    }
                    return (
                      <tr key={key} className="hover:bg-[#18202d] transition-colors">
                        <td className="py-3 px-3 font-semibold text-[#f1f3f7]">{dim.name}</td>
                        <td className="py-3 px-3 font-mono text-[#d4af37]">{dim.value.toFixed(3)}</td>
                        <td className="py-3 px-3 font-mono text-[#c8d0de]">
                          [{dim.ci_90[0].toFixed(3)}, {dim.ci_90[1].toFixed(3)}]
                        </td>
                        <td className="py-3 px-3 font-mono text-[#c8d0de]">
                          {dim.percentile.toFixed(1)}%
                        </td>
                        <td className="py-3 px-3 text-[#8c96a8] max-w-xs">{dim.definition_tooltip}</td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        ) : (
          /* Visual Dimension Bars with CI Whiskers */
          <div className="space-y-6">
            {dimensions &&
              Object.entries(dimensions).map(([key, dim]) => {
                if (!dim) {
                  return (
                    <div key={key} className="p-4 bg-[#11151e] border border-[#1e2535] rounded-xl">
                      <div className="flex justify-between items-center text-xs text-[#647187]">
                        <span className="font-semibold capitalize">{key}</span>
                        <span className="italic">Awaiting feedback events (&ge; 10 required)</span>
                      </div>
                    </div>
                  );
                }

                const pointPct = Math.round(dim.value * 100);
                const ciLowPct = Math.round(dim.ci_90[0] * 100);
                const ciHighPct = Math.round(dim.ci_90[1] * 100);

                return (
                  <div key={key} className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-[#f1f3f7]">{dim.name}</span>
                        {/* Tooltip Icon & Popover */}
                        <div className="relative">
                          <button
                            type="button"
                            onClick={() =>
                              setActiveTooltip(activeTooltip === key ? null : key)
                            }
                            onMouseEnter={() => setActiveTooltip(key)}
                            onMouseLeave={() => setActiveTooltip(null)}
                            className="text-[#647187] hover:text-[#d4af37] focus:outline-none"
                            aria-label={`Show definition for ${dim.name}`}
                          >
                            <HelpCircle className="w-3.5 h-3.5" />
                          </button>
                          {activeTooltip === key && (
                            <div className="absolute left-6 top-0 -mt-2 w-64 p-3 bg-[#1c2433] border border-[#2a354c] rounded-xl shadow-2xl z-50 text-xs text-[#c8d0de] leading-relaxed">
                              <p className="font-semibold text-[#f1f3f7] mb-1">{dim.name}</p>
                              <p>{dim.definition_tooltip}</p>
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-3 text-xs">
                        <span className="text-[#8c96a8] font-mono text-[11px]">
                          CI: [{dim.ci_90[0].toFixed(2)}, {dim.ci_90[1].toFixed(2)}]
                        </span>
                        <span className="px-2 py-0.5 rounded bg-[#1f2738] border border-[#2b364d] text-[#d4af37] font-mono font-medium">
                          {dim.percentile.toFixed(0)}th percentile
                        </span>
                      </div>
                    </div>

                    {/* Progress Bar Container with Whisker */}
                    <div className="relative h-4 bg-[#11151e] border border-[#1e2535] rounded-full overflow-hidden">
                      {/* CI Range Whisker Area */}
                      <div
                        className="absolute top-0 bottom-0 bg-[#d4af37]/20 border-l border-r border-[#d4af37]/60"
                        style={{
                          left: `${ciLowPct}%`,
                          width: `${Math.max(2, ciHighPct - ciLowPct)}%`,
                        }}
                        title={`90% Confidence Interval: [${dim.ci_90[0]}, ${dim.ci_90[1]}]`}
                      />
                      {/* Point Estimate Bar */}
                      <div
                        className="h-full bg-gradient-to-r from-[#d4af37]/70 to-[#d4af37] rounded-full transition-all duration-500"
                        style={{ width: `${pointPct}%` }}
                      />
                    </div>

                    <p className="text-[11px] text-[#647187] italic">{dim.description}</p>
                  </div>
                );
              })}
          </div>
        )}
      </div>

      {/* Blindspots & Region Exploration Section (WOW #5) */}
      <div className="bg-[#141923] border border-[#232a3b] rounded-2xl p-6 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-bold text-[#f1f3f7] flex items-center gap-2">
              <Compass className="w-5 h-5 text-[#d4af37]" />
              Unexplored Blindspots (Steerable Bridge)
            </h3>
            <p className="text-xs text-[#8c96a8]">
              Adjacent musical territories that share underlying aesthetic DNA with your taste
              modes but have low exposure in your current history.
            </p>
          </div>
        </div>

        {isBlindspotsLoading ? (
          <div className="py-8 text-center text-xs text-[#8c96a8]">
            <RefreshCw className="w-5 h-5 animate-spin mx-auto text-[#d4af37] mb-2" />
            Analyzing cluster adjacency graph...
          </div>
        ) : blindspots.length === 0 ? (
          <p className="text-xs text-[#647187] italic py-4">
            No adjacent blindspots detected yet. Add more seeds or tracks across genres.
          </p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {blindspots.slice(0, 4).map((b) => (
              <div
                key={b.region_id}
                className="bg-[#11151e] border border-[#202838] hover:border-[#d4af37]/40 rounded-xl p-4 flex flex-col justify-between transition-all"
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] font-bold text-[#d4af37] uppercase tracking-wider">
                      Region {b.region_id}
                    </span>
                    <span className="text-[11px] text-[#8c96a8] font-mono">
                      Adjacency: {(b.adjacency_score * 100).toFixed(0)}%
                    </span>
                  </div>

                  <h4 className="text-base font-bold text-[#f1f3f7] mb-1">{b.name}</h4>
                  <p className="text-xs text-[#8c96a8] mb-2">{b.genre_focus}</p>
                  <p className="text-[11px] text-[#647187] line-clamp-2 mb-3">
                    {b.description}
                  </p>

                  {/* Bridge Tags */}
                  <div className="flex flex-wrap gap-1.5 mb-4">
                    {b.bridge_tags.map((t, idx) => (
                      <span
                        key={idx}
                        className="text-[10px] bg-[#1a2230] text-[#c8d0de] border border-[#263145] px-2 py-0.5 rounded"
                      >
                        #{t}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Explore Button */}
                <button
                  type="button"
                  onClick={() => onExploreRegion(b.region_id, b.name)}
                  className="w-full flex items-center justify-center gap-2 bg-[#d4af37]/10 hover:bg-[#d4af37]/20 border border-[#d4af37]/30 hover:border-[#d4af37] text-xs font-semibold text-[#d4af37] py-2 px-3 rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-[#d4af37]"
                >
                  <span>Explore this region</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 24-Region Exposure Breakdown */}
      <div className="bg-[#141923] border border-[#232a3b] rounded-2xl p-6 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold text-[#f1f3f7] uppercase tracking-wider">
            24-Region Listening Footprint
          </h3>
          <span className="text-xs text-[#647187]">Soft cluster assignments</span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2.5">
          {profileData?.region_exposures?.map((reg) => {
            const expPct = Math.round(reg.exposure * 100);
            return (
              <div
                key={reg.region_id}
                className="bg-[#11151e] border border-[#1b2230] rounded-lg p-2.5 text-xs flex flex-col justify-between"
              >
                <div>
                  <div className="flex justify-between items-center text-[10px] text-[#647187] mb-1">
                    <span>R{reg.region_id}</span>
                    <span className="font-mono text-[#d4af37]">{expPct}%</span>
                  </div>
                  <p className="font-semibold text-[#c8d0de] truncate text-[11px]" title={reg.name}>
                    {reg.name}
                  </p>
                </div>
                <div className="h-1 bg-[#1a212e] rounded-full overflow-hidden mt-2">
                  <div
                    className="h-full bg-[#d4af37] rounded-full transition-all"
                    style={{ width: `${Math.min(100, Math.max(expPct, expPct > 0 ? 3 : 0))}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ListenBrainz History Import Card */}
      <div className="bg-[#141923] border border-[#232a3b] rounded-2xl p-6 shadow-xl">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <ExternalLink className="w-4 h-4 text-[#d4af37]" />
            <h3 className="text-sm font-bold text-[#f1f3f7]">
              Import Public Listens from ListenBrainz
            </h3>
          </div>
          <span className="text-[10px] bg-[#1a212e] text-[#8c96a8] px-2 py-0.5 rounded border border-[#283247]">
            Official API
          </span>
        </div>
        <p className="text-xs text-[#8c96a8] mb-4">
          Connect your public ListenBrainz listening history. No password or private data required.
          Fetches recent scrobbles and matches recording MBIDs to catalog tracks.
        </p>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (lbUsername.trim()) {
              lbMutation.mutate(lbUsername.trim());
            }
          }}
          className="flex flex-col sm:flex-row gap-2"
        >
          <input
            type="text"
            placeholder="Enter public ListenBrainz username..."
            value={lbUsername}
            onChange={(e) => setLbUsername(e.target.value)}
            disabled={lbMutation.isPending}
            className="flex-1 bg-[#0d1017] border border-[#262e40] rounded-xl px-4 py-2.5 text-xs text-[#f1f3f7] placeholder-[#5a657a] focus:outline-none focus:ring-2 focus:ring-[#d4af37] disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={lbMutation.isPending || !lbUsername.trim()}
            className="px-4 py-2.5 bg-[#d4af37] hover:bg-[#c29e2e] text-[#0d1017] font-semibold rounded-xl text-xs flex items-center justify-center gap-1.5 transition-colors disabled:opacity-50"
          >
            {lbMutation.isPending ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>Importing...</span>
              </>
            ) : (
              <span>Import Listens</span>
            )}
          </button>
        </form>

        {lbMessage && (
          <p className="text-xs text-emerald-400 mt-3 font-medium">{lbMessage}</p>
        )}
        {lbError && (
          <p className="text-xs text-rose-400 mt-3 font-medium">{lbError}</p>
        )}
      </div>
    </div>
  );
}
