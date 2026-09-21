"use client";

import React, { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  Compass,
  ArrowLeft,
  Music,
  Sparkles,
  CheckCircle2,
  RefreshCw,
  Info,
  Sliders,
  Send,
  HelpCircle,
} from "lucide-react";
import Link from "next/link";
import { Button } from "../components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/Card";
import { ErrorState } from "../components/ui/ErrorState";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface StudyTrack {
  id: string;
  track_idx: number;
  title: string;
  artist_name: string;
  year?: number | null;
  popularity_pct: number;
  tags?: string[];
}

interface SeedTrack {
  id: string;
  track_idx: number;
  title: string;
  artist_name: string;
  year?: number | null;
}

interface StudySession {
  session_id: string;
  seed_set_id: string;
  seed_set_name: string;
  seed_tracks: SeedTrack[];
  playlist_a: StudyTrack[];
  playlist_b: StudyTrack[];
}

export default function StudyPage() {
  const [activeTab, setActiveTab] = useState<"a" | "b">("a");
  const [isSubmitted, setIsSubmitted] = useState(false);

  // Ratings state
  const [relevanceA, setRelevanceA] = useState<number>(3);
  const [discoveryA, setDiscoveryA] = useState<number>(3);
  const [flowA, setFlowA] = useState<number>(3);
  const [satisfactionA, setSatisfactionA] = useState<number>(3);

  const [relevanceB, setRelevanceB] = useState<number>(3);
  const [discoveryB, setDiscoveryB] = useState<number>(3);
  const [flowB, setFlowB] = useState<number>(3);
  const [satisfactionB, setSatisfactionB] = useState<number>(3);

  const [preferredOverall, setPreferredOverall] = useState<"playlist_a" | "playlist_b" | "tie">("playlist_a");
  const [feedbackText, setFeedbackText] = useState("");

  // Fetch blind session
  const {
    data: session,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery<StudySession>({
    queryKey: ["studySession"],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/study/session`, { credentials: "include" });
      if (!res.ok) {
        throw new Error("Failed to load study trial session");
      }
      return await res.json();
    },
    refetchOnWindowFocus: false,
  });

  // Submit rating mutation
  const submitMutation = useMutation({
    mutationFn: async () => {
      if (!session) return;
      const payload = {
        session_id: session.session_id,
        relevance_a: relevanceA,
        discovery_a: discoveryA,
        flow_a: flowA,
        satisfaction_a: satisfactionA,
        relevance_b: relevanceB,
        discovery_b: discoveryB,
        flow_b: flowB,
        satisfaction_b: satisfactionB,
        preferred_overall: preferredOverall,
        feedback_text: feedbackText.trim() || undefined,
      };

      const res = await fetch(`${API_BASE}/study/rate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.error?.message || "Failed to submit ratings");
      }
      return await res.json();
    },
    onSuccess: () => {
      setIsSubmitted(true);
    },
  });

  const handleNextTrial = () => {
    setIsSubmitted(false);
    setRelevanceA(3);
    setDiscoveryA(3);
    setFlowA(3);
    setSatisfactionA(3);
    setRelevanceB(3);
    setDiscoveryB(3);
    setFlowB(3);
    setSatisfactionB(3);
    setPreferredOverall("playlist_a");
    setFeedbackText("");
    setActiveTab("a");
    refetch();
  };

  const renderLikertSelector = (
    label: string,
    description: string,
    value: number,
    onChange: (val: number) => void
  ) => {
    return (
      <div className="space-y-1.5 p-3.5 bg-[#121620] rounded-xl border border-[#202738]">
        <div className="flex justify-between items-center text-xs">
          <span className="font-semibold text-[#f1f3f7]">{label}</span>
          <span className="font-mono text-xs font-bold text-[#d4af37]">{value} / 5</span>
        </div>
        <p className="text-[11px] text-[#8c96a8]">{description}</p>
        <div className="flex items-center gap-2 pt-1">
          {[1, 2, 3, 4, 5].map((num) => (
            <button
              key={num}
              type="button"
              onClick={() => onChange(num)}
              className={`flex-1 py-1.5 rounded-lg text-xs font-bold transition-all ${
                value === num
                  ? "bg-[#d4af37] text-black shadow-md"
                  : "bg-[#1b2230] text-[#8c96a8] hover:text-[#f1f3f7] hover:bg-[#252f44]"
              }`}
            >
              {num}
            </button>
          ))}
        </div>
      </div>
    );
  };

  return (
    <main className="min-h-screen bg-[#090b10] text-[#f1f3f7] font-sans pb-24">
      {/* Top Header */}
      <header className="border-b border-[#212631] bg-[#11141d]/90 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="flex items-center gap-1.5 text-xs text-[#8c96a8] hover:text-[#f1f3f7] transition-colors p-1 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cool"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Back to Engine</span>
            </Link>
            <span className="text-zinc-600">|</span>
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded bg-[#38bdf8]/20 text-[#38bdf8] flex items-center justify-center font-bold text-xs">
                A/B
              </div>
              <h1 className="text-sm font-bold text-[#f5ecd5] font-serif-display">
                Double-Blind Evaluation Study
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono px-2.5 py-0.5 rounded-full bg-[#1b2230] border border-[#2b354a] text-[#8c96a8]">
              Anonymous Participant
            </span>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <div className="max-w-5xl mx-auto px-4 pt-8">
        {/* Informed Consent Notice */}
        <div className="mb-6 p-4 bg-[#11141d] border border-[#273042] rounded-2xl flex items-start gap-3.5 shadow-lg">
          <Info className="w-5 h-5 text-[#38bdf8] shrink-0 mt-0.5" />
          <div className="text-xs text-[#8c96a8] leading-relaxed">
            <span className="font-semibold text-[#f1f3f7]">Study Protocol & Consent: </span>
            You are evaluating two distinct candidate playlists (&ldquo;Playlist A&rdquo; and &ldquo;Playlist B&rdquo;) generated from the same seed tracks. One playlist was created by Melovia&apos;s Multi-Channel Engine; the other by a standard reference control. The assignment is strictly blinded and randomized. Zero personal data is collected.
          </div>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="flex flex-col items-center justify-center py-24 text-[#8c96a8]">
            <RefreshCw className="w-8 h-8 animate-spin text-[#d4af37] mb-3" />
            <p className="text-sm font-medium">Generating randomized trial session...</p>
          </div>
        )}

        {/* Error State */}
        {isError && (
          <ErrorState
            title="Failed to Load Study Trial"
            message={(error as Error)?.message || "Could not retrieve seed set and playlists."}
            onRetry={() => refetch()}
          />
        )}

        {/* Completion Card */}
        {isSubmitted && (
          <Card className="max-w-xl mx-auto text-center p-8 bg-[#111520] border-[#d4af37]/40">
            <div className="w-16 h-16 rounded-2xl bg-[#d4af37]/20 border border-[#d4af37]/50 flex items-center justify-center text-[#d4af37] mx-auto mb-4">
              <CheckCircle2 className="w-8 h-8" />
            </div>
            <CardTitle className="text-2xl mb-2">Evaluation Submitted!</CardTitle>
            <CardDescription className="mb-6">
              Your ratings have been securely and anonymously recorded for empirical statistical analysis. Thank you for contributing to music recommendation research!
            </CardDescription>
            <div className="flex justify-center gap-3">
              <Button variant="primary" size="md" onClick={handleNextTrial}>
                Evaluate Next Seed Set
              </Button>
              <Link href="/">
                <Button variant="outline" size="md">
                  Return to Discovery
                </Button>
              </Link>
            </div>
          </Card>
        )}

        {/* Active Study Form */}
        {session && !isSubmitted && (
          <div className="space-y-8">
            {/* Reference Seeds Card */}
            <Card>
              <CardHeader className="mb-3">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold text-[#d4af37] uppercase tracking-wider">
                    Reference Seeds
                  </span>
                  <span className="text-xs text-[#8c96a8]">
                    {session.seed_set_name} ({session.seed_tracks.length} tracks)
                  </span>
                </div>
                <CardTitle className="text-base">Target Musical Theme</CardTitle>
                <CardDescription>
                  Both playlists were seeded with these reference tracks. Compare how well each playlist captures this vibe while offering exciting discovery and smooth flow.
                </CardDescription>
              </CardHeader>

              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                {session.seed_tracks.map((st) => (
                  <div
                    key={st.id}
                    className="p-3 bg-[#11141d] border border-[#202738] rounded-xl flex items-center gap-3"
                  >
                    <div className="w-8 h-8 rounded-lg bg-[#1b2230] border border-[#2b354a] flex items-center justify-center text-[#d4af37] shrink-0">
                      <Music className="w-4 h-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-semibold text-[#f1f3f7] truncate">{st.title}</p>
                      <p className="text-[11px] text-[#8c96a8] truncate">
                        {st.artist_name} {st.year ? `• ${st.year}` : ""}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </Card>

            {/* Blind Playlists Section */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-base font-bold text-[#f1f3f7] flex items-center gap-2">
                  <Sliders className="w-4 h-4 text-[#38bdf8]" />
                  <span>Audition Playlists</span>
                </h3>
                <div className="flex bg-[#11141d] p-1 rounded-xl border border-[#202738]">
                  <button
                    type="button"
                    data-testid="tab-playlist-a"
                    onClick={() => setActiveTab("a")}
                    className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${
                      activeTab === "a"
                        ? "bg-[#1b2230] text-[#38bdf8] shadow"
                        : "text-[#8c96a8] hover:text-[#f1f3f7]"
                    }`}
                  >
                    Playlist A ({session.playlist_a.length} tracks)
                  </button>
                  <button
                    type="button"
                    data-testid="tab-playlist-b"
                    onClick={() => setActiveTab("b")}
                    className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${
                      activeTab === "b"
                        ? "bg-[#1b2230] text-[#38bdf8] shadow"
                        : "text-[#8c96a8] hover:text-[#f1f3f7]"
                    }`}
                  >
                    Playlist B ({session.playlist_b.length} tracks)
                  </button>
                </div>
              </div>

              {/* Playlist Tracks Table */}
              <div className="bg-[#141923] border border-[#232a3b] rounded-2xl p-4 shadow-xl overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-[#202738] text-[#8c96a8]">
                      <th className="py-2.5 px-3 w-12 text-center">#</th>
                      <th className="py-2.5 px-3">Title</th>
                      <th className="py-2.5 px-3">Artist</th>
                      <th className="py-2.5 px-3">Year</th>
                      <th className="py-2.5 px-3">Tags</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1b2230]">
                    {(activeTab === "a" ? session.playlist_a : session.playlist_b).map(
                      (track, idx) => (
                        <tr key={track.id} className="hover:bg-[#18202d] transition-colors">
                          <td className="py-3 px-3 text-center font-mono text-[#647187]">
                            {idx + 1}
                          </td>
                          <td className="py-3 px-3 font-semibold text-[#f1f3f7]">{track.title}</td>
                          <td className="py-3 px-3 text-[#c8d0de]">{track.artist_name}</td>
                          <td className="py-3 px-3 text-[#8c96a8] font-mono">
                            {track.year || "—"}
                          </td>
                          <td className="py-3 px-3">
                            <div className="flex flex-wrap gap-1">
                              {track.tags &&
                                track.tags.slice(0, 3).map((t, tIdx) => {
                                  const tagStr = typeof t === "string" ? t : (t as any).name || "";
                                  return (
                                    <span
                                      key={tIdx}
                                      className="px-2 py-0.5 rounded bg-[#1b2230] text-[10px] text-[#8c96a8]"
                                    >
                                      #{tagStr}
                                    </span>
                                  );
                                })}
                            </div>
                          </td>
                        </tr>
                      )
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Likert Rating Form */}
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-[#d4af37]" />
                  <CardTitle className="text-base">Evaluation Form (1–5 Likert Scales)</CardTitle>
                </div>
                <CardDescription>
                  Rate each playlist independently on the 4 evaluation dimensions, then indicate your overall preference.
                </CardDescription>
              </CardHeader>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Playlist A Ratings */}
                <div className="space-y-3 p-4 bg-[#0d1017] rounded-2xl border border-[#202738]">
                  <h4 className="text-sm font-bold text-[#38bdf8] flex items-center gap-2">
                    <span>Playlist A Ratings</span>
                  </h4>
                  {renderLikertSelector(
                    "Relevance",
                    "How well do these tracks match the mood of the seeds?",
                    relevanceA,
                    setRelevanceA
                  )}
                  {renderLikertSelector(
                    "Discovery",
                    "Did this playlist introduce compelling unfamiliar tracks?",
                    discoveryA,
                    setDiscoveryA
                  )}
                  {renderLikertSelector(
                    "Flow & Coherence",
                    "How smooth is the transition from track to track?",
                    flowA,
                    setFlowA
                  )}
                  {renderLikertSelector(
                    "Overall Satisfaction",
                    "How satisfied are you with this playlist as a whole?",
                    satisfactionA,
                    setSatisfactionA
                  )}
                </div>

                {/* Playlist B Ratings */}
                <div className="space-y-3 p-4 bg-[#0d1017] rounded-2xl border border-[#202738]">
                  <h4 className="text-sm font-bold text-[#38bdf8] flex items-center gap-2">
                    <span>Playlist B Ratings</span>
                  </h4>
                  {renderLikertSelector(
                    "Relevance",
                    "How well do these tracks match the mood of the seeds?",
                    relevanceB,
                    setRelevanceB
                  )}
                  {renderLikertSelector(
                    "Discovery",
                    "Did this playlist introduce compelling unfamiliar tracks?",
                    discoveryB,
                    setDiscoveryB
                  )}
                  {renderLikertSelector(
                    "Flow & Coherence",
                    "How smooth is the transition from track to track?",
                    flowB,
                    setFlowB
                  )}
                  {renderLikertSelector(
                    "Overall Satisfaction",
                    "How satisfied are you with this playlist as a whole?",
                    satisfactionB,
                    setSatisfactionB
                  )}
                </div>
              </div>

              {/* Forced Choice & Qualitative Feedback */}
              <div className="mt-6 pt-6 border-t border-[#202738] space-y-4">
                <div>
                  <label className="block text-xs font-bold text-[#f1f3f7] uppercase tracking-wider mb-2">
                    Which playlist did you prefer overall?
                  </label>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {[
                      { val: "playlist_a", label: "Playlist A" },
                      { val: "playlist_b", label: "Playlist B" },
                      { val: "tie", label: "About Equal / No Preference" },
                    ].map((opt) => (
                      <button
                        key={opt.val}
                        type="button"
                        onClick={() => setPreferredOverall(opt.val as any)}
                        className={`p-3 rounded-xl text-xs font-bold border transition-all ${
                          preferredOverall === opt.val
                            ? "bg-[#d4af37]/20 border-[#d4af37] text-[#f5ecd5] shadow-md"
                            : "bg-[#121620] border-[#202738] text-[#8c96a8] hover:text-[#f1f3f7] hover:bg-[#1a212e]"
                        }`}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label htmlFor="feedback-text" className="block text-xs font-bold text-[#c8d0de] mb-1.5">
                    Optional Feedback / Observations (Max 1000 chars):
                  </label>
                  <textarea
                    id="feedback-text"
                    value={feedbackText}
                    onChange={(e) => setFeedbackText(e.target.value)}
                    maxLength={1000}
                    rows={3}
                    placeholder="Describe what stood out in either playlist (e.g. surprising track connections, abrupt changes, or favorite discoveries)..."
                    className="w-full bg-[#0d1017] border border-[#262e40] rounded-xl p-3 text-xs text-[#f1f3f7] placeholder-[#5a657a] focus:outline-none focus:ring-2 focus:ring-[#d4af37]/60"
                  />
                </div>

                {submitMutation.isError && (
                  <p className="text-xs text-rose-400">
                    {(submitMutation.error as Error)?.message || "Failed to submit ratings."}
                  </p>
                )}

                <div className="flex justify-end pt-2">
                  <Button
                    variant="primary"
                    size="lg"
                    isLoading={submitMutation.isPending}
                    onClick={() => submitMutation.mutate()}
                    rightIcon={<Send className="w-4 h-4 ml-1" />}
                  >
                    Submit Evaluation
                  </Button>
                </div>
              </div>
            </Card>
          </div>
        )}
      </div>
    </main>
  );
}
