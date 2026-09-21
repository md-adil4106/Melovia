import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DiscoveryHome from "../page";
import { useDiscoveryStore, Track } from "../store";

const mockFetch = vi.fn();
global.fetch = mockFetch;

if (typeof window !== "undefined") {
  window.HTMLAnchorElement.prototype.click = vi.fn();
}

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

const mockTrack1: Track = {
  id: "track-1",
  track_idx: 1,
  title: "Solar Eclipse",
  artist_id: "art-1",
  artist_name: "Cosmic Sound",
  year: 2023,
  popularity_pct: 65,
  has_a: true,
  has_t: true,
  scalars: { energy: 0.8, valence: 0.6, bpm: 124 },
  tags: ["electronic", "synthwave"],
};

const mockTrack2: Track = {
  id: "track-2",
  track_idx: 2,
  title: "Deep Midnight",
  artist_id: "art-2",
  artist_name: "Luna Project",
  year: 2022,
  popularity_pct: 45,
  has_a: true,
  has_t: true,
  scalars: { energy: 0.4, valence: 0.3, bpm: 95 },
  tags: ["ambient", "chill"],
};

describe("End-to-End User Flow (Phase 14 Consolidation)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useDiscoveryStore.getState().clearSeeds();
    useDiscoveryStore.getState().setRecommendations([]);

    mockFetch.mockImplementation(async (urlInput: RequestInfo | URL) => {
      const url = typeof urlInput === "string" ? urlInput : (urlInput as any).url || urlInput.toString();

      if (url.includes("/health")) {
        return {
          ok: true,
          json: async () => ({
            status: "ok",
            version: "0.1.0",
            catalog: { version: "v1", track_count: 3000 },
          }),
        };
      }

      if (url.includes("/recommendations/rerank")) {
        return {
          ok: true,
          json: async () => ({
            candidate_set_id: "cand-set-e2e",
            total_candidates: 200,
            items: [
              {
                track: mockTrack2,
                score: 0.92,
                discovery_value: 0.75,
                signals: { relevance: 0.85, novelty: 0.72 },
              },
            ],
          }),
        };
      }

      if (url.includes("/why")) {
        return {
          ok: true,
          json: async () => ({
            candidate_set_id: "cand-set-e2e",
            track_id: "track-2",
            reasons: [
              {
                id: "r1",
                text: "Shares warm ambient synth textures with Solar Eclipse.",
                signal_keys: ["cos_t"],
                evidence: { cos_t: 0.88 },
                weight: 0.8,
              },
            ],
            signals: { cos_t: 0.88, relevance: 0.89, novelty: 0.42 },
            discovery_value: 0.75,
            llm_polished: false,
          }),
        };
      }

      if (url.includes("/recommendations")) {
        return {
          ok: true,
          json: async () => ({
            candidate_set_id: "cand-set-e2e",
            total_candidates: 200,
            items: [
              {
                track: mockTrack2,
                score: 0.89,
                discovery_value: 0.35,
                signals: {
                  relevance: 0.89,
                  novelty: 0.42,
                  cos_t: 0.88,
                  cos_a: 0.81,
                },
              },
            ],
          }),
        };
      }

      if (url.includes("/feedback")) {
        return {
          ok: true,
          json: async () => ({
            status: "ok",
            event: "like",
            track_id: "track-2",
            mode_shifted: true,
            nearest_mode_idx: 0,
            cosine_shift: 0.04,
            candidate_set_id: "cand-set-e2e",
            items: [],
            applied_negatives_count: 0,
          }),
        };
      }

      if (url.includes("/taste/profile")) {
        return {
          ok: true,
          json: async () => ({
            known_track_count: 2,
            confidence: "low",
            confidence_reason: "2 tracks rated (< 8)",
            dimensions: {
              breadth: {
                name: "Breadth",
                key: "breadth",
                value: 0.35,
                percentile: 40.0,
                ci_90: [0.25, 0.45],
                description: "Diversity across musical genres",
                definition_tooltip: "Catalog entropy across regions",
              },
            },
            music_dna: { dominant_tags: [], mean_scalars: {}, dominant_regions: [] },
            archetype: {
              id: "synth_voyager",
              name: "Synth Voyager",
              tagline: "Exploring electronic frontiers",
              description: "Drawn to synthetic and ambient soundscapes",
              criteria_summary: "Dominant electronic tags",
            },
            region_exposures: [],
          }),
        };
      }

      return {
        ok: true,
        json: async () => ({}),
      };
    });
  });

  it("completes full flow: seeds -> recs -> slider -> why -> feedback -> tabs", async () => {
    // 1. Pre-add seed so Discover Tracks button is enabled
    useDiscoveryStore.getState().addSeed(mockTrack1);

    renderWithClient(<DiscoveryHome />);

    expect(screen.getByText("MELOVIA")).toBeDefined();
    expect(screen.getByText("Solar Eclipse")).toBeDefined();

    // 2. Discover Tracks button click
    const discoverButton = screen.getByRole("button", { name: /Discover Tracks/i });
    fireEvent.click(discoverButton);

    await waitFor(() => {
      expect(screen.getByText("Deep Midnight")).toBeDefined();
      expect(screen.getByText(/Luna Project/)).toBeDefined();
    });

    // 3. Discovery Slider Rerank
    const slider = screen.getByTestId("discovery-slider");
    fireEvent.change(slider, { target: { value: "0.75" } });

    // 4. Why Explanation Drawer
    const whyButton = screen.getByRole("button", { name: /Why was Deep Midnight recommended/i });
    fireEvent.click(whyButton);

    await waitFor(() => {
      expect(screen.getByText(/Shares warm ambient synth textures/i)).toBeDefined();
    });

    // 5. Interactive Feedback (Like)
    const likeButton = screen.getByRole("button", { name: /Like Deep Midnight/i });
    fireEvent.click(likeButton);

    // 6. Switch to Taste DNA tab
    const dnaTab = screen.getByRole("tab", { name: "Taste DNA" });
    fireEvent.click(dnaTab);

    await waitFor(() => {
      expect(screen.getByText("Music DNA & Taste Profile")).toBeDefined();
    });
  });
});
