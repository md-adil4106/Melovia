import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DiscoveryHome from "./page";
import { useDiscoveryStore } from "./store";

const mockFetch = vi.fn();
global.fetch = mockFetch;

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("Discovery Home Page (Phase 4 & Phase 5)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useDiscoveryStore.getState().clearSeeds();
  });

  it("renders MELOVIA title, seed search, and empty discovery feed", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        status: "ok",
        version: "0.1.0",
        catalog: { version: "v1", track_count: 3000 },
      }),
    });

    renderWithClient(<DiscoveryHome />);

    expect(screen.getByText("MELOVIA")).toBeDefined();
    expect(screen.getByText("Explainable Music Discovery")).toBeDefined();
    expect(screen.getByPlaceholderText(/Type track title or artist name/i)).toBeDefined();
    expect(screen.getByText("Your discovery feed is empty")).toBeDefined();

    await waitFor(() => {
      expect(screen.getByText(/Catalog v1/i)).toBeDefined();
    });
  });

  it("searches tracks and allows selecting a seed track", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        status: "ok",
        version: "0.1.0",
        catalog: { version: "v1", track_count: 3000 },
      }),
    });

    renderWithClient(<DiscoveryHome />);

    const input = screen.getByPlaceholderText(/Type track title or artist name/i);

    // Mock search response
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        items: [
          {
            id: "track-101",
            track_idx: 1,
            title: "Paranoid Android",
            artist_id: "art-1",
            artist_name: "Radiohead",
            year: 1997,
            popularity_pct: 85,
            has_a: true,
            has_t: true,
          },
        ],
        total: 1,
      }),
    });

    fireEvent.change(input, { target: { value: "Radiohead" } });

    await waitFor(() => {
      expect(screen.getByText("Paranoid Android")).toBeDefined();
    });

    fireEvent.click(screen.getByText("Paranoid Android"));

    await waitFor(() => {
      expect(screen.getByText("1")).toBeDefined();
      expect(screen.getByLabelText(/Remove Paranoid Android by Radiohead/i)).toBeDefined();
    });
  });

  it("triggers recommendations and displays sticky Discovery Control slider and tracks", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: "ok", catalog: null }),
    });

    useDiscoveryStore.getState().addSeed({
      id: "seed-1",
      track_idx: 10,
      title: "Subterranean Homesick Alien",
      artist_id: "art-1",
      artist_name: "Radiohead",
      popularity_pct: 75,
      has_a: true,
      has_t: true,
    });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        candidate_set_id: "cand-abc-123",
        items: [
          {
            track: {
              id: "rec-1",
              track_idx: 50,
              title: "Space Oddity",
              artist_id: "art-2",
              artist_name: "David Bowie",
              year: 1969,
              popularity_pct: 90,
              has_a: true,
              has_t: true,
            },
            score: 0.925,
            signals: {
              raw_sim_t: 0.88,
              percentile_t: 0.95,
              raw_sim_a: 0.84,
              percentile_a: 0.90,
              has_audio: true,
              novelty: 0.15,
              familiarity: 0.85,
              artist_new: true,
              popularity_pct: 90.0,
              relevance: 0.925,
              utility: 0.925,
              discovery_d: 0.35,
            },
          },
        ],
        timing_ms: { total_ms: 12.5 },
      }),
    });

    renderWithClient(<DiscoveryHome />);

    const discoverBtn = screen.getByRole("button", { name: /Discover Tracks/i });
    fireEvent.click(discoverBtn);

    await waitFor(() => {
      expect(screen.getByText("Space Oddity")).toBeDefined();
      expect(screen.getByText(/David Bowie/i)).toBeDefined();
      // Verify Discovery Control slider is visible
      expect(screen.getByTestId("discovery-slider")).toBeDefined();
      expect(screen.getByTestId("discovery-pct-badge")).toBeDefined();
      expect(screen.getByText(/35%/)).toBeDefined();
      // Verify card novelty tick indicator
      expect(screen.getByText("Familiar")).toBeDefined();
      expect(screen.getByText("15%")).toBeDefined();
    });
  });

  it("updates discovery slider via keyboard and fires /recommendations/rerank", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: "ok", catalog: null }),
    });

    // Populate store with an active candidateSetId and recommendations
    useDiscoveryStore.getState().setCandidateSetId("cand-set-789");
    useDiscoveryStore.getState().setRecommendations([
      {
        track: {
          id: "rec-1",
          track_idx: 50,
          title: "Heroes",
          artist_id: "art-2",
          artist_name: "David Bowie",
          popularity_pct: 88,
          has_a: true,
          has_t: true,
        },
        score: 0.9,
        signals: {
          novelty: 0.12,
          familiarity: 0.88,
          relevance: 0.9,
          utility: 0.9,
          discovery_d: 0.35,
        },
      },
    ]);

    renderWithClient(<DiscoveryHome />);

    const slider = screen.getByTestId("discovery-slider") as HTMLInputElement;
    expect(slider).toBeDefined();

    // Mock rerank response
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        candidate_set_id: "cand-set-789",
        items: [
          {
            track: {
              id: "rec-2",
              track_idx: 60,
              title: "Starman",
              artist_id: "art-2",
              artist_name: "David Bowie",
              popularity_pct: 85,
              has_a: true,
              has_t: true,
            },
            score: 0.82,
            signals: {
              novelty: 0.65,
              familiarity: 0.35,
              relevance: 0.82,
              utility: 0.82,
              discovery_d: 0.75,
            },
          },
        ],
      }),
    });

    // Change slider value to 0.75
    fireEvent.change(slider, { target: { value: "0.75" } });

    expect(screen.getByTestId("discovery-pct-badge").textContent).toBe("75%");

    // Wait for debounced rerank mutation
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/recommendations/rerank"),
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining('"discovery":0.75'),
        })
      );
    });

    await waitFor(() => {
      expect(screen.getByText("Starman")).toBeDefined();
    });
  });

  it("handles slider keyboard navigation with Home and End keys", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: "ok", catalog: null }),
    });

    useDiscoveryStore.getState().setCandidateSetId("cand-set-keys");
    useDiscoveryStore.getState().setRecommendations([
      {
        track: {
          id: "rec-1",
          track_idx: 1,
          title: "Track 1",
          artist_id: "art-1",
          artist_name: "Artist",
          popularity_pct: 50,
          has_a: true,
          has_t: true,
        },
        score: 0.8,
      },
    ]);

    renderWithClient(<DiscoveryHome />);

    const slider = screen.getByTestId("discovery-slider") as HTMLInputElement;

    // Press End key -> should set to 100%
    fireEvent.keyDown(slider, { key: "End" });
    expect(screen.getByTestId("discovery-pct-badge").textContent).toBe("100%");

    // Press Home key -> should set to 0%
    fireEvent.keyDown(slider, { key: "Home" });
    expect(screen.getByTestId("discovery-pct-badge").textContent).toBe("0%");
  });
});
