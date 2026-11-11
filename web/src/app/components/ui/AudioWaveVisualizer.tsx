"use client";

import React, { useEffect, useRef, useState } from "react";

interface AudioWaveVisualizerProps {
  isPlaying: boolean;
  audioElement?: HTMLAudioElement | null;
  className?: string;
}

const BAR_COUNT = 7;
const BAR_COLORS = [
  "#fa2d55", // Sub-bass (Apple Ruby)
  "#fa2d55", // Bass
  "#fb7185", // Low-mid (Rose)
  "#e879f9", // Mid (Fuchsia)
  "#c084fc", // High-mid (Purple)
  "#8b5cf6", // Presence (Violet)
  "#38bdf8", // Brilliance (Cyan)
];

/**
 * AudioWaveVisualizer: Real-time visual frequency band equalizer.
 * Drives synchronized multi-band harmonic animation and live playback progress
 * without intercepting or hijacking the HTMLAudioElement media graph (preventing
 * Web Audio suspended-context or cross-origin stream muting).
 * Strictly respects prefers-reduced-motion.
 */
export function AudioWaveVisualizer({
  isPlaying,
  audioElement,
  className = "",
}: AudioWaveVisualizerProps) {
  const [barHeights, setBarHeights] = useState<number[]>([6, 12, 18, 14, 10, 8, 5]);
  const [playbackTime, setPlaybackTime] = useState<string>("0:00");
  const animationFrameRef = useRef<number | null>(null);

  useEffect(() => {
    if (!isPlaying) {
      setPlaybackTime("0:00");
      return;
    }

    // Check for reduced motion preference safely
    if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
      const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
      if (mediaQuery.matches) {
        setBarHeights([10, 14, 18, 14, 12, 10, 8]);
        return;
      }
    }

    const startTime = performance.now();

    const updateBars = () => {
      const now = performance.now();
      const elapsedSec = (now - startTime) / 1000;

      // Update playback time if audio element is present
      if (audioElement && !isNaN(audioElement.currentTime)) {
        const cur = Math.floor(audioElement.currentTime);
        const mins = Math.floor(cur / 60);
        const secs = cur % 60;
        setPlaybackTime(`${mins}:${secs < 10 ? "0" : ""}${secs}`);
      }

      // High-fidelity multi-band procedural harmonic oscillation
      const baseH = [
        Math.sin(elapsedSec * 4.2) * 7 + 12,
        Math.cos(elapsedSec * 5.6) * 8 + 13,
        Math.sin(elapsedSec * 3.8 + 1) * 9 + 14,
        Math.cos(elapsedSec * 6.4 + 2) * 8 + 12,
        Math.sin(elapsedSec * 5.1 + 0.5) * 7 + 11,
        Math.cos(elapsedSec * 4.7 + 1.5) * 6 + 10,
        Math.sin(elapsedSec * 6.0 + 3) * 5 + 8,
      ];
      setBarHeights(baseH.map((h) => Math.max(4, Math.min(22, Math.round(h)))));

      animationFrameRef.current = requestAnimationFrame(updateBars);
    };

    animationFrameRef.current = requestAnimationFrame(updateBars);

    return () => {
      if (animationFrameRef.current !== null) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [isPlaying, audioElement]);

  if (!isPlaying) return null;

  return (
    <div
      aria-label="Audio playing indicator"
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/[0.06] border border-[#fa2d55]/30 backdrop-blur-md shadow-[0_0_16px_rgba(250,45,85,0.3)] transition-all ${className}`}
    >
      <div className="flex items-end gap-0.5 h-5 px-0.5" aria-hidden="true">
        {barHeights.map((h, i) => (
          <span
            key={i}
            className="w-0.5 rounded-full transition-[height] duration-75 ease-out"
            style={{
              height: `${h}px`,
              backgroundColor: BAR_COLORS[i % BAR_COLORS.length],
            }}
          />
        ))}
      </div>

      <div className="flex items-center gap-1.5">
        <span className="text-[10px] font-mono font-bold text-[#fa2d55] uppercase tracking-wider">
          Playing
        </span>
        {playbackTime !== "0:00" && (
          <span className="text-[9px] font-mono font-semibold text-white/50 pl-0.5">
            {playbackTime}
          </span>
        )}
      </div>
    </div>
  );
}
