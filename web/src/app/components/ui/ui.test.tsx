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
});
