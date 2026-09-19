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
  raw_sim_t?: number;
  percentile_t?: number;
  raw_sim_a?: number | null;
  percentile_a?: number | null;
  has_audio?: boolean;
  nearest_seed_id?: string;
  nearest_seed_similarity?: number;
}

export interface RecommendedItem {
  track: Track;
  score: number;
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
  error: string | null;
  setError: (err: string | null) => void;
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
  clearSeeds: () => set({ seeds: [], recommendations: [], candidateSetId: null, error: null }),
  recommendations: [],
  setRecommendations: (items) => set({ recommendations: items, error: null }),
  candidateSetId: null,
  setCandidateSetId: (id) => set({ candidateSetId: id }),
  error: null,
  setError: (err) => set({ error: err }),
}));
