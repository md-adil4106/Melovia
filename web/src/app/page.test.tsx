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

  it("opens Why drawer on clicking Why? button and displays explanation", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: "ok", catalog: null }),
    });

    useDiscoveryStore.getState().setCandidateSetId("cand-set-why-1");
    useDiscoveryStore.getState().setRecommendations([
      {
        track: {
          id: "rec-why-1",
          track_idx: 10,
          title: "Karma Police",
          artist_id: "art-1",
          artist_name: "Radiohead",
          popularity_pct: 82,
          has_a: true,
          has_t: true,
        },
        score: 0.94,
        signals: {
          novelty: 0.2,
          familiarity: 0.8,
          relevance: 0.94,
        },
      },
    ]);

    renderWithClient(<DiscoveryHome />);

    const whyBtn = screen.getByTestId("why-button-rec-why-1");
    expect(whyBtn).toBeDefined();

    // Mock the Why endpoint response
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        track_id: "rec-why-1",
        title: "Karma Police",
        artist_name: "Radiohead",
        reasons: [
          {
            id: "SHARED_TAG_TOP",
            text: "Shares alternative rock and art rock with your seed tracks",
            signal_keys: ["shared_tags"],
            evidence: { top_tag: "alternative rock" },
            salience: 0.95,
          },
          {
            id: "SEMANTIC_SIM_HIGH",
            text: "Strong semantic similarity across community tagging folksonomy",
            signal_keys: ["pct_t", "sim_t"],
            evidence: { pct_t: 0.92 },
            salience: 0.85,
          },
        ],
        signals: {
          sim_t: 0.85,
          pct_t: 0.92,
          sim_a: 0.78,
          pct_a: 0.88,
          novelty: 0.2,
          popularity_pct: 82,
        },
        discovery_value: 0.35,
        cached: true,
      }),
    });

    fireEvent.click(whyBtn);

    await waitFor(() => {
      expect(screen.getByTestId("why-drawer")).toBeDefined();
      expect(screen.getByText(/Why "Karma Police"\?/i)).toBeDefined();
      expect(screen.getByText(/Shares alternative rock and art rock/i)).toBeDefined();
      expect(screen.getByText(/Semantic Taste Alignment \(t\)/i)).toBeDefined();
      expect(screen.getByText("92%")).toBeDefined();
    });

    // Close the drawer using the close button
    const closeBtn = screen.getByTestId("why-drawer-close");
    fireEvent.click(closeBtn);

    await waitFor(() => {
      expect(screen.queryByTestId("why-drawer")).toBeNull();
    });
  });

  it("closes Why drawer when Escape key is pressed", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: "ok", catalog: null }),
    });

    useDiscoveryStore.getState().setCandidateSetId("cand-set-why-2");
    useDiscoveryStore.getState().setRecommendations([
      {
        track: {
          id: "rec-why-2",
          track_idx: 11,
          title: "No Surprises",
          artist_id: "art-1",
          artist_name: "Radiohead",
          popularity_pct: 79,
          has_a: true,
          has_t: true,
        },
        score: 0.91,
      },
    ]);

    renderWithClient(<DiscoveryHome />);

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        track_id: "rec-why-2",
        title: "No Surprises",
        artist_name: "Radiohead",
        reasons: [],
        signals: {},
        discovery_value: 0.35,
        cached: true,
      }),
    });

    fireEvent.click(screen.getByTestId("why-button-rec-why-2"));

    await waitFor(() => {
      expect(screen.getByTestId("why-drawer")).toBeDefined();
    });

    // Press Escape
    fireEvent.keyDown(window, { key: "Escape" });

    await waitFor(() => {
      expect(screen.queryByTestId("why-drawer")).toBeNull();
    });
  });

  it("opens Chat Drawer, submits natural language refinement, and displays applied constraint chips", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: "ok", catalog: null }),
    });

    useDiscoveryStore.getState().setCandidateSetId("cand-set-refine-1");
    useDiscoveryStore.getState().setRecommendations([
      {
        track: {
          id: "rec-refine-1",
          track_idx: 1,
          title: "Karma Police",
          artist_id: "art-1",
          artist_name: "Radiohead",
          popularity_pct: 82,
          has_a: true,
          has_t: true,
        },
        score: 0.94,
      },
    ]);

    renderWithClient(<DiscoveryHome />);

    // 1. Click Steer Vibe button
    const steerBtn = screen.getByLabelText(/Open steer discovery chat drawer/i);
    fireEvent.click(steerBtn);

    // Verify ChatDrawer opened
    expect(screen.getByText("Steer Discovery")).toBeDefined();
    expect(screen.getByText(/Natural-language session steering/i)).toBeDefined();

    // 2. Type "more energetic" and submit
    const textarea = screen.getByPlaceholderText(/more energetic/i);
    fireEvent.change(textarea, { target: { value: "more energetic" } });
    expect(screen.getByText("14/300")).toBeDefined();

    // Mock /refine response
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        candidate_set_id: "cand-set-refine-1",
        session_id: "sess_test_123",
        applied: [
          {
            id: "cnst_energy_1",
            type: "knob",
            description: "energy (+50%)",
          },
        ],
        unsupported: [],
        items: [
          {
            track: {
              id: "rec-refine-2",
              track_idx: 2,
              title: "Bodysnatchers",
              artist_id: "art-1",
              artist_name: "Radiohead",
              popularity_pct: 80,
              has_a: true,
              has_t: true,
            },
            score: 0.96,
          },
        ],
      }),
    });

    const submitBtn = screen.getByLabelText(/Submit refinement/i);
    fireEvent.click(submitBtn);

    await waitFor(() => {
      // Applied constraint pill should be visible in drawer and main page
      expect(screen.getAllByText(/energy \(\+50%\)/i).length).toBeGreaterThan(0);
      // Recommendation list updated
      expect(screen.getByText("Bodysnatchers")).toBeDefined();
    });

    // 3. Delete applied constraint
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        candidate_set_id: "cand-set-refine-1",
        session_id: "sess_test_123",
        applied: [],
        items: [
          {
            track: {
              id: "rec-refine-1",
              track_idx: 1,
              title: "Karma Police",
              artist_id: "art-1",
              artist_name: "Radiohead",
              popularity_pct: 82,
              has_a: true,
              has_t: true,
            },
            score: 0.94,
          },
        ],
      }),
    });

    const removeBtns = screen.getAllByLabelText(/Remove constraint energy \(\+50%\)/i);
    expect(removeBtns.length).toBeGreaterThan(0);
    fireEvent.click(removeBtns[0]);

    await waitFor(() => {
      expect(screen.queryByText(/energy \(\+50%\)/i)).toBeNull();
    });
  });

  it("submits like feedback, displays taste shifted indicator, and marks track as liked", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: "ok", catalog: null }),
    });

    useDiscoveryStore.getState().setCandidateSetId("cand-set-fb-1");
    useDiscoveryStore.getState().setRecommendations([
      {
        track: {
          id: "rec-fb-1",
          track_idx: 1,
          title: "Karma Police",
          artist_id: "art-1",
          artist_name: "Radiohead",
          popularity_pct: 82,
          has_a: true,
          has_t: true,
        },
        score: 0.94,
      },
    ]);

    renderWithClient(<DiscoveryHome />);

    const likeBtn = screen.getByTestId("like-button-rec-fb-1");
    expect(likeBtn).toBeDefined();

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        status: "ok",
        event: "like",
        track_id: "rec-fb-1",
        mode_shifted: true,
        nearest_mode_idx: 0,
        cosine_shift: 0.125,
        candidate_set_id: "cand-set-fb-1",
        items: [
          {
            track: {
              id: "rec-fb-1",
              track_idx: 1,
              title: "Karma Police",
              artist_id: "art-1",
              artist_name: "Radiohead",
              popularity_pct: 82,
              has_a: true,
              has_t: true,
            },
            score: 0.98,
          },
        ],
        applied_negatives_count: 0,
      }),
    });

    fireEvent.click(likeBtn);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/feedback"),
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining('"event":"like"'),
        })
      );
      expect(useDiscoveryStore.getState().likedTrackIds).toContain("rec-fb-1");
      expect(screen.getByTestId("taste-shifted-indicator")).toBeDefined();
      expect(screen.getByText(/Taste shifted \(\+0.125 toward this vibe\)/i)).toBeDefined();
    });
  });

  it("submits dislike feedback and excludes track from active recommendations", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: "ok", catalog: null }),
    });

    useDiscoveryStore.getState().setCandidateSetId("cand-set-fb-2");
    useDiscoveryStore.getState().setRecommendations([
      {
        track: {
          id: "rec-fb-dislike",
          track_idx: 1,
          title: "Creep",
          artist_id: "art-1",
          artist_name: "Radiohead",
          popularity_pct: 95,
          has_a: true,
          has_t: true,
        },
        score: 0.9,
      },
      {
        track: {
          id: "rec-fb-keep",
          track_idx: 2,
          title: "Paranoid Android",
          artist_id: "art-1",
          artist_name: "Radiohead",
          popularity_pct: 88,
          has_a: true,
          has_t: true,
        },
        score: 0.85,
      },
    ]);

    renderWithClient(<DiscoveryHome />);

    const dislikeBtn = screen.getByTestId("dislike-button-rec-fb-dislike");
    expect(dislikeBtn).toBeDefined();

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        status: "ok",
        event: "dislike",
        track_id: "rec-fb-dislike",
        mode_shifted: true,
        nearest_mode_idx: 0,
        cosine_shift: -0.08,
        candidate_set_id: "cand-set-fb-2",
        items: [
          {
            track: {
              id: "rec-fb-keep",
              track_idx: 2,
              title: "Paranoid Android",
              artist_id: "art-1",
              artist_name: "Radiohead",
              popularity_pct: 88,
              has_a: true,
              has_t: true,
            },
            score: 0.85,
          },
        ],
        applied_negatives_count: 1,
      }),
    });

    fireEvent.click(dislikeBtn);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/feedback"),
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining('"event":"dislike"'),
        })
      );
      expect(useDiscoveryStore.getState().dislikedTrackIds).toContain("rec-fb-dislike");
      expect(screen.queryByText("Creep")).toBeNull();
      expect(screen.getByText("Paranoid Android")).toBeDefined();
    });
  });

  it("submits 'remember this vibe' to merge session taste into persistent profile", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: "ok", catalog: null }),
    });

    useDiscoveryStore.getState().setCandidateSetId("cand-set-rem-1");
    useDiscoveryStore.getState().setRecommendations([
      {
        track: {
          id: "rec-rem-1",
          track_idx: 1,
          title: "Lotus Flower",
          artist_id: "art-1",
          artist_name: "Radiohead",
          popularity_pct: 70,
          has_a: true,
          has_t: true,
        },
        score: 0.88,
      },
    ]);

    renderWithClient(<DiscoveryHome />);

    const rememberBtn = screen.getByLabelText(/Remember this vibe/i);
    expect(rememberBtn).toBeDefined();

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        status: "ok",
        device_id_hash: "dc2ecfb8",
        num_modes: 2,
        known_tracks_count: 5,
        updated_at: "2026-09-20T12:00:00Z",
      }),
    });

    fireEvent.click(rememberBtn);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/profile/remember"),
        expect.objectContaining({ method: "POST" })
      );
      expect(useDiscoveryStore.getState().hasPersistentProfile).toBe(true);
      expect(screen.getByText(/Saved 2 taste modes to persistent profile!/i)).toBeDefined();
    });
  });

  it("starts recommendations from saved persistent taste", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: "ok", catalog: null }),
    });

    useDiscoveryStore.getState().setHasPersistentProfile(true);

    renderWithClient(<DiscoveryHome />);

    const startSavedBtn = screen.getByLabelText(/Start discovery using saved persistent taste/i);
    expect(startSavedBtn).toBeDefined();

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        candidate_set_id: "cand-set-from-saved",
        total_candidates: 150,
        items: [
          {
            track: {
              id: "rec-saved-1",
              track_idx: 99,
              title: "Saved Taste Recommendation",
              artist_id: "art-saved",
              artist_name: "Saved Artist",
              popularity_pct: 65,
              has_a: true,
              has_t: true,
            },
            score: 0.91,
          },
        ],
      }),
    });

    fireEvent.click(startSavedBtn);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/recommendations"),
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining('"use_saved_taste":true'),
        })
      );
      expect(screen.getByText("Saved Taste Recommendation")).toBeDefined();
    });
  });

  it("opens Settings drawer, views anonymous profile, and allows export/delete", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: "ok", catalog: null }),
    });

    renderWithClient(<DiscoveryHome />);

    // Mock GET /profile when opening drawer
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        has_profile: true,
        device_id_hash: "dc2ecfb8",
        num_modes: 3,
        known_tracks_count: 12,
        updated_at: "2026-09-20T12:00:00Z",
      }),
    });

    const settingsBtn = screen.getByLabelText(/Open anonymous taste profile/i);
    fireEvent.click(settingsBtn);

    await waitFor(() => {
      expect(screen.getByText("Taste Profile & Privacy")).toBeDefined();
      expect(screen.getByText("#dc2ecfb8")).toBeDefined();
      expect(screen.getByText("Export Taste Profile (JSON)")).toBeDefined();
      expect(screen.getByText(/Delete Profile & Interaction History/i)).toBeDefined();
    });

    // Close drawer on Escape
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => {
      expect(screen.queryByText("Taste Profile & Privacy")).toBeNull();
    });
  });
});
