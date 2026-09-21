import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ExportModal } from "./ExportModal";
import { RecommendedItem } from "../../store";

const mockTracks: RecommendedItem[] = [
  {
    track: {
      id: "trk-1",
      track_idx: 0,
      title: "Solaris Echoes",
      artist_id: "art-1",
      artist_name: "Starlight Ensemble",
      popularity_pct: 65,
      has_a: true,
      has_t: true,
      isrcs: ["USMLV2600001"],
      scalars: { bpm: 120, energy: 0.75 },
    },
    score: 0.88,
  },
  {
    track: {
      id: "trk-2",
      track_idx: 1,
      title: "Midnight Reverie",
      artist_id: "art-2",
      artist_name: "Lunar Wave",
      popularity_pct: 45,
      has_a: true,
      has_t: true,
      isrcs: ["USMLV2600002"],
      scalars: { bpm: 95, energy: 0.4 },
    },
    score: 0.76,
  },
];

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  );
}

describe("ExportModal Component", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    HTMLAnchorElement.prototype.click = vi.fn();
    window.URL.createObjectURL = vi.fn().mockReturnValue("blob:mock-url");
    window.URL.revokeObjectURL = vi.fn();

    global.fetch = vi.fn().mockImplementation(async (url: string) => {
      if (url.includes("/export/spotify/status")) {
        return {
          ok: true,
          json: async () => ({ connected: false }),
        };
      }
      if (url.includes("/export/file")) {
        return {
          ok: true,
          headers: new Headers({
            "Content-Disposition": 'attachment; filename="melovia_playlist.csv"',
          }),
          blob: async () => new Blob(["track_id,title\ntrk-1,Solaris Echoes"]),
        };
      }
      return { ok: true, json: async () => ({}) };
    });
  });

  it("renders offline file export formats by default when open", () => {
    renderWithClient(
      <ExportModal
        isOpen={true}
        onClose={vi.fn()}
        tracks={mockTracks}
        playlistName="Test Playlist"
        apiBase="http://test-api"
      />
    );

    expect(screen.getByRole("dialog")).toBeDefined();
    expect(screen.getByText("Export Playlist")).toBeDefined();
    expect(screen.getByText(/2 tracks ready for export/i)).toBeDefined();
    expect(screen.getByText("CSV Spreadsheet")).toBeDefined();
    expect(screen.getByText("JSON (JSPF)")).toBeDefined();
    expect(screen.getByText("Extended M3U")).toBeDefined();
    expect(screen.getByText("Plain Text Tracklist")).toBeDefined();
  });

  it("triggers file download when clicking download button", async () => {
    renderWithClient(
      <ExportModal
        isOpen={true}
        onClose={vi.fn()}
        tracks={mockTracks}
        playlistName="Test Playlist"
        apiBase="http://test-api"
      />
    );

    const csvButton = screen.getByRole("button", { name: /download \.csv/i });
    fireEvent.click(csvButton);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "http://test-api/export/file",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining('"format":"csv"'),
        })
      );
    });
  });

  it("switches to Spotify Dev Mode tab and displays connection prompt", async () => {
    renderWithClient(
      <ExportModal
        isOpen={true}
        onClose={vi.fn()}
        tracks={mockTracks}
        playlistName="Test Playlist"
        apiBase="http://test-api"
      />
    );

    const spotifyTab = screen.getByRole("button", { name: /spotify \(dev mode\)/i });
    fireEvent.click(spotifyTab);

    await waitFor(() => {
      expect(screen.getByText("Connect Spotify Dev Mode")).toBeDefined();
      expect(screen.getByRole("button", { name: /connect to spotify/i })).toBeDefined();
      expect(screen.getByText(/Developer Mode Allowlist/i)).toBeDefined();
    });
  });

  it("calls onClose when clicking close button or pressing Escape", () => {
    const handleClose = vi.fn();
    renderWithClient(
      <ExportModal
        isOpen={true}
        onClose={handleClose}
        tracks={mockTracks}
        playlistName="Test Playlist"
        apiBase="http://test-api"
      />
    );

    const closeBtn = screen.getByRole("button", { name: "Close export modal" });
    fireEvent.click(closeBtn);
    expect(handleClose).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(window, { key: "Escape" });
    expect(handleClose).toHaveBeenCalledTimes(2);
  });
});
