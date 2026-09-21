"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  X,
  Download,
  FileText,
  FileSpreadsheet,
  FileCode,
  Music2,
  ExternalLink,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Radio,
  Loader2,
  LogOut,
  Sparkles,
} from "lucide-react";
import { RecommendedItem, Track } from "../../store";

interface ExportTrackItem {
  catalog_track_id: string;
  title: string;
  artist: string;
  isrc?: string | null;
  status: "matched" | "ambiguous" | "unmatched" | "added" | "failed";
  confidence: number;
  platform_uri?: string | null;
  platform_title?: string | null;
  platform_artist?: string | null;
  match_strategy: string;
}

interface ExportJob {
  job_id: string;
  status: "pending" | "processing" | "completed" | "failed";
  platform: string;
  playlist_name: string;
  playlist_id?: string | null;
  playlist_url?: string | null;
  total_tracks: number;
  matched_count: number;
  ambiguous_count: number;
  unmatched_count: number;
  tracks: ExportTrackItem[];
  error?: string | null;
  created_at: string;
}

interface SpotifyStatus {
  connected: boolean;
  display_name?: string | null;
  user_id?: string | null;
  profile_url?: string | null;
}

export interface ExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  tracks: Array<RecommendedItem | Track>;
  playlistName?: string;
  apiBase: string;
}

