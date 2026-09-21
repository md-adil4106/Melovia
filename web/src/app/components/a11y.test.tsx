import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DiscoveryHome from "../page";
import { useDiscoveryStore, Track } from "../store";

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

const sampleTrack: Track = {
  id: "track-a11y",
  track_idx: 1,
  title: "Accessible Melody",
  artist_id: "art-a11y",
  artist_name: "Test Artist",
  popularity_pct: 70,
  has_a: true,
  has_t: true,
};

describe("Accessibility & Quality Audit (Phase 14)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useDiscoveryStore.getState().clearSeeds();
    useDiscoveryStore.getState().setRecommendations([]);
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        status: "ok",
        version: "0.1.0",
        catalog: { version: "v1", track_count: 3000 },
      }),
    });
  });

  it("ensures all navigation buttons and inputs have accessible names and aria attributes", () => {
    renderWithClient(<DiscoveryHome />);

    // Search input has clear placeholder and accessible label
    const searchInput = screen.getByPlaceholderText(/Type track title or artist name/i);
    expect(searchInput).toBeDefined();

    // Mode tab buttons have proper accessible labels and tab roles
    const discoverTab = screen.getByRole("tab", { name: "Discover" });
    const dnaTab = screen.getByRole("tab", { name: "Taste DNA" });
    expect(discoverTab).toBeDefined();
    expect(dnaTab).toBeDefined();

    // Header action buttons have accessible labels
    expect(screen.getByRole("button", { name: /Open Conversational Refinement/i })).toBeDefined();
    expect(screen.getByRole("button", { name: /Open Playlist Sequencing/i })).toBeDefined();
    expect(screen.getByRole("button", { name: /Open 3D Taste Universe/i })).toBeDefined();
    expect(screen.getByRole("button", { name: /Open anonymous taste profile/i })).toBeDefined();
  });

  it("verifies keyboard accessibility and focusable controls", () => {
    // Add recommendations so Discovery slider is rendered
    useDiscoveryStore.getState().addSeed(sampleTrack);
    useDiscoveryStore.getState().setRecommendations([
      {
        track: sampleTrack,
        score: 0.9,
        discovery_value: 0.35,
        signals: { relevance: 0.9, novelty: 0.2 },
      },
    ]);

    renderWithClient(<DiscoveryHome />);

    // Primary action elements must not have negative tabIndex
    const searchInput = screen.getByPlaceholderText(/Type track title or artist name/i);
    expect(searchInput.getAttribute("tabindex")).not.toBe("-1");

    const slider = screen.getByTestId("discovery-slider");
    expect(slider).toBeDefined();
    expect(slider.getAttribute("tabindex")).not.toBe("-1");
  });
});
