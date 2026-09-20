"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  AlertCircle,
  HelpCircle,
  MessageSquare,
  RotateCcw,
  Send,
  Sliders,
  Sparkles,
  Tag,
  Volume2,
  X,
} from "lucide-react";
import { AppliedConstraint, useDiscoveryStore } from "../store";

interface ChatDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  apiBase: string;
}

const SUGGESTIONS = [
  "More energetic",
  "Less mainstream",
  "Keep the vibe but add rock",
  "Night drive at 2 AM",
  "Too sad, make it happier",
  "Unplugged acoustic sound",
];

export function ChatDrawer({ isOpen, onClose, apiBase }: ChatDrawerProps) {
  const {
    candidateSetId,
    setRecommendations,
    sessionId,
    setSessionId,
    appliedConstraints,
    setAppliedConstraints,
    removeAppliedConstraint,
    unsupportedIntents,
    setUnsupportedIntents,
    clarificationMessage,
    setClarificationMessage,
  } = useDiscoveryStore();

  const [utterance, setUtterance] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const drawerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  // Focus management and Escape key trap
  useEffect(() => {
    if (!isOpen) return;

    const timer = setTimeout(() => {
      inputRef.current?.focus();
    }, 50);

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }

      if (e.key === "Tab" && drawerRef.current) {
        const focusableElements = drawerRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        const first = focusableElements[0];
        const last = focusableElements[focusableElements.length - 1];

        if (e.shiftKey) {
          if (document.activeElement === first) {
            e.preventDefault();
            last?.focus();
          }
        } else {
          if (document.activeElement === last) {
            e.preventDefault();
            first?.focus();
          }
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      clearTimeout(timer);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose]);

  // Mutation: POST /refine
  const refineMutation = useMutation({
    mutationFn: async (text: string) => {
      if (!candidateSetId) {
        throw new Error("Generate recommendations first before steering.");
      }
      const trimmed = text.trim();
      if (!trimmed) return null;

      const res = await fetch(`${apiBase}/refine`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          candidate_set_id: candidateSetId,
          utterance: trimmed,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData?.error?.message || "Failed to apply refinement");
      }
      return await res.json();
    },
    onSuccess: (data) => {
      if (!data) return;
      setRecommendations(data.items || []);
      setAppliedConstraints(data.applied || []);
      if (data.session_id) setSessionId(data.session_id);
      if (data.unsupported && data.unsupported.length > 0) {
        setUnsupportedIntents(data.unsupported);
      } else {
        setUnsupportedIntents([]);
      }
      setClarificationMessage(data.clarify || null);
      setUtterance("");
      setErrorMessage(null);
    },
    onError: (err: Error) => {
      setErrorMessage(err.message);
    },
  });

  // Mutation: DELETE /refine/{constraint_id}
  const deleteConstraintMutation = useMutation({
    mutationFn: async (constraintId: string) => {
      if (!candidateSetId) return null;
      const res = await fetch(
        `${apiBase}/refine/${encodeURIComponent(constraintId)}?candidate_set_id=${encodeURIComponent(candidateSetId)}`,
        {
          method: "DELETE",
          credentials: "include",
        }
      );
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData?.error?.message || "Failed to remove constraint");
      }
      return await res.json();
    },
    onSuccess: (data, constraintId) => {
      if (!data) return;
      setRecommendations(data.items || []);
      setAppliedConstraints(data.applied || []);
      removeAppliedConstraint(constraintId);
      setErrorMessage(null);
    },
    onError: (err: Error) => {
      setErrorMessage(err.message);
    },
  });

  // Mutation: POST /refine/session/reset
  const resetSessionMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${apiBase}/refine/session/reset`, {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData?.error?.message || "Failed to reset session");
      }
      return await res.json();
    },
    onSuccess: () => {
      setAppliedConstraints([]);
      setUnsupportedIntents([]);
      setClarificationMessage(null);
      setErrorMessage(null);
      // Trigger rerank or refresh recommendations without session context
      if (candidateSetId) {
        fetch(`${apiBase}/recommendations/rerank`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            candidate_set_id: candidateSetId,
            discovery: 0.35,
            n: 30,
            include_signals: true,
          }),
        })
          .then((res) => (res.ok ? res.json() : null))
          .then((data) => {
            if (data?.items) setRecommendations(data.items);
          })
          .catch(() => {});
      }
    },
    onError: (err: Error) => {
      setErrorMessage(err.message);
    },
  });

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!utterance.trim() || refineMutation.isPending) return;
    refineMutation.mutate(utterance);
  };

  const handleSuggestionClick = (suggestionText: string) => {
    setUtterance(suggestionText);
    refineMutation.mutate(suggestionText);
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm transition-opacity duration-200"
      aria-modal="true"
      role="dialog"
      aria-labelledby="chat-drawer-title"
      onClick={onClose}
    >
      <div
        ref={drawerRef}
        onClick={(e) => e.stopPropagation()}
        className="relative flex h-full w-full max-w-md flex-col bg-zinc-950 border-l border-zinc-800 shadow-2xl overflow-hidden transition-transform duration-200 ease-out sm:max-w-lg"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-zinc-800/80 bg-zinc-900/40">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20">
              <MessageSquare className="h-5 w-5" />
            </div>
            <div>
              <h2 id="chat-drawer-title" className="text-base font-semibold text-zinc-100 flex items-center gap-2">
                Steer Discovery
                <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-purple-500/15 text-purple-300 border border-purple-500/20">
                  WOW #4
                </span>
              </h2>
              <p className="text-xs text-zinc-400">
                Natural-language session steering via untrusted LLM boundary
              </p>
            </div>
          </div>
          <button
            ref={closeButtonRef}
            onClick={onClose}
            className="rounded-lg p-2 text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-200 transition-colors focus:outline-none focus:ring-2 focus:ring-purple-500"
            aria-label="Close chat drawer"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6 text-sm">
          {/* Architecture Guarantee Info Banner */}
          <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-3.5 text-xs text-zinc-400 flex items-start gap-2.5">
            <Sparkles className="h-4 w-4 text-purple-400 flex-shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold text-zinc-300">Strict Boundary Invariant: </span>
              The LLM parses intent into mathematical constraints (knobs & vectors). It never selects tracks, invents metadata, or mutates persistent profiles.
            </div>
          </div>

          {/* Active Applied Constraints */}
          <div className="space-y-2.5">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
                <Sliders className="h-3.5 w-3.5 text-zinc-400" />
                Active Session Context ({appliedConstraints.length})
              </h3>
              {appliedConstraints.length > 0 && (
                <button
                  type="button"
                  onClick={() => resetSessionMutation.mutate()}
                  disabled={resetSessionMutation.isPending}
                  className="text-xs text-zinc-400 hover:text-red-400 flex items-center gap-1 transition-colors disabled:opacity-50"
                  title="Clear all session steering"
                >
                  <RotateCcw className="h-3 w-3" />
                  Reset
                </button>
              )}
            </div>

            {appliedConstraints.length === 0 ? (
              <p className="text-xs text-zinc-500 italic py-2">
                No active session steering. Type an utterance below or choose a suggestion to steer your vibe.
              </p>
            ) : (
              <div className="flex flex-wrap gap-2 pt-1">
                {appliedConstraints.map((c: AppliedConstraint) => (
                  <span
                    key={c.id}
                    className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium bg-zinc-900 text-zinc-200 border border-zinc-700/80 shadow-sm"
                  >
                    <span className="text-purple-400 font-mono text-[11px] uppercase tracking-wide">
                      {c.type}:
                    </span>
                    <span>{c.description}</span>
                    <button
                      type="button"
                      onClick={() => deleteConstraintMutation.mutate(c.id)}
                      disabled={deleteConstraintMutation.isPending}
                      className="ml-1 text-zinc-400 hover:text-red-400 hover:bg-zinc-800 rounded p-0.5 transition-colors focus:outline-none focus:ring-1 focus:ring-purple-500"
                      aria-label={`Remove constraint ${c.description}`}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Unsupported Intents Notice */}
          {unsupportedIntents.length > 0 && (
            <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3.5 text-xs text-amber-200/90 space-y-1">
              <div className="flex items-center gap-1.5 font-semibold text-amber-300">
                <AlertCircle className="h-4 w-4 text-amber-400 flex-shrink-0" />
                Unsupported Filter Detected
              </div>
              <p className="text-amber-200/80">
                The music catalog cannot filter by:
              </p>
              <ul className="list-disc list-inside space-y-0.5 text-amber-300 font-mono text-[11px]">
                {unsupportedIntents.map((item, idx) => (
                  <li key={idx}>{item}</li>
                ))}
              </ul>
              <p className="text-[11px] text-amber-200/70 pt-1">
                Recommendations are ranked purely on high-dimensional audio embeddings, acoustic scalars, and catalog tags.
              </p>
            </div>
          )}

          {/* Clarification Notice */}
          {clarificationMessage && (
            <div className="rounded-xl border border-blue-500/30 bg-blue-500/10 p-3.5 text-xs text-blue-200 flex items-start gap-2">
              <HelpCircle className="h-4 w-4 text-blue-400 flex-shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-blue-300">Notice: </span>
                {clarificationMessage}
              </div>
            </div>
          )}

          {/* Error Message */}
          {errorMessage && (
            <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3.5 text-xs text-red-200 flex items-start gap-2">
              <AlertCircle className="h-4 w-4 text-red-400 flex-shrink-0 mt-0.5" />
              <div>{errorMessage}</div>
            </div>
          )}

          {/* Quick Suggestions */}
          <div className="space-y-2 pt-2">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
              Suggestions
            </h3>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((sugg) => (
                <button
                  key={sugg}
                  type="button"
                  onClick={() => handleSuggestionClick(sugg)}
                  disabled={refineMutation.isPending || !candidateSetId}
                  className="rounded-lg border border-zinc-800 bg-zinc-900/60 px-2.5 py-1.5 text-xs text-zinc-300 hover:border-purple-500/40 hover:bg-zinc-800/80 hover:text-white transition-all disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  {sugg}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Input Footer */}
        <div className="border-t border-zinc-800/80 bg-zinc-900/50 p-4">
          <form onSubmit={handleSubmit} className="space-y-2">
            <div className="relative">
              <textarea
                ref={inputRef}
                value={utterance}
                onChange={(e) => setUtterance(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit();
                  }
                }}
                maxLength={300}
                placeholder={
                  candidateSetId
                    ? 'e.g., "more energetic", "less mainstream", "keep the vibe but add rock"...'
                    : "Add seeds and generate recommendations first to steer"
                }
                disabled={!candidateSetId || refineMutation.isPending}
                rows={2}
                className="w-full resize-none rounded-xl border border-zinc-700/80 bg-zinc-950 px-3.5 py-2.5 text-sm text-zinc-100 placeholder-zinc-500 shadow-inner focus:border-purple-500 focus:outline-none focus:ring-2 focus:ring-purple-500/20 disabled:cursor-not-allowed disabled:opacity-50"
              />
              <div className="absolute right-2.5 bottom-2.5 flex items-center gap-2">
                <span
                  className={`text-[11px] font-mono ${
                    utterance.length > 270 ? "text-amber-400" : "text-zinc-500"
                  }`}
                >
                  {utterance.length}/300
                </span>
                <button
                  type="submit"
                  disabled={!utterance.trim() || !candidateSetId || refineMutation.isPending}
                  className="flex h-7 w-7 items-center justify-center rounded-lg bg-purple-600 text-white shadow-md hover:bg-purple-500 transition-colors disabled:cursor-not-allowed disabled:opacity-40 focus:outline-none focus:ring-2 focus:ring-purple-400"
                  aria-label="Submit refinement"
                >
                  {refineMutation.isPending ? (
                    <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  ) : (
                    <Send className="h-3.5 w-3.5" />
                  )}
                </button>
              </div>
            </div>
            <div className="flex items-center justify-between text-[11px] text-zinc-500 px-1">
              <span>Press Enter to apply refinement</span>
              <span>Temporary session context</span>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
