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
import { SourceBadge, getTrackSource } from "./SourceBadge";
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

  it("renders AudioWaveVisualizer when playing without hijacking AudioContext", () => {
    const createMediaElementSourceMock = vi.fn();
    const audioContextSpy = vi.fn().mockImplementation(() => ({
      createMediaElementSource: createMediaElementSourceMock,
      createAnalyser: vi.fn(),
      close: vi.fn(),
    }));
    const originalAudioContext = window.AudioContext;
    Object.defineProperty(window, "AudioContext", {
      value: audioContextSpy,
      configurable: true,
    });

    try {
      const { rerender } = render(<AudioWaveVisualizer isPlaying={false} />);
      expect(screen.queryByLabelText("Audio playing indicator")).toBeNull();

      const mockAudio = { currentTime: 14 } as HTMLAudioElement;
      rerender(<AudioWaveVisualizer isPlaying={true} audioElement={mockAudio} />);
      expect(screen.getByLabelText("Audio playing indicator")).toBeDefined();
      expect(screen.getByText(/playing/i)).toBeDefined();
      expect(audioContextSpy).not.toHaveBeenCalled();
      expect(createMediaElementSourceMock).not.toHaveBeenCalled();
    } finally {
      Object.defineProperty(window, "AudioContext", {
        value: originalAudioContext,
        configurable: true,
      });
    }
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
    expect(screen.getByText("Mute / Unmute")).toBeDefined();
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

    // Test Next, Prev, Auto-Advance, Crossfade, Volume & Mute controls
    const handleNext = vi.fn();
    const handlePrev = vi.fn();
    const handleToggleAuto = vi.fn();
    const handleToggleCrossfade = vi.fn();
    const handleVolumeChange = vi.fn();
    const handleToggleMute = vi.fn();

    rerender(
      <AudioPlayerDock
        track={sampleTrack}
        isPlaying={true}
        audioElement={null}
        volume={0.75}
        isMuted={false}
        onVolumeChange={handleVolumeChange}
        onToggleMute={handleToggleMute}
        onTogglePlay={handleToggle}
        onNextTrack={handleNext}
        onPrevTrack={handlePrev}
        hasNextTrack={true}
        hasPrevTrack={true}
        autoAdvance={true}
        onToggleAutoAdvance={handleToggleAuto}
        crossfadeEnabled={true}
        onToggleCrossfade={handleToggleCrossfade}
        onClose={handleClose}
      />
    );

    const nextBtn = screen.getByTestId("next-track-btn");
    fireEvent.click(nextBtn);
    expect(handleNext).toHaveBeenCalledTimes(1);

    const prevBtn = screen.getByTestId("prev-track-btn");
    fireEvent.click(prevBtn);
    expect(handlePrev).toHaveBeenCalledTimes(1);

    const autoAdvBtn = screen.getByTestId("auto-advance-toggle");
    fireEvent.click(autoAdvBtn);
    expect(handleToggleAuto).toHaveBeenCalledTimes(1);

    const crossfadeBtn = screen.getByTestId("crossfade-toggle");
    fireEvent.click(crossfadeBtn);
    expect(handleToggleCrossfade).toHaveBeenCalledTimes(1);

    const muteBtn = screen.getByTestId("mute-toggle-btn");
    expect(muteBtn.getAttribute("aria-label")).toBe("Mute audio");
    fireEvent.click(muteBtn);
    expect(handleToggleMute).toHaveBeenCalledTimes(1);

    const volSlider = screen.getByTestId("volume-slider") as HTMLInputElement;
    expect(volSlider.value).toBe("0.75");
    fireEvent.change(volSlider, { target: { value: "0.4" } });
    expect(handleVolumeChange).toHaveBeenCalledWith(0.4);

    // Verify muted visual ARIA state
    rerender(
      <AudioPlayerDock
        track={sampleTrack}
        isPlaying={true}
        audioElement={null}
        volume={0.75}
        isMuted={true}
        onVolumeChange={handleVolumeChange}
        onToggleMute={handleToggleMute}
        onTogglePlay={handleToggle}
        onClose={handleClose}
      />
    );
    expect(screen.getByTestId("mute-toggle-btn").getAttribute("aria-label")).toBe("Unmute audio");
    expect((screen.getByTestId("volume-slider") as HTMLInputElement).value).toBe("0");

    // Test buffering indicator on play buttons
    rerender(
      <AudioPlayerDock
        track={sampleTrack}
        isPlaying={true}
        isBuffering={true}
        audioElement={null}
        volume={0.75}
        isMuted={false}
        onTogglePlay={handleToggle}
        onClose={handleClose}
      />
    );
    expect(screen.getByTestId("dock-main-play-btn").getAttribute("aria-label")).toBe("Buffering");
    expect(screen.getByTestId("dock-artwork-play-btn").getAttribute("aria-label")).toBe("Buffering preview...");

    // Test timeline hover tooltip and buffered progress
    const mockAudioWithBuffer = {
      currentTime: 10,
      duration: 30,
      buffered: {
        length: 1,
        start: () => 0,
        end: () => 18,
      },
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    } as unknown as HTMLAudioElement;

    rerender(
      <AudioPlayerDock
        track={sampleTrack}
        isPlaying={true}
        audioElement={mockAudioWithBuffer}
        volume={0.75}
        isMuted={false}
        onTogglePlay={handleToggle}
        onClose={handleClose}
      />
    );

    expect(screen.getByTestId("buffered-range-bar")).toBeDefined();
    const scrubberContainer = screen.getByLabelText("Audio preview scrubber").parentElement;
    expect(scrubberContainer).toBeDefined();

    if (scrubberContainer) {
      // Mock getBoundingClientRect
      vi.spyOn(scrubberContainer, "getBoundingClientRect").mockReturnValue({
        left: 0,
        top: 0,
        width: 300,
        height: 20,
        right: 300,
        bottom: 20,
        x: 0,
        y: 0,
        toJSON: () => {},
      });

      fireEvent.mouseMove(scrubberContainer, { clientX: 150 });
      expect(screen.getByTestId("scrubber-hover-tooltip")).toBeDefined();
      expect(screen.getByText("0:15")).toBeDefined();

      fireEvent.mouseLeave(scrubberContainer);
      expect(screen.queryByTestId("scrubber-hover-tooltip")).toBeNull();
    }
  });

  it("renders SourceBadge correctly for JioSaavn, iTunes, and Catalog tracks", () => {
    const saavnTrack: Partial<Track> = { id: "ext:saavn:12345", title: "EX-FILES" };
    const itunesTrack: Partial<Track> = { id: "ext:itunes:67890", title: "Rich Flex" };
    const catalogTrack: Partial<Track> = { id: "cat:111", title: "Midnight City" };

    expect(getTrackSource(saavnTrack)).toBe("saavn");
    expect(getTrackSource(itunesTrack)).toBe("itunes");
    expect(getTrackSource(catalogTrack)).toBe("catalog");

    const { rerender } = render(<SourceBadge track={saavnTrack} />);
    expect(screen.getByTestId("source-badge-saavn")).toBeDefined();
    expect(screen.getByText("JioSaavn")).toBeDefined();

    rerender(<SourceBadge track={itunesTrack} compact />);
    expect(screen.getByTestId("source-badge-itunes")).toBeDefined();
    expect(screen.getByText("iTunes")).toBeDefined();

    rerender(<SourceBadge track={catalogTrack} />);
    expect(screen.getByTestId("source-badge-catalog")).toBeDefined();
    expect(screen.getByText("Catalog")).toBeDefined();
  });

  it("handles live stream JioSaavn full duration and keyboard seek in AudioPlayerDock", () => {
    const handleToggle = vi.fn();
    const handleClose = vi.fn();
    const liveStreamTrack: Track = {
      id: "ext:saavn:exfiles123",
      title: "EX-FILES",
      artist_name: "Karan Aujla",
      preview_url: "https://aac.saavn.cdn.jio.com/test.mp4",
      source: "saavn",
      duration_sec: 215, // 3:35 full track
    };

    render(
      <AudioPlayerDock
        track={liveStreamTrack}
        isPlaying={true}
        audioElement={null}
        onTogglePlay={handleToggle}
        onClose={handleClose}
      />
    );

    // Verifies source badge and stream quality indicator
    expect(screen.getByTestId("source-badge-saavn")).toBeDefined();
    expect(screen.getByTestId("dock-stream-quality")).toBeDefined();
    expect(screen.getByTestId("dock-stream-quality").textContent).toBe("HQ Stream");
    expect(screen.getByText("3:35")).toBeDefined();

    // Verifies keyboard seek on the scrubber container
    const scrubber = screen.getByRole("slider", { name: "Audio scrubber" });
    expect(scrubber).toBeDefined();
    fireEvent.keyDown(scrubber, { key: "ArrowRight" });
    fireEvent.keyDown(scrubber, { key: "ArrowLeft" });
  });
});
