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
}));
