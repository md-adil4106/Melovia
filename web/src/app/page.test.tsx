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

describe("Discovery Home Page (Phase 4)", () => {
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
    // Health check mock
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

    // Wait for debounce and query result
    await waitFor(() => {
      expect(screen.getByText("Paranoid Android")).toBeDefined();
    });

    // Click on the track to add as seed
    fireEvent.click(screen.getByText("Paranoid Android"));

    // Verify seed chip rendered
    await waitFor(() => {
      expect(screen.getByText("1")).toBeDefined(); // "1 / 10 seeds selected"
      expect(screen.getByLabelText(/Remove Paranoid Android by Radiohead/i)).toBeDefined();
    });
  });

  it("removes a seed track when remove button is clicked", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: "ok", catalog: null }),
    });

    // Pre-populate store
    useDiscoveryStore.getState().addSeed({
      id: "track-1",
      track_idx: 1,
      title: "Karma Police",
      artist_id: "art-1",
      artist_name: "Radiohead",
      popularity_pct: 80,
      has_a: true,
      has_t: true,
    });

    renderWithClient(<DiscoveryHome />);

    expect(screen.getByText("Karma Police")).toBeDefined();
    const removeBtn = screen.getByLabelText(/Remove Karma Police by Radiohead/i);
    fireEvent.click(removeBtn);

    await waitFor(() => {
      expect(screen.queryByText("Karma Police")).toBeNull();
      expect(screen.getByText(/No seed tracks selected yet/i)).toBeDefined();
    });
  });

  it("triggers recommendations and displays recommended tracks", async () => {
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

    // Mock recommendations response
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
            },
          },
        ],
        timing_ms: { total_ms: 12.5 },
      }),
    });

    renderWithClient(<DiscoveryHome />);

    const discoverBtn = screen.getByRole("button", { name: /Discover Tracks/i });
    expect(discoverBtn).toBeDefined();
    fireEvent.click(discoverBtn);

    await waitFor(() => {
      expect(screen.getByText("Space Oddity")).toBeDefined();
      expect(screen.getByText(/David Bowie/i)).toBeDefined();
      expect(screen.getByText("93%")).toBeDefined(); // 0.925 rounded to 93%
      expect(screen.getByText("1 recommendations generated")).toBeDefined();
    });
  });

  it("displays error message when recommendation API fails", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: "ok", catalog: null }),
    });

    useDiscoveryStore.getState().addSeed({
      id: "seed-1",
      track_idx: 10,
      title: "Unknown Song",
      artist_id: "art-1",
      artist_name: "Artist",
      popularity_pct: 10,
      has_a: false,
      has_t: true,
    });

    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({
        error: { code: "NOT_FOUND", message: "Seed track not found in catalog" },
      }),
    });

    renderWithClient(<DiscoveryHome />);

    const discoverBtn = screen.getByRole("button", { name: /Discover Tracks/i });
    fireEvent.click(discoverBtn);

    await waitFor(() => {
      expect(screen.getByText("Recommendation Failed")).toBeDefined();
      expect(screen.getByText("Seed track not found in catalog")).toBeDefined();
    });
  });
});
