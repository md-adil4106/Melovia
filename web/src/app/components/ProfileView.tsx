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
  Globe,
  Share2,
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
  const { seeds, setUniverseModalOpen, setUniverseFocusedRegionId } = useDiscoveryStore();
  const [showTableAlternative, setShowTableAlternative] = useState(false);
  const [activeTooltip, setActiveTooltip] = useState<string | null>(null);
  const [isExportingImage, setIsExportingImage] = useState(false);

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

  const handleShareAsImage = () => {
    if (!profileData) return;
    setIsExportingImage(true);

    try {
      const canvas = document.createElement("canvas");
      canvas.width = 1200;
      canvas.height = 630;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      // 1. Background gradient
      const bgGradient = ctx.createLinearGradient(0, 0, 1200, 630);
      bgGradient.addColorStop(0, "#090b10");
      bgGradient.addColorStop(0.5, "#11141d");
      bgGradient.addColorStop(1, "#0d1017");
      ctx.fillStyle = bgGradient;
      ctx.fillRect(0, 0, 1200, 630);

      // Decorative ambient glow
      const glow1 = ctx.createRadialGradient(150, 150, 10, 150, 150, 300);
      glow1.addColorStop(0, "rgba(212, 175, 55, 0.15)");
      glow1.addColorStop(1, "rgba(212, 175, 55, 0)");
      ctx.fillStyle = glow1;
      ctx.fillRect(0, 0, 600, 630);

      const glow2 = ctx.createRadialGradient(1050, 480, 10, 1050, 480, 300);
      glow2.addColorStop(0, "rgba(56, 189, 248, 0.12)");
      glow2.addColorStop(1, "rgba(56, 189, 248, 0)");
      ctx.fillStyle = glow2;
      ctx.fillRect(600, 0, 600, 630);

      // 2. Border
      ctx.strokeStyle = "#273042";
      ctx.lineWidth = 2;
      ctx.strokeRect(30, 30, 1140, 570);

      // 3. Header: Brand & Non-evaluative badge
      ctx.fillStyle = "#d4af37";
      ctx.font = "bold 24px system-ui, sans-serif";
      ctx.fillText("MELOVIA", 60, 80);

      ctx.fillStyle = "#8c96a8";
      ctx.font = "14px system-ui, sans-serif";
      ctx.fillText("EXPLAINABLE MUSIC DISCOVERY • TASTE PROFILE", 190, 80);

      // "Describes, Never Ranks" badge
      ctx.fillStyle = "rgba(56, 189, 248, 0.15)";
      ctx.beginPath();
      if (typeof ctx.roundRect === "function") {
        ctx.roundRect(880, 56, 260, 32, 8);
      } else {
        ctx.rect(880, 56, 260, 32);
      }
      ctx.fill();
      ctx.strokeStyle = "rgba(56, 189, 248, 0.4)";
      ctx.lineWidth = 1;
      ctx.stroke();

      ctx.fillStyle = "#38bdf8";
      ctx.font = "bold 12px system-ui, sans-serif";
      ctx.fillText("DESCRIBES, NEVER RANKS", 915, 77);

      // 4. Archetype Card (Left side)
      ctx.fillStyle = "#141923";
      ctx.beginPath();
      if (typeof ctx.roundRect === "function") {
        ctx.roundRect(60, 120, 480, 440, 16);
      } else {
        ctx.rect(60, 120, 480, 440);
      }
      ctx.fill();
      ctx.strokeStyle = "#232a3b";
      ctx.stroke();

      ctx.fillStyle = "#8c96a8";
      ctx.font = "bold 12px system-ui, sans-serif";
      ctx.fillText("MUSICAL ARCHETYPE", 90, 160);

      ctx.fillStyle = "#f1f3f7";
      ctx.font = "bold 28px Georgia, serif";
      const archName = profileData.archetype?.name || "The Balanced Explorer";
      ctx.fillText(archName, 90, 205);

      ctx.fillStyle = "#d4af37";
      ctx.font = "italic 15px Georgia, serif";
      const tagline = `"${profileData.archetype?.tagline || "Navigating between resonance and discovery"}"`;
      ctx.fillText(tagline, 90, 235);

      ctx.fillStyle = "#8c96a8";
      ctx.font = "14px system-ui, sans-serif";
      const desc = profileData.archetype?.description || "Curates soundscapes balancing familiarity with sonic novelty.";
      const words = desc.split(" ");
      let line = "";
      let y = 280;
      for (const w of words) {
        const testLine = line + w + " ";
        if (ctx.measureText(testLine).width > 420 && line !== "") {
          ctx.fillText(line, 90, y);
          line = w + " ";
          y += 22;
        } else {
          line = testLine;
        }
      }
      if (line) ctx.fillText(line, 90, y);

      // Dominant Tags
      ctx.fillStyle = "#647187";
      ctx.font = "bold 11px system-ui, sans-serif";
      ctx.fillText("DOMINANT DNA TAGS", 90, 450);

      const tags = profileData.music_dna?.dominant_tags?.slice(0, 4) || [];
      let tagX = 90;
      for (const t of tags) {
        const label = `#${t.tag}`;
        const width = ctx.measureText(label).width + 20;
        ctx.fillStyle = "#1b2230";
        ctx.beginPath();
        if (typeof ctx.roundRect === "function") {
          ctx.roundRect(tagX, 465, width, 26, 6);
        } else {
          ctx.rect(tagX, 465, width, 26);
        }
        ctx.fill();
        ctx.strokeStyle = "#2b354a";
        ctx.stroke();

        ctx.fillStyle = "#d4af37";
        ctx.font = "11px system-ui, sans-serif";
        ctx.fillText(label, tagX + 10, 482);
        tagX += width + 10;
      }

      ctx.fillStyle = "#647187";
      ctx.font = "11px system-ui, sans-serif";
      ctx.fillText(`Profile derived from ${profileData.known_track_count || 0} catalog tracks • Zero PII`, 90, 530);

      // 5. Taste-o-meter Dimensions (Right side)
      ctx.fillStyle = "#141923";
      ctx.beginPath();
      if (typeof ctx.roundRect === "function") {
        ctx.roundRect(570, 120, 570, 440, 16);
      } else {
        ctx.rect(570, 120, 570, 440);
      }
      ctx.fill();
      ctx.strokeStyle = "#232a3b";
      ctx.stroke();

      ctx.fillStyle = "#f1f3f7";
      ctx.font = "bold 18px system-ui, sans-serif";
      ctx.fillText("Taste-o-Meter Dimensions", 600, 160);

      ctx.fillStyle = "#8c96a8";
      ctx.font = "12px system-ui, sans-serif";
      ctx.fillText("Objective coordinates relative to catalog distribution", 600, 182);

      const dims = [
        { label: "Genre Breadth", dim: profileData.dimensions?.breadth },
        { label: "Acoustic Rarity", dim: profileData.dimensions?.rarity },
        { label: "Release Era Range", dim: profileData.dimensions?.range },
        { label: "Semantic Cohesion", dim: profileData.dimensions?.cohesion },
        { label: "Adventurousness", dim: profileData.dimensions?.adventurousness },
      ];

      let dimY = 225;
      for (const d of dims) {
        ctx.fillStyle = "#c8d0de";
        ctx.font = "13px system-ui, sans-serif";
        ctx.fillText(d.label, 600, dimY);

        const val = d.dim?.value || 0.5;
        const pct = d.dim?.percentile ? `${d.dim.percentile.toFixed(0)}th percentile` : `${Math.round(val * 100)}%`;

        ctx.fillStyle = "#d4af37";
        ctx.font = "12px monospace";
        ctx.fillText(pct, 1030, dimY);

        // Track bar background
        ctx.fillStyle = "#1e2535";
        ctx.beginPath();
        if (typeof ctx.roundRect === "function") {
          ctx.roundRect(600, dimY + 8, 510, 8, 4);
        } else {
          ctx.rect(600, dimY + 8, 510, 8);
        }
        ctx.fill();

        // Progress bar fill
        const barGrad = ctx.createLinearGradient(600, 0, 1110, 0);
        barGrad.addColorStop(0, "#d4af37");
        barGrad.addColorStop(1, "#38bdf8");
        ctx.fillStyle = barGrad;
        ctx.beginPath();
        if (typeof ctx.roundRect === "function") {
          ctx.roundRect(600, dimY + 8, Math.max(8, 510 * val), 8, 4);
        } else {
          ctx.rect(600, dimY + 8, Math.max(8, 510 * val), 8);
        }
        ctx.fill();

        dimY += 56;
      }

      // 6. Programmatic Download
      const dataUrl = canvas.toDataURL("image/png");
      const link = document.createElement("a");
      link.download = "melovia-taste-profile.png";
      link.href = dataUrl;
      link.click();
    } catch (err) {
      console.error("Failed to render share image:", err);
    } finally {
      setIsExportingImage(false);
    }
  };

  const isLowConfidence = profileData?.confidence === "low";
  const dimensions = profileData?.dimensions;
  const dna = profileData?.music_dna;
  const archetype = profileData?.archetype;
  const blindspots = blindspotsData?.blindspots || [];

  return (
    <div className="space-y-8 animate-fadeIn pb-16">
      {/* Top Header & Confidence Banner */}
      <div className="bg-white/[0.035] backdrop-blur-2xl border border-white/[0.08] rounded-3xl p-6 sm:p-7 shadow-[0_16px_40px_rgba(0,0,0,0.5)] relative overflow-hidden">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Sparkles className="w-5 h-5 text-[#fa2d55]" />
              <h2 className="text-2xl font-bold text-white font-sans tracking-tight">
                Music DNA & Taste Profile
              </h2>
            </div>
            <p className="text-xs sm:text-sm text-white/60">
              Grounded strictly in computed acoustic vectors, entropy, and release era data.
              Descriptive, non-evaluative analytics.
            </p>
          </div>

          <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
            {/* Confidence Badge */}
            <div
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold border ${
                isLowConfidence
                  ? "bg-amber-500/15 border-amber-500/30 text-amber-200"
                  : "bg-emerald-500/15 border-emerald-500/30 text-emerald-200"
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

            {/* Share as Image Button */}
            <button
              type="button"
              onClick={handleShareAsImage}
              disabled={isExportingImage || !profileData}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-white/[0.06] hover:bg-white/[0.12] border border-white/10 hover:border-[#fa2d55]/40 rounded-full text-xs font-semibold text-white transition-all shadow-sm focus:outline-none focus:ring-2 focus:ring-[#fa2d55] disabled:opacity-50"
              title="Export high-resolution PNG image of your profile (Zero server upload)"
              aria-label="Share as Image"
            >
              <Share2 className="w-3.5 h-3.5 text-[#fb7185]" />
              <span>{isExportingImage ? "Exporting..." : "Share as Image"}</span>
            </button>

            {/* Refresh Button */}
            <button
              type="button"
              onClick={() => refetchProfile()}
              className="p-2 bg-white/[0.06] hover:bg-white/[0.12] border border-white/10 rounded-full text-white/60 hover:text-white transition-colors"
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
        <div className="bg-white/[0.03] backdrop-blur-xl border border-white/[0.08] rounded-3xl p-6 shadow-xl flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <span className="text-[11px] uppercase tracking-wider font-semibold text-white/60">
                Musical Archetype
              </span>
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-white/[0.06] border border-white/10 text-[#fa2d55]">
                Rule-Derived
              </span>
            </div>

            <h3 className="text-2xl font-black text-white tracking-tight mb-1">
              {archetype?.name || "The Balanced Explorer"}
            </h3>
            <p className="text-xs text-[#fa2d55] italic mb-4">
              &ldquo;{archetype?.tagline}&rdquo;
            </p>

            <p className="text-xs sm:text-sm text-white/70 leading-relaxed mb-4">
              {archetype?.description}
            </p>
          </div>

          <div className="pt-4 border-t border-white/[0.08]">
            <p className="text-[11px] font-semibold text-white/50 uppercase tracking-wider mb-2">
              Triggered By Signals
            </p>
            <div className="flex flex-wrap gap-1.5">
              {archetype?.matched_rules?.map((rule, idx) => (
                <span
                  key={idx}
                  className="text-xs bg-white/[0.04] text-white/80 border border-white/10 px-2.5 py-1 rounded-full"
                >
                  {rule}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Music DNA Card */}
        <div className="bg-white/[0.03] backdrop-blur-xl border border-white/[0.08] rounded-3xl p-6 shadow-xl">
          <div className="flex items-center justify-between mb-4">
            <span className="text-[11px] uppercase tracking-wider font-semibold text-white/60 flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-[#fa2d55]" />
              Music DNA
            </span>
            <span className="text-xs text-white/50">Acoustic & Semantic Footprint</span>
          </div>

          {/* Dominant Tags */}
          <div className="mb-5">
            <p className="text-xs font-semibold text-white/90 mb-2">Dominant Folksonomy Tags</p>
            {dna?.dominant_tags && dna.dominant_tags.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {dna.dominant_tags.map((t, idx) => (
                  <span
                    key={idx}
                    className="inline-flex items-center gap-1.5 bg-white/[0.04] border border-white/10 text-xs px-2.5 py-1 rounded-full text-white"
                  >
                    <span className="text-[#fa2d55]">#{t.tag}</span>
                    <span className="text-[10px] text-white/40">({t.count}x)</span>
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-xs text-white/40 italic">No tag footprint recorded yet.</p>
            )}
          </div>

          {/* Mean Scalars with Ranges */}
          <div>
            <p className="text-xs font-semibold text-white/90 mb-3">Acoustic Descriptors (Mean & Range)</p>
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
                        <span className="text-white/60 capitalize">{label}</span>
                        <span className="text-white font-mono text-[11px]">
                          {sname === "tempo_bpm"
                            ? `${Math.round(svals.mean)} bpm [${Math.round(svals.min)}–${Math.round(svals.max)}]`
                            : `${(svals.mean).toFixed(2)} [${svals.min.toFixed(2)}–${svals.max.toFixed(2)}]`}
                        </span>
                      </div>
                      {sname !== "tempo_bpm" && (
                        <div className="h-1.5 bg-white/10 rounded-full overflow-hidden relative">
                          {/* Range background */}
                          <div
                            className="absolute top-0 bottom-0 bg-[#fa2d55]/25 rounded-full"
                            style={{ left: `${minPct}%`, width: `${Math.max(4, maxPct - minPct)}%` }}
                          />
                          {/* Mean indicator */}
                          <div
                            className="absolute top-0 bottom-0 w-2 bg-[#fa2d55] rounded-full -ml-1"
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
      <div className="bg-white/[0.035] backdrop-blur-2xl border border-white/[0.08] rounded-3xl p-6 sm:p-7 shadow-[0_16px_40px_rgba(0,0,0,0.5)]">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6 pb-4 border-b border-white/[0.08]">
          <div>
            <h3 className="text-xl font-bold text-white flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-[#fa2d55]" />
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

                {/* Action Buttons */}
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => onExploreRegion(b.region_id, b.name)}
                    className="flex-1 flex items-center justify-center gap-2 bg-[#d4af37]/10 hover:bg-[#d4af37]/20 border border-[#d4af37]/30 hover:border-[#d4af37] text-xs font-semibold text-[#d4af37] py-2 px-3 rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-[#d4af37]"
                  >
                    <span>Explore this region</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setUniverseFocusedRegionId(b.region_id);
                      setUniverseModalOpen(true);
                    }}
                    title="Focus region in 3D Taste Universe"
                    aria-label={`View region ${b.region_id} in 3D Taste Universe`}
                    className="p-2 bg-[#1a2230] hover:bg-[#252f44] border border-[#2b354a] hover:border-[#38bdf8] text-[#38bdf8] rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-[#38bdf8]"
                  >
                    <Globe className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 24-Region Exposure Breakdown */}
      <div className="bg-[#141923] border border-[#232a3b] rounded-2xl p-6 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-bold text-[#f1f3f7] uppercase tracking-wider">
              24-Region Listening Footprint
            </h3>
            <span className="text-xs text-[#647187]">Soft cluster assignments</span>
          </div>

          <button
            type="button"
            onClick={() => {
              setUniverseFocusedRegionId(null);
              setUniverseModalOpen(true);
            }}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#18202e] hover:bg-[#252f44] border border-[#2b374d] text-xs font-semibold text-[#d4af37] hover:text-[#f5ecd5] transition-colors focus:outline-none focus:ring-2 focus:ring-[#d4af37]"
          >
            <Globe className="w-3.5 h-3.5 text-[#d4af37]" />
            <span>View in 3D Universe</span>
          </button>
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
