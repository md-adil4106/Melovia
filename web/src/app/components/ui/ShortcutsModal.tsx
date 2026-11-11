"use client";

import React, { useEffect, useRef } from "react";
import { Command, X, Search, Sparkles, Sliders, Volume2, Globe, MessageSquare, ListMusic, Layers, Eye, SkipForward, SkipBack } from "lucide-react";

interface ShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface ShortcutItem {
  keys: string[];
  label: string;
  description: string;
  icon?: React.ReactNode;
}

const SHORTCUT_GROUPS: Array<{ title: string; shortcuts: ShortcutItem[] }> = [
  {
    title: "Discovery & Search",
    shortcuts: [
      {
        keys: ["/"],
        label: "Search Seeds",
        description: "Quickly focus the seed track search console",
        icon: <Search className="w-3.5 h-3.5 text-[#fa2d55]" />,
      },
      {
        keys: ["1"],
        label: "Discover View",
        description: "Switch to interactive discovery feed",
        icon: <Sparkles className="w-3.5 h-3.5 text-[#fb7185]" />,
      },
      {
        keys: ["2"],
        label: "Taste DNA",
        description: "View acoustic profile and blindspot regions",
        icon: <Layers className="w-3.5 h-3.5 text-[#8b5cf6]" />,
      },
      {
        keys: ["G"],
        label: "Toggle Glass Mode",
        description: "Switch between Clear Liquid and Frosted Glass",
        icon: <Eye className="w-3.5 h-3.5 text-[#38bdf8]" />,
      },
    ],
  },
  {
    title: "Tuning & Playback",
    shortcuts: [
      {
        keys: ["←", "→"],
        label: "Tune Discovery",
        description: "Adjust slider between Familiarity and Discovery (-5% / +5%)",
        icon: <Sliders className="w-3.5 h-3.5 text-[#fa2d55]" />,
      },
      {
        keys: ["Home", "End"],
        label: "Min / Max Discovery",
        description: "Instantly jump to 0% (Familiar) or 100% (Exploratory)",
        icon: <Sliders className="w-3.5 h-3.5 text-emerald-400" />,
      },
      {
        keys: ["Space"],
        label: "Play / Pause",
        description: "Toggle 30s audio preview for the active track",
        icon: <Volume2 className="w-3.5 h-3.5 text-[#e879f9]" />,
      },
      {
        keys: ["J"],
        label: "Next Preview",
        description: "Advance to next playable track in queue",
        icon: <SkipForward className="w-3.5 h-3.5 text-[#fb7185]" />,
      },
      {
        keys: ["K"],
        label: "Previous Preview",
        description: "Skip to previous playable track in queue",
        icon: <SkipBack className="w-3.5 h-3.5 text-white/70" />,
      },
    ],
  },
  {
    title: "Spatial & Drawers",
    shortcuts: [
      {
        keys: ["U"],
        label: "3D Universe",
        description: "Open 3D interactive Taste Universe starfield",
        icon: <Globe className="w-3.5 h-3.5 text-[#fa2d55]" />,
      },
      {
        keys: ["C"],
        label: "Chat Refine",
        description: "Open natural language session steering drawer",
        icon: <MessageSquare className="w-3.5 h-3.5 text-[#8b5cf6]" />,
      },
      {
        keys: ["P"],
        label: "Playlist Arcs",
        description: "Open energy arc sequencing playlist builder",
        icon: <ListMusic className="w-3.5 h-3.5 text-[#10b981]" />,
      },
      {
        keys: ["Esc"],
        label: "Dismiss / Close",
        description: "Close any active modal, drawer, or dropdown",
        icon: <X className="w-3.5 h-3.5 text-white/50" />,
      },
    ],
  },
];

/**
 * ShortcutsModal: Apple-styled liquid glass keyboard shortcuts overlay.
 * Opens on '?' or clicking the keycap button in header/footer.
 */
export function ShortcutsModal({ isOpen, onClose }: ShortcutsModalProps) {
  const modalRef = useRef<HTMLDivElement>(null);
  const closeBtnRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!isOpen) return;

    // Focus close button on open
    setTimeout(() => {
      closeBtnRef.current?.focus();
    }, 50);

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }

      if (e.key === "Tab" && modalRef.current) {
        const focusable = modalRef.current.querySelectorAll<HTMLElement>(
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

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="shortcuts-modal-title"
      data-testid="shortcuts-modal"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={modalRef}
        className="relative w-full max-w-2xl max-h-[85vh] flex flex-col glass-panel-elevated rounded-3xl border border-white/[0.14] shadow-[0_32px_90px_rgba(0,0,0,0.9)] overflow-hidden animate-in zoom-in-95 duration-200"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4.5 border-b border-white/[0.08] bg-white/[0.02]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-[#fa2d55]/20 to-[#8b5cf6]/20 border border-[#fa2d55]/30 flex items-center justify-center text-[#fa2d55] shadow-ruby-glow">
              <Command className="w-4.5 h-4.5" />
            </div>
            <div>
              <h2 id="shortcuts-modal-title" className="text-base font-semibold text-white apple-heading tracking-tight flex items-center gap-2">
                Keyboard Shortcuts
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/[0.08] border border-white/10 text-white/60">
                  Press ? anywhere
                </span>
              </h2>
              <p className="text-xs text-white/50">Speed up your music exploration workflow</p>
            </div>
          </div>
          <button
            ref={closeBtnRef}
            type="button"
            onClick={onClose}
            aria-label="Close keyboard shortcuts"
            className="p-1.5 rounded-full text-white/60 hover:text-white hover:bg-white/10 transition-colors focus:outline-none focus:ring-2 focus:ring-[#fa2d55]"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1 text-sm">
          {SHORTCUT_GROUPS.map((group) => (
            <div key={group.title} className="space-y-3">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-white/50 flex items-center gap-2">
                {group.title}
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {group.shortcuts.map((sc) => (
                  <div
                    key={sc.label}
                    className="glass-card rounded-2xl p-3 flex items-center justify-between gap-3 border border-white/[0.08] hover:border-white/20 transition-all shadow-sm"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div className="p-1.5 rounded-lg bg-white/[0.05] border border-white/10 flex-shrink-0">
                        {sc.icon}
                      </div>
                      <div className="min-w-0">
                        <h4 className="text-xs font-semibold text-white truncate">{sc.label}</h4>
                        <p className="text-[11px] text-white/50 truncate">{sc.description}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      {sc.keys.map((k) => (
                        <kbd
                          key={k}
                          className="glass-pill font-mono font-bold text-[11px] px-2.5 py-1 text-white border border-white/20 shadow-[0_2px_8px_rgba(0,0,0,0.5),inset_0_1px_0_rgba(255,255,255,0.2)]"
                        >
                          {k}
                        </kbd>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Footer Hint */}
        <div className="px-6 py-3.5 border-t border-white/[0.08] bg-white/[0.01] flex items-center justify-between text-xs text-white/40">
          <span>Shortcuts disabled while typing in text inputs</span>
          <span>Press <kbd className="font-mono text-white/70">Esc</kbd> to return</span>
        </div>
      </div>
    </div>
  );
}