export function ExportModal({
  isOpen,
  onClose,
  tracks,
  playlistName = "Melovia Discovery",
  apiBase,
}: ExportModalProps) {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<"files" | "spotify">("files");
  const [customName, setCustomName] = useState(playlistName);
  const [customDesc, setCustomDesc] = useState("Curated with Melovia Music Discovery");
  const [downloadingFormat, setDownloadingFormat] = useState<string | null>(null);
  const [exportJob, setExportJob] = useState<ExportJob | null>(null);
  const modalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setCustomName(playlistName);
  }, [playlistName]);

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  // Focus trap
  useEffect(() => {
    if (isOpen) {
      modalRef.current?.focus();
    }
  }, [isOpen]);

  // Normalize tracks to payload items
  const normalizedTracks = tracks.map((item) => {
    const t = "track" in item ? (item as RecommendedItem).track : (item as Track);
    return {
      id: t.id,
      track_id: t.id,
      title: t.title,
      artist: t.artist_name,
      artist_name: t.artist_name,
      isrc: t.isrcs && t.isrcs.length > 0 ? t.isrcs[0] : undefined,
      year: t.year,
      scalars: t.scalars,
    };
  });

  // Check Spotify status
  const { data: spotifyStatus, isLoading: isStatusLoading } = useQuery<SpotifyStatus>({
    queryKey: ["spotify-status"],
    queryFn: async () => {
      const res = await fetch(`${apiBase}/export/spotify/status`, {
        credentials: "include",
      });
      if (!res.ok) return { connected: false };
      return res.json();
    },
    enabled: isOpen,
    staleTime: 5000,
  });

  // Spotify Connect (Popup window)
  const handleConnectSpotify = async () => {
    try {
      const res = await fetch(`${apiBase}/export/spotify/auth-url`, {
        credentials: "include",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || "Spotify credentials not configured in backend.");
        return;
      }
      const data = await res.json();
      const popup = window.open(
        data.auth_url,
        "spotify_oauth",
        "width=550,height=700,status=no,toolbar=no,menubar=no"
      );

      const handleMessage = (event: MessageEvent) => {
        if (event.data?.type === "SPOTIFY_AUTH_SUCCESS") {
          window.removeEventListener("message", handleMessage);
          queryClient.invalidateQueries({ queryKey: ["spotify-status"] });
        }
      };
      window.addEventListener("message", handleMessage);

      // Fallback polling
      const pollTimer = setInterval(() => {
        if (popup?.closed) {
          clearInterval(pollTimer);
          queryClient.invalidateQueries({ queryKey: ["spotify-status"] });
        }
      }, 1000);
    } catch {
      alert("Failed to initiate Spotify login.");
    }
  };

  // Disconnect Spotify
  const disconnectMutation = useMutation({
    mutationFn: async () => {
      await fetch(`${apiBase}/export/spotify/disconnect`, {
        method: "POST",
        credentials: "include",
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["spotify-status"] });
      setExportJob(null);
    },
  });

  // Offline File Download
  const handleDownloadFile = async (format: "csv" | "json" | "m3u" | "txt") => {
    try {
      setDownloadingFormat(format);
      const res = await fetch(`${apiBase}/export/file`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          format,
          playlist_name: customName || "Melovia Playlist",
          tracks: normalizedTracks,
        }),
      });

      if (!res.ok) {
        throw new Error("File export failed.");
      }

      const blob = await res.blob();
      const disposition = res.headers.get("Content-Disposition") || "";
      const filenameMatch = disposition.match(/filename="?([^"]+)"?/);
      const filename = filenameMatch ? filenameMatch[1] : `melovia_playlist.${format}`;

      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (e) {
      alert((e as Error).message || "Download failed.");
    } finally {
      setDownloadingFormat(null);
    }
  };

  // Export to Spotify Mutation
  const spotifyExportMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${apiBase}/export/playlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          platform: "spotify",
          playlist_name: customName || "Melovia Discoveries",
          playlist_description: customDesc,
          tracks: normalizedTracks,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to export playlist to Spotify.");
      }
      return (await res.json()) as ExportJob;
    },
    onSuccess: (data) => {
      setExportJob(data);
    },
    onError: (err: Error) => {
      alert(err.message);
    },
  });

  // Download Unmatched Tracks
  const handleDownloadUnmatched = async (jobId: string) => {
    try {
      const res = await fetch(`${apiBase}/export/jobs/${jobId}/unmatched`, {
        credentials: "include",
      });
      if (!res.ok) throw new Error("Could not download unmatched tracks.");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `unmatched_${jobId.slice(0, 8)}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch {
      alert("Failed to download unmatched list.");
    }
  };

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="export-modal-title"
      ref={modalRef}
      tabIndex={-1}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200"
    >
      <div className="relative w-full max-w-2xl max-h-[90vh] flex flex-col bg-[#0f131a] border border-[#232a3b] rounded-2xl shadow-2xl overflow-hidden focus:outline-none focus:ring-1 focus:ring-[#d4af37]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#1b2230] bg-[#141923]">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-[#d4af37]/10 border border-[#d4af37]/30 flex items-center justify-center text-[#d4af37]">
              <Download className="w-4 h-4" />
            </div>
            <div>
              <h2 id="export-modal-title" className="text-base font-semibold text-[#f1f3f7]">
                Export Playlist
              </h2>
              <p className="text-xs text-[#8c96a8]">
                {normalizedTracks.length} track{normalizedTracks.length === 1 ? "" : "s"} ready for export
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close export modal"
            className="p-1.5 rounded-lg text-[#8c96a8] hover:text-[#f1f3f7] hover:bg-[#1f2637] transition-colors focus:outline-none focus:ring-2 focus:ring-[#d4af37]"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-[#1b2230] bg-[#111620] px-6">
          <button
            type="button"
            onClick={() => setActiveTab("files")}
            className={`py-3 px-4 text-xs font-semibold border-b-2 flex items-center gap-2 transition-colors ${
              activeTab === "files"
                ? "border-[#d4af37] text-[#d4af37]"
                : "border-transparent text-[#8c96a8] hover:text-[#f1f3f7]"
            }`}
          >
            <FileSpreadsheet className="w-4 h-4" />
            Offline File Formats (Always Available)
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("spotify")}
            className={`py-3 px-4 text-xs font-semibold border-b-2 flex items-center gap-2 transition-colors ${
              activeTab === "spotify"
                ? "border-[#1DB954] text-[#1DB954]"
                : "border-transparent text-[#8c96a8] hover:text-[#f1f3f7]"
            }`}
          >
            <Radio className="w-4 h-4" />
            Spotify (Dev Mode)
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-5">
          {/* Playlist Metadata Inputs */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 bg-[#141923] p-4 rounded-xl border border-[#1f2637]">
            <div>
              <label htmlFor="export-playlist-name" className="block text-xs font-medium text-[#8c96a8] mb-1">
                Playlist Title
              </label>
              <input
                id="export-playlist-name"
                type="text"
                value={customName}
                onChange={(e) => setCustomName(e.target.value)}
                maxLength={100}
                className="w-full px-3 py-2 text-xs bg-[#0b0e14] border border-[#232a3b] rounded-lg text-[#f1f3f7] focus:outline-none focus:ring-2 focus:ring-[#d4af37]"
              />
            </div>
            <div>
              <label htmlFor="export-playlist-desc" className="block text-xs font-medium text-[#8c96a8] mb-1">
                Description / Note
              </label>
              <input
                id="export-playlist-desc"
                type="text"
                value={customDesc}
                onChange={(e) => setCustomDesc(e.target.value)}
                maxLength={200}
                className="w-full px-3 py-2 text-xs bg-[#0b0e14] border border-[#232a3b] rounded-lg text-[#f1f3f7] focus:outline-none focus:ring-2 focus:ring-[#d4af37]"
              />
            </div>
          </div>

          {/* TAB 1: Offline File Export */}
          {activeTab === "files" && (
            <div className="space-y-4">
              <div className="bg-[#141923]/60 border border-[#232a3b] rounded-xl p-4 text-xs text-[#8c96a8] flex items-start gap-2.5">
                <Sparkles className="w-4 h-4 text-[#d4af37] flex-shrink-0 mt-0.5" />
                <p>
                  Offline files work 100% locally with zero external network access or account credentials.
                  Download your sequenced playlist to import into local media players, DJ tools, or backup.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {/* CSV */}
                <div className="p-4 bg-[#141923] border border-[#232a3b] rounded-xl flex flex-col justify-between hover:border-[#3b4764] transition-colors">
                  <div>
                    <div className="flex items-center gap-2 text-sm font-semibold text-[#f1f3f7] mb-1">
                      <FileSpreadsheet className="w-4 h-4 text-emerald-400" />
                      CSV Spreadsheet
                    </div>
                    <p className="text-[11px] text-[#8c96a8] mb-4">
                      RFC 4180 table with Track ID, Title, Artist, ISRC, Year, BPM, and Energy.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDownloadFile("csv")}
                    disabled={downloadingFormat === "csv"}
                    className="w-full py-2 px-3 bg-[#1b2230] hover:bg-[#252f42] text-xs font-medium text-[#f1f3f7] rounded-lg flex items-center justify-center gap-2 border border-[#2b354a] transition-colors disabled:opacity-50"
                  >
                    {downloadingFormat === "csv" ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Download className="w-3.5 h-3.5" />
                    )}
                    Download .csv
                  </button>
                </div>

                {/* JSON (JSPF) */}
                <div className="p-4 bg-[#141923] border border-[#232a3b] rounded-xl flex flex-col justify-between hover:border-[#3b4764] transition-colors">
                  <div>
                    <div className="flex items-center gap-2 text-sm font-semibold text-[#f1f3f7] mb-1">
                      <FileCode className="w-4 h-4 text-amber-400" />
                      JSON (JSPF)
                    </div>
                    <p className="text-[11px] text-[#8c96a8] mb-4">
                      Standard JSON Shareable Playlist Format specification with Melovia acoustic extensions.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDownloadFile("json")}
                    disabled={downloadingFormat === "json"}
                    className="w-full py-2 px-3 bg-[#1b2230] hover:bg-[#252f42] text-xs font-medium text-[#f1f3f7] rounded-lg flex items-center justify-center gap-2 border border-[#2b354a] transition-colors disabled:opacity-50"
                  >
                    {downloadingFormat === "json" ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Download className="w-3.5 h-3.5" />
                    )}
                    Download .json
                  </button>
                </div>

                {/* M3U */}
                <div className="p-4 bg-[#141923] border border-[#232a3b] rounded-xl flex flex-col justify-between hover:border-[#3b4764] transition-colors">
                  <div>
                    <div className="flex items-center gap-2 text-sm font-semibold text-[#f1f3f7] mb-1">
                      <Music2 className="w-4 h-4 text-cyan-400" />
                      Extended M3U
                    </div>
                    <p className="text-[11px] text-[#8c96a8] mb-4">
                      #EXTM3U and #EXTINF directives for VLC, Foobar2000, Winamp, and offline players.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDownloadFile("m3u")}
                    disabled={downloadingFormat === "m3u"}
                    className="w-full py-2 px-3 bg-[#1b2230] hover:bg-[#252f42] text-xs font-medium text-[#f1f3f7] rounded-lg flex items-center justify-center gap-2 border border-[#2b354a] transition-colors disabled:opacity-50"
                  >
                    {downloadingFormat === "m3u" ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Download className="w-3.5 h-3.5" />
                    )}
                    Download .m3u8
                  </button>
                </div>

                {/* Plain Text */}
                <div className="p-4 bg-[#141923] border border-[#232a3b] rounded-xl flex flex-col justify-between hover:border-[#3b4764] transition-colors">
                  <div>
                    <div className="flex items-center gap-2 text-sm font-semibold text-[#f1f3f7] mb-1">
                      <FileText className="w-4 h-4 text-rose-400" />
                      Plain Text Tracklist
                    </div>
                    <p className="text-[11px] text-[#8c96a8] mb-4">
                      Simple numbered list (&quot;1. Artist - Title&quot;) ideal for sharing or text notes.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDownloadFile("txt")}
                    disabled={downloadingFormat === "txt"}
                    className="w-full py-2 px-3 bg-[#1b2230] hover:bg-[#252f42] text-xs font-medium text-[#f1f3f7] rounded-lg flex items-center justify-center gap-2 border border-[#2b354a] transition-colors disabled:opacity-50"
                  >
                    {downloadingFormat === "txt" ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Download className="w-3.5 h-3.5" />
                    )}
                    Download .txt
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: Spotify Dev Mode */}
          {activeTab === "spotify" && (
            <div className="space-y-4">
              {isStatusLoading ? (
                <div className="flex items-center justify-center py-10 text-xs text-[#8c96a8] gap-2">
                  <Loader2 className="w-4 h-4 animate-spin text-[#1DB954]" />
                  Checking Spotify connection...
                </div>
              ) : !spotifyStatus?.connected ? (
                /* Disconnected State */
                <div className="bg-[#141923] border border-[#232a3b] rounded-xl p-6 text-center space-y-4">
                  <div className="w-12 h-12 rounded-full bg-[#1DB954]/10 border border-[#1DB954]/30 flex items-center justify-center text-[#1DB954] mx-auto">
                    <Radio className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-[#f1f3f7]">Connect Spotify Dev Mode</h3>
                    <p className="text-xs text-[#8c96a8] max-w-md mx-auto mt-1">
                      Authenticate with Spotify OAuth PKCE to export playlists directly to your account.
                      Tokens are held in memory only for this session.
                    </p>
                  </div>

                  <div className="max-w-md mx-auto bg-[#0b0e14] border border-[#1f2637] rounded-lg p-3 text-[11px] text-[#8c96a8] text-left flex items-start gap-2">
                    <HelpCircle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <strong className="text-[#f1f3f7]">Developer Mode Allowlist:</strong> Under Spotify Dev Mode,
                      up to 5 Spotify accounts added in your Spotify Developer Dashboard can authorize. Client secrets
                      remain in your local <code className="text-[#d4af37]">.env</code>.
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={handleConnectSpotify}
                    className="py-2.5 px-6 bg-[#1DB954] hover:bg-[#1ed760] text-black font-semibold text-xs rounded-full transition-colors inline-flex items-center gap-2 focus:outline-none focus:ring-2 focus:ring-[#1DB954]"
                  >
                    <Radio className="w-4 h-4" />
                    Connect to Spotify
                  </button>
                </div>
              ) : (
                /* Connected State */
                <div className="space-y-4">
                  {/* Account Header */}
                  <div className="flex items-center justify-between bg-[#141923] border border-[#1DB954]/30 rounded-xl p-3.5">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-[#1DB954]/20 border border-[#1DB954]/50 flex items-center justify-center text-[#1DB954]">
                        <CheckCircle2 className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="text-xs font-semibold text-[#f1f3f7]">
                          {spotifyStatus.display_name || "Spotify User"}
                        </div>
                        <div className="text-[10px] text-[#1DB954] font-medium">Connected (Dev Mode)</div>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => disconnectMutation.mutate()}
                      disabled={disconnectMutation.isPending}
                      className="p-1.5 text-xs text-[#8c96a8] hover:text-rose-400 rounded-lg hover:bg-[#1f2637] flex items-center gap-1 transition-colors"
                      title="Disconnect Spotify session"
                    >
                      <LogOut className="w-3.5 h-3.5" />
                      Disconnect
                    </button>
                  </div>

                  {/* Export Trigger */}
                  {!exportJob && (
                    <button
                      type="button"
                      onClick={() => spotifyExportMutation.mutate()}
                      disabled={spotifyExportMutation.isPending}
                      className="w-full py-3 bg-[#1DB954] hover:bg-[#1ed760] text-black font-semibold text-xs rounded-xl flex items-center justify-center gap-2 transition-colors disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-[#1DB954]"
                    >
                      {spotifyExportMutation.isPending ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          Matching tracks &amp; creating playlist on Spotify...
                        </>
                      ) : (
                        <>
                          <Radio className="w-4 h-4" />
                          Create Spotify Playlist ({normalizedTracks.length} tracks)
                        </>
                      )}
                    </button>
                  )}

                  {/* Export Results Report */}
                  {exportJob && (
                    <div className="space-y-3 animate-in fade-in duration-300">
                      {/* Success Banner */}
                      <div className="bg-[#141923] border border-emerald-500/40 rounded-xl p-4 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center">
                            <CheckCircle2 className="w-5 h-5" />
                          </div>
                          <div>
                            <div className="text-sm font-semibold text-[#f1f3f7]">Playlist Exported!</div>
                            <div className="text-xs text-[#8c96a8]">
                              {exportJob.matched_count} of {exportJob.total_tracks} tracks added to &quot;{exportJob.playlist_name}&quot;
                            </div>
                          </div>
                        </div>
                        {exportJob.playlist_url && (
                          <a
                            href={exportJob.playlist_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="py-1.5 px-3 bg-[#1DB954] text-black font-semibold text-xs rounded-lg flex items-center gap-1.5 hover:bg-[#1ed760] transition-colors"
                          >
                            Open in Spotify
                            <ExternalLink className="w-3.5 h-3.5" />
                          </a>
                        )}
                      </div>

                      {/* Matching Stats */}
                      <div className="grid grid-cols-3 gap-2">
                        <div className="bg-[#141923] border border-emerald-800/40 rounded-lg p-2.5 text-center">
                          <div className="text-sm font-bold text-emerald-400">{exportJob.matched_count}</div>
                          <div className="text-[10px] text-[#8c96a8] uppercase">Matched</div>
                        </div>
                        <div className="bg-[#141923] border border-amber-800/40 rounded-lg p-2.5 text-center">
                          <div className="text-sm font-bold text-amber-400">{exportJob.ambiguous_count}</div>
                          <div className="text-[10px] text-[#8c96a8] uppercase">Ambiguous</div>
                        </div>
                        <div className="bg-[#141923] border border-rose-800/40 rounded-lg p-2.5 text-center">
                          <div className="text-sm font-bold text-rose-400">{exportJob.unmatched_count}</div>
                          <div className="text-[10px] text-[#8c96a8] uppercase">Unmatched</div>
                        </div>
                      </div>

                      {/* Download Unmatched Button */}
                      {exportJob.unmatched_count > 0 && (
                        <div className="flex justify-end">
                          <button
                            type="button"
                            onClick={() => handleDownloadUnmatched(exportJob.job_id)}
                            className="text-xs text-[#d4af37] hover:underline flex items-center gap-1.5"
                          >
                            <Download className="w-3.5 h-3.5" />
                            Download {exportJob.unmatched_count} unmatched tracks (CSV)
                          </button>
                        </div>
                      )}

                      {/* Per-Track Status Breakdown */}
                      <div className="max-h-48 overflow-y-auto space-y-1.5 pr-1">
                        {exportJob.tracks.map((t) => (
                          <div
                            key={t.catalog_track_id}
                            className="flex items-center justify-between bg-[#141923] border border-[#232a3b] rounded-lg px-3 py-1.5 text-xs"
                          >
                            <div className="min-w-0 flex-1 mr-3">
                              <div className="font-medium text-[#f1f3f7] truncate">{t.title}</div>
                              <div className="text-[10px] text-[#8c96a8] truncate">{t.artist}</div>
                            </div>
                            <div className="flex items-center gap-2">
                              {t.status === "matched" ? (
                                <span className="inline-flex items-center gap-1 text-[10px] font-mono text-emerald-400 bg-emerald-950/40 border border-emerald-800/40 px-2 py-0.5 rounded">
                                  <CheckCircle2 className="w-3 h-3" />
                                  {t.match_strategy.toUpperCase()} ({(t.confidence * 100).toFixed(0)}%)
                                </span>
                              ) : t.status === "ambiguous" ? (
                                <span className="inline-flex items-center gap-1 text-[10px] font-mono text-amber-400 bg-amber-950/40 border border-amber-800/40 px-2 py-0.5 rounded">
                                  <AlertCircle className="w-3 h-3" />
                                  Ambiguous ({(t.confidence * 100).toFixed(0)}%)
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 text-[10px] font-mono text-rose-400 bg-rose-950/40 border border-rose-800/40 px-2 py-0.5 rounded">
                                  <X className="w-3 h-3" />
                                  Unmatched
                                </span>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-[#1b2230] bg-[#141923] flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="py-1.5 px-4 text-xs font-medium text-[#8c96a8] hover:text-[#f1f3f7] hover:bg-[#1f2637] rounded-lg transition-colors focus:outline-none focus:ring-1 focus:ring-[#d4af37]"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
