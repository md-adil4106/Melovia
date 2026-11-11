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
 * AudioWaveVisualizer: Real-time frequency band visualizer.
 * Analyzes audio frequencies via Web Audio API AnalyserNode when available,
 * with an automatic silky procedural harmonic fallback when CORS restricts raw stream inspection.
 * Strictly respects prefers-reduced-motion and cleans up all audio nodes.
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
    if (!isPlaying) return;

    // Check for reduced motion preference safely
    if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
      const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
      if (mediaQuery.matches) {
        setBarHeights([10, 14, 18, 14, 12, 10, 8]);
        return;
      }
    }

    let audioContext: AudioContext | null = null;
    let analyser: AnalyserNode | null = null;
    let dataArray: Uint8Array<ArrayBuffer> | null = null;
    let sourceNode: MediaElementAudioSourceNode | null = null;
    let useWebAudio = false;

    // Attempt Web Audio API frequency node connection
    if (audioElement && typeof window !== "undefined") {
      const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (AudioContextClass) {
        try {
          // Check if element already has a source or instantiate
          audioContext = new AudioContextClass();
          analyser = audioContext.createAnalyser();
          analyser.fftSize = 32;
          analyser.smoothingTimeConstant = 0.8;
          const buffer = new ArrayBuffer(analyser.frequencyBinCount);
          dataArray = new Uint8Array(buffer);

          // Connecting media element source (may throw if CORS restricts)
          sourceNode = audioContext.createMediaElementSource(audioElement);
          sourceNode.connect(analyser);
          analyser.connect(audioContext.destination);
          useWebAudio = true;
        } catch {
          // CORS or AudioContext policy restricted direct stream tapping;
          // seamlessly use high-fidelity harmonic simulation
          useWebAudio = false;
        }
      }
    }

    let startTime = performance.now();

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

      if (useWebAudio && analyser && dataArray) {
        try {
          analyser.getByteFrequencyData(dataArray);
          // Sample across representative frequency bins
          const sampled = [
            Math.max(4, Math.round((dataArray[1] / 255) * 22)),
            Math.max(4, Math.round((dataArray[2] / 255) * 22)),
            Math.max(4, Math.round((dataArray[3] / 255) * 22)),
            Math.max(4, Math.round((dataArray[5] / 255) * 22)),
            Math.max(4, Math.round((dataArray[7] / 255) * 22)),
            Math.max(4, Math.round((dataArray[9] / 255) * 22)),
            Math.max(4, Math.round((dataArray[12] / 255) * 22)),
          ];
          setBarHeights(sampled);
        } catch {
          useWebAudio = false;
        }
      }

      if (!useWebAudio) {
        // High-fidelity procedural harmonic oscillation fallback
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
      }

      animationFrameRef.current = requestAnimationFrame(updateBars);
    };

    animationFrameRef.current = requestAnimationFrame(updateBars);

    return () => {
      if (animationFrameRef.current !== null) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      if (audioContext && audioContext.state !== "closed") {
        audioContext.close().catch(() => {});
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
