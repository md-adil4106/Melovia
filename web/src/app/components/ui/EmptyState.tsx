import React from "react";
import { Music } from "lucide-react";
import { Button } from "./Button";
import { cn } from "./utils";

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
}

export function EmptyState({
  icon = <Music className="w-8 h-8 text-[#fa2d55]" />,
  title,
  description,
  actionLabel,
  onAction,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center p-8 text-center bg-white/[0.025] backdrop-blur-xl border border-white/[0.08] rounded-xl shadow-lg",
        className
      )}
    >
      <div className="w-14 h-14 rounded-xl bg-white/[0.05] border border-white/10 flex items-center justify-center mb-4 text-[#fa2d55] shadow-inner">
        {icon}
      </div>
      <h3 className="text-base font-bold text-white mb-1.5">{title}</h3>
      <p className="text-xs sm:text-sm text-white/60 max-w-sm mb-6 leading-relaxed">
        {description}
      </p>
      {actionLabel && onAction && (
        <Button variant="primary" size="sm" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
}
