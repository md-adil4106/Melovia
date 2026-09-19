import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import Home from "./page";

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe("Home Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders AMDE title and description", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: "ok", version: "0.1.0", catalog: null }),
    });

    render(<Home />);
    expect(screen.getByText("AMDE")).toBeDefined();
    expect(screen.getByText("Backend Status")).toBeDefined();

    await waitFor(() => {
      expect(screen.getByText("ok")).toBeDefined();
    });
  });

  it("displays health check data when API call succeeds", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: "ok", version: "0.1.0", catalog: null }),
    });

    render(<Home />);

    await waitFor(() => {
      expect(screen.getByText("ok")).toBeDefined();
      expect(screen.getByText("v0.1.0")).toBeDefined();
      expect(screen.getByText("null (unmounted)")).toBeDefined();
    });
  });

  it("displays error message when API call fails", async () => {
    mockFetch.mockRejectedValueOnce(new Error("Connection refused"));

    render(<Home />);

    await waitFor(() => {
      expect(screen.getByText("Offline / Unreachable")).toBeDefined();
      expect(screen.getByText("Connection refused")).toBeDefined();
    });
  });
});
