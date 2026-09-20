"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  Fingerprint,
  Info,
  KeyRound,
  Layers,
  Music2,
  ShieldCheck,
  Trash2,
  X,
} from "lucide-react";
import { useDiscoveryStore } from "../store";

interface SettingsDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  apiBase: string;
}

interface ProfileStatus {
  has_profile: boolean;
  device_id_hash: string;
  num_modes: number;
  known_tracks_count: number;
  updated_at: string | null;
}

export function SettingsDrawer({ isOpen, onClose, apiBase }: SettingsDrawerProps) {
  const drawerRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const queryClient = useQueryClient();
  const { setHasPersistentProfile, clearFeedbackState } = useDiscoveryStore();

  // Focus trap and Escape listener
  useEffect(() => {
    if (!isOpen) {
      setConfirmDelete(false);
      setStatusMessage(null);
      return;
    }

    setTimeout(() => {
      closeButtonRef.current?.focus();
    }, 50);

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }

      if (e.key === "Tab" && drawerRef.current) {
        const focusable = drawerRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        const first = focusable[0];
        const last = focusable[focusable.length - 1];

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

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  // Fetch current profile status
  const { data: profile, isLoading, refetch } = useQuery<ProfileStatus>({
    queryKey: ["profileStatus"],
    queryFn: async () => {
      const res = await fetch(`${apiBase}/profile`, {
        credentials: "include",
      });
      if (!res.ok) throw new Error("Failed to load profile status");
      const data = await res.json();
      setHasPersistentProfile(data.has_profile);
      return data;
    },
    enabled: isOpen,
  });

  // Export Profile Mutation
  const exportMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${apiBase}/profile/export`, {
        credentials: "include",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.error?.message || "Failed to export profile");
      }
      return await res.json();
    },
    onSuccess: (data) => {
      // Trigger client file download
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `melovia_taste_profile_${data.device_id_hash || "device"}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setStatusMessage("Profile JSON exported successfully!");
    },
    onError: (err: Error) => {
      setStatusMessage(`Export failed: ${err.message}`);
    },
  });

  // Delete Profile Mutation
  const deleteMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${apiBase}/profile`, {
        method: "DELETE",
        credentials: "include",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.error?.message || "Failed to delete profile");
      }
      return await res.json();
    },
    onSuccess: () => {
      clearFeedbackState();
      setConfirmDelete(false);
      setStatusMessage("Persistent profile and interaction history permanently deleted.");
      queryClient.invalidateQueries({ queryKey: ["profileStatus"] });
      refetch();
    },
    onError: (err: Error) => {
      setStatusMessage(`Delete failed: ${err.message}`);
    },
  });

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm animate-in fade-in duration-200"
      aria-labelledby="settings-drawer-title"
      role="dialog"
      aria-modal="true"
    >
      {/* Backdrop click to dismiss */}
      <div className="absolute inset-0" onClick={onClose} aria-hidden="true" />

      {/* Drawer Body */}
      <div
        ref={drawerRef}
        className="relative w-full max-w-md bg-[#12161f] border-l border-[#242b3b] shadow-2xl h-full flex flex-col z-10 animate-in slide-in-from-right duration-300 motion-reduce:transition-none"
      >
        {/* Header */}
        <div className="p-5 border-b border-[#202738] flex items-center justify-between bg-[#141923]">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#1b2230] border border-[#2b354a] flex items-center justify-center text-[#d4af37]">
              <ShieldCheck className="w-5 h-5 text-[#d4af37]" />
            </div>
            <div>
              <h2 id="settings-drawer-title" className="text-base font-bold text-[#f1f3f7] font-serif-display">
                Taste Profile & Privacy
              </h2>
              <p className="text-xs text-[#8c96a8]">Anonymous Device Preferences</p>
            </div>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            aria-label="Close settings drawer"
            className="p-1.5 rounded-lg text-[#8c96a8] hover:text-[#f1f3f7] hover:bg-[#1f2637] transition-colors focus:outline-none focus:ring-2 focus:ring-[#d4af37]"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-6 text-sm">
          {/* Status Alert Banner */}
          {statusMessage && (
            <div className="p-3.5 rounded-xl bg-emerald-950/40 border border-emerald-800/60 text-emerald-300 text-xs flex items-center gap-2.5 animate-in fade-in">
              <CheckCircle2 className="w-4 h-4 flex-shrink-0 text-emerald-400" />
              <span>{statusMessage}</span>
            </div>
          )}

          {/* Anonymous Device Identity Card */}
          <section className="bg-[#161c27] border border-[#262f42] rounded-xl p-4 space-y-3">
            <div className="flex items-center gap-2 text-xs font-semibold text-[#c8d0de]">
              <Fingerprint className="w-4 h-4 text-[#d4af37]" />
              <span>Device Identity</span>
            </div>
            <div className="flex items-center justify-between text-xs bg-[#10141d] px-3 py-2 rounded-lg border border-[#1f2637]">
              <span className="text-[#8c96a8]">Hashed Device ID:</span>
              <span className="font-mono text-[#d4af37] font-bold">
                {profile?.device_id_hash ? `#${profile.device_id_hash}` : "Detecting..."}
              </span>
            </div>
            <p className="text-xs text-[#8c96a8] leading-relaxed">
              Melovia requires <strong>no account, email, or passwords</strong>. Your musical profile is stored strictly as mathematical vectors associated with your anonymous local device cookie.
            </p>
          </section>

          {/* Profile Status Card */}
          <section className="bg-[#161c27] border border-[#262f42] rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-[#c8d0de] flex items-center gap-2">
                <Layers className="w-4 h-4 text-[#d4af37]" />
                Persistent Profile Status
              </span>
              {isLoading ? (
                <span className="text-xs text-[#8c96a8]">Loading...</span>
              ) : profile?.has_profile ? (
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-950/50 text-emerald-400 border border-emerald-800/50">
                  Active
                </span>
              ) : (
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-zinc-900 text-zinc-400 border border-zinc-800">
                  Not Saved
                </span>
              )}
            </div>

            {profile?.has_profile ? (
              <div className="space-y-2 pt-1">
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="bg-[#10141d] p-2.5 rounded-lg border border-[#1f2637]">
                    <div className="text-[#8c96a8] text-[11px]">Taste Modes</div>
                    <div className="text-base font-mono font-bold text-[#f1f3f7]">
                      {profile.num_modes}
                    </div>
                  </div>
                  <div className="bg-[#10141d] p-2.5 rounded-lg border border-[#1f2637]">
                    <div className="text-[#8c96a8] text-[11px]">Known Tracks</div>
                    <div className="text-base font-mono font-bold text-[#f1f3f7]">
                      {profile.known_tracks_count}
                    </div>
                  </div>
                </div>
                {profile.updated_at && (
                  <div className="text-[11px] text-[#6b778d]">
                    Last updated: {new Date(profile.updated_at).toLocaleString()}
                  </div>
                )}
              </div>
            ) : (
              <div className="text-xs text-[#8c96a8] bg-[#10141d] p-3 rounded-lg border border-[#1f2637] leading-relaxed">
                You haven&apos;t saved a persistent profile yet. Click <strong>&quot;Remember this vibe&quot;</strong> in the Discovery header to merge your session taste into your device&apos;s profile.
              </div>
            )}
          </section>

          {/* Export Action */}
          <section className="space-y-2">
            <h3 className="text-xs font-semibold text-[#8c96a8] uppercase tracking-wider">
              Data Portability
            </h3>
            <button
              type="button"
              onClick={() => exportMutation.mutate()}
              disabled={!profile?.has_profile || exportMutation.isPending}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold bg-[#1a2130] border border-[#2b364d] text-[#f1f3f7] hover:bg-[#20293d] hover:border-[#d4af37]/50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors focus:outline-none focus:ring-2 focus:ring-[#d4af37]"
            >
              <Download className="w-4 h-4 text-[#d4af37]" />
              <span>{exportMutation.isPending ? "Exporting..." : "Export Taste Profile (JSON)"}</span>
            </button>
            <p className="text-[11px] text-[#6b778d]">
              Exports your full multi-modal taste representations, weights, and known tracks in standardized JSON format.
            </p>
          </section>

          {/* Danger Zone: Delete Profile */}
          <section className="space-y-2 pt-4 border-t border-[#202738]">
            <h3 className="text-xs font-semibold text-red-400 uppercase tracking-wider flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
              Privacy & Erasure
            </h3>

            {!confirmDelete ? (
              <button
                type="button"
                onClick={() => setConfirmDelete(true)}
                disabled={deleteMutation.isPending}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold bg-red-950/30 border border-red-800/40 text-red-300 hover:bg-red-900/40 hover:border-red-600 transition-colors focus:outline-none focus:ring-2 focus:ring-red-400"
              >
                <Trash2 className="w-4 h-4 text-red-400" />
                <span>Delete Profile & Interaction History</span>
              </button>
            ) : (
              <div className="p-3.5 rounded-xl bg-red-950/40 border border-red-700/60 space-y-3 animate-in fade-in">
                <p className="text-xs text-red-200 leading-relaxed">
                  Are you sure? This permanently deletes your anonymous taste profile and all interaction feedback from Melovia.
                </p>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => deleteMutation.mutate()}
                    disabled={deleteMutation.isPending}
                    className="flex-1 py-1.5 px-3 rounded-lg text-xs font-bold bg-red-600 text-white hover:bg-red-700 transition-colors focus:outline-none focus:ring-2 focus:ring-white"
                  >
                    {deleteMutation.isPending ? "Deleting..." : "Yes, Delete Everything"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmDelete(false)}
                    className="py-1.5 px-3 rounded-lg text-xs font-medium bg-[#1a2130] text-[#c8d0de] hover:bg-[#252f44] transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
            <p className="text-[11px] text-[#6b778d]">
              Immediately purges your device profile and all historical interaction events from the database.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
