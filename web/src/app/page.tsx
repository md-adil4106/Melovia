"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  Bookmark,
  BookmarkCheck,
  BookmarkPlus,
  Compass,
  Download,
  Globe,
  Headphones,
  HelpCircle,
  ListMusic,
  MessageSquare,
  Moon,
  Music,
  Pause,
  Play,
  Plus,
  Radio,
  RefreshCw,
  Search,
  Shield,
  SkipForward,
  Sliders,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  Volume2,
  X,
} from "lucide-react";
import dynamic from "next/dynamic";
import { Track, RecommendedItem, useDiscoveryStore } from "./store";
import { WhyDrawer } from "./components/WhyDrawer";
import { ChatDrawer } from "./components/ChatDrawer";
import { SettingsDrawer } from "./components/SettingsDrawer";
import { PlaylistBuilder } from "./components/PlaylistBuilder";
import { ProfileView } from "./components/ProfileView";
import { ExportModal } from "./components/export/ExportModal";
import { HeroParticleField } from "./components/HeroParticleField";
import { Button } from "./components/ui/Button";
import { Card } from "./components/ui/Card";
import { Chip } from "./components/ui/Chip";
import { Slider } from "./components/ui/Slider";
import { Toast } from "./components/ui/Toast";
import { ErrorState } from "./components/ui/ErrorState";
import { FlaskConical } from "lucide-react";

const TasteUniverseModal = dynamic(
  () => import("./components/universe/TasteUniverseModal"),
  { ssr: false }
);

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface SeedPreset {
  id: string;
  name: string;
  description: string;
  tracks: Track[];
}

