"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import { Music, Play, Pause, X, SkipBack, SkipForward, Repeat, Volume2, Volume1, VolumeX, AudioLines, Loader2, Radio } from "lucide-react";
import { Track } from "../../store";
import { AudioWaveVisualizer } from "./AudioWaveVisualizer";
import { SourceBadge, getTrackSource } from "./SourceBadge";

interface AudioPlayerDockProps {
  track: Track | null;
  isPlaying: boolean;
  isBuffering?: boolean;
  audioElement: HTMLAudioElement | null;
  volume?: number;
  isMuted?: boolean;
  onVolumeChange?: (volume: number) => void;
  onToggleMute?: () => void;
  onTogglePlay: (track: Track) => void;
  onNextTrack?: () => void;
  onPrevTrack?: () => void;
  hasNextTrack?: boolean;
  hasPrevTrack?: boolean;
  autoAdvance?: boolean;
  onToggleAutoAdvance?: () => void;
  crossfadeEnabled?: boolean;
  onToggleCrossfade?: () => void;
  onClose: () => void;
  className?: string;
}

/**
 * AudioPlayerDock: Persistent liquid glass floating mini-player.
 * Anchored at the bottom of the screen to provide continuous playback controls,
 * volume & mute calibration, optional 500ms crossfade, queue auto-advancement,
 * real-time waveform visualization, and scrubbable progress across feed scrolling.
 */
