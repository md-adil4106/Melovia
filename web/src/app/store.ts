import { create } from "zustand";

export interface Track {
  id: string;
  track_idx: number;
  mbid?: string | null;
  title: string;
  artist_id: string;
  artist_name: string;
  year?: number | null;
  popularity_pct: number;
  has_a: boolean;
  has_t: boolean;
  region_id?: number | null;
  tags?: string[];
  scalars?: {
    bpm?: number | null;
    tempo_bpm?: number | null;
    energy?: number | null;
    valence?: number | null;
    danceability?: number | null;
    acousticness?: number | null;
    instrumentalness?: number | null;
    loudness_db?: number | null;
  } | null;
}

export interface RecommendationSignals {
  sim_t?: number;
  pct_t?: number;
  sim_a?: number | null;
  pct_a?: number | null;
  raw_sim_t?: number;
  percentile_t?: number;
  raw_sim_a?: number | null;
  percentile_a?: number | null;
  has_audio?: boolean;
  nearest_seed_id?: string;
  nearest_seed_title?: string;
  nearest_seed_artist?: string;
  nearest_seed_similarity?: number;
  novelty?: number;
  familiarity?: number;
  artist_new?: boolean;
  popularity_pct?: number;
  mmr_penalty?: number;
  relevance?: number;
  utility?: number;
  discovery_score?: number;
  discovery_value?: number;
  discovery_d?: number;
  region_id?: number | null;
  region_label?: string | null;
  shared_tags?: Array<{ tag: string; idf: number; weight: number }>;
  scalar_deltas?: Record<string, number>;
}

export interface WhyExplanationReason {
  id: string;
  text: string;
  signal_keys: string[];
  evidence: Record<string, any>;
  weight: number;
}

export interface WhyExplanationData {
  candidate_set_id: string;
  track_id: string;
  reasons: WhyExplanationReason[];
  signals: RecommendationSignals;
  discovery_value: number;
  llm_polished: boolean;
}

export interface AppliedConstraint {
  id: string;
  type: string;
  description: string;
  raw_value?: any;
  created_at?: string;
}

export interface RecommendedItem {
  track: Track;
  score: number;
  discovery_value?: number;
  signals?: RecommendationSignals | null;
}

export interface TasteDimension {
  name: string;
  key: string;
  value: number;
  percentile: number;
  ci_90: [number, number];
  description: string;
  definition_tooltip: string;
}

export interface RegionExposure {
  region_id: number;
  name: string;
  genre_focus: string;
  exposure: number;
}

export interface BlindspotItem {
  region_id: number;
  name: string;
  genre_focus: string;
  description: string;
  top_tags: string[];
  exposure: number;
  adjacency_score: number;
  rank_score: number;
  bridge_tags: string[];
  sample_tracks: Track[];
}

export interface TasteProfileData {
  known_track_count: number;
  confidence: "low" | "high";
  confidence_reason: string;
  dimensions: {
    breadth: TasteDimension | null;
    rarity: TasteDimension | null;
    range: TasteDimension | null;
    cohesion: TasteDimension | null;
    adventurousness: TasteDimension | null;
  };
  music_dna: {
    dominant_tags: Array<{ tag: string; count: number; share: number }>;
    mean_scalars: Record<string, { mean: number; min: number; max: number }>;
    dominant_regions: RegionExposure[];
  };
  archetype: {
    id: string;
    name: string;
    tagline: string;
    description: string;
    criteria_summary: string;
    matched_rules: string[];
    is_fallback: boolean;
  };
  region_exposures: RegionExposure[];
}

interface DiscoveryStore {
  seeds: Track[];
  addSeed: (track: Track) => boolean;
  removeSeed: (trackId: string) => void;
  clearSeeds: () => void;
  recommendations: RecommendedItem[];
  setRecommendations: (items: RecommendedItem[]) => void;
  candidateSetId: string | null;
  setCandidateSetId: (id: string | null) => void;
  discovery: number;
  setDiscovery: (d: number) => void;
  error: string | null;
  setError: (err: string | null) => void;
  // Phase 8: Session Context & Refinement
  sessionId: string | null;
  setSessionId: (id: string | null) => void;
  appliedConstraints: AppliedConstraint[];
  setAppliedConstraints: (constraints: AppliedConstraint[]) => void;
  removeAppliedConstraint: (constraintId: string) => void;
  isChatDrawerOpen: boolean;
  setChatDrawerOpen: (open: boolean) => void;
  unsupportedIntents: string[];
  setUnsupportedIntents: (items: string[]) => void;
  clarificationMessage: string | null;
  setClarificationMessage: (msg: string | null) => void;
  // Phase 9: Feedback & Persistent Profile
  likedTrackIds: string[];
  dislikedTrackIds: string[];
  savedTrackIds: string[];
  hasPersistentProfile: boolean;
  setHasPersistentProfile: (val: boolean) => void;
  tasteShiftedMessage: string | null;
  setTasteShiftedMessage: (msg: string | null) => void;
  isSettingsDrawerOpen: boolean;
  setSettingsDrawerOpen: (open: boolean) => void;
  addLikedTrack: (trackId: string) => void;
  addDislikedTrack: (trackId: string) => void;
  toggleSavedTrack: (trackId: string) => void;
  clearFeedbackState: () => void;
  // Phase 10: Playlist Builder
  isPlaylistBuilderOpen: boolean;
  setPlaylistBuilderOpen: (open: boolean) => void;
  selectedArc: "steady" | "build" | "wave" | "wind_down";
  setSelectedArc: (arc: "steady" | "build" | "wave" | "wind_down") => void;
  playlistLength: number;
  setPlaylistLength: (len: number) => void;
  // Phase 11: Taste Profile & Region Exploration
  activeTab: "discover" | "profile";
  setActiveTab: (tab: "discover" | "profile") => void;
  exploringRegion: { id: number; name: string } | null;
  setExploringRegion: (region: { id: number; name: string } | null) => void;
  clearExploringRegion: () => void;
  // Phase 12: 3D Taste Universe
  isUniverseModalOpen: boolean;
  setUniverseModalOpen: (open: boolean) => void;
  universeFocusedRegionId: number | null;
  setUniverseFocusedRegionId: (id: number | null) => void;
  universeFocusedTrackId: string | null;
  setUniverseFocusedTrackId: (id: string | null) => void;
}