const SAMPLE_PRESETS: SeedPreset[] = [
  {
    id: "night-drive",
    name: "Night Drive",
    description: "Driving synths & dark electric energy",
    tracks: [
      {
        id: "e6e33bfb-d1c8-52c4-b400-09b91558864b",
        track_idx: 1,
        title: "Electric Gravity",
        artist_name: "Ghost Echo",
        artist_id: "artist_1",
        year: 2020,
        popularity_pct: 70,
        has_a: true,
        has_t: true,
      },
      {
        id: "9558a519-9578-5a1e-bf33-0e61c9c274b4",
        track_idx: 4,
        title: "Fractured Glitch",
        artist_name: "Stellar Shade",
        artist_id: "artist_4",
        year: 2021,
        popularity_pct: 65,
        has_a: true,
        has_t: true,
      },
    ],
  },
  {
    id: "ambient-focus",
    name: "Ambient Focus",
    description: "Deep starlight, spatial resonance & calm",
    tracks: [
      {
        id: "b7ac542c-1b90-550d-a778-f94510231bd5",
        track_idx: 2,
        title: "Quiet Starlight",
        artist_name: "Mirage Signals",
        artist_id: "artist_2",
        year: 2019,
        popularity_pct: 60,
        has_a: true,
        has_t: true,
      },
      {
        id: "c73dc950-5de6-54c7-8fb6-2d8c095521ef",
        track_idx: 3,
        title: "Floating Resonance",
        artist_name: "Amber Frequency",
        artist_id: "artist_3",
        year: 2022,
        popularity_pct: 58,
        has_a: true,
        has_t: true,
      },
    ],
  },
  {
    id: "cosmic-drift",
    name: "Cosmic Drift",
    description: "Reflective space ambient & subtle pulses",
    tracks: [
      {
        id: "f312f449-e24b-5b91-83a4-69c6e61ff5b1",
        track_idx: 0,
        title: "Endless Reflection, Pt. 1",
        artist_name: "Lunar Fables",
        artist_id: "artist_0",
        year: 2018,
        popularity_pct: 62,
        has_a: true,
        has_t: true,
      },
      {
        id: "ee84d0a1-0a12-5973-9b4e-de6a9635b586",
        track_idx: 8,
        title: "Quiet Pulse",
        artist_name: "Azure Frequency",
        artist_id: "artist_8",
        year: 2023,
        popularity_pct: 55,
        has_a: true,
        has_t: true,
      },
    ],
  },
];

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
    likedTrackIds,
    dislikedTrackIds,
    savedTrackIds,
    hasPersistentProfile,
    setHasPersistentProfile,
    tasteShiftedMessage,
    setTasteShiftedMessage,
    isSettingsDrawerOpen,
    setSettingsDrawerOpen,
    addLikedTrack,
    addDislikedTrack,
    toggleSavedTrack,
    isPlaylistBuilderOpen,
    setPlaylistBuilderOpen,
    activeTab,
    setActiveTab,
    exploringRegion,
    setExploringRegion,
    clearExploringRegion,
    setUniverseModalOpen,
    setUniverseFocusedRegionId,
  } = useDiscoveryStore();

  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const [sliderValue, setSliderValue] = useState(discovery);
  const [selectedTrackForWhy, setSelectedTrackForWhy] = useState<Track | null>(null);
  const [isWhyDrawerOpen, setIsWhyDrawerOpen] = useState(false);
  const [isMainExportOpen, setIsMainExportOpen] = useState(false);
  const [onboardingDismissed, setOnboardingDismissed] = useState(true);
  const [playingTrackId, setPlayingTrackId] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const handleTogglePlay = (track: Track) => {
    if (!track.preview_url) return;

    if (playingTrackId === track.id) {
      if (audioRef.current) {
        audioRef.current.pause();
      }
      setPlayingTrackId(null);
    } else {
      if (audioRef.current) {
        audioRef.current.pause();
      }
      const audio = new Audio(track.preview_url);
      audioRef.current = audio;
      audio.play().catch(() => {
        setPlayingTrackId(null);
      });
      audio.onended = () => {
        setPlayingTrackId(null);
      };
      audio.onerror = () => {
        setPlayingTrackId(null);
      };
      setPlayingTrackId(track.id);
    }
  };

  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    try {
      const saved = localStorage.getItem("melovia_onboarding_dismissed");
      if (!saved) {
        setOnboardingDismissed(false);
      }
    } catch {
      // ignore
    }
  }, []);

  const handleDismissOnboarding = () => {
    setOnboardingDismissed(true);
    try {
      localStorage.setItem("melovia_onboarding_dismissed", "true");
    } catch {
      // ignore
    }
  };

  const handleApplyPreset = (preset: SeedPreset) => {
    clearSeeds();
    preset.tracks.forEach((t) => addSeed(t));
    recommendMutation.mutate({
      seedIds: preset.tracks.map((t) => t.id),
      d: sliderValue,
    });
  };

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
    mutationFn: async ({
      seedIds,
      d,
      useSavedTaste = false,
      regionId = null,
    }: {
      seedIds?: string[];
      d: number;
      useSavedTaste?: boolean;
      regionId?: number | null;
    }) => {
      const res = await fetch(`${API_BASE}/recommendations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          seed_track_ids: seedIds || [],
          use_saved_taste: useSavedTaste,
          n: 30,
          discovery: d,
          region_id: regionId,
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

  // Mutation for submitting live user interaction feedback
  const feedbackMutation = useMutation({
    mutationFn: async ({ trackId, event }: { trackId: string; event: string }) => {
      const res = await fetch(`${API_BASE}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          track_id: trackId,
          event,
          candidate_set_id: candidateSetId || undefined,
        }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData?.error?.message || "Failed to submit feedback");
      }
      return await res.json();
    },
    onSuccess: (data, variables) => {
      if (variables.event === "like") {
        addLikedTrack(variables.trackId);
      } else if (variables.event === "dislike") {
        addDislikedTrack(variables.trackId);
      } else if (variables.event === "save") {
        toggleSavedTrack(variables.trackId);
      }

      if (data.items && data.items.length > 0) {
        setRecommendations(data.items);
      }

      if (data.mode_shifted) {
        const shiftVal = data.cosine_shift;
        const sign = shiftVal > 0 ? "+" : "";
        setTasteShiftedMessage(
          variables.event === "like"
            ? `Taste shifted (${sign}${shiftVal} toward this vibe)`
            : `Taste shifted (${sign}${shiftVal})`
        );
        setTimeout(() => setTasteShiftedMessage(null), 3000);
      }
    },
  });

  // Mutation for explicitly merging session modes into persistent profile
  const rememberMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${API_BASE}/profile/remember`, {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData?.error?.message || "Failed to remember taste profile");
      }
      return await res.json();
    },
    onSuccess: (data) => {
      setHasPersistentProfile(true);
      setTasteShiftedMessage(`Saved ${data.num_modes} taste modes to persistent profile!`);
      setTimeout(() => setTasteShiftedMessage(null), 3500);
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
      regionId: exploringRegion?.id || null,
    });
  };

  const handleExploreRegion = (regionId: number, regionName: string) => {
    setExploringRegion({ id: regionId, name: regionName });
    setActiveTab("discover");
    if (seeds.length > 0 || hasPersistentProfile) {
      recommendMutation.mutate({
        seedIds: seeds.map((s) => s.id),
        d: sliderValue,
        useSavedTaste: seeds.length === 0 && hasPersistentProfile,
        regionId: regionId,
      });
    }
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
    <main className="min-h-screen aurora-bg text-white font-sans pb-24 selection:bg-[#fa2d55]/30 selection:text-white">
      {/* Top Header */}
      <header className="border-b border-white/[0.08] bg-[#07080b]/75 backdrop-blur-2xl sticky top-0 z-40 transition-all">
        <div className="max-w-6xl mx-auto px-4 py-3.5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-[#fa2d55] via-[#fb7185] to-[#8b5cf6] flex items-center justify-center text-white font-bold shadow-[0_0_20px_rgba(250,45,85,0.4)]">
              <Compass className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-white font-sans">
                MELOVIA
              </h1>
              <p className="text-xs text-white/50 tracking-wide font-medium">Explainable Music Discovery</p>
            </div>
          </div>

          {/* Navigation Tabs (Discover vs Taste Profile) */}
          <nav className="flex items-center bg-white/[0.06] p-1 rounded-lg border border-white/10 backdrop-blur-md" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === "discover"}
              aria-label="Discover"
              onClick={() => setActiveTab("discover")}
              className={`px-3.5 py-1.5 rounded-md text-xs font-semibold transition-all ${
                activeTab === "discover"
                  ? "bg-white/[0.14] text-white shadow-sm"
                  : "text-white/60 hover:text-white"
              }`}
            >
              Discover
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === "profile"}
              aria-label="Taste DNA"
              onClick={() => setActiveTab("profile")}
              className={`px-3.5 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 transition-all ${
                activeTab === "profile"
                  ? "bg-white/[0.14] text-white shadow-sm"
                  : "text-white/60 hover:text-white"
              }`}
            >
              <Sparkles className="w-3.5 h-3.5 text-[#fb7185]" />
              <span>Taste DNA</span>
            </button>
          </nav>

          {/* Right Header Actions */}
          <div className="flex items-center gap-2 text-xs">
            {/* Conversational Steering Chat Button */}
            <button
              type="button"
              onClick={() => setChatDrawerOpen(true)}
              aria-label="Open Conversational Refinement"
              className="flex items-center gap-1.5 text-xs text-white/80 hover:text-white bg-white/[0.05] hover:bg-white/[0.1] border border-white/10 px-3 py-1.5 rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-[#fa2d55]"
            >
              <MessageSquare className="w-3.5 h-3.5 text-[#fa2d55]" />
              <span className="hidden sm:inline">Chat Refine</span>
            </button>

            {/* Playlist Builder Button */}
            <button
              type="button"
              onClick={() => setPlaylistBuilderOpen(true)}
              aria-label="Open Playlist Sequencing"
              className="flex items-center gap-1.5 text-xs text-white/80 hover:text-white bg-white/[0.05] hover:bg-white/[0.1] border border-white/10 px-3 py-1.5 rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-[#fa2d55]"
            >
              <ListMusic className="w-3.5 h-3.5 text-[#fb7185]" />
              <span className="hidden sm:inline">Playlist Arcs</span>
            </button>

            {/* 3D Taste Universe Map Button (Phase 12) */}
            <button
              type="button"
              onClick={() => setUniverseModalOpen(true)}
              aria-label="Open 3D Taste Universe interactive starfield map"
              className="flex items-center gap-1.5 text-xs text-white bg-gradient-to-r from-[#fa2d55]/15 to-[#8b5cf6]/15 hover:from-[#fa2d55]/25 hover:to-[#8b5cf6]/25 border border-[#fa2d55]/30 px-3 py-1.5 rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-[#fa2d55] shadow-sm"
            >
              <Globe className="w-3.5 h-3.5 text-[#fa2d55]" />
              <span className="font-semibold hidden sm:inline">3D Universe</span>
            </button>

            {/* Study Mode Button (Phase 15) */}
            <a
              href="/study"
              aria-label="Open blind A/B evaluation study mode"
              className="flex items-center gap-1.5 text-xs text-sky-200 hover:text-white bg-sky-500/15 hover:bg-sky-500/25 border border-sky-500/30 px-3 py-1.5 rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-sky-400"
            >
              <FlaskConical className="w-3.5 h-3.5 text-sky-300" />
              <span className="font-semibold hidden sm:inline">Study Mode</span>
            </a>

            {/* Anonymous Taste Profile & Settings Button */}
            <button
              type="button"
              onClick={() => setSettingsDrawerOpen(true)}
              aria-label="Open anonymous taste profile and device settings"
              className="flex items-center gap-1.5 text-xs text-white/80 hover:text-white bg-white/[0.05] hover:bg-white/[0.1] border border-white/10 px-3 py-1.5 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-[#fa2d55]"
            >
              <Shield className="w-3.5 h-3.5 text-[#fb7185]" />
              <span className="hidden md:inline">Privacy & Sync</span>
              {hasPersistentProfile && (
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" title="Profile saved" />
              )}
            </button>

            {/* Backend Status Indicator */}
            {healthData ? (
              <span className="flex items-center gap-1.5 text-emerald-300 bg-emerald-500/10 border border-emerald-500/30 px-2.5 py-1 rounded-lg text-xs font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Catalog {healthData.catalog?.version || "ready"} ({healthData.catalog?.track_count?.toLocaleString() || 0} tracks)
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-amber-300 bg-amber-500/10 border border-amber-500/30 px-2.5 py-1 rounded-lg text-xs">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                Connecting...
              </span>
            )}
          </div>
        </div>
      </header>

      {/* Main Container */}
      <div className="max-w-4xl mx-auto px-4 pt-8">
        {activeTab === "profile" ? (
          <ProfileView onExploreRegion={handleExploreRegion} />
        ) : (
          <>
            {/* Exploring Region Banner */}
            {exploringRegion && (
              <div className="mb-6 p-4 bg-gradient-to-r from-[#fa2d55]/10 via-[#8b5cf6]/10 to-transparent border border-[#fa2d55]/30 rounded-2xl flex items-center justify-between shadow-lg backdrop-blur-xl">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl bg-[#fa2d55]/20 border border-[#fa2d55]/40 flex items-center justify-center text-[#fa2d55]">
                    <Compass className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-bold text-[#fa2d55] uppercase tracking-wider">
                        Exploring Region {exploringRegion.id}
                      </span>
                      <span className="text-xs text-white/50">• Adjacent Blindspot</span>
                    </div>
                    <h4 className="text-sm font-bold text-white">{exploringRegion.name}</h4>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    clearExploringRegion();
                    if (seeds.length > 0 || hasPersistentProfile) {
                      recommendMutation.mutate({
                        seedIds: seeds.map((s) => s.id),
                        d: sliderValue,
                        useSavedTaste: seeds.length === 0 && hasPersistentProfile,
                        regionId: null,
                      });
                    }
                  }}
                  className="px-3.5 py-1.5 bg-white/[0.08] hover:bg-white/[0.15] border border-white/10 text-xs text-white/80 hover:text-white rounded-full transition-colors"
                >
                  Exit Exploration
                </button>
              </div>
            )}
        {/* Hero Section with Ambient Particle Field */}
        <section className="relative overflow-hidden rounded-2xl p-7 sm:p-9 mb-8 border border-white/[0.08] bg-gradient-to-b from-white/[0.05] to-white/[0.015] backdrop-blur-2xl text-center shadow-[0_20px_50px_rgba(0,0,0,0.5)]">
          <HeroParticleField />
          <div className="relative z-10">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-md bg-white/[0.06] border border-white/10 text-xs text-[#fa2d55] mb-3 backdrop-blur-md shadow-sm font-medium">
              <Sparkles className="w-3.5 h-3.5 text-[#fa2d55]" />
              <span>Interactive Discovery Control (WOW #1)</span>
            </div>
            <h2 className="text-3xl sm:text-5xl font-black text-white tracking-tight mb-3">
              Steerable Discovery from Seed Tracks
            </h2>
            <p className="text-sm sm:text-base text-white/60 max-w-xl mx-auto mb-6 leading-relaxed">
              Choose 1 to 10 seed tracks, then dynamically tune the Familiarity ↔ Discovery slider to traverse from familiar sounds to exploratory musical horizons.
            </p>

            {/* Curated Sample Seed Presets (<= 2 clicks to recommendations) */}
            <div className="flex flex-wrap items-center justify-center gap-2.5">
              <span className="text-xs text-white/50 font-semibold uppercase tracking-wider mr-1">
                Quick Presets:
              </span>
              {SAMPLE_PRESETS.map((preset) => (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => handleApplyPreset(preset)}
                  className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-white/[0.06] hover:bg-white/[0.12] border border-white/10 hover:border-[#fa2d55]/50 text-white transition-all transform active:scale-95 shadow-sm backdrop-blur-md"
                  title={preset.description}
                >
                  {preset.id === "night-drive" && <Moon className="w-3.5 h-3.5 text-[#fb7185]" />}
                  {preset.id === "ambient-focus" && <Radio className="w-3.5 h-3.5 text-[#38bdf8]" />}
                  {preset.id === "cosmic-drift" && <Sparkles className="w-3.5 h-3.5 text-[#a78bfa]" />}
                  <span className="font-semibold">{preset.name}</span>
                </button>
              ))}
            </div>
          </div>
        </section>

        {/* 3-Step First-Run Hint Banner (Dismissible + Remembered) */}
        {!onboardingDismissed && (
          <div className="mb-6 p-5 bg-white/[0.035] border border-white/10 rounded-xl relative shadow-xl backdrop-blur-xl animate-in fade-in duration-300">
            <button
              type="button"
              onClick={handleDismissOnboarding}
              aria-label="Dismiss quick start guide"
              className="absolute top-3.5 right-3.5 text-white/60 hover:text-white p-1 rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-[#fa2d55]"
            >
              <X className="w-4 h-4" />
            </button>
            <div className="flex items-center gap-2 mb-3">
              <Sparkles className="w-4 h-4 text-[#fa2d55]" />
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                Quick Start Guide (3 Simple Steps)
              </h3>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs text-white/70">
              <div className="p-3.5 bg-white/[0.04] rounded-lg border border-white/[0.06]">
                <strong className="text-white block mb-1">1. Pick Seeds</strong>
                Search tracks or click a Quick Preset above to establish your initial taste beacon.
              </div>
              <div className="p-3.5 bg-white/[0.04] rounded-lg border border-white/[0.06]">
                <strong className="text-[#fb7185] block mb-1">2. Set Discovery</strong>
                Slide from Familiarity (0%) toward adventurous musical Discovery (100%).
              </div>
              <div className="p-3.5 bg-white/[0.04] rounded-lg border border-white/[0.06]">
                <strong className="text-[#38bdf8] block mb-1">3. Steer with Vibe</strong>
                Like, dislike, or use Conversational Refine to guide your path in real-time.
              </div>
            </div>
          </div>
        )}

        {/* Seed Search & Input Box */}
        <section className={`bg-white/[0.035] backdrop-blur-2xl border border-white/[0.08] rounded-xl p-5 sm:p-6 mb-8 shadow-[0_16px_40px_rgba(0,0,0,0.5)] transition-all ${isDropdownOpen && debouncedQuery.length >= 2 ? "relative z-40" : "relative z-20"}`}>
          <div className="flex items-center justify-between mb-3">
            <label htmlFor="seed-search" className="text-sm font-semibold text-white/90 flex items-center gap-2">
              <Search className="w-4 h-4 text-[#fa2d55]" />
              Search Seed Tracks
            </label>
            <span className="text-xs text-white/60">
              <strong className="text-[#fa2d55] font-bold">{seeds.length}</strong> / 10 seeds selected
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
              className="w-full bg-black/40 border border-white/10 hover:border-white/20 rounded-xl px-4 py-3 text-sm text-white placeholder-white/40 focus:outline-none focus:border-[#fa2d55] focus:ring-4 focus:ring-[#fa2d55]/20 transition-all shadow-inner backdrop-blur-md disabled:opacity-50"
            />

            {isSearchLoading && (
              <div className="absolute right-4 top-3.5 text-xs text-white/60 animate-spin">
                <RefreshCw className="w-5 h-5 text-[#fa2d55]" />
              </div>
            )}

            {/* Dropdown Suggestions */}
            {isDropdownOpen && debouncedQuery.length >= 2 && (
              <div
                ref={dropdownRef}
                className="absolute left-0 right-0 top-full mt-2 glass-dropdown rounded-xl shadow-[0_25px_60px_rgba(0,0,0,0.95)] z-50 overflow-hidden max-h-88 overflow-y-auto"
              >
                {searchResults && searchResults.length > 0 ? (
                  <div className="p-2 divide-y divide-white/[0.06]">
                    {searchResults.map((t, idx) => {
                      const isAlreadySeed = seeds.some((s) => s.id === t.id);
                      const isHighlighted = idx === highlightedIndex;
                      return (
                        <button
                          key={t.id}
                          type="button"
                          onClick={() => handleSelectTrack(t)}
                          disabled={isAlreadySeed}
                          className={`w-full text-left px-3.5 py-2.5 rounded-lg flex items-center justify-between gap-3.5 transition-all ${
                            isHighlighted ? "bg-white/[0.1]" : "hover:bg-white/[0.06]"
                          } ${isAlreadySeed ? "opacity-40 cursor-not-allowed" : ""}`}
                        >
                          <div className="flex items-center gap-3.5 min-w-0 pr-2">
                            <div className="relative w-10 h-10 rounded-lg bg-white/[0.05] border border-white/10 flex items-center justify-center flex-shrink-0 text-[#fa2d55] overflow-hidden shadow-md">
                              <Music className="w-4 h-4 text-[#fa2d55]/60" />
                              {t.artwork_url ? (
                                <img
                                  src={t.artwork_url}
                                  alt=""
                                  className="absolute inset-0 w-full h-full object-cover rounded-lg"
                                  onError={(e) => {
                                    e.currentTarget.style.display = "none";
                                  }}
                                />
                              ) : null}
                            </div>
                            <div className="min-w-0">
                              <p className="text-sm font-semibold text-white truncate">{t.title}</p>
                              <div className="flex items-center gap-2 text-xs text-white/60 truncate mt-0.5">
                                <span className="truncate">{t.artist_name}</span>
                                {t.year ? <span>• {t.year}</span> : null}
                                {t.tags && t.tags.length > 0 && (
                                  <span className="text-[10px] bg-white/[0.06] text-white/70 px-2 py-0.5 rounded-md border border-white/10 hidden sm:inline">
                                    {t.tags[0]}
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-1.5 text-xs flex-shrink-0">
                            {isAlreadySeed ? (
                              <span className="text-white/40 text-xs font-medium">Selected</span>
                            ) : (
                              <span className="inline-flex items-center gap-1 text-xs bg-white/[0.08] hover:bg-[#fa2d55] hover:text-white px-2.5 py-1 rounded-md text-white/90 transition-all font-semibold active:scale-95 shadow-sm">
                                <Plus className="w-3.5 h-3.5 text-[#fa2d55]" /> Add
                              </span>
                            )}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                ) : !isSearchLoading ? (
                  <div className="p-5 text-center text-xs text-white/60">
                    No tracks found matching &ldquo;{debouncedQuery}&rdquo;.
                  </div>
                ) : null}
              </div>
            )}
          </div>

          {/* Seed Chips */}
          <div className="mt-5 pt-4 border-t border-white/[0.08]">
            {seeds.length === 0 ? (
              <p className="text-xs text-white/40 italic">
                No seed tracks selected yet. Search above to add seeds.
              </p>
            ) : (
              <div className="flex flex-wrap items-center gap-2">
                {seeds.map((s) => (
                  <div
                    key={s.id}
                    className="inline-flex items-center gap-2.5 bg-white/[0.06] hover:bg-white/[0.1] border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white shadow-sm backdrop-blur-md animate-in fade-in duration-200"
                  >
                    <div className="relative w-5 h-5 rounded-md bg-white/10 flex items-center justify-center flex-shrink-0 text-[#fa2d55] overflow-hidden">
                      <Music className="w-3 h-3 text-[#fa2d55]/80" />
                      {s.artwork_url ? (
                        <img
                          src={s.artwork_url}
                          alt=""
                          className="absolute inset-0 w-full h-full object-cover rounded-md"
                          onError={(e) => {
                            e.currentTarget.style.display = "none";
                          }}
                        />
                      ) : null}
                    </div>
                    <span className="font-medium max-w-[160px] truncate">{s.title}</span>
                    <span className="text-white/60 max-w-[100px] truncate">({s.artist_name})</span>
                    <button
                      type="button"
                      onClick={() => removeSeed(s.id)}
                      aria-label={`Remove ${s.title} by ${s.artist_name}`}
                      className="text-white/60 hover:text-rose-400 p-0.5 rounded-md transition-colors focus:outline-none focus:ring-1 focus:ring-rose-400"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}

                <button
                  type="button"
                  onClick={clearSeeds}
                  className="text-xs text-white/50 hover:text-rose-400 ml-auto transition-colors underline"
                >
                  Clear all
                </button>
              </div>
            )}
          </div>

          {/* Action Row */}
          <div className="mt-6 flex items-center justify-between gap-3 flex-wrap">
            <div className="text-xs text-white/60 flex items-center gap-1.5">
              <Sliders className="w-3.5 h-3.5 text-[#fa2d55]" />
              Dual-Channel + MMR Diversity
            </div>

            <div className="flex items-center gap-3">
              {/* Start from Saved Taste Button (Phase 9) */}
              {(hasPersistentProfile || seeds.length === 0) && (
                <button
                  type="button"
                  onClick={() =>
                    recommendMutation.mutate({
                      useSavedTaste: true,
                      d: sliderValue,
                    })
                  }
                  disabled={recommendMutation.isPending}
                  aria-label="Start discovery using saved persistent taste"
                  className="inline-flex items-center gap-2 bg-white/[0.06] hover:bg-white/[0.12] border border-white/10 hover:border-white/20 text-white font-semibold text-xs px-3.5 py-2 rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-[#fa2d55] disabled:opacity-40"
                >
                  <Sparkles className="w-3.5 h-3.5 text-[#fb7185]" />
                  <span>Start from Saved Taste</span>
                </button>
              )}

              <button
                type="button"
                onClick={handleDiscover}
                disabled={seeds.length === 0 || recommendMutation.isPending}
                className="inline-flex items-center gap-2.5 bg-gradient-to-r from-[#fa2d55] via-[#e11d48] to-[#be123c] hover:from-[#ff375f] hover:to-[#d01344] text-white font-bold px-6 py-2.5 rounded-lg shadow-[0_4px_24px_rgba(250,45,85,0.45)] hover:shadow-[0_6px_32px_rgba(250,45,85,0.65)] transition-all transform active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed disabled:transform-none"
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
          </div>
        </section>

        {/* Error Notification */}
        {(recommendMutation.isError || rerankMutation.isError) && (
          <div className="bg-rose-950/40 border border-rose-500/40 rounded-2xl p-4 mb-6 text-rose-200 text-sm flex items-start gap-3 backdrop-blur-xl">
            <div className="p-1.5 rounded-full bg-rose-900/60 text-rose-300">
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
          <div className="sticky top-[61px] z-30 bg-[#0c0f17]/90 backdrop-blur-2xl border border-white/10 rounded-xl p-4 sm:p-5 mb-8 shadow-[0_16px_40px_rgba(0,0,0,0.6)] transition-all">
            <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
              <div className="flex items-center gap-2">
                <Sliders className="w-4 h-4 text-[#fa2d55]" />
                <span className="text-xs font-bold text-white uppercase tracking-wider">
                  Discovery Control (Familiarity ↔ Discovery)
                </span>
                {rerankMutation.isPending && (
                  <span className="flex items-center gap-1 text-[11px] text-[#fb7185] animate-pulse">
                    <RefreshCw className="w-3 h-3 animate-spin" />
                    Reranking...
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2 flex-wrap">
                {/* Remember this vibe button (Phase 9) */}
                <button
                  type="button"
                  onClick={() => rememberMutation.mutate()}
                  disabled={rememberMutation.isPending}
                  aria-label="Remember this vibe to persistent device profile"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-white/[0.05] border border-white/10 hover:border-white/20 text-white/80 hover:text-white transition-colors focus:outline-none focus:ring-2 focus:ring-[#fa2d55]"
                >
                  <BookmarkPlus className="w-3.5 h-3.5 text-[#fb7185]" />
                  <span>{rememberMutation.isPending ? "Saving..." : "Remember Vibe"}</span>
                </button>

                {/* Build Playlist button (Phase 10) */}
                <button
                  type="button"
                  onClick={() => setPlaylistBuilderOpen(true)}
                  aria-label="Open playlist builder to sequence tracks into a listening journey"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/25 transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-400"
                >
                  <ListMusic className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Build Playlist</span>
                </button>

                {/* 3D Taste Universe Map button (Phase 12) */}
                <button
                  type="button"
                  onClick={() => setUniverseModalOpen(true)}
                  aria-label="Open interactive 3D Taste Universe"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-sky-500/15 border border-sky-500/30 text-sky-200 hover:bg-sky-500/25 transition-colors focus:outline-none focus:ring-2 focus:ring-sky-400"
                >
                  <Globe className="w-3.5 h-3.5 text-sky-400" />
                  <span>3D Map</span>
                </button>

                <button
                  type="button"
                  onClick={() => setChatDrawerOpen(true)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-purple-500/15 border border-purple-500/30 text-purple-200 hover:bg-purple-500/25 transition-colors focus:outline-none focus:ring-2 focus:ring-purple-400"
                  aria-label="Open steer discovery chat drawer"
                >
                  <MessageSquare className="w-3.5 h-3.5 text-purple-400" />
                  <span>Steer Vibe</span>
                  {appliedConstraints.length > 0 && (
                    <span className="ml-0.5 px-1.5 py-0.2 rounded-md bg-purple-500 text-white text-[10px] font-bold">
                      {appliedConstraints.length}
                    </span>
                  )}
                </button>

                <span className="text-xs text-white/60">Discovery:</span>
                <span
                  data-testid="discovery-pct-badge"
                  className="font-mono text-xs font-bold text-[#fa2d55] bg-[#fa2d55]/15 border border-[#fa2d55]/30 px-2 py-0.5 rounded-md shadow-[0_0_10px_rgba(250,45,85,0.2)]"
                >
                  {Math.round(sliderValue * 100)}%
                </span>
              </div>
            </div>

            {/* Slider Input */}
            <div className="space-y-2">
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
                className="w-full h-2.5 bg-white/10 rounded-full appearance-none cursor-pointer accent-[#fa2d55] focus:outline-none focus:ring-2 focus:ring-[#fa2d55]/60"
                style={{
                  background: `linear-gradient(to right, #10b981 0%, #fa2d55 ${sliderValue * 100}%, #6366f1 100%)`,
                }}
              />

              <div className="flex justify-between items-center text-[11px] text-white/60">
                <span className="flex items-center gap-1 text-emerald-400 font-semibold">
                  ← Familiarity (0%)
                </span>
                <span className="text-white/40">Balanced (50%)</span>
                <span className="flex items-center gap-1 text-[#fb7185] font-semibold">
                  Discovery (100%) →
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Active Applied Session Constraints Banner */}
        {appliedConstraints.length > 0 && (
          <div className="flex items-center gap-2 mb-5 flex-wrap p-3.5 rounded-xl bg-purple-950/30 border border-purple-500/30 shadow-sm backdrop-blur-xl animate-in fade-in">
            <span className="text-xs font-semibold text-purple-300 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-purple-400" />
              Session Steering:
            </span>
            {appliedConstraints.map((c) => (
              <span
                key={c.id}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-black/40 text-zinc-200 border border-purple-500/30 shadow-sm"
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
        <section className="mb-20">
          <div className="flex items-center justify-between mb-5">
            <h3 className="text-xl font-bold text-white flex items-center gap-2.5 font-sans tracking-tight">
              <div className="w-7 h-7 rounded-lg bg-[#fa2d55]/20 border border-[#fa2d55]/40 flex items-center justify-center">
                <Headphones className="w-4 h-4 text-[#fa2d55]" />
              </div>
              Recommended Tracks
            </h3>
            {recommendations.length > 0 && (
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setIsMainExportOpen(true)}
                  aria-label="Export recommended tracks"
                  className="flex items-center gap-1.5 text-xs font-semibold text-white/80 hover:text-white bg-white/[0.06] hover:bg-white/[0.12] border border-white/10 px-3.5 py-1.5 rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-[#fa2d55]"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Export</span>
                </button>
                <span className="text-xs text-white/60 bg-white/[0.04] px-2.5 py-1 rounded-md border border-white/10">
                  {recommendations.length} recommendations ranked
                </span>
              </div>
            )}
          </div>

          {/* Skeleton Loading State */}
          {recommendMutation.isPending && (
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <div
                  key={i}
                  className="bg-white/[0.03] border border-white/[0.06] rounded-xl p-4 flex items-center justify-between animate-pulse"
                >
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-lg bg-white/[0.08]" />
                    <div className="space-y-2">
                      <div className="w-48 h-4 bg-white/[0.08] rounded" />
                      <div className="w-32 h-3 bg-white/[0.05] rounded" />
                    </div>
                  </div>
                  <div className="w-16 h-6 bg-white/[0.08] rounded-md" />
                </div>
              ))}
            </div>
          )}

          {/* Empty State */}
          {!recommendMutation.isPending && recommendations.length === 0 && (
            <div className="border border-dashed border-white/15 rounded-xl p-10 text-center bg-white/[0.02] backdrop-blur-md">
              <div className="w-14 h-14 rounded-xl bg-white/[0.05] border border-white/10 flex items-center justify-center mx-auto mb-4 text-[#fa2d55]">
                <Compass className="w-7 h-7" />
              </div>
              <h4 className="text-lg font-bold text-white mb-1.5">Your discovery feed is empty</h4>
              <p className="text-xs sm:text-sm text-white/60 max-w-sm mx-auto leading-relaxed">
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
                    className="bg-white/[0.025] border border-white/[0.06] hover:border-white/[0.16] rounded-xl p-3.5 sm:p-4 transition-all duration-250 ease-out motion-reduce:transition-none hover:bg-white/[0.065] hover:shadow-[0_8px_30px_rgba(0,0,0,0.5)] flex flex-col sm:flex-row sm:items-center justify-between gap-4 group"
                  >
                    <div className="flex items-center gap-3.5 min-w-0">
                      <span className="w-7 text-center font-mono text-xs font-semibold text-white/40 group-hover:text-white/70">
                        #{idx + 1}
                      </span>
                      <div className={`relative w-12 h-12 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center text-[#fa2d55] flex-shrink-0 overflow-hidden group/art shadow-[0_4px_16px_rgba(0,0,0,0.5)] group-hover:scale-105 transition-all duration-300 ${
                        playingTrackId === item.track.id ? "ring-2 ring-[#fa2d55] shadow-[0_0_20px_rgba(250,45,85,0.6)]" : ""
                      }`}>
                        <Music className="w-5 h-5 text-[#fa2d55]/60" />
                        {item.track.artwork_url ? (
                          <img
                            src={item.track.artwork_url}
                            alt=""
                            className="absolute inset-0 w-full h-full object-cover rounded-lg"
                            onError={(e) => {
                              e.currentTarget.style.display = "none";
                            }}
                          />
                        ) : null}
                        {item.track.preview_url ? (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleTogglePlay(item.track);
                            }}
                            aria-label={
                              playingTrackId === item.track.id
                                ? `Pause preview for ${item.track.title}`
                                : `Play 30s preview for ${item.track.title}`
                            }
                            className={`absolute inset-0 flex items-center justify-center bg-black/60 transition-all focus:outline-none focus:ring-2 focus:ring-[#fa2d55] ${
                              playingTrackId === item.track.id
                                ? "opacity-100 text-[#fa2d55]"
                                : "opacity-0 group-hover/art:opacity-100 text-white hover:text-[#fa2d55]"
                            }`}
                          >
                            {playingTrackId === item.track.id ? (
                              <div className="flex items-center gap-0.5">
                                <span className="w-1 h-3.5 bg-[#fa2d55] rounded-full animate-bounce [animation-delay:-0.3s]" />
                                <span className="w-1 h-4.5 bg-[#fa2d55] rounded-full animate-bounce [animation-delay:-0.15s]" />
                                <span className="w-1 h-3.5 bg-[#fa2d55] rounded-full animate-bounce" />
                              </div>
                            ) : (
                              <Play className="w-4 h-4 fill-current translate-x-0.5" />
                            )}
                          </button>
                        ) : null}
                      </div>
                      <div className="min-w-0">
                        <h4 className="text-sm sm:text-base font-semibold text-white truncate group-hover:text-[#fa2d55] transition-colors">
                          {item.track.title}
                        </h4>
                        <p className="text-xs text-white/60 truncate mt-0.5">
                          {item.track.artist_name} {item.track.year ? `• ${item.track.year}` : ""}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center justify-between sm:justify-end gap-2.5 pl-10 sm:pl-0 flex-wrap">
                      {/* Subtle Familiarity <-> Discovery Tick Indicator */}
                      {novPct !== null && (
                        <div
                          className="flex items-center gap-1.5 text-[10px] font-mono px-2 py-0.5 rounded-md bg-white/[0.04] border border-white/10"
                          title={`Novelty: ${novPct}% | Familiarity: ${100 - novPct}%`}
                        >
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${
                              isHighNovelty
                                ? "bg-[#fa2d55] shadow-[0_0_8px_rgba(250,45,85,0.6)]"
                                : isModerateNovelty
                                ? "bg-[#38bdf8]"
                                : "bg-[#10b981]"
                            }`}
                          />
                          <span className="text-white/70">
                            {isHighNovelty ? "Discovery" : isModerateNovelty ? "Balanced" : "Familiar"}
                          </span>
                          <span className="text-white/40">{novPct}%</span>
                        </div>
                      )}

                      {/* Audio channel badge */}
                      {item.track.has_a ? (
                        <span className="text-[10px] text-emerald-300 bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 rounded-md font-mono">
                          Audio
                        </span>
                      ) : (
                        <span className="text-[10px] text-white/40 bg-white/[0.04] border border-white/10 px-2 py-0.5 rounded-md font-mono">
                          No Audio
                        </span>
                      )}

                      {/* Match Score Badge */}
                      <div className="flex items-center gap-1.5 bg-gradient-to-r from-[#fa2d55]/15 to-[#8b5cf6]/15 border border-[#fa2d55]/30 px-2.5 py-1 rounded-lg shadow-sm">
                        <span className="text-xs font-mono font-bold text-white">
                          {matchPct}%
                        </span>
                        <span className="text-[10px] text-white/60">match</span>
                      </div>

                      {/* Preview Button */}
                      {item.track.preview_url ? (
                        <button
                          type="button"
                          onClick={() => handleTogglePlay(item.track)}
                          aria-label={
                            playingTrackId === item.track.id
                              ? `Pause 30s preview for ${item.track.title}`
                              : `Play 30s preview for ${item.track.title}`
                          }
                          className={`inline-flex items-center gap-1.5 text-xs px-3 py-1 rounded-lg border transition-all focus:outline-none focus:ring-2 focus:ring-[#fa2d55] ${
                            playingTrackId === item.track.id
                              ? "bg-[#fa2d55] border-[#fa2d55] text-white font-medium shadow-[0_0_16px_rgba(250,45,85,0.5)]"
                              : "bg-white/[0.05] border-white/10 hover:border-white/20 text-white/80 hover:text-white"
                          }`}
                        >
                          {playingTrackId === item.track.id ? (
                            <>
                              <Pause className="w-3.5 h-3.5 fill-current" />
                              <span>Pause</span>
                            </>
                          ) : (
                            <>
                              <Play className="w-3.5 h-3.5 fill-current" />
                              <span>Preview</span>
                            </>
                          )}
                        </button>
                      ) : null}

                      {/* Interactive Feedback Controls (Phase 9) */}
                      <div className="flex items-center gap-1 bg-white/[0.04] border border-white/10 rounded-lg p-0.5 backdrop-blur-md">
                        {/* Like button */}
                        <button
                          type="button"
                          onClick={() =>
                            feedbackMutation.mutate({ trackId: item.track.id, event: "like" })
                          }
                          data-testid={`like-button-${item.track.id}`}
                          aria-label={`Like ${item.track.title}`}
                          className={`p-1.5 rounded-md transition-all focus:outline-none focus:ring-1 focus:ring-[#fa2d55] ${
                            likedTrackIds.includes(item.track.id)
                              ? "bg-[#fa2d55] text-white shadow-[0_0_12px_rgba(250,45,85,0.5)]"
                              : "text-white/60 hover:text-white hover:bg-white/10"
                          }`}
                        >
                          <ThumbsUp className="w-3.5 h-3.5" />
                        </button>

                        {/* Dislike button */}
                        <button
                          type="button"
                          onClick={() =>
                            feedbackMutation.mutate({ trackId: item.track.id, event: "dislike" })
                          }
                          data-testid={`dislike-button-${item.track.id}`}
                          aria-label={`Dislike and exclude ${item.track.title}`}
                          className={`p-1.5 rounded-md transition-all focus:outline-none focus:ring-1 focus:ring-red-400 ${
                            dislikedTrackIds.includes(item.track.id)
                              ? "bg-rose-900/70 text-rose-200"
                              : "text-white/60 hover:text-red-400 hover:bg-white/10"
                          }`}
                        >
                          <ThumbsDown className="w-3.5 h-3.5" />
                        </button>

                        {/* Skip button */}
                        <button
                          type="button"
                          onClick={() =>
                            feedbackMutation.mutate({ trackId: item.track.id, event: "skip" })
                          }
                          data-testid={`skip-button-${item.track.id}`}
                          aria-label={`Skip ${item.track.title}`}
                          className="p-1.5 rounded-md text-white/60 hover:text-white hover:bg-white/10 transition-colors focus:outline-none focus:ring-1 focus:ring-white/40"
                        >
                          <SkipForward className="w-3.5 h-3.5" />
                        </button>

                        {/* Save / Bookmark button */}
                        <button
                          type="button"
                          onClick={() =>
                            feedbackMutation.mutate({ trackId: item.track.id, event: "save" })
                          }
                          data-testid={`save-button-${item.track.id}`}
                          aria-label={`Save ${item.track.title}`}
                          className={`p-1.5 rounded-md transition-all focus:outline-none focus:ring-1 focus:ring-[#8b5cf6] ${
                            savedTrackIds.includes(item.track.id)
                              ? "bg-[#8b5cf6] text-white shadow-[0_0_12px_rgba(139,92,246,0.5)]"
                              : "text-white/60 hover:text-white hover:bg-white/10"
                          }`}
                        >
                          {savedTrackIds.includes(item.track.id) ? (
                            <BookmarkCheck className="w-3.5 h-3.5" />
                          ) : (
                            <Bookmark className="w-3.5 h-3.5" />
                          )}
                        </button>
                      </div>

                      {/* Why Explanation Button */}
                      <button
                        type="button"
                        onClick={() => handleOpenWhy(item.track)}
                        data-testid={`why-button-${item.track.id}`}
                        aria-label={`Why was ${item.track.title} recommended?`}
                        className="inline-flex items-center gap-1.5 text-xs px-3 py-1 rounded-lg bg-white/[0.05] hover:bg-white/[0.12] border border-white/10 text-white/80 hover:text-white transition-all focus:outline-none focus:ring-2 focus:ring-[#fa2d55]"
                      >
                        <HelpCircle className="w-3.5 h-3.5 text-[#fb7185]" />
                        <span>Why?</span>
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>
        </>
        )}
      </div>

      {/* Floating Taste Shifted Micro-Indicator (Phase 9) */}
      {tasteShiftedMessage && (
        <div
          data-testid="taste-shifted-indicator"
          role="status"
          aria-live="polite"
          className="fixed bottom-6 right-6 z-50 flex items-center gap-2.5 px-4 py-2.5 rounded-xl bg-[#0c0f17]/90 border border-[#fa2d55]/50 text-white shadow-[0_12px_32px_rgba(0,0,0,0.6)] backdrop-blur-2xl text-xs font-semibold animate-in fade-in slide-in-from-bottom-3"
        >
          <Sparkles className="w-4 h-4 text-[#fa2d55]" />
          <span>{tasteShiftedMessage}</span>
        </div>
      )}

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

      {/* Accessible Anonymous Taste Profile & Settings Drawer (Phase 9) */}
      <SettingsDrawer
        isOpen={isSettingsDrawerOpen}
        onClose={() => setSettingsDrawerOpen(false)}
        apiBase={API_BASE}
      />

      {/* Playlist Builder Drawer (Phase 10) */}
      <PlaylistBuilder
        isOpen={isPlaylistBuilderOpen}
        onClose={() => setPlaylistBuilderOpen(false)}
        apiBase={API_BASE}
      />

      {/* 3D Taste Universe Interactive Modal (Phase 12, lazy chunk) */}
      <TasteUniverseModal />

      {/* Main Recommendations Export Modal (Phase 13) */}
      <ExportModal
        isOpen={isMainExportOpen}
        onClose={() => setIsMainExportOpen(false)}
        tracks={recommendations}
        playlistName="Melovia Recommended Tracks"
        apiBase={API_BASE}
      />
    </main>
  );
}
