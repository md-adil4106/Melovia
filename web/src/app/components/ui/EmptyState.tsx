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
  icon = <Music className="w-8 h-8 text-[#d4af37]" />,
  title,
  description,
  actionLabel,
  onAction,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center p-8 text-center bg-[#141923]/60 border border-[#232a3b] rounded-2xl",
        className
      )}
    >
      <div className="w-16 h-16 rounded-2xl bg-[#1c2433] border border-[#2a364d] flex items-center justify-center mb-4 shadow-inner">
        {icon}
      </div>
      <h3 className="text-base font-bold text-[#f1f3f7] mb-1">{title}</h3>
      <p className="text-xs sm:text-sm text-[#8c96a8] max-w-sm mb-6 leading-relaxed">
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
