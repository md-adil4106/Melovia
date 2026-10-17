"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  X,
  Download,
  FileText,
  FileSpreadsheet,
  ExternalLink,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Radio,
  Loader2,
  LogOut,
  Sparkles,
  Copy,
  Check,
  Settings,
  Music2,
  Play,
  Share2,
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
  client_id_configured?: boolean;
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
  const [activeTab, setActiveTab] = useState<"files" | "spotify" | "apple_music" | "ytmusic">("files");
  const [customName, setCustomName] = useState(playlistName);
  const [customDesc, setCustomDesc] = useState("Curated with Melovia Music Discovery");
  const [downloadingFormat, setDownloadingFormat] = useState<string | null>(null);
  const [exportJob, setExportJob] = useState<ExportJob | null>(null);
  const [clientIdInput, setClientIdInput] = useState("");
  const [showConfig, setShowConfig] = useState(false);
  const [copiedType, setCopiedType] = useState<string | null>(null);
  const [configSaving, setConfigSaving] = useState(false);
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
      if (!res.ok) return { connected: false, client_id_configured: false };
      return res.json();
    },
    enabled: isOpen,
    staleTime: 5000,
  });

  // Copy helper
  const handleCopyText = (text: string, type: string) => {
    navigator.clipboard.writeText(text);
    setCopiedType(type);
    setTimeout(() => setCopiedType(null), 2500);
  };

  // Save custom Spotify client ID
  const handleSaveSpotifyConfig = async () => {
    if (!clientIdInput.trim()) return;
    try {
      setConfigSaving(true);
      const res = await fetch(`${apiBase}/export/spotify/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ client_id: clientIdInput.trim() }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || "Failed to save Spotify Client ID.");
        return;
      }
      queryClient.invalidateQueries({ queryKey: ["spotify-status"] });
      setShowConfig(false);
    } catch {
      alert("Failed to communicate with server.");
    } finally {
      setConfigSaving(false);
    }
  };

  // Spotify Connect (Popup window)
  const handleConnectSpotify = async () => {
    try {
      const res = await fetch(`${apiBase}/export/spotify/auth-url`, {
        credentials: "include",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setShowConfig(true);
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
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Download failed");
      }

      const blob = await res.blob();
      const disposition = res.headers.get("content-disposition");
      let filename = `melovia_playlist.${format === "m3u" ? "m3u8" : format}`;
      if (disposition && disposition.includes("filename=")) {
        const match = disposition.match(/filename="?([^"]+)"?/);
        if (match && match[1]) filename = match[1];
      }

      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to download playlist file.");
    } finally {
      setDownloadingFormat(null);
    }
  };

  // Spotify Export Mutation
  const spotifyExportMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${apiBase}/export/playlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          platform: "spotify",
          playlist_name: customName || "Melovia Discovery",
          playlist_description: customDesc || "Exported from Melovia Music Discovery",
          tracks: normalizedTracks,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Spotify export failed");
      }
      return res.json() as Promise<ExportJob>;
    },
    onSuccess: (data) => {
      setExportJob(data);
    },
    onError: (err: Error) => {
      alert(err.message || "Failed to export playlist to Spotify.");
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

  // Direct Apple Music M3U8 Generator
  const handleDownloadAppleMusicPlaylist = () => {
    const lines = ["#EXTM3U"];
    normalizedTracks.forEach((t) => {
      lines.push(`#EXTINF:-1,${t.artist} - ${t.title}`);
      lines.push(`${t.title} ${t.artist}`);
    });
    const blob = new Blob([lines.join("\n")], { type: "audio/x-mpegurl;charset=utf-8" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${(customName || "Melovia_Apple_Music").replace(/\s+/g, "_")}.m3u8`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  };

  // Universal transfer launcher
  const handleUniversalTransfer = (platform: "spotify" | "apple_music" | "ytmusic") => {
    // Generate text tracklist and copy to clipboard
    const tracklistText = normalizedTracks.map((t, idx) => `${idx + 1}. ${t.artist} - ${t.title}`).join("\n");
    navigator.clipboard.writeText(tracklistText);
    setCopiedType("universal");
    setTimeout(() => setCopiedType(null), 3000);
    // Open TuneMyMusic in new tab
    window.open("https://www.tunemymusic.com/transfer", "_blank", "noopener,noreferrer");
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
      <div className="relative w-full max-w-2xl max-h-[90vh] flex flex-col bg-[#07080b]/95 backdrop-blur-2xl border border-white/10 rounded-2xl shadow-2xl overflow-hidden focus:outline-none focus:ring-1 focus:ring-[#fa2d55]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-white/[0.02]">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-[#fa2d55]/15 border border-[#fa2d55]/30 flex items-center justify-center text-[#fa2d55]">
              <Download className="w-4 h-4" />
            </div>
            <div>
              <h2 id="export-modal-title" className="text-base font-semibold text-white">
                Export Playlist
              </h2>
              <p className="text-xs text-white/50">
                {normalizedTracks.length} track{normalizedTracks.length === 1 ? "" : "s"} ready for export
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close export modal"
            className="p-1.5 rounded-lg text-white/60 hover:text-white hover:bg-white/10 transition-colors focus:outline-none focus:ring-2 focus:ring-[#fa2d55]"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-white/10 bg-white/[0.01] px-4 overflow-x-auto no-scrollbar">
          <button
            type="button"
            onClick={() => setActiveTab("files")}
            className={`py-3 px-3.5 text-xs font-semibold border-b-2 flex items-center gap-2 transition-colors whitespace-nowrap ${
              activeTab === "files"
                ? "border-[#fa2d55] text-[#fa2d55]"
                : "border-transparent text-white/60 hover:text-white"
            }`}
          >
            <FileSpreadsheet className="w-4 h-4" />
            Offline File Formats (Always Available)
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("spotify")}
            className={`py-3 px-3.5 text-xs font-semibold border-b-2 flex items-center gap-2 transition-colors whitespace-nowrap ${
              activeTab === "spotify"
                ? "border-[#1DB954] text-[#1DB954]"
                : "border-transparent text-white/60 hover:text-white"
            }`}
          >
            <Radio className="w-4 h-4" />
            Spotify (Dev Mode)
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("apple_music")}
            className={`py-3 px-3.5 text-xs font-semibold border-b-2 flex items-center gap-2 transition-colors whitespace-nowrap ${
              activeTab === "apple_music"
                ? "border-[#fa2d55] text-[#fa2d55]"
                : "border-transparent text-white/60 hover:text-white"
            }`}
          >
            <Music2 className="w-4 h-4" />
            Apple Music
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("ytmusic")}
            className={`py-3 px-3.5 text-xs font-semibold border-b-2 flex items-center gap-2 transition-colors whitespace-nowrap ${
              activeTab === "ytmusic"
                ? "border-[#ff0000] text-[#ff0000]"
                : "border-transparent text-white/60 hover:text-white"
            }`}
          >
            <Play className="w-4 h-4" />
            YouTube Music
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-5">
          {/* Playlist Metadata Inputs */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 bg-white/[0.03] p-4 rounded-xl border border-white/10">
            <div>
              <label htmlFor="export-playlist-name" className="block text-xs font-medium text-white/70 mb-1">
                Playlist Title
              </label>
              <input
                id="export-playlist-name"
                type="text"
                value={customName}
                onChange={(e) => setCustomName(e.target.value)}
                maxLength={100}
                className="w-full px-3 py-2 text-xs bg-[#0b0e14] border border-white/15 rounded-lg text-white focus:outline-none focus:ring-1 focus:ring-[#fa2d55]"
              />
            </div>
            <div>
              <label htmlFor="export-playlist-desc" className="block text-xs font-medium text-white/70 mb-1">
                Description / Note
              </label>
              <input
                id="export-playlist-desc"
                type="text"
                value={customDesc}
                onChange={(e) => setCustomDesc(e.target.value)}
                maxLength={200}
                className="w-full px-3 py-2 text-xs bg-[#0b0e14] border border-white/15 rounded-lg text-white focus:outline-none focus:ring-1 focus:ring-[#fa2d55]"
              />
            </div>
          </div>

          {/* TAB 1: Offline File Export */}
          {activeTab === "files" && (
            <div className="space-y-4">
              <div className="bg-white/[0.02] border border-white/10 rounded-xl p-4 text-xs text-white/70 flex items-start gap-2.5">
                <Sparkles className="w-4 h-4 text-[#fa2d55] flex-shrink-0 mt-0.5" />
                <p>
                  Offline files work 100% locally with zero external network access or account credentials.
                  Download your sequenced playlist to import into local media players, DJ tools, or backup.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                {/* CSV */}
                <div className="p-4 bg-white/[0.03] border border-white/10 rounded-xl flex flex-col justify-between hover:border-white/20 transition-colors">
                  <div>
                    <div className="flex items-center gap-2 text-sm font-semibold text-white mb-1">
                      <FileSpreadsheet className="w-4 h-4 text-emerald-400" />
                      CSV Spreadsheet
                    </div>
                    <p className="text-[11px] text-white/60 mb-4">
                      Complete tabular export with track title, artist, ISRC, BPM, and acoustic scores.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDownloadFile("csv")}
                    disabled={downloadingFormat === "csv"}
                    className="w-full py-2 px-3 bg-white/[0.05] hover:bg-white/[0.1] text-xs font-medium text-white rounded-lg flex items-center justify-center gap-2 border border-white/10 transition-colors disabled:opacity-50"
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
                <div className="p-4 bg-white/[0.03] border border-white/10 rounded-xl flex flex-col justify-between hover:border-white/20 transition-colors">
                  <div>
                    <div className="flex items-center gap-2 text-sm font-semibold text-white mb-1">
                      <FileText className="w-4 h-4 text-amber-400" />
                      JSON (JSPF)
                    </div>
                    <p className="text-[11px] text-white/60 mb-4">
                      XSPF/JSPF open standard playlist format with full structured metadata.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDownloadFile("json")}
                    disabled={downloadingFormat === "json"}
                    className="w-full py-2 px-3 bg-white/[0.05] hover:bg-white/[0.1] text-xs font-medium text-white rounded-lg flex items-center justify-center gap-2 border border-white/10 transition-colors disabled:opacity-50"
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
                <div className="p-4 bg-white/[0.03] border border-white/10 rounded-xl flex flex-col justify-between hover:border-white/20 transition-colors">
                  <div>
                    <div className="flex items-center gap-2 text-sm font-semibold text-white mb-1">
                      <Music2 className="w-4 h-4 text-sky-400" />
                      Extended M3U
                    </div>
                    <p className="text-[11px] text-white/60 mb-4">
                      Universal M3U8 format with #EXTINF tags compatible with VLC, Winamp, and media players.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDownloadFile("m3u")}
                    disabled={downloadingFormat === "m3u"}
                    className="w-full py-2 px-3 bg-white/[0.05] hover:bg-white/[0.1] text-xs font-medium text-white rounded-lg flex items-center justify-center gap-2 border border-white/10 transition-colors disabled:opacity-50"
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
                <div className="p-4 bg-white/[0.03] border border-white/10 rounded-xl flex flex-col justify-between hover:border-white/20 transition-colors">
                  <div>
                    <div className="flex items-center gap-2 text-sm font-semibold text-white mb-1">
                      <FileText className="w-4 h-4 text-rose-400" />
                      Plain Text Tracklist
                    </div>
                    <p className="text-[11px] text-white/60 mb-4">
                      Simple numbered list (&quot;1. Artist - Title&quot;) ideal for sharing or text notes.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDownloadFile("txt")}
                    disabled={downloadingFormat === "txt"}
                    className="w-full py-2 px-3 bg-white/[0.05] hover:bg-white/[0.1] text-xs font-medium text-white rounded-lg flex items-center justify-center gap-2 border border-white/10 transition-colors disabled:opacity-50"
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
                <div className="flex items-center justify-center py-10 text-xs text-white/60 gap-2">
                  <Loader2 className="w-4 h-4 animate-spin text-[#1DB954]" />
                  Checking Spotify connection...
                </div>
              ) : !spotifyStatus?.connected ? (
                /* Disconnected State */
                <div className="bg-white/[0.03] border border-white/10 rounded-xl p-6 text-center space-y-4">
                  <div className="w-12 h-12 rounded-xl bg-[#1DB954]/15 border border-[#1DB954]/30 flex items-center justify-center text-[#1DB954] mx-auto">
                    <Radio className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-white">Connect Spotify Dev Mode</h3>
                    <p className="text-xs text-white/60 max-w-md mx-auto mt-1">
                      Authenticate with Spotify OAuth PKCE to export playlists directly to your account.
                      Tokens are held in memory only for this session.
                    </p>
                  </div>

                  <div className="max-w-md mx-auto bg-[#0b0e14] border border-white/10 rounded-lg p-3 text-[11px] text-white/70 text-left flex items-start gap-2">
                    <HelpCircle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <strong className="text-white">Developer Mode Allowlist:</strong> Under Spotify Dev Mode,
                      up to 5 Spotify accounts added in your Spotify Developer Dashboard can authorize. Client secrets
                      remain in your local <code className="text-[#fa2d55]">.env</code>.
                    </div>
                  </div>

                  {/* Inline Client ID Configuration */}
                  <div className="max-w-md mx-auto text-left">
                    <button
                      type="button"
                      onClick={() => setShowConfig(!showConfig)}
                      className="text-xs text-[#1DB954] hover:underline flex items-center gap-1.5 mb-2 font-medium"
                    >
                      <Settings className="w-3.5 h-3.5" />
                      {showConfig ? "Hide Client ID Settings" : "Configure Spotify Client ID (Takes 1 min)"}
                    </button>

                    {showConfig && (
                      <div className="p-3.5 bg-black/40 border border-white/10 rounded-lg space-y-2.5 text-xs text-white/70 animate-in fade-in duration-200">
                        <p className="text-[11px] leading-relaxed">
                          To connect directly via OAuth:
                          <br />
                          1. Go to{" "}
                          <a
                            href="https://developer.spotify.com/dashboard"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[#1DB954] underline inline-flex items-center gap-0.5"
                          >
                            developer.spotify.com/dashboard <ExternalLink className="w-3 h-3" />
                          </a>
                          <br />
                          2. Create an App &amp; set Redirect URI:{" "}
                          <code className="text-white bg-white/10 px-1 py-0.5 rounded text-[10px]">
                            http://127.0.0.1:8000/export/spotify/callback
                          </code>
                          <br />
                          3. Paste your <strong>Client ID</strong> below:
                        </p>
                        <div className="flex gap-2">
                          <input
                            type="text"
                            placeholder="Enter Spotify Client ID"
                            value={clientIdInput}
                            onChange={(e) => setClientIdInput(e.target.value)}
                            className="flex-1 px-3 py-1.5 text-xs bg-[#0b0e14] border border-white/15 rounded text-white focus:outline-none focus:ring-1 focus:ring-[#1DB954]"
                          />
                          <button
                            type="button"
                            onClick={handleSaveSpotifyConfig}
                            disabled={configSaving || !clientIdInput.trim()}
                            className="py-1.5 px-3 bg-[#1DB954] hover:bg-[#1ed760] text-black text-xs font-semibold rounded disabled:opacity-50"
                          >
                            {configSaving ? "Saving..." : "Save"}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
                    <button
                      type="button"
                      onClick={handleConnectSpotify}
                      className="py-2.5 px-6 bg-[#1DB954] hover:bg-[#1ed760] text-black font-semibold text-xs rounded-lg transition-colors inline-flex items-center gap-2 focus:outline-none focus:ring-2 focus:ring-[#1DB954]"
                    >
                      <Radio className="w-4 h-4" />
                      Connect to Spotify
                    </button>

                    <button
                      type="button"
                      onClick={() => handleUniversalTransfer("spotify")}
                      className="py-2.5 px-4 bg-white/[0.05] hover:bg-white/[0.1] text-white border border-white/10 font-medium text-xs rounded-lg transition-colors inline-flex items-center gap-2"
                    >
                      <Share2 className="w-4 h-4 text-[#1DB954]" />
                      Universal Transfer (TuneMyMusic)
                    </button>
                  </div>

                  {/* Instant Copy Alternative */}
                  <div className="pt-2 border-t border-white/10 text-center">
                    <button
                      type="button"
                      onClick={() =>
                        handleCopyText(
                          normalizedTracks.map((t) => `${t.title} - ${t.artist}`).join("\n"),
                          "spotify_copy"
                        )
                      }
                      className="text-xs text-white/60 hover:text-white inline-flex items-center gap-1.5 py-1 px-2.5 rounded hover:bg-white/5 transition-colors"
                    >
                      {copiedType === "spotify_copy" ? (
                        <>
                          <Check className="w-3.5 h-3.5 text-[#1DB954]" />
                          <span className="text-[#1DB954]">Copied! Press Ctrl+V in Spotify Desktop playlist</span>
                        </>
                      ) : (
                        <>
                          <Copy className="w-3.5 h-3.5" />
                          Copy Tracklist (Paste directly into Spotify Desktop)
                        </>
                      )}
                    </button>
                  </div>
                </div>
              ) : (
                /* Connected State */
                <div className="space-y-4">
                  {/* Account Header */}
                  <div className="flex items-center justify-between bg-white/[0.03] border border-[#1DB954]/30 rounded-xl p-3.5">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-[#1DB954]/20 border border-[#1DB954]/50 flex items-center justify-center text-[#1DB954]">
                        <CheckCircle2 className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="text-xs font-semibold text-white">
                          {spotifyStatus.display_name || "Spotify User"}
                        </div>
                        <div className="text-[10px] text-[#1DB954] font-medium">Connected (Dev Mode)</div>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => disconnectMutation.mutate()}
                      disabled={disconnectMutation.isPending}
                      className="p-1.5 text-xs text-white/60 hover:text-rose-400 rounded-lg hover:bg-white/10 flex items-center gap-1 transition-colors"
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
                      <div className="bg-white/[0.03] border border-emerald-500/40 rounded-xl p-4 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center">
                            <CheckCircle2 className="w-5 h-5" />
                          </div>
                          <div>
                            <div className="text-sm font-semibold text-white">Playlist Exported!</div>
                            <div className="text-xs text-white/60">
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
                        <div className="bg-white/[0.03] border border-emerald-800/40 rounded-lg p-2.5 text-center">
                          <div className="text-sm font-bold text-emerald-400">{exportJob.matched_count}</div>
                          <div className="text-[10px] text-white/60 uppercase">Matched</div>
                        </div>
                        <div className="bg-white/[0.03] border border-amber-800/40 rounded-lg p-2.5 text-center">
                          <div className="text-sm font-bold text-amber-400">{exportJob.ambiguous_count}</div>
                          <div className="text-[10px] text-white/60 uppercase">Ambiguous</div>
                        </div>
                        <div className="bg-white/[0.03] border border-rose-800/40 rounded-lg p-2.5 text-center">
                          <div className="text-sm font-bold text-rose-400">{exportJob.unmatched_count}</div>
                          <div className="text-[10px] text-white/60 uppercase">Unmatched</div>
                        </div>
                      </div>

                      {/* Download Unmatched Button */}
                      {exportJob.unmatched_count > 0 && (
                        <div className="flex justify-end">
                          <button
                            type="button"
                            onClick={() => handleDownloadUnmatched(exportJob.job_id)}
                            className="text-xs text-[#fa2d55] hover:underline flex items-center gap-1.5"
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
                            className="flex items-center justify-between bg-white/[0.03] border border-white/10 rounded-lg px-3 py-1.5 text-xs"
                          >
                            <div className="min-w-0 flex-1 mr-3">
                              <div className="font-medium text-white truncate">{t.title}</div>
                              <div className="text-[10px] text-white/60 truncate">{t.artist}</div>
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

          {/* TAB 3: Apple Music */}
          {activeTab === "apple_music" && (
            <div className="space-y-4">
              <div className="bg-[#fa2d55]/10 border border-[#fa2d55]/20 rounded-xl p-4 text-xs text-white/80 flex items-start gap-3">
                <Music2 className="w-5 h-5 text-[#fa2d55] flex-shrink-0 mt-0.5" />
                <div>
                  <h4 className="font-semibold text-white mb-0.5">Export Directly to Apple Music</h4>
                  <p className="text-white/60 text-[11px] leading-relaxed">
                    Download a native Apple Music / iTunes library playlist, launch direct web playback links,
                    or transfer all tracks automatically into your Apple Music account.
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                {/* Native Apple Music M3U8 */}
                <div className="p-4 bg-white/[0.03] border border-white/10 rounded-xl flex flex-col justify-between hover:border-[#fa2d55]/40 transition-colors">
                  <div>
                    <div className="flex items-center gap-2 text-sm font-semibold text-white mb-1">
                      <Download className="w-4 h-4 text-[#fa2d55]" />
                      Apple Music Playlist File (.m3u8)
                    </div>
                    <p className="text-[11px] text-white/60 mb-4">
                      Native UTF-8 playlist file with extended tags. Double-click or drag into macOS Music / iTunes to import automatically.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={handleDownloadAppleMusicPlaylist}
                    className="w-full py-2 px-3 bg-[#fa2d55] hover:bg-[#ff3b60] text-xs font-semibold text-white rounded-lg flex items-center justify-center gap-2 transition-colors"
                  >
                    <Download className="w-3.5 h-3.5" />
                    Download Apple Music .m3u8
                  </button>
                </div>

                {/* Universal Transfer */}
                <div className="p-4 bg-white/[0.03] border border-white/10 rounded-xl flex flex-col justify-between hover:border-white/20 transition-colors">
                  <div>
                    <div className="flex items-center gap-2 text-sm font-semibold text-white mb-1">
                      <Share2 className="w-4 h-4 text-purple-400" />
                      Universal Account Transfer
                    </div>
                    <p className="text-[11px] text-white/60 mb-4">
                      Copies tracklist to clipboard and opens TuneMyMusic / Soundiiz to sync directly into your Apple Music account.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleUniversalTransfer("apple_music")}
                    className="w-full py-2 px-3 bg-white/[0.05] hover:bg-white/[0.1] text-xs font-medium text-white rounded-lg flex items-center justify-center gap-2 border border-white/10 transition-colors"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    Sync with TuneMyMusic
                  </button>
                </div>
              </div>

              {/* Track Quick Links */}
              <div className="bg-white/[0.02] border border-white/10 rounded-xl p-3.5">
                <div className="flex items-center justify-between mb-2">
                  <div className="text-xs font-semibold text-white">Apple Music Track Search Links</div>
                  <button
                    type="button"
                    onClick={() =>
                      handleCopyText(
                        normalizedTracks.map((t) => `${t.artist} - ${t.title}`).join("\n"),
                        "am_text"
                      )
                    }
                    className="text-[11px] text-[#fa2d55] hover:underline flex items-center gap-1"
                  >
                    {copiedType === "am_text" ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                    Copy Tracklist
                  </button>
                </div>
                <div className="max-h-36 overflow-y-auto space-y-1.5 pr-1">
                  {normalizedTracks.slice(0, 15).map((t, i) => (
                    <div
                      key={t.id || i}
                      className="flex items-center justify-between text-[11px] py-1 px-2 rounded bg-white/[0.02] hover:bg-white/[0.05]"
                    >
                      <div className="truncate text-white/80 mr-2">
                        <span className="text-white/40 font-mono mr-1.5">{i + 1}.</span>
                        <span className="font-medium text-white">{t.title}</span> — {t.artist}
                      </div>
                      <a
                        href={`https://music.apple.com/search?term=${encodeURIComponent(`${t.title} ${t.artist}`)}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[#fa2d55] hover:underline flex items-center gap-1 flex-shrink-0 text-[10px]"
                      >
                        Listen <ExternalLink className="w-2.5 h-2.5" />
                      </a>
                    </div>
                  ))}
                  {normalizedTracks.length > 15 && (
                    <div className="text-[10px] text-white/40 text-center pt-1">
                      + {normalizedTracks.length - 15} more tracks included in export
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: YouTube Music */}
          {activeTab === "ytmusic" && (
            <div className="space-y-4">
              <div className="bg-[#ff0000]/10 border border-[#ff0000]/20 rounded-xl p-4 text-xs text-white/80 flex items-start gap-3">
                <Play className="w-5 h-5 text-[#ff0000] flex-shrink-0 mt-0.5" />
                <div>
                  <h4 className="font-semibold text-white mb-0.5">Export to YouTube Music</h4>
                  <p className="text-white/60 text-[11px] leading-relaxed">
                    Launch your tracks directly in YouTube Music, copy ready-to-paste playlist descriptions,
                    or transfer the entire playlist to your YouTube Music account.
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                {/* Open in YouTube Music */}
                <div className="p-4 bg-white/[0.03] border border-white/10 rounded-xl flex flex-col justify-between hover:border-[#ff0000]/40 transition-colors">
                  <div>
                    <div className="flex items-center gap-2 text-sm font-semibold text-white mb-1">
                      <Play className="w-4 h-4 text-[#ff0000]" />
                      Launch YouTube Music
                    </div>
                    <p className="text-[11px] text-white/60 mb-4">
                      Opens YouTube Music search for the playlist tracks to begin playback immediately.
                    </p>
                  </div>
                  <a
                    href={`https://music.youtube.com/search?q=${encodeURIComponent(
                      normalizedTracks[0] ? `${normalizedTracks[0].title} ${normalizedTracks[0].artist}` : customName
                    )}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="w-full py-2 px-3 bg-[#ff0000] hover:bg-[#ff2222] text-xs font-semibold text-white rounded-lg flex items-center justify-center gap-2 transition-colors"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    Open in YouTube Music
                  </a>
                </div>

                {/* Universal Transfer */}
                <div className="p-4 bg-white/[0.03] border border-white/10 rounded-xl flex flex-col justify-between hover:border-white/20 transition-colors">
                  <div>
                    <div className="flex items-center gap-2 text-sm font-semibold text-white mb-1">
                      <Share2 className="w-4 h-4 text-purple-400" />
                      Universal Account Transfer
                    </div>
                    <p className="text-[11px] text-white/60 mb-4">
                      Copies tracklist to clipboard and opens TuneMyMusic / Soundiiz to sync directly into your YouTube Music library.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleUniversalTransfer("ytmusic")}
                    className="w-full py-2 px-3 bg-white/[0.05] hover:bg-white/[0.1] text-xs font-medium text-white rounded-lg flex items-center justify-center gap-2 border border-white/10 transition-colors"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    Sync with TuneMyMusic
                  </button>
                </div>
              </div>

              {/* YouTube Description Tracklist */}
              <div className="bg-white/[0.02] border border-white/10 rounded-xl p-3.5">
                <div className="flex items-center justify-between mb-2">
                  <div className="text-xs font-semibold text-white">YouTube Description Formatted Tracklist</div>
                  <button
                    type="button"
                    onClick={() =>
                      handleCopyText(
                        normalizedTracks.map((t, idx) => `${idx + 1}. ${t.artist} - ${t.title}`).join("\n"),
                        "yt_desc"
                      )
                    }
                    className="text-[11px] text-[#ff0000] hover:underline flex items-center gap-1"
                  >
                    {copiedType === "yt_desc" ? (
                      <>
                        <Check className="w-3 h-3" />
                        Copied to Clipboard!
                      </>
                    ) : (
                      <>
                        <Copy className="w-3 h-3" />
                        Copy Formatted Tracklist
                      </>
                    )}
                  </button>
                </div>
                <div className="max-h-36 overflow-y-auto space-y-1.5 pr-1">
                  {normalizedTracks.slice(0, 15).map((t, i) => (
                    <div
                      key={t.id || i}
                      className="flex items-center justify-between text-[11px] py-1 px-2 rounded bg-white/[0.02] hover:bg-white/[0.05]"
                    >
                      <div className="truncate text-white/80 mr-2">
                        <span className="text-white/40 font-mono mr-1.5">{i + 1}.</span>
                        <span className="font-medium text-white">{t.title}</span> — {t.artist}
                      </div>
                      <a
                        href={`https://music.youtube.com/search?q=${encodeURIComponent(`${t.title} ${t.artist}`)}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[#ff0000] hover:underline flex items-center gap-1 flex-shrink-0 text-[10px]"
                      >
                        Play <ExternalLink className="w-2.5 h-2.5" />
                      </a>
                    </div>
                  ))}
                  {normalizedTracks.length > 15 && (
                    <div className="text-[10px] text-white/40 text-center pt-1">
                      + {normalizedTracks.length - 15} more tracks included in export
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-white/10 bg-white/[0.02] flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="py-1.5 px-4 text-xs font-medium text-white/70 hover:text-white hover:bg-white/10 rounded-lg transition-colors focus:outline-none focus:ring-1 focus:ring-[#fa2d55]"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
