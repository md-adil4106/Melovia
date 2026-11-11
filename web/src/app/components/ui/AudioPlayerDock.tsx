"use client";

import React, { useEffect, useState } from "react";
import { Music, Play, Pause, X, Volume2 } from "lucide-react";
import { Track } from "../../store";
import { AudioWaveVisualizer } from "./AudioWaveVisualizer";

interface AudioPlayerDockProps {
  track: Track | null;
  isPlaying: boolean;
  audioElement: HTMLAudioElement | null;
  onTogglePlay: (track: Track) => void;
  onClose: () => void;
  className?: string;
}

/**
 * AudioPlayerDock: Persistent liquid glass floating mini-player.
 * Anchored at the bottom of the screen to provide continuous playback controls,
 * real-time waveform visualization, and scrubbable progress across feed scrolling.
 */
export function AudioPlayerDock({
  track,
  isPlaying,
  audioElement,
  onTogglePlay,
  onClose,
  className = "",
}: AudioPlayerDockProps) {
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(30);

  useEffect(() => {
    if (!audioElement) {
      setCurrentTime(0);
      return;
    }

    const updateTimes = () => {
      if (!isNaN(audioElement.currentTime)) {
        setCurrentTime(audioElement.currentTime);
      }
      if (!isNaN(audioElement.duration) && audioElement.duration > 0) {
        setDuration(audioElement.duration);
      }
    };

    audioElement.addEventListener("timeupdate", updateTimes);
    audioElement.addEventListener("loadedmetadata", updateTimes);

    return () => {
      audioElement.removeEventListener("timeupdate", updateTimes);
      audioElement.removeEventListener("loadedmetadata", updateTimes);
    };
  }, [audioElement]);

  if (!track) return null;

  const formatTime = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const secs = Math.floor(sec % 60);
    return `${mins}:${secs < 10 ? "0" : ""}${secs}`;
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newTime = parseFloat(e.target.value);
    setCurrentTime(newTime);
    if (audioElement) {
      audioElement.currentTime = newTime;
    }
  };

  const pct = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div
      role="region"
      aria-label="Audio preview mini-player"
      data-testid="audio-player-dock"
      className={`fixed bottom-6 left-1/2 -translate-x-1/2 z-40 w-[calc(100%-2rem)] max-w-xl glass-panel-elevated rounded-full p-2 pl-2.5 pr-4 shadow-[0_24px_64px_rgba(0,0,0,0.85)] border border-white/[0.14] backdrop-blur-3xl animate-in fade-in slide-in-from-bottom-5 duration-300 ${className}`}
    >
      <div className="flex items-center justify-between gap-3 min-w-0">
        {/* Track Artwork & Play Trigger */}
        <div className="flex items-center gap-3 min-w-0">
          <div className="relative w-11 h-11 rounded-full bg-white/[0.08] border border-white/15 flex items-center justify-center text-[#fa2d55] flex-shrink-0 overflow-hidden shadow-md group">
            <Music className="w-5 h-5 text-[#fa2d55]/80" />
            {track.artwork_url ? (
              <img
                src={track.artwork_url}
                alt=""
                className="absolute inset-0 w-full h-full object-cover rounded-full"
                onError={(e) => {
                  e.currentTarget.style.display = "none";
                }}
              />
            ) : null}
            <button
              type="button"
              onClick={() => onTogglePlay(track)}
              aria-label={isPlaying ? `Pause preview for ${track.title}` : `Play preview for ${track.title}`}
              className={`absolute inset-0 flex items-center justify-center bg-black/60 transition-all ${
                isPlaying ? "opacity-100 text-[#fa2d55]" : "opacity-0 group-hover:opacity-100 text-white"
              }`}
            >
              {isPlaying ? (
                <Pause className="w-4 h-4 fill-current" />
              ) : (
                <Play className="w-4 h-4 fill-current translate-x-0.5" />
              )}
            </button>
          </div>

          {/* Track Info & Scrubber */}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h4 className="text-xs font-bold text-white truncate apple-heading tracking-tight">
                {track.title}
              </h4>
              <span className="text-white/40 text-[10px]">•</span>
              <p className="text-[11px] text-white/60 truncate font-normal">
                {track.artist_name}
              </p>
            </div>

            {/* Scrubbable Progress Slider */}
            <div className="flex items-center gap-2 mt-1">
              <span className="text-[10px] font-mono font-medium text-white/50 w-7 text-right">
                {formatTime(currentTime)}
              </span>
              <div className="relative flex-1 flex items-center">
                <input
                  type="range"
                  min="0"
                  max={duration || 30}
                  step="0.1"
                  value={currentTime}
                  onChange={handleSeek}
                  aria-label="Audio preview scrubber"
                  className="w-full h-1 bg-white/10 rounded-full appearance-none cursor-pointer accent-[#fa2d55] focus:outline-none focus:ring-1 focus:ring-[#fa2d55]"
                  style={{
                    background: `linear-gradient(to right, #fa2d55 0%, #fb7185 ${pct}%, rgba(255,255,255,0.1) ${pct}%, rgba(255,255,255,0.1) 100%)`,
                  }}
                />
              </div>
              <span className="text-[10px] font-mono font-medium text-white/40 w-7">
                {formatTime(duration)}
              </span>
            </div>
          </div>
        </div>

        {/* Live FFT Visualizer & Controls */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <AudioWaveVisualizer
            isPlaying={isPlaying}
            audioElement={audioElement}
            className="hidden sm:inline-flex"
          />

          <button
            type="button"
            onClick={() => onTogglePlay(track)}
            aria-label={isPlaying ? "Pause" : "Play"}
            className="w-9 h-9 rounded-full btn-ruby flex items-center justify-center shadow-md active:scale-95 transition-transform"
          >
            {isPlaying ? (
              <Pause className="w-4 h-4 fill-current text-white" />
            ) : (
              <Play className="w-4 h-4 fill-current text-white translate-x-0.5" />
            )}
          </button>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close preview player"
            className="w-7 h-7 rounded-full text-white/50 hover:text-white hover:bg-white/10 flex items-center justify-center transition-colors focus:outline-none focus:ring-1 focus:ring-white/40"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
