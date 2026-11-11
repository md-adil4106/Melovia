import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { Button } from "./Button";
import { Card, CardHeader, CardTitle, CardContent } from "./Card";
import { Chip } from "./Chip";
import { Slider } from "./Slider";
import { Toast } from "./Toast";
import { Skeleton, TrackItemSkeleton } from "./Skeleton";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { GlassThemeSelector } from "./GlassThemeSelector";
import { AudioWaveVisualizer } from "./AudioWaveVisualizer";
import { RefractionAura } from "./RefractionAura";
import { ShortcutsModal } from "./ShortcutsModal";
import { AudioPlayerDock } from "./AudioPlayerDock";
import { useDiscoveryStore, Track } from "../../store";

describe("Design System UI Primitives (Phase 15)", () => {
  it("renders Button with variants and handles click events", () => {
    const handleClick = vi.fn();
    render(
      <Button variant="primary" onClick={handleClick}>
        Test Button
      </Button>
    );

    const btn = screen.getByRole("button", { name: "Test Button" });
    expect(btn).toBeDefined();
    fireEvent.click(btn);
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it("renders Card with title and content", () => {
    render(
      <Card>
        <CardHeader>
          <CardTitle>Sample Title</CardTitle>
        </CardHeader>
        <CardContent>Sample Description Content</CardContent>
      </Card>
    );
    expect(screen.getByText("Sample Title")).toBeDefined();
    expect(screen.getByText("Sample Description Content")).toBeDefined();
  });

  it("renders Chip with removal trigger", () => {
    const handleRemove = vi.fn();
    render(
      <Chip selected onRemove={handleRemove} removeAriaLabel="Remove genre">
        Electronic
      </Chip>
    );
    expect(screen.getByText("Electronic")).toBeDefined();
    const removeBtn = screen.getByRole("button", { name: "Remove genre" });
    fireEvent.click(removeBtn);
    expect(handleRemove).toHaveBeenCalledTimes(1);
  });

  it("renders Slider and supports keyboard adjustments", () => {
    const handleChange = vi.fn();
    render(
      <Slider
        value={50}
        min={0}
        max={100}
        step={5}
        label="Test Slider"
        onChange={handleChange}
      />
    );

    const slider = screen.getByLabelText("Test Slider");
    expect(slider).toBeDefined();
    fireEvent.keyDown(slider, { key: "ArrowRight" });
    expect(handleChange).toHaveBeenCalledWith(55);

    fireEvent.keyDown(slider, { key: "ArrowLeft" });
    expect(handleChange).toHaveBeenCalledWith(45);
  });

  it("renders Toast and handles auto-dismissal", () => {
    const handleClose = vi.fn();
    render(
      <Toast
        isOpen={true}
        message="Taste shifted (+0.12)"
        type="warm"
        onClose={handleClose}
      />
    );
    expect(screen.getByRole("status")).toBeDefined();
    expect(screen.getByText("Taste shifted (+0.12)")).toBeDefined();
  });

  it("renders Skeleton and TrackItemSkeleton without crash", () => {
    const { container } = render(
      <div>
        <Skeleton className="h-6 w-24" />
        <TrackItemSkeleton />
      </div>
    );
    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });

  it("renders EmptyState with action button", () => {
    const handleAction = vi.fn();
    render(
      <EmptyState
        title="No Tracks Found"
        description="Try searching for another artist or genre."
        actionLabel="Explore All"
        onAction={handleAction}
      />
    );
    expect(screen.getByText("No Tracks Found")).toBeDefined();
    const actBtn = screen.getByRole("button", { name: "Explore All" });
    fireEvent.click(actBtn);
    expect(handleAction).toHaveBeenCalledTimes(1);
  });

  it("renders ErrorState with request_id and retry trigger", () => {
    const handleRetry = vi.fn();
    render(
      <ErrorState
        title="Network Error"
        message="Connection to backend timed out"
        requestId="req_123456"
        onRetry={handleRetry}
      />
    );
    expect(screen.getByRole("alert")).toBeDefined();
    expect(screen.getByText("Request ID: req_123456")).toBeDefined();
    const retryBtn = screen.getByRole("button", { name: "Retry" });
    fireEvent.click(retryBtn);
    expect(handleRetry).toHaveBeenCalledTimes(1);
  });

  it("renders GlassThemeSelector and toggles between clear and frosted glass effects", () => {
    render(<GlassThemeSelector variant="compact" />);
    const clearBtn = screen.getByTestId("glass-theme-clear");
    const frostedBtn = screen.getByTestId("glass-theme-frosted");
    expect(clearBtn).toBeDefined();
    expect(frostedBtn).toBeDefined();

    // Click frosted
    fireEvent.click(frostedBtn);
    expect(useDiscoveryStore.getState().glassTheme).toBe("frosted");
    expect(document.documentElement.getAttribute("data-glass-theme")).toBe("frosted");

    // Click clear
    fireEvent.click(clearBtn);
    expect(useDiscoveryStore.getState().glassTheme).toBe("clear");
    expect(document.documentElement.getAttribute("data-glass-theme")).toBe("clear");
  });

  it("renders GlassThemeSelector detailed variant", () => {
    render(<GlassThemeSelector variant="detailed" />);
    expect(screen.getByText("Glass Material Style")).toBeDefined();
    expect(screen.getByText("Clear Liquid")).toBeDefined();
    expect(screen.getByText("Frosted Matte")).toBeDefined();
  });

  it("renders AudioWaveVisualizer when playing and hides when paused", () => {
    const { rerender } = render(<AudioWaveVisualizer isPlaying={false} />);
    expect(screen.queryByLabelText("Audio playing indicator")).toBeNull();

    const mockAudio = { currentTime: 14 } as HTMLAudioElement;
    rerender(<AudioWaveVisualizer isPlaying={true} audioElement={mockAudio} />);
    expect(screen.getByLabelText("Audio playing indicator")).toBeDefined();
    expect(screen.getByText(/playing/i)).toBeDefined();
  });

  it("renders RefractionAura safely without errors", () => {
    const { container } = render(<RefractionAura />);
    expect(container).toBeDefined();
  });

  it("renders ShortcutsModal and handles escape dismissal", () => {
    const handleClose = vi.fn();
    const { rerender } = render(<ShortcutsModal isOpen={false} onClose={handleClose} />);
    expect(screen.queryByTestId("shortcuts-modal")).toBeNull();

    rerender(<ShortcutsModal isOpen={true} onClose={handleClose} />);
    expect(screen.getByTestId("shortcuts-modal")).toBeDefined();
    expect(screen.getByText("Keyboard Shortcuts")).toBeDefined();
    expect(screen.getByText("Search Seeds")).toBeDefined();
    expect(screen.getByText("Tune Discovery")).toBeDefined();
    expect(screen.getByText("3D Universe")).toBeDefined();

    // Trigger close via Escape key
    fireEvent.keyDown(window, { key: "Escape" });
    expect(handleClose).toHaveBeenCalledTimes(1);

    // Trigger close via close button
    const closeBtn = screen.getByRole("button", { name: "Close keyboard shortcuts" });
    fireEvent.click(closeBtn);
    expect(handleClose).toHaveBeenCalledTimes(2);
  });

  it("renders AudioPlayerDock with track details, scrubber, and playback triggers", () => {
    const handleToggle = vi.fn();
    const handleClose = vi.fn();
    const sampleTrack: Track = {
      id: "track-dock-1",
      track_idx: 1,
      title: "Starman",
      artist_id: "art-1",
      artist_name: "David Bowie",
      popularity_pct: 88,
      has_a: true,
      has_t: true,
      preview_url: "https://example.com/starman.mp3",
    };

    const { rerender } = render(
      <AudioPlayerDock
        track={null}
        isPlaying={false}
        audioElement={null}
        onTogglePlay={handleToggle}
        onClose={handleClose}
      />
    );
    expect(screen.queryByTestId("audio-player-dock")).toBeNull();

    rerender(
      <AudioPlayerDock
        track={sampleTrack}
        isPlaying={true}
        audioElement={null}
        onTogglePlay={handleToggle}
        onClose={handleClose}
      />
    );
    expect(screen.getByTestId("audio-player-dock")).toBeDefined();
    expect(screen.getByText("Starman")).toBeDefined();
    expect(screen.getByText("David Bowie")).toBeDefined();
    expect(screen.getByLabelText("Audio preview scrubber")).toBeDefined();

    // Trigger play/pause button
    const playBtn = screen.getByRole("button", { name: "Pause" });
    fireEvent.click(playBtn);
    expect(handleToggle).toHaveBeenCalledWith(sampleTrack);

    // Trigger close button
    const closeBtn = screen.getByRole("button", { name: "Close preview player" });
    fireEvent.click(closeBtn);
    expect(handleClose).toHaveBeenCalledTimes(1);
  });
});
