import React, { useEffect, useRef } from "react";
import { X } from "lucide-react";
import { cn } from "./utils";

export interface DrawerProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  position?: "right" | "left" | "bottom";
  children: React.ReactNode;
  className?: string;
}

export function Drawer({
  isOpen,
  onClose,
  title,
  description,
  position = "right",
  children,
  className,
}: DrawerProps) {
  const drawerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    if (isOpen) {
      document.addEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "hidden";
    }
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const positionStyles = {
    right: "right-0 top-0 bottom-0 w-full max-w-md border-l animate-in slide-in-from-right duration-250",
    left: "left-0 top-0 bottom-0 w-full max-w-md border-r animate-in slide-in-from-left duration-250",
    bottom: "bottom-0 left-0 right-0 max-h-[85vh] border-t rounded-t-3xl animate-in slide-in-from-bottom duration-250",
  };

  return (
    <div className="fixed inset-0 z-50 flex" role="dialog" aria-modal="true" aria-label={title}>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity animate-in fade-in duration-200"
        onClick={onClose}
      />

      {/* Panel */}
      <div
        ref={drawerRef}
        className={cn(
          "fixed bg-[#11141d] border-ink-border text-ink-text shadow-2xl flex flex-col z-10 overflow-hidden",
          positionStyles[position],
          className
        )}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-ink-border flex items-center justify-between shrink-0 bg-[#0d1017]">
          <div>
            <h2 className="text-base font-bold text-ink-text">{title}</h2>
            {description && <p className="text-xs text-ink-muted mt-0.5">{description}</p>}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close drawer"
            className="p-1.5 rounded-lg text-ink-muted hover:text-ink-text hover:bg-ink-surface transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cool"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">{children}</div>
      </div>
    </div>
  );
}
