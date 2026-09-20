import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { UniverseFallback2D } from "./UniverseFallback2D";
import { UniverseSidePanel } from "./UniverseSidePanel";
import { UniverseData } from "./types";
import { useDiscoveryStore } from "../../store";

const mockUniverseData: UniverseData = {
  points_quantized: [
    100, 200, 300, 0, 1,
    -400, 500, -600, 1, 2,
    700, -800, 900, 2, 3,
  ],
  scale: 1.0,
  point_count: 3,
  regions: [
    {
      region_id: 0,
      name: "Ambient & Drone",
      genre_focus: "Ambient / Minimal",
      centroid_3d: [0.1, 0.2, 0.3],
      exposure: 0.35,
    },
    {
      region_id: 1,
      name: "Post-Rock & Math Rock",
      genre_focus: "Post-Rock / Instrumental",
      centroid_3d: [-0.4, 0.5, -0.6],
      exposure: 0.25,
    },
    {
      region_id: 2,
      name: "IDM & Glitch",
      genre_focus: "Electronic / Experimental",
      centroid_3d: [0.7, -0.8, 0.9],
      exposure: 0.15,
    },
  ],
  quality_metrics: {
    trustworthiness_k15: 0.9828,
    continuity_k15: 0.9869,
    distortion_note: "3D distances are approximate. High-dimensional vectors are used for recommendations.",
  },
};

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("Phase 12 — 3D Universe Fallback & SidePanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    HTMLCanvasElement.prototype.getContext = vi.fn().mockReturnValue({
      fillRect: vi.fn(),
      clearRect: vi.fn(),
      beginPath: vi.fn(),
      moveTo: vi.fn(),
      lineTo: vi.fn(),
      stroke: vi.fn(),
      arc: vi.fn(),
      fill: vi.fn(),
      fillText: vi.fn(),
    });
  });

  it("renders UniverseFallback2D canvas and allows opening accessible region table", () => {
    const onSelectRegion = vi.fn();
    const onSelectTrack = vi.fn();

    renderWithClient(
      <UniverseFallback2D
        data={mockUniverseData}
        focusedRegionId={null}
        onSelectRegion={onSelectRegion}
        onSelectTrack={onSelectTrack}
      />
    );

    // Checks header
    expect(screen.getByText("2D Canvas Fallback View")).toBeDefined();
    expect(screen.getByText(/Trustworthiness k=15: 98.3%/i)).toBeDefined();

    // Toggle accessible table
    const tableBtn = screen.getByRole("button", { name: /Accessible Region Table/i });
    fireEvent.click(tableBtn);

    // Table should now be visible
    expect(screen.getByText("Accessible Region Catalog Summary")).toBeDefined();
    expect(screen.getByText("Ambient & Drone")).toBeDefined();
    expect(screen.getByText("Post-Rock & Math Rock")).toBeDefined();
    expect(screen.getByText("IDM & Glitch")).toBeDefined();

    // Focus region button
    const focusButtons = screen.getAllByRole("button", { name: "Focus" });
    expect(focusButtons.length).toBe(3);
    fireEvent.click(focusButtons[0]);
    expect(onSelectRegion).toHaveBeenCalledWith(0);
  });

  it("renders UniverseSidePanel with distortion warning and original-space neighbors", async () => {
    const mockNeighborResponse = {
      track_id: "trk_42",
      track_title: "Solar Winds",
      artist_name: "Cosmic Array",
      position_3d: [0.12, -0.34, 0.56],
      region_id: 0,
      region_name: "Ambient & Drone",
      distortion_warning:
        "3D spatial proximity reflects an approximate projection (trustworthiness ~98.3%). Showing true original-space 256d cosine neighbors below.",
      neighbors: [
        {
          track_id: "trk_101",
          title: "Echoing Deep",
          artist_name: "Submerged",
          original_cosine_sim: 0.934,
          shared_tags: ["drone", "meditative", "ambient"],
          region_name: "Ambient & Drone",
        },
      ],
    };

    const mockFetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => mockNeighborResponse,
    });
    global.fetch = mockFetch;

    const onClose = vi.fn();
    const onSelectTrack = vi.fn();

    renderWithClient(
      <UniverseSidePanel
        trackId="trk_42"
        onClose={onClose}
        onSelectTrack={onSelectTrack}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("Solar Winds")).toBeDefined();
      expect(screen.getByText("Cosmic Array")).toBeDefined();
      expect(screen.getByText("Ambient & Drone")).toBeDefined();
      expect(screen.getByText(/Geometric Distortion Note:/i)).toBeDefined();
      expect(screen.getByText("Echoing Deep")).toBeDefined();
      expect(screen.getByText("93%")).toBeDefined();
      expect(screen.getByText("#drone")).toBeDefined();
    });

    // Clicking close button
    const closeBtn = screen.getByRole("button", { name: /Close track inspector/i });
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalled();
  });
});
