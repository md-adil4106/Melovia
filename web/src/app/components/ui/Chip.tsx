import React from "react";
import { X } from "lucide-react";
import { cn } from "./utils";

export interface ChipProps extends React.HTMLAttributes<HTMLDivElement> {
  selected?: boolean;
  onRemove?: () => void;
  removeAriaLabel?: string;
  icon?: React.ReactNode;
}

export function Chip({
  className,
  selected = false,
  onRemove,
  removeAriaLabel = "Remove tag",
  icon,
  children,
  ...props
}: ChipProps) {
  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 border select-none",
        selected
          ? "bg-[#d4af37]/20 border-[#d4af37]/60 text-[#f5ecd5]"
          : "bg-[#1b2230] border-[#2b354a] text-[#f1f3f7] hover:border-ink-muted/50",
        className
      )}
      {...props}
    >
      {icon && <span className="shrink-0">{icon}</span>}
      <span className="truncate">{children}</span>
      {onRemove && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          aria-label={removeAriaLabel}
          className="p-0.5 rounded text-[#8c96a8] hover:text-rose-400 hover:bg-rose-950/40 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-rose-400 ml-1"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}