export function AudioPlayerDock({
  track,
  isPlaying,
  isBuffering = false,
  audioElement,
  volume,
  isMuted,
  onVolumeChange,
  onToggleMute,
  onTogglePlay,
  onNextTrack,
  onPrevTrack,
  hasNextTrack = false,
  hasPrevTrack = false,
  autoAdvance = true,
  onToggleAutoAdvance,
  crossfadeEnabled = true,
  onToggleCrossfade,
  onClose,
  className = "",
}: AudioPlayerDockProps) {
  const trackDuration =
    track?.duration_sec && track.duration_sec > 0
      ? track.duration_sec
      : track?.duration_ms && track.duration_ms > 0
      ? Math.round(track.duration_ms / 1000)
      : 30;

  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(trackDuration);
  const [isScrubbing, setIsScrubbing] = useState(false);
  const [internalBuffering, setInternalBuffering] = useState(false);
  const [bufferedPct, setBufferedPct] = useState(0);
  const [hoverPosition, setHoverPosition] = useState<{ x: number; time: number; pct: number } | null>(null);
  const scrubberContainerRef = useRef<HTMLDivElement>(null);

  const [internalVolume, setInternalVolume] = useState(() => {
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem("melovia_preview_volume");
        if (saved !== null) {
          const parsed = parseFloat(saved);
          if (!isNaN(parsed) && parsed >= 0 && parsed <= 1) return parsed;
        }
      } catch {
        // ignore
      }
    }
    return 0.8;
  });
  const [internalMuted, setInternalMuted] = useState(false);

  const effectiveVolume = volume !== undefined ? volume : internalVolume;
  const effectiveMuted = isMuted !== undefined ? isMuted : internalMuted;
  const effectiveBuffering = isBuffering || internalBuffering;

  useEffect(() => {
    if (audioElement && !isNaN(audioElement.duration) && audioElement.duration > 0) {
      setDuration(audioElement.duration);
    } else {
      setDuration(trackDuration);
    }
  }, [track?.id, trackDuration, audioElement]);

  useEffect(() => {
    if (!audioElement) {
      setCurrentTime(0);
      setInternalBuffering(false);
      setBufferedPct(0);
      return;
    }

    const updateTimes = () => {
      if (!isScrubbing && !isNaN(audioElement.currentTime)) {
        setCurrentTime(audioElement.currentTime);
      }
      if (!isNaN(audioElement.duration) && audioElement.duration > 0) {
        setDuration(audioElement.duration);
      }
      if (audioElement.buffered.length > 0) {
        try {
          const end = audioElement.buffered.end(audioElement.buffered.length - 1);
          const dur = audioElement.duration || duration || 30;
          setBufferedPct(Math.min(100, Math.max(0, (end / dur) * 100)));
        } catch {
          // ignore
        }
      }
    };

    const handleWaiting = () => setInternalBuffering(true);
    const handlePlaying = () => setInternalBuffering(false);
    const handleCanPlay = () => setInternalBuffering(false);

    updateTimes();
    if (isPlaying && audioElement.readyState < 3) {
      setInternalBuffering(true);
    } else {
      setInternalBuffering(false);
    }

    audioElement.addEventListener("timeupdate", updateTimes);
    audioElement.addEventListener("loadedmetadata", updateTimes);
    audioElement.addEventListener("progress", updateTimes);
    audioElement.addEventListener("waiting", handleWaiting);
    audioElement.addEventListener("playing", handlePlaying);
    audioElement.addEventListener("canplay", handleCanPlay);
    audioElement.addEventListener("canplaythrough", handleCanPlay);

    return () => {
      audioElement.removeEventListener("timeupdate", updateTimes);
      audioElement.removeEventListener("loadedmetadata", updateTimes);
      audioElement.removeEventListener("progress", updateTimes);
      audioElement.removeEventListener("waiting", handleWaiting);
      audioElement.removeEventListener("playing", handlePlaying);
      audioElement.removeEventListener("canplay", handleCanPlay);
      audioElement.removeEventListener("canplaythrough", handleCanPlay);
    };
  }, [audioElement, isPlaying, isScrubbing, duration]);

  const seekToClientX = useCallback(
    (clientX: number) => {
      if (!scrubberContainerRef.current) return;
      const rect = scrubberContainerRef.current.getBoundingClientRect();
      if (rect.width <= 0) return;
      const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      const targetDuration = duration > 0 ? duration : 30;
      const newTime = ratio * targetDuration;
      setCurrentTime(newTime);
      if (audioElement) {
        audioElement.currentTime = newTime;
      }
    },
    [audioElement, duration]
  );

  const handleScrubberMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    setIsScrubbing(true);
    seekToClientX(e.clientX);
  };

  const handleScrubberTouchStart = (e: React.TouchEvent<HTMLDivElement>) => {
    if (e.touches.length > 0) {
      setIsScrubbing(true);
      seekToClientX(e.touches[0].clientX);
    }
  };

  useEffect(() => {
    if (!isScrubbing) return;

    const handleWindowMouseMove = (e: MouseEvent) => {
      seekToClientX(e.clientX);
    };

    const handleWindowTouchMove = (e: TouchEvent) => {
      if (e.touches.length > 0) {
        seekToClientX(e.touches[0].clientX);
      }
    };

    const handleWindowMouseUp = () => {
      setIsScrubbing(false);
    };

    window.addEventListener("mousemove", handleWindowMouseMove);
    window.addEventListener("mouseup", handleWindowMouseUp);
    window.addEventListener("touchmove", handleWindowTouchMove, { passive: true });
    window.addEventListener("touchend", handleWindowMouseUp);

    return () => {
      window.removeEventListener("mousemove", handleWindowMouseMove);
      window.removeEventListener("mouseup", handleWindowMouseUp);
      window.removeEventListener("touchmove", handleWindowTouchMove);
      window.removeEventListener("touchend", handleWindowMouseUp);
    };
  }, [isScrubbing, seekToClientX]);

  const seekDelta = (seconds: number) => {
    const targetDuration = duration > 0 ? duration : 30;
    const newTime = Math.max(0, Math.min(targetDuration, currentTime + seconds));
    setCurrentTime(newTime);
    if (audioElement) {
      audioElement.currentTime = newTime;
    }
  };

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

  const handleScrubberMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!scrubberContainerRef.current) return;
    const rect = scrubberContainerRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(rect.width, e.clientX - rect.left));
    const p = rect.width > 0 ? x / rect.width : 0;
    const time = p * (duration || 30);
    setHoverPosition({ x, time, pct: p * 100 });
  };

  const handleScrubberMouseLeave = () => {
    setHoverPosition(null);
  };

  const handleVolumeInput = (val: number) => {
    if (onVolumeChange) {
      onVolumeChange(val);
    } else {
      setInternalVolume(val);
      if (audioElement) {
        audioElement.volume = effectiveMuted ? 0 : val;
      }
    }
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem("melovia_preview_volume", val.toString());
      } catch {
        // ignore
      }
    }
  };

  const handleToggleMuteClick = () => {
    if (onToggleMute) {
      onToggleMute();
    } else {
      setInternalMuted((prev) => !prev);
      if (audioElement) {
        audioElement.volume = !internalMuted ? 0 : internalVolume;
      }
    }
  };

  const pct = duration > 0 ? (currentTime / duration) * 100 : 0;
  const volPct = Math.round((effectiveMuted ? 0 : effectiveVolume) * 100);

  const source = getTrackSource(track);
  const streamQuality =
    source === "saavn"
      ? "HQ Stream"
      : source === "itunes"
      ? "AAC Preview"
      : "Catalog Preview";

  return (
    <div
      role="region"
      aria-label="Audio preview mini-player"
      data-testid="audio-player-dock"
      className={`fixed bottom-6 left-1/2 -translate-x-1/2 z-40 w-[calc(100%-2rem)] max-w-3xl glass-panel-elevated rounded-full p-2 pl-2.5 pr-4 shadow-[0_24px_64px_rgba(0,0,0,0.85)] border border-white/[0.14] backdrop-blur-3xl animate-in fade-in slide-in-from-bottom-5 duration-300 ${className}`}
    >
      <div className="flex items-center justify-between gap-3 min-w-0">
        {/* Track Artwork & Play Trigger */}
        <div className="flex items-center gap-3 min-w-0 flex-1">
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
              aria-label={
                effectiveBuffering
                  ? "Buffering preview..."
                  : isPlaying
                  ? `Pause preview for ${track.title}`
                  : `Play preview for ${track.title}`
              }
              data-testid="dock-artwork-play-btn"
              className={`absolute inset-0 flex items-center justify-center bg-black/60 transition-all ${
                isPlaying || effectiveBuffering
                  ? "opacity-100 text-[#fa2d55]"
                  : "opacity-0 group-hover:opacity-100 text-white"
              }`}
            >
              {effectiveBuffering ? (
                <Loader2 className="w-4 h-4 animate-spin text-[#fa2d55]" />
              ) : isPlaying ? (
                <Pause className="w-4 h-4 fill-current" />
              ) : (
                <Play className="w-4 h-4 fill-current translate-x-0.5" />
              )}
            </button>
          </div>

          {/* Track Info & Scrubber */}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5 min-w-0 flex-wrap">
              <h4 className="text-xs font-bold text-white truncate apple-heading tracking-tight max-w-[140px] sm:max-w-[200px]">
                {track.title}
              </h4>
              <span className="text-white/40 text-[10px]">•</span>
              <p className="text-[11px] text-white/60 truncate font-normal max-w-[100px] sm:max-w-[160px]">
                {track.artist_name}
              </p>
              <SourceBadge track={track} compact />
              <span
                data-testid="dock-stream-quality"
                className="hidden md:inline-flex items-center gap-1 text-[9px] font-mono text-white/50 px-1.5 py-0.5 rounded-md bg-white/5 border border-white/10"
              >
                {streamQuality}
              </span>
            </div>

            {/* Scrubbable Progress Slider */}
            <div className="flex items-center gap-2 mt-1">
              <span className="text-[10px] font-mono font-medium text-white/50 w-7 text-right">
                {formatTime(currentTime)}
              </span>
              <div
                ref={scrubberContainerRef}
                onMouseDown={handleScrubberMouseDown}
                onTouchStart={handleScrubberTouchStart}
                onMouseMove={handleScrubberMouseMove}
                onMouseLeave={handleScrubberMouseLeave}
                tabIndex={0}
                role="slider"
                aria-label="Audio scrubber"
                aria-valuemin={0}
                aria-valuemax={duration || 30}
                aria-valuenow={currentTime}
                aria-valuetext={`${formatTime(currentTime)} of ${formatTime(duration)}`}
                onKeyDown={(e) => {
                  if (e.key === "ArrowLeft" || e.key === "j" || e.key === "J") {
                    e.preventDefault();
                    seekDelta(-5);
                  } else if (e.key === "ArrowRight" || e.key === "l" || e.key === "L") {
                    e.preventDefault();
                    seekDelta(5);
                  } else if (e.key === " ") {
                    e.preventDefault();
                    onTogglePlay(track);
                  }
                }}
                className="relative flex-1 flex items-center group/scrubber h-5 cursor-pointer select-none focus:outline-none focus:ring-1 focus:ring-[#fa2d55]/70 rounded-full"
              >
                {/* Floating Liquid Glass Timestamp Tooltip on Hover */}
                {hoverPosition && (
                  <div
                    data-testid="scrubber-hover-tooltip"
                    className="absolute -top-7 -translate-x-1/2 px-2 py-0.5 rounded-md glass-panel text-[10px] font-mono font-bold text-white shadow-lg pointer-events-none border border-white/20 z-50 flex items-center gap-1 animate-in fade-in zoom-in-95 duration-100"
                    style={{ left: `${hoverPosition.pct}%` }}
                  >
                    <span>{formatTime(hoverPosition.time)}</span>
                  </div>
                )}

                {/* Dynamic Waveform Spectrum Track behind progress slider */}
                <div
                  className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-3 flex items-center justify-between px-0.5 opacity-30 group-hover/scrubber:opacity-65 transition-opacity overflow-hidden pointer-events-none"
                  aria-hidden="true"
                >
                  {Array.from({ length: 30 }).map((_, idx) => {
                    const barPct = (idx / 30) * 100;
                    const isPassed = barPct <= pct;
                    const isBuffered = barPct <= bufferedPct;
                    const heights = [3, 5, 8, 4, 10, 6, 12, 5, 7, 11, 4, 8, 12, 6, 9, 5, 11, 8, 4, 12, 6, 9, 5, 8, 11, 4, 7, 3, 9, 4];
                    const h = heights[idx % heights.length];
                    return (
                      <span
                        key={idx}
                        className={`w-0.5 rounded-full transition-all duration-150 ${
                          isPassed
                            ? "bg-[#fa2d55] shadow-[0_0_6px_rgba(250,45,85,0.6)]"
                            : isBuffered
                            ? "bg-white/40"
                            : "bg-white/15"
                        }`}
                        style={{ height: `${h}px` }}
                      />
                    );
                  })}
                </div>

                {/* Network Buffer Range Bar */}
                {bufferedPct > 0 && (
                  <div
                    data-testid="buffered-range-bar"
                    aria-hidden="true"
                    className="absolute left-0 top-1/2 -translate-y-1/2 h-1 bg-white/20 rounded-full pointer-events-none transition-[width] duration-300"
                    style={{ width: `${bufferedPct}%` }}
                  />
                )}

                {/* Native Range Slider for Full Accessibility */}
                <input
                  type="range"
                  min="0"
                  max={duration || 30}
                  step="0.1"
                  value={currentTime}
                  onChange={handleSeek}
                  aria-label="Audio preview scrubber"
                  className="w-full h-1 bg-white/10 rounded-full appearance-none cursor-pointer accent-[#fa2d55] focus:outline-none relative z-10"
                  style={{
                    background: `linear-gradient(to right, #fa2d55 0%, #fb7185 ${pct}%, transparent ${pct}%, transparent 100%)`,
                  }}
                />
              </div>
              <span className="text-[10px] font-mono font-medium text-white/40 w-7">
                {formatTime(duration)}
              </span>
            </div>
          </div>
        </div>

        {/* Live FFT Visualizer & Queue Controls */}
        <div className="flex items-center gap-1.5 sm:gap-2 flex-shrink-0">
          <AudioWaveVisualizer
            isPlaying={isPlaying}
            audioElement={audioElement}
            className="hidden lg:inline-flex"
          />

          {/* Volume Control & Mute Button */}
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={handleToggleMuteClick}
              aria-label={effectiveMuted ? "Unmute audio" : "Mute audio"}
              data-testid="mute-toggle-btn"
              title={effectiveMuted ? "Unmute (M)" : "Mute (M)"}
              className={`p-1.5 rounded-full transition-colors focus:outline-none focus:ring-1 focus:ring-[#fa2d55] ${
                effectiveMuted || effectiveVolume === 0
                  ? "text-[#fa2d55] hover:text-[#fb7185] bg-[#fa2d55]/10"
                  : "text-white/60 hover:text-white hover:bg-white/10"
              }`}
            >
              {effectiveMuted || effectiveVolume === 0 ? (
                <VolumeX className="w-3.5 h-3.5 text-[#fa2d55]" />
              ) : effectiveVolume < 0.5 ? (
                <Volume1 className="w-3.5 h-3.5" />
              ) : (
                <Volume2 className="w-3.5 h-3.5" />
              )}
            </button>

            <div className="hidden sm:flex items-center w-14 sm:w-16">
              <input
                type="range"
                min="0"
                max="1"
                step="0.01"
                value={effectiveMuted ? 0 : effectiveVolume}
                onChange={(e) => handleVolumeInput(parseFloat(e.target.value))}
                aria-label="Volume slider"
                data-testid="volume-slider"
                title={`Volume: ${volPct}%`}
                className="w-full h-1 bg-white/15 rounded-full appearance-none cursor-pointer accent-[#fa2d55] focus:outline-none focus:ring-1 focus:ring-[#fa2d55]"
                style={{
                  background: `linear-gradient(to right, #fa2d55 0%, #fa2d55 ${volPct}%, rgba(255,255,255,0.15) ${volPct}%, rgba(255,255,255,0.15) 100%)`,
                }}
              />
            </div>
          </div>

          {/* Crossfade 500ms Toggle Button */}
          {onToggleCrossfade && (
            <button
              type="button"
              onClick={onToggleCrossfade}
              aria-label={crossfadeEnabled ? "Disable 500ms audio crossfade" : "Enable 500ms audio crossfade"}
              data-testid="crossfade-toggle"
              title={crossfadeEnabled ? "Crossfade: 500ms smooth transition" : "Crossfade: Off"}
              className={`hidden sm:flex p-1.5 rounded-full transition-all focus:outline-none focus:ring-1 focus:ring-[#8b5cf6] ${
                crossfadeEnabled
                  ? "bg-[#8b5cf6]/20 text-[#c084fc] border border-[#8b5cf6]/40 shadow-[0_0_10px_rgba(139,92,246,0.3)]"
                  : "text-white/40 hover:text-white/70 hover:bg-white/5 border border-transparent"
              }`}
            >
              <AudioLines className="w-3.5 h-3.5" />
            </button>
          )}

          {/* Auto-Advance Toggle Button */}
          {onToggleAutoAdvance && (
            <button
              type="button"
              onClick={onToggleAutoAdvance}
              aria-label={autoAdvance ? "Disable queue auto-play" : "Enable queue auto-play"}
              data-testid="auto-advance-toggle"
              title={autoAdvance ? "Auto-Play: Automatically advances to next preview" : "Auto-Play: Off"}
              className={`p-1.5 rounded-full transition-all focus:outline-none focus:ring-1 focus:ring-[#fa2d55] ${
                autoAdvance
                  ? "bg-[#fa2d55]/20 text-[#fa2d55] border border-[#fa2d55]/40 shadow-[0_0_10px_rgba(250,45,85,0.3)]"
                  : "text-white/40 hover:text-white/70 hover:bg-white/5 border border-transparent"
              }`}
            >
              <Repeat className="w-3.5 h-3.5" />
            </button>
          )}

          {/* Previous Track */}
          {onPrevTrack && (
            <button
              type="button"
              onClick={onPrevTrack}
              disabled={!hasPrevTrack}
              aria-label="Previous track"
              data-testid="prev-track-btn"
              className="p-1.5 rounded-full text-white/70 hover:text-white hover:bg-white/10 transition-colors disabled:opacity-30 disabled:cursor-not-allowed focus:outline-none focus:ring-1 focus:ring-white/40"
            >
              <SkipBack className="w-4 h-4 fill-current" />
            </button>
          )}

          {/* Main Play / Pause Trigger */}
          <button
            type="button"
            onClick={() => onTogglePlay(track)}
            aria-label={effectiveBuffering ? "Buffering" : isPlaying ? "Pause" : "Play"}
            data-testid="dock-main-play-btn"
            className="w-9 h-9 rounded-full btn-ruby flex items-center justify-center shadow-md active:scale-95 transition-transform"
          >
            {effectiveBuffering ? (
              <Loader2 className="w-4 h-4 animate-spin text-white" />
            ) : isPlaying ? (
              <Pause className="w-4 h-4 fill-current text-white" />
            ) : (
              <Play className="w-4 h-4 fill-current text-white translate-x-0.5" />
            )}
          </button>

          {/* Next Track */}
          {onNextTrack && (
            <button
              type="button"
              onClick={onNextTrack}
              disabled={!hasNextTrack}
              aria-label="Next track"
              data-testid="next-track-btn"
              className="p-1.5 rounded-full text-white/70 hover:text-white hover:bg-white/10 transition-colors disabled:opacity-30 disabled:cursor-not-allowed focus:outline-none focus:ring-1 focus:ring-white/40"
            >
              <SkipForward className="w-4 h-4 fill-current" />
            </button>
          )}

          {/* Dismiss Player Button */}
          <button
            type="button"
            onClick={onClose}
            aria-label="Close preview player"
            className="w-7 h-7 rounded-full text-white/50 hover:text-white hover:bg-white/10 flex items-center justify-center transition-colors focus:outline-none focus:ring-1 focus:ring-white/40 ml-0.5"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
