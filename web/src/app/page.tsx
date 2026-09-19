"use client";

import { useEffect, useState, useCallback } from "react";
import { Activity, CheckCircle2, AlertCircle, RefreshCw, Layers, ShieldCheck, Sparkles } from "lucide-react";

interface HealthData {
  status: string;
  version: string;
  catalog: string | null;
}

export default function Home() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<string | null>(null);

  const fetchHealth = useCallback(async () => {
    setLoading(true);
    setError(null);
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    try {
      const res = await fetch(`${apiUrl}/health`, {
        cache: "no-store",
      });

      if (!res.ok) {
        throw new Error(`API responded with HTTP ${res.status}`);
      }

      const data: HealthData = await res.json();
      setHealth(data);
      setLastChecked(new Date().toLocaleTimeString());
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to connect to backend API";
      setError(message);
      setHealth(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
  }, [fetchHealth]);

  return (
    <main className="min-h-screen px-4 py-12 md:px-8 max-w-5xl mx-auto flex flex-col gap-8">
      {/* Header */}
      <header className="border-b border-ink-border pb-6">
        <div className="flex items-center gap-3 mb-2">
          <span className="px-2.5 py-1 text-xs font-mono font-medium rounded-full bg-warm-subtle text-warm border border-warm/30">
            Internal Preview
          </span>
          <span className="text-xs font-mono text-ink-muted">v0.1.0-alpha</span>
        </div>
        <h1 className="text-4xl md:text-5xl font-display font-medium tracking-tight text-ink-text mb-2">
          MELOVIA
        </h1>
        <p className="text-lg text-ink-muted max-w-2xl font-sans">
          An explainable, user-steerable music-discovery engine with strict deterministic guarantees and structured reasoning.
        </p>
      </header>

      {/* Backend Status Section */}
      <section
        aria-labelledby="system-status-heading"
        className="rounded-xl border border-ink-border bg-ink-surface p-6 shadow-sm"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div className="flex items-center gap-3">
            <Activity className="w-5 h-5 text-cool" aria-hidden="true" />
            <h2 id="system-status-heading" className="text-xl font-display font-semibold text-ink-text">
              Backend Status
            </h2>
          </div>

          <button
            onClick={fetchHealth}
            disabled={loading}
            aria-label="Refresh API health status"
            className="inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-ink-elevated hover:bg-ink-border text-ink-text border border-ink-border transition-colors duration-fast disabled:opacity-50 focus-visible:ring-2 focus-visible:ring-cool"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} aria-hidden="true" />
            <span>{loading ? "Checking..." : "Refresh Status"}</span>
          </button>
        </div>

        {/* Status Indicators */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Status tile */}
          <div className="rounded-lg border border-ink-border bg-ink-elevated p-4 flex flex-col gap-2">
            <span className="text-xs font-mono text-ink-muted uppercase tracking-wider">Service Health</span>
            <div className="flex items-center gap-2">
              {loading ? (
                <span className="text-sm font-mono text-ink-muted">Pinging /health...</span>
              ) : error ? (
                <div className="flex items-center gap-2 text-red-400">
                  <AlertCircle className="w-5 h-5" aria-hidden="true" />
                  <span className="font-semibold text-sm">Offline / Unreachable</span>
                </div>
              ) : (
                <div className="flex items-center gap-2 text-emerald-400">
                  <CheckCircle2 className="w-5 h-5" aria-hidden="true" />
                  <span className="font-semibold text-sm capitalize">{health?.status || "OK"}</span>
                </div>
              )}
            </div>
            {error && <p className="text-xs text-red-400/90 font-mono mt-1">{error}</p>}
          </div>

          {/* Version tile */}
          <div className="rounded-lg border border-ink-border bg-ink-elevated p-4 flex flex-col gap-2">
            <span className="text-xs font-mono text-ink-muted uppercase tracking-wider">API Version</span>
            <span className="text-base font-mono font-medium text-ink-text">
              {health?.version ? `v${health.version}` : "—"}
            </span>
            <span className="text-xs text-ink-muted">FastAPI + Python 3.12</span>
          </div>

          {/* Catalog tile */}
          <div className="rounded-lg border border-ink-border bg-ink-elevated p-4 flex flex-col gap-2">
            <span className="text-xs font-mono text-ink-muted uppercase tracking-wider">Vector Catalog</span>
            <span className="text-base font-mono font-medium text-ink-text">
              {health?.catalog === null ? "null (unmounted)" : String(health?.catalog || "unmounted")}
            </span>
            <span className="text-xs text-ink-muted">data/bundles/ (immutable)</span>
          </div>
        </div>

        {lastChecked && (
          <p className="mt-4 text-xs font-mono text-ink-muted">
            Last checked at: <time dateTime={new Date().toISOString()}>{lastChecked}</time>
          </p>
        )}
      </section>

      {/* System Architecture & Tokens Overview */}
      <section
        aria-labelledby="architecture-heading"
        className="grid grid-cols-1 md:grid-cols-2 gap-6"
      >
        {/* Core Architectural Pillars */}
        <div className="rounded-xl border border-ink-border bg-ink-surface p-6 flex flex-col gap-4">
          <div className="flex items-center gap-2 text-warm">
            <ShieldCheck className="w-5 h-5" aria-hidden="true" />
            <h3 id="architecture-heading" className="text-lg font-display font-medium text-ink-text">
              Architectural Constraints
            </h3>
          </div>
          <ul className="text-sm text-ink-muted space-y-2.5 font-sans">
            <li className="flex items-start gap-2">
              <span className="text-warm font-mono font-bold">•</span>
              <span><strong>api/app/recsys/*</strong> is pure Python and deterministic with stable tie-breaks.</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-warm font-mono font-bold">•</span>
              <span><strong>api/app/llm/*</strong> yields structured constraints; the LLM never ranks tracks directly.</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-warm font-mono font-bold">•</span>
              <span><strong>api/app/platforms/*</strong> is isolated behind PlatformAdapter.</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-warm font-mono font-bold">•</span>
              <span><strong>PostgreSQL 16</strong> only — strictly no Redis and no pgvector.</span>
            </li>
          </ul>
        </div>

        {/* Dark Theme Design Tokens */}
        <div className="rounded-xl border border-ink-border bg-ink-surface p-6 flex flex-col gap-4">
          <div className="flex items-center gap-2 text-cool">
            <Sparkles className="w-5 h-5" aria-hidden="true" />
            <h3 className="text-lg font-display font-medium text-ink-text">
              Design Tokens & Accents
            </h3>
          </div>
          <p className="text-sm text-ink-muted">
            Design tokens parameterized via CSS variables respecting WCAG AA contrast and motion accessibility:
          </p>

          <div className="grid grid-cols-3 gap-3 font-mono text-xs">
            <div className="rounded-lg p-3 border border-ink-border bg-ink-bg flex flex-col gap-1">
              <span className="text-ink-muted">Ink Background</span>
              <span className="font-semibold text-ink-text">#090B10</span>
            </div>
            <div className="rounded-lg p-3 border border-warm/40 bg-warm-subtle flex flex-col gap-1 text-warm">
              <span className="opacity-80">Warm Accent</span>
              <span className="font-semibold">#F59E0B</span>
            </div>
            <div className="rounded-lg p-3 border border-cool/40 bg-cool-subtle flex flex-col gap-1 text-cool">
              <span className="opacity-80">Cool Accent</span>
              <span className="font-semibold">#38BDF8</span>
            </div>
          </div>

          <div className="flex items-center gap-2 text-xs text-ink-muted pt-2 border-t border-ink-border">
            <Layers className="w-4 h-4 text-cool" aria-hidden="true" />
            <span>Global <code className="text-cool font-mono">prefers-reduced-motion</code> overrides applied.</span>
          </div>
        </div>
      </section>
    </main>
  );
}