export const useDiscoveryStore = create<DiscoveryStore>((set) => ({
  seeds: [],
  addSeed: (track) => {
    let added = false;
    set((state) => {
      if (state.seeds.length >= 10) return state;
      if (state.seeds.some((s) => s.id === track.id)) return state;
      added = true;
      return { seeds: [...state.seeds, track], error: null };
    });
    return added;
  },
  removeSeed: (trackId) =>
    set((state) => ({
      seeds: state.seeds.filter((s) => s.id !== trackId),
    })),
  clearSeeds: () =>
    set({
      seeds: [],
      recommendations: [],
      candidateSetId: null,
      error: null,
      discovery: 0.35,
      appliedConstraints: [],
      unsupportedIntents: [],
      clarificationMessage: null,
      isChatDrawerOpen: false,
    }),
  recommendations: [],
  setRecommendations: (items) => set({ recommendations: items, error: null }),
  candidateSetId: null,
  setCandidateSetId: (id) => set({ candidateSetId: id }),
  discovery: 0.35,
  setDiscovery: (d) => set({ discovery: d }),
  error: null,
  setError: (err) => set({ error: err }),
  // Phase 8 session defaults
  sessionId: null,
  setSessionId: (id) => set({ sessionId: id }),
  appliedConstraints: [],
  setAppliedConstraints: (constraints) => set({ appliedConstraints: constraints }),
  removeAppliedConstraint: (constraintId) =>
    set((state) => ({
      appliedConstraints: state.appliedConstraints.filter((c) => c.id !== constraintId),
    })),
  isChatDrawerOpen: false,
  setChatDrawerOpen: (open) => set({ isChatDrawerOpen: open }),
  unsupportedIntents: [],
  setUnsupportedIntents: (items) => set({ unsupportedIntents: items }),
  clarificationMessage: null,
  setClarificationMessage: (msg) => set({ clarificationMessage: msg }),
  // Phase 9 feedback & profile defaults
  likedTrackIds: [],
  dislikedTrackIds: [],
  savedTrackIds: [],
  hasPersistentProfile: false,
  setHasPersistentProfile: (val) => set({ hasPersistentProfile: val }),
  tasteShiftedMessage: null,
  setTasteShiftedMessage: (msg) => set({ tasteShiftedMessage: msg }),
  isSettingsDrawerOpen: false,
  setSettingsDrawerOpen: (open) => set({ isSettingsDrawerOpen: open }),
  addLikedTrack: (trackId) =>
    set((state) => ({
      likedTrackIds: state.likedTrackIds.includes(trackId)
        ? state.likedTrackIds
        : [...state.likedTrackIds, trackId],
      dislikedTrackIds: state.dislikedTrackIds.filter((id) => id !== trackId),
    })),
  addDislikedTrack: (trackId) =>
    set((state) => ({
      dislikedTrackIds: state.dislikedTrackIds.includes(trackId)
        ? state.dislikedTrackIds
        : [...state.dislikedTrackIds, trackId],
      likedTrackIds: state.likedTrackIds.filter((id) => id !== trackId),
    })),
  toggleSavedTrack: (trackId) =>
    set((state) => ({
      savedTrackIds: state.savedTrackIds.includes(trackId)
        ? state.savedTrackIds.filter((id) => id !== trackId)
        : [...state.savedTrackIds, trackId],
    })),
  clearFeedbackState: () =>
    set({
      likedTrackIds: [],
      dislikedTrackIds: [],
      savedTrackIds: [],
      hasPersistentProfile: false,
      tasteShiftedMessage: null,
    }),
  // Phase 10: Playlist Builder defaults
  isPlaylistBuilderOpen: false,
  setPlaylistBuilderOpen: (open) => set({ isPlaylistBuilderOpen: open }),
  selectedArc: "build",
  setSelectedArc: (arc) => set({ selectedArc: arc }),
  playlistLength: 15,
  setPlaylistLength: (len) => set({ playlistLength: Math.max(2, Math.min(30, len)) }),
  // Phase 11: Taste Profile & Region Exploration
  activeTab: "discover",
  setActiveTab: (tab) => set({ activeTab: tab }),
  exploringRegion: null,
  setExploringRegion: (region) => set({ exploringRegion: region }),
  clearExploringRegion: () => set({ exploringRegion: null }),
  // Phase 12: 3D Taste Universe
  isUniverseModalOpen: false,
  setUniverseModalOpen: (open) => set({ isUniverseModalOpen: open }),
  universeFocusedRegionId: null,
  setUniverseFocusedRegionId: (id) => set({ universeFocusedRegionId: id }),
  universeFocusedTrackId: null,
  setUniverseFocusedTrackId: (id) => set({ universeFocusedTrackId: id }),
}));
