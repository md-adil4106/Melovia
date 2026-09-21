import React, { useEffect } from "react";
import { CheckCircle2, Info, X } from "lucide-react";
import { cn } from "./utils";

export interface ToastProps {
  message: string;
  type?: "success" | "info" | "warm";
  isOpen: boolean;
  onClose: () => void;
  durationMs?: number;
}

export function Toast({
  message,
  type = "warm",
  isOpen,
  onClose,
  durationMs = 4000,
}: ToastProps) {
  useEffect(() => {
    if (!isOpen) return;
    const timer = setTimeout(() => {
      onClose();
    }, durationMs);
    return () => clearTimeout(timer);
  }, [isOpen, onClose, durationMs]);

  if (!isOpen) return null;

  const typeStyles = {
    warm: "bg-[#141923] border-[#d4af37]/60 text-[#f5ecd5] shadow-[#d4af37]/10",
    success: "bg-[#111c18] border-emerald-500/50 text-emerald-100 shadow-emerald-500/10",
    info: "bg-[#101a26] border-sky-500/50 text-sky-100 shadow-sky-500/10",
  };

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-6 right-6 z-50 animate-in slide-in-from-bottom-5 fade-in duration-200"
    >
      <div
        className={cn(
          "flex items-center gap-3 px-4 py-3 rounded-xl border shadow-xl max-w-md",
          typeStyles[type]
        )}
      >
        {type === "warm" ? (
          <span className="w-2 h-2 rounded-full bg-[#d4af37] animate-ping shrink-0" />
        ) : type === "success" ? (
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
        ) : (
          <Info className="w-4 h-4 text-sky-400 shrink-0" />
        )}
        <span className="text-xs sm:text-sm font-medium leading-snug">{message}</span>
        <button
          type="button"
          onClick={onClose}
          aria-label="Dismiss notification"
          className="p-1 rounded text-ink-muted hover:text-ink-text transition-colors ml-auto focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cool"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
