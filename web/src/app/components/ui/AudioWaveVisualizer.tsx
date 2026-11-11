"use client";

import React from "react";

interface AudioWaveVisualizerProps {
  isPlaying: boolean;
  className?: string;
}

/**
 * AudioWaveVisualizer: Sleek Apple Music-style dynamic equalizer waves
 * displayed when 30s preview audio is playing.
 */
export function AudioWaveVisualizer({
  isPlaying,
  className = "",
}: AudioWaveVisualizerProps) {
  if (!isPlaying) return null;

  return (
    <div
      aria-label="Audio playing indicator"
      className={`inline-flex items-center gap-0.5 px-2.5 py-1 rounded-full bg-white/[0.06] border border-[#fa2d55]/30 backdrop-blur-md shadow-[0_0_12px_rgba(250,45,85,0.3)] ${className}`}
    >
      <span className="w-0.5 h-3 bg-[#fa2d55] rounded-full animate-eq-1" />
      <span className="w-0.5 h-4 bg-[#fb7185] rounded-full animate-eq-2" />
      <span className="w-0.5 h-5 bg-[#fa2d55] rounded-full animate-eq-3" />
      <span className="w-0.5 h-3.5 bg-[#c084fc] rounded-full animate-eq-4" />
      <span className="w-0.5 h-2.5 bg-[#8b5cf6] rounded-full animate-eq-5" />
      <span className="ml-1 text-[10px] font-mono font-bold text-[#fa2d55] uppercase tracking-wider">
        Playing
      </span>
    </div>
  );
}
