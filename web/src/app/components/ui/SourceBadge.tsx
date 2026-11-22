"use client";

import React from "react";
import { Radio, Music2, Database } from "lucide-react";
import { Track } from "../../store";

export type TrackSourceType = "saavn" | "itunes" | "catalog";

/**
 * Determine the canonical source for a track based on explicit source attribute or ID prefix.
 */
export function getTrackSource(track?: Partial<Track> | { id?: string; source?: string | null } | null): TrackSourceType {
  if (!track) return "catalog";
  if (track.source) {
    const s = String(track.source).toLowerCase();
    if (s.includes("saavn")) return "saavn";
    if (s.includes("itunes")) return "itunes";
  }
  const id = track.id || "";
  if (id.startsWith("ext:saavn:")) return "saavn";
  if (id.startsWith("ext:itunes:")) return "itunes";
  return "catalog";
}

interface SourceBadgeProps {
  track?: Partial<Track> | { id?: string; source?: string | null } | null;
  compact?: boolean;
  showIcon?: boolean;
  className?: string;
}

/**
 * SourceBadge: Client-side origin badge distinguishing JioSaavn, iTunes, and Melovia Catalog tracks.
 * Features Apple liquid glass styled pill with glowing accent dot and responsive typography.
 */
export function SourceBadge({
  track,
  compact = false,
  showIcon = true,
  className = "",
}: SourceBadgeProps) {
  const source = getTrackSource(track);

  let label = "Catalog";
  let badgeStyle =
    "bg-purple-500/15 text-purple-300 border-purple-500/30 shadow-[0_0_10px_rgba(168,85,247,0.18)]";
  let dotStyle = "bg-purple-400 shadow-[0_0_6px_rgba(192,132,252,0.8)]";
  let Icon = Database;

  if (source === "saavn") {
    label = "JioSaavn";
    badgeStyle =
      "bg-emerald-500/15 text-emerald-300 border-emerald-500/35 shadow-[0_0_10px_rgba(16,185,129,0.2)]";
    dotStyle = "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.8)]";
    Icon = Radio;
  } else if (source === "itunes") {
    label = "iTunes";
    badgeStyle =
      "bg-rose-500/15 text-rose-300 border-rose-500/35 shadow-[0_0_10px_rgba(244,63,94,0.2)]";
    dotStyle = "bg-rose-400 shadow-[0_0_6px_rgba(251,113,133,0.8)]";
    Icon = Music2;
  }

  if (compact) {
    return (
      <span
        data-testid={`source-badge-${source}`}
        title={`Source: ${label}`}
        className={`inline-flex items-center gap-1 text-[9px] font-mono font-semibold px-1.5 py-0.5 rounded-md border backdrop-blur-md transition-colors ${badgeStyle} ${className}`}
      >
        <span className={`w-1 h-1 rounded-full ${dotStyle}`} aria-hidden="true" />
        {label}
      </span>
    );
  }

  return (
    <span
      data-testid={`source-badge-${source}`}
      title={`Source: ${label}`}
      className={`inline-flex items-center gap-1.5 text-[10px] font-mono font-medium px-2.5 py-0.5 rounded-full border backdrop-blur-md transition-colors ${badgeStyle} ${className}`}
    >
      {showIcon && <Icon className="w-2.5 h-2.5 opacity-90 flex-shrink-0" aria-hidden="true" />}
      <span className={`w-1.5 h-1.5 rounded-full ${dotStyle}`} aria-hidden="true" />
      <span>{label}</span>
    </span>
  );
}
