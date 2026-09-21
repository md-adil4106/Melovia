import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import StudyPage from "./page";

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

describe("Blind A/B Study Mode Page (Phase 15)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders study protocol, loads blind session, and ensures zero arm leakage", async () => {
    const mockSession = {
      session_id: "sess_test_123",
      seed_set_id: "seedset_01",
      seed_set_name: "Indie Rock Discovery",
      seed_tracks: [
        {
          id: "track_seed_1",
          track_idx: 10,
          title: "Reflective Horizon",
          artist_name: "Lunar Tide",
          year: 2021,
        },
      ],
      playlist_a: [
        {
          id: "track_a_1",
          track_idx: 101,
          title: "Electric Pulse",
          artist_name: "Signal One",
          year: 2022,
          popularity_pct: 60,
          tags: ["indie", "rock"],
        },
      ],
      playlist_b: [
        {
          id: "track_b_1",
          track_idx: 102,
          title: "Static Reverie",
          artist_name: "Neon Shade",
          year: 2020,
          popularity_pct: 55,
          tags: ["ambient", "indie"],
        },
      ],
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockSession,
    });

    const { container } = renderWithClient(<StudyPage />);

    expect(screen.getByText("Double-Blind Evaluation Study")).toBeDefined();
    expect(screen.getByText(/Study Protocol & Consent/i)).toBeDefined();

    await waitFor(() => {
      expect(screen.getByText("Indie Rock Discovery (1 tracks)")).toBeDefined();
      expect(screen.getByText("Reflective Horizon")).toBeDefined();
      expect(screen.getByText("Electric Pulse")).toBeDefined();
    });

    // Verify strict blindness: No HTML/DOM attributes or texts mention hybrid or baseline
    const htmlContent = container.innerHTML.toLowerCase();
    expect(htmlContent).not.toContain("hybrid");
    expect(htmlContent).not.toContain("baseline");
    expect(htmlContent).not.toContain("algorithm");
  });

  it("allows toggling between Playlist A and B, adjusting Likert ratings, and submitting", async () => {
    const mockSession = {
      session_id: "sess_test_456",
      seed_set_id: "seedset_02",
      seed_set_name: "Ambient Focus",
      seed_tracks: [
        { id: "s1", track_idx: 1, title: "Deep Drift", artist_name: "Starlight", year: 2020 },
      ],
      playlist_a: [
        { id: "a1", track_idx: 2, title: "Echo One", artist_name: "Artist A", year: 2021, popularity_pct: 50 },
      ],
      playlist_b: [
        { id: "b1", track_idx: 3, title: "Echo Two", artist_name: "Artist B", year: 2022, popularity_pct: 50 },
      ],
    };

    // 1. Session load response
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockSession,
    });

    renderWithClient(<StudyPage />);

    await waitFor(() => {
      expect(screen.getByText("Echo One")).toBeDefined();
    });

    // Toggle to Playlist B
    const tabB = screen.getByTestId("tab-playlist-b");
    fireEvent.click(tabB);
    expect(screen.getByText("Echo Two")).toBeDefined();

    // Submit ratings
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        status: "ok",
        message: "Thank you!",
        rating_id: "rating_123",
      }),
    });

    const submitBtn = screen.getByRole("button", { name: /Submit Evaluation/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText("Evaluation Submitted!")).toBeDefined();
    });
  });
});
